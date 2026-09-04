#!/usr/bin/env bash
# 打包 dmg —— 双击安装器式:
#   dmg 内只有 Lufly.app（自带 Installer）+ 安装说明.txt。
#   双击 → 「安装」→ 落位 ~/Library/Input Methods（不做主动注册——实测自动
#   注册的条目打不了字，必须用户「− 删除 + ＋ 添加」手动来一遍）→ 弹指引。
# 不再放「输入法」文件夹替身（拖拽式）: 拖拽路径无代码可执行，TIS 注册全靠
# 系统扫描；彻底删除重装后 TIS 缓存不认同 Bundle ID → 输入法消失且无报错
# （2026-09 实测）。Installer 会请求管理员密码清理拖拽时代残留的
# /Library/Input Methods/Lufly.app。
# 公证（拿到 Developer ID 证书后）:
#   codesign --deep --options runtime --sign "Developer ID Application: ..." <app>
#   xcrun notarytool submit <dmg> --keychain ... && xcrun stapler staple <dmg>
set -euo pipefail
cd "$(dirname "$0")"

APP="build/Lufly.app"
STAGE="build/dmg-staging"
PLIST="Info.plist"

# 每次打包自动 bump 补丁版本号（0.1.0 → 0.1.1），dmg 文件名据此区分构建；
# 旧 dmg 保留不删，可回滚对比。CFBundleVersion 同步成一样的值，免得两处漂移。
OLD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")
MAJOR=${OLD%.*.*}
MINOR=$(echo "$OLD" | cut -d. -f2)
PATCH=$(echo "$OLD" | cut -d. -f3)
VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST"
echo "版本: $OLD → $VERSION"

# 重新构建，让 app 带上新版本号（cargo/swiftc 增量，很快）
./build.sh

OUT="build/Lufly-${VERSION}-aarch64.dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/Lufly.app"
# 去隔离属性，防 Gatekeeper 误拦（本地构建通常没有，防御性处理）
xattr -dr com.apple.quarantine "$STAGE/Lufly.app" 2>/dev/null || true

# 背景引导图（「双击安装」提示；裸 dmg 用户不知道要干什么——用户反馈）
mkdir -p "$STAGE/.background"
BG_TOOL="build/mkdmgbg"
if [ ! -x "$BG_TOOL" ] || [ "tools/mkdmgbg.swift" -nt "$BG_TOOL" ]; then
    swiftc -O tools/mkdmgbg.swift -o "$BG_TOOL"
fi
"$BG_TOOL" "$STAGE/.background/bg.png"

cat > "$STAGE/安装说明.txt" <<'EOF'
小鹭音形 —— 安装两步:

1. 双击 Lufly.app → 点「安装」。
   装到当前用户输入法目录，装完即可添加，一般无需注销。
   （若机器上有拖拽式安装的旧版本，会请求一次管理员密码做清理）

2. 添加输入法（仅需一次）:
   系统设置 → 键盘 → 输入法 → 编辑… → ＋ → 简体中文 → 选「小鹭音形」。
   若列表里已有「小鹭音形」: 先选中点 − 删除，再点 ＋ 添加。
   若列表里暂时没有它: 注销并重新登录后再添加。

菜单栏切到「小鹭音形」即可打字，Shift 单击切换中/英文。

卸载:
菜单栏点输入法图标（小鹭音形激活时）→ 「卸载小鹭音形」→ 确认。
会自动从系统输入法列表移除并删除程序本体，无需注销。
备选方式（dmg 还在手边）: 双击 Lufly.app → 点「卸载」。
备选方式（终端）:
  "~/Library/Input Methods/Lufly.app/Contents/MacOS/Lufly" --uninstall
造词词典保留在 ~/Library/Application Support/lufly，
彻底清除可手动删除该文件夹。

提示:
- 双击被系统拦截（未公证的开发者包）: 右键 Lufly.app → 「打开」；
  或 系统设置 → 隐私与安全性 → 点「仍要打开」。
EOF

# 布置 dmg 窗口: 背景引导图 + 图标定位。注意必须先建**可写**镜像（UDRW）
# 让 Finder 写入 .DS_Store，再 convert 成压缩 UDZO——直接对 UDZO 布置是
# 只读卷，样式静默丢失（踩过）。自动化权限被拒等失败不阻塞打包。
TMP_DMG="build/Lufly-${VERSION}-rw.dmg"
hdiutil create -volname "Lufly ${VERSION}" -srcfolder "$STAGE" -ov -format UDRW "$TMP_DMG" >/dev/null
hdiutil attach "$TMP_DMG" -nobrowse -quiet
osascript <<APPLESCRIPT || echo "警告: dmg 窗口布置失败（Finder 自动化权限？）"
tell application "Finder"
    tell disk "Lufly ${VERSION}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {200, 160, 860, 580}
        set opts to icon view options of container window
        set arrangement of opts to not arranged
        set icon size of opts to 96
        set background picture of opts to file ".background:bg.png"
        set position of item "Lufly.app" to {330, 215}
        set position of item "安装说明.txt" to {565, 90}
        close
        open
    end tell
end tell
APPLESCRIPT
sync; sleep 2
hdiutil detach "/Volumes/Lufly ${VERSION}" -quiet
hdiutil convert "$TMP_DMG" -format UDZO -o "$OUT" -ov >/dev/null
rm -f "$TMP_DMG"

echo "OK: $OUT"
du -h "$OUT"
