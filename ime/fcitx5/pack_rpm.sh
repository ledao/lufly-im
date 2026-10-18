#!/usr/bin/env bash
# 打包 .rpm: pack/fcitx5-lufly-<ver>-1<dist>.<arch>.rpm
# 用法: ./pack_rpm.sh [版本号]   （默认 0.1.0）
# 载荷与零配置体验对齐 pack.sh（deb 版），差异仅三点:
#   - lib 目录用 rpm 的 %{_libdir}（Fedora/openSUSE 64 位为 /usr/lib64，非 deb multiarch）
#   - %post 复用 data/postinst（deb/rpm 单一安装脚本共用），另补 RPM 系图标缓存命令
#   - glibc/libstdc++/libgcc 依赖由 rpm 从 ELF 自动提取，无需手写
# 注意: 需在目标 RPM 发行版上构建（build.sh 链接的是本机 fcitx5 库）。
set -euo pipefail
cd "$(dirname "$0")"

PKG=fcitx5-lufly
VER="${1:-${VERSION:-0.1.0}}"

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "错误: 缺少 rpmbuild（Fedora: dnf install -y rpm-build; openSUSE: zypper install rpm-build）" >&2
    exit 1
fi
# RPM Version 字段不许含 '-' 等字符
case "$VER" in *[!A-Za-z0-9.]*)
    echo "错误: 版本号含 RPM 不允许的字符: $VER" >&2; exit 1 ;; esac

ARCH=$(rpm --eval '%{_arch}')
LIBDIR=$(rpm --eval '%{_libdir}')

./build.sh
# lufly-cli 供 ojc 加词弹窗管线使用（usr/bin/lufly-cli）
cargo build --release -p lufly-cli --manifest-path ../Cargo.toml

# 载荷先布置到独立 payload 目录（不能直接用 buildroot:
# rpmbuild 在 %install 前会 rm -rf 清空 buildroot）
PAYLOAD="pack/${PKG}_payload"
RPMDIR="pack/${PKG}_rpm_build"
rm -rf "$PAYLOAD" "$RPMDIR"
mkdir -p "$PAYLOAD/usr/bin" \
    "$PAYLOAD$LIBDIR/fcitx5" \
    "$PAYLOAD/usr/share/fcitx5/addon" \
    "$PAYLOAD/usr/share/fcitx5/inputmethod" \
    "$PAYLOAD/usr/share/fcitx5/lufly" \
    "$PAYLOAD/usr/share/fcitx5/themes/lufly" \
    "$PAYLOAD/usr/share/fcitx5/themes/lufly-dark" \
    "$PAYLOAD/usr/share/icons/hicolor/48x48/apps" \
    "$PAYLOAD/usr/share/icons/hicolor/16x16/apps"
mkdir -p "$RPMDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

install -m 755 build/liblufly.so "$PAYLOAD$LIBDIR/fcitx5/liblufly.so"
# ojc 加词命令管线: zenity 表单 → lufly-cli addword（查码表自动算码）
install -m 755 ../target/release/lufly-cli "$PAYLOAD/usr/bin/lufly-cli"
install -m 644 data/lufly-addon.conf    "$PAYLOAD/usr/share/fcitx5/addon/lufly.conf"
install -m 644 data/lufly-im.conf       "$PAYLOAD/usr/share/fcitx5/inputmethod/lufly.conf"
install -m 644 data/lufly.png           "$PAYLOAD/usr/share/icons/hicolor/48x48/apps/lufly.png"
# 16x16 供托盘菜单等小尺寸场景: 无底板灰色天鹅剪影, 与系统图标视觉一致
install -m 644 data/lufly-16.png        "$PAYLOAD/usr/share/icons/hicolor/16x16/apps/lufly.png"
# 英文模式子模式图标 (subModeIcon): 白底圆角板 + "en"
install -m 644 data/lufly-en.png        "$PAYLOAD/usr/share/icons/hicolor/48x48/apps/lufly-en.png"
install -m 644 data/lufly-en-16.png     "$PAYLOAD/usr/share/icons/hicolor/16x16/apps/lufly-en.png"
install -m 644 ../data/xiaolu_he_he.bin "$PAYLOAD/usr/share/fcitx5/lufly/dict.bin"
install -m 644 ../data/xiaolu_fuzhu.bin "$PAYLOAD/usr/share/fcitx5/lufly/fuzhu.bin"
# 主题（亮/暗，圆角卡片 9-patch 贴图 + 药丸高亮；%post 负责选中并跟随系统深浅色）
install -m 644 data/theme/lufly/theme.conf         "$PAYLOAD/usr/share/fcitx5/themes/lufly/theme.conf"
install -m 644 data/theme/lufly/panel.png          "$PAYLOAD/usr/share/fcitx5/themes/lufly/panel.png"
install -m 644 data/theme/lufly/highlight.png      "$PAYLOAD/usr/share/fcitx5/themes/lufly/highlight.png"
install -m 644 data/theme/lufly-dark/theme.conf    "$PAYLOAD/usr/share/fcitx5/themes/lufly-dark/theme.conf"
install -m 644 data/theme/lufly-dark/panel.png     "$PAYLOAD/usr/share/fcitx5/themes/lufly-dark/panel.png"
install -m 644 data/theme/lufly-dark/highlight.png "$PAYLOAD/usr/share/fcitx5/themes/lufly-dark/highlight.png"

SPEC="$RPMDIR/${PKG}.spec"
PAYLOAD_ABS="$PWD/$PAYLOAD"
{
    cat <<EOF
Name:           $PKG
Version:        $VER
Release:        1%{?dist}
Summary:        小鹭音形输入法（fcitx5 前端）
License:        ASL 2.0
URL:            https://github.com/ledao/lufly-im
Packager:       ledao <ledao@users.noreply.github.com>
Requires:       fcitx5
# CJK 字体为弱依赖: 各发行版包名不一（openSUSE 为 noto-sans-cjk-fonts），缺了不阻塞
Recommends:     google-noto-sans-cjk-ttc-fonts

%description
定长音形输入法：双拼两键 + 形码两键，词组简语与全码。
词频自学习与 ojc 候选窗内造词；Rust 引擎经 C ABI 静态链接进 fcitx5 addon。

# 载荷已由 pack_rpm.sh 布置在 payload 目录，拷入 buildroot（保留模式位）
%install
rm -rf "%{buildroot}"
mkdir -p "%{buildroot}"
cp -a "$PAYLOAD_ABS/." "%{buildroot}/"

%files
%defattr(-,root,-)
%attr(755,-,-) /usr/bin/lufly-cli
%attr(755,-,-) $LIBDIR/fcitx5/liblufly.so
/usr/share/fcitx5/addon/lufly.conf
/usr/share/fcitx5/inputmethod/lufly.conf
%dir /usr/share/fcitx5/lufly
/usr/share/fcitx5/lufly/dict.bin
/usr/share/fcitx5/lufly/fuzhu.bin
%dir /usr/share/fcitx5/themes/lufly
/usr/share/fcitx5/themes/lufly/theme.conf
/usr/share/fcitx5/themes/lufly/panel.png
/usr/share/fcitx5/themes/lufly/highlight.png
%dir /usr/share/fcitx5/themes/lufly-dark
/usr/share/fcitx5/themes/lufly-dark/theme.conf
/usr/share/fcitx5/themes/lufly-dark/panel.png
/usr/share/fcitx5/themes/lufly-dark/highlight.png
/usr/share/icons/hicolor/48x48/apps/lufly.png
/usr/share/icons/hicolor/16x16/apps/lufly.png
/usr/share/icons/hicolor/48x48/apps/lufly-en.png
/usr/share/icons/hicolor/16x16/apps/lufly-en.png

%post
EOF
    # RPM 系的图标缓存命令（deb 侧用的 update-icon-caches 在 RPM 系不存在）。
    # 必须放在 postinst 之前: postinst 末尾的 exit 0 会结束整个 scriptlet。
    echo 'gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || :'
    # 与 deb 的 postinst 单一来源共用；spec 里 % 是宏引导符，嵌入须整体转义成 %%
    sed 's/%/%%/g' data/postinst
    cat <<'EOF'

%postun
if [ "$1" = 0 ]; then
    # 完全卸载（卸最后一个副本）时刷新图标缓存
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || :
fi
exit 0
EOF
cat <<EOF

%changelog
* $(LC_ALL=C date '+%a %b %d %Y') ledao <ledao@users.noreply.github.com> - $VER-1
- 自动打包生成（pack_rpm.sh），与 deb（pack.sh）载荷一致
EOF
} > "$SPEC"

# debug_package / __os_install_post 关闭: 预编译产物不拆 debuginfo、不被 brp-strip，
# 包内二进制与 deb 完全一致；ELF 自动依赖（libc/libstdc++/libgcc/libFcitx5Core）不受影响。
# buildroot 由 rpmbuild 自行清空重建（%install 里从 payload 拷入）。
rpmbuild -bb \
    --define "_topdir $PWD/$RPMDIR" \
    --define "debug_package %{nil}" \
    --define "__os_install_post %{nil}" \
    --buildroot "$PWD/$RPMDIR/BUILDROOT" \
    "$SPEC"

shopt -s nullglob
BUILT=("$RPMDIR"/RPMS/*/"${PKG}-${VER}-"*.rpm)
[ ${#BUILT[@]} -gt 0 ] || { echo "错误: rpmbuild 未产出 rpm" >&2; exit 1; }
cp -f "${BUILT[0]}" pack/
echo "OK: $PWD/pack/$(basename "${BUILT[0]}")"
