#!/usr/bin/env bash
# 打包 dmg —— 传统拖拽安装式（用户拍板，符合直觉）:
#   Lufly.app + 「输入法」文件夹替身（指向 /Library/Input Methods，清歌输入法同款）
# 拖拽到替身上 → Finder 要求输密码 → 装入系统输入法目录（机器所有用户可用）。
# 装完需注销重登: 既让 TIS 发现/刷新注册（名称、图标元数据有缓存，同 TSF ctfmon 坑），
# 也是系统设置里添加输入法的前提。
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
# 拖拽目标: 系统输入法目录的替身（/Library/Input Methods 各机皆有）
ln -s "/Library/Input Methods" "$STAGE/输入法"
# 去隔离属性，防 Gatekeeper 误拦（本地构建通常没有，防御性处理）
xattr -dr com.apple.quarantine "$STAGE/Lufly.app" 2>/dev/null || true

cat > "$STAGE/安装说明.txt" <<'EOF'
小鹭音形 —— 安装两步:

1. 把 Lufly 拖到旁边的「输入法」文件夹上（会要求输入开机密码）。
2. 注销并重新登录，然后添加输入法（仅需一次）:
   系统设置 → 键盘 → 输入法 → 编辑… → ＋ → 简体中文 → 选「小鹭音形」。

菜单栏切到「小鹭音形」即可打字，Shift 单击切换中/英文。

提示:
- 注销重登既是添加输入法的前提，也会刷新系统缓存的名称/图标。
- 若之前装过用户目录版（~/Library/Input Methods/Lufly.app），
  建议删掉避免两份重复。
EOF

hdiutil create -volname "Lufly ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "OK: $OUT"
du -h "$OUT"
