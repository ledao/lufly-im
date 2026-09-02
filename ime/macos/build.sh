#!/usr/bin/env bash
# 构建 Lufly.app（macOS IMK 输入法）。
# 架构: aarch64（本机 M1）。Rust 引擎经 lufly-capi staticlib 静态链接。
# 若 shell 跑在 Rosetta 下（uname 会误报 x86_64），重启自身到原生 arm64。
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)" = "1" ]; then
    exec arch -arm64 /bin/bash "$0" "$@"
fi

RUST_TARGET="aarch64-apple-darwin"
SWIFT_TARGET="arm64-apple-macos13.0"
APP="build/Lufly.app"
IME_ROOT="$(cd .. && pwd)"

# 1. Rust 引擎 staticlib（engine + capi，平台无关零改动）
cargo build --release -p lufly-capi \
    --manifest-path "$IME_ROOT/Cargo.toml" --target "$RUST_TARGET"
RUST_LIB="$IME_ROOT/target/$RUST_TARGET/release/liblufly_capi.a"
[ -f "$RUST_LIB" ] || { echo "静态库缺失: $RUST_LIB"; exit 1; }

# 2. C 头文件（单源在 fcitx5 侧，构建时同步，勿在 include/ 里手改）
mkdir -p include
cp -f ../fcitx5/src/lufly_capi.h include/

# 3. Swift 编译（IMK 前端 + 引擎 staticlib）
# 显式链接 .a 全路径，不用 -L+-l：release 目录若同时有 dylib 会被挑中，
# 留下绝对路径 install_name，换机器分发即 dyld 加载失败（踩过）。
mkdir -p "$APP/Contents/MacOS"
printf 'APPL????' > "$APP/Contents/PkgInfo"  # 正规 bundle 标配，手搓别漏
swiftc -O -swift-version 5 \
    -target "$SWIFT_TARGET" \
    -import-objc-header BridgingHeader.h \
    -I include "$RUST_LIB" \
    -framework Cocoa -framework InputMethodKit \
    -module-name Lufly \
    -o "$APP/Contents/MacOS/Lufly" \
    src/*.swift

# 4. Resources: 码表 + 图标
mkdir -p "$APP/Contents/Resources"
cp -f ../data/xiaolu_he_he.bin  "$APP/Contents/Resources/dict.bin"
cp -f ../data/xiaolu_fuzhu.bin  "$APP/Contents/Resources/fuzhu.bin"

# 菜单栏/切换器图标: 透明底黑鸟，命名 menu_icon.pdf（同微信/豆包）。两条实测坑:
# 1) **词干绝不能与 lufly.icns 撞名**: TIS 按扩展名无关的 imageForResource: 查找，
#    词干 "lufly" 会命中 icns → 图标加载失败显示占位方块（2026-09-02 实测，
#    与矢量/位图、安装位置、签名、缓存均无关，名字是唯一根因）
# 2) **必须经 CGPDFContext 出标准结构 PDF**（见 tools/mkiconpdf.swift 头注释）:
#    手写极简 PDF 菜单栏正常、Ctrl+Space 切换器（远端视图服务渲染）白方块
ICON_SRC="../fcitx5/data/lufly.png"
[ -f "$ICON_SRC" ] || { echo "图标缺失: $ICON_SRC"; exit 1; }
ICON_TOOL="build/mkiconpdf"
if [ ! -x "$ICON_TOOL" ] || [ "tools/mkiconpdf.swift" -nt "$ICON_TOOL" ]; then
    swiftc -O tools/mkiconpdf.swift -o "$ICON_TOOL"
fi
"$ICON_TOOL" "$ICON_SRC" "$APP/Contents/Resources/menu_icon.pdf"
rm -f "$APP/Contents/Resources/lufly.pdf" "$APP/Contents/Resources/lufly.png"  # 旧图标名残留

# Dock/Finder 图标 icns: mkappicon 合成徽章+白鸟再转 icns——48px 源直接
# sips 放大是黑团（用户实测）；正式图标后续替换
APPICON_TOOL="build/mkappicon"
if [ ! -x "$APPICON_TOOL" ] || [ "tools/mkappicon.swift" -nt "$APPICON_TOOL" ]; then
    swiftc -O tools/mkappicon.swift -o "$APPICON_TOOL"
fi
APPICON_PNG="build/appicon_1024.png"
"$APPICON_TOOL" "$ICON_SRC" "$APPICON_PNG"
ICONSET="build/lufly.iconset"
rm -rf "$ICONSET" && mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
    sips -z $s $s "$APPICON_PNG" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z $d $d "$APPICON_PNG" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/lufly.icns"

# 输入法显示名本地化：mode ID 必须作为 key 出现在 InfoPlist.strings 里，
# 否则 TIS 显示设置里直接回落成 mode ID 原文（"im.lufly..."）。已实测验证。
# 两个语言包都给中文名：系统语言为英文时 en.lproj 会盖掉 zh-Hans，
# 用户要求输入法列表一律显示「小鹭音形」（同鼠鬚管做法）。
mkdir -p "$APP/Contents/Resources/en.lproj" "$APP/Contents/Resources/zh-Hans.lproj"
printf 'CFBundleName = "小鹭音形";\nCFBundleDisplayName = "小鹭音形";\nim.lufly.inputmethod.Lufly.Hans = "小鹭音形";\n' \
    > "$APP/Contents/Resources/en.lproj/InfoPlist.strings"
printf 'CFBundleName = "小鹭音形";\nCFBundleDisplayName = "小鹭音形";\nim.lufly.inputmethod.Lufly.Hans = "小鹭音形";\n' \
    > "$APP/Contents/Resources/zh-Hans.lproj/InfoPlist.strings"

# 5. Info.plist + ad-hoc 签名（本地开发；正式分发公证见 pack.sh）
cp -f Info.plist "$APP/Contents/Info.plist"
codesign --force --sign - "$APP"

echo "OK: $(pwd)/$APP"
file "$APP/Contents/MacOS/Lufly"
codesign -dv "$APP" 2>&1 | head -2 || true
