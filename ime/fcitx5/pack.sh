#!/usr/bin/env bash
# 打包 .deb: fcitx5-lufly_<ver>_amd64.deb
# 用法: ./pack.sh [版本号]   （默认 0.1.0）
# 产物自动装到系统路径，由 dpkg 管理，升级/卸载干净。
set -euo pipefail
cd "$(dirname "$0")"

PKG=fcitx5-lufly
VER="${1:-${VERSION:-0.1.0}}"
ARCH=amd64
MULTIARCH=$(dpkg-architecture -qDEB_HOST_MULTIARCH 2>/dev/null || gcc -dumpmachine)

./build.sh

STAGE="pack/${PKG}_${VER}_${ARCH}"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
    "$STAGE/usr/lib/$MULTIARCH/fcitx5" \
    "$STAGE/usr/share/fcitx5/addon" \
    "$STAGE/usr/share/fcitx5/inputmethod" \
    "$STAGE/usr/share/fcitx5/lufly" \
    "$STAGE/usr/share/fcitx5/themes/lufly" \
    "$STAGE/usr/share/fcitx5/themes/lufly-dark" \
    "$STAGE/usr/share/icons/hicolor/48x48/apps" \
    "$STAGE/usr/share/icons/hicolor/16x16/apps"

install -m 644 build/liblufly.so        "$STAGE/usr/lib/$MULTIARCH/fcitx5/liblufly.so"
install -m 644 data/lufly-addon.conf    "$STAGE/usr/share/fcitx5/addon/lufly.conf"
install -m 644 data/lufly-im.conf       "$STAGE/usr/share/fcitx5/inputmethod/lufly.conf"
install -m 644 data/lufly.png           "$STAGE/usr/share/icons/hicolor/48x48/apps/lufly.png"
# 16x16 供托盘菜单等小尺寸场景: 无底板灰色天鹅剪影, 与系统图标视觉一致
install -m 644 data/lufly-16.png        "$STAGE/usr/share/icons/hicolor/16x16/apps/lufly.png"
install -m 644 ../data/xiaolu_he_he.bin "$STAGE/usr/share/fcitx5/lufly/dict.bin"
# 主题（亮/暗，圆角卡片 9-patch 贴图 + 药丸高亮；postinst 负责选中并跟随系统深浅色）
install -m 644 data/theme/lufly/theme.conf      "$STAGE/usr/share/fcitx5/themes/lufly/theme.conf"
install -m 644 data/theme/lufly/panel.png       "$STAGE/usr/share/fcitx5/themes/lufly/panel.png"
install -m 644 data/theme/lufly/highlight.png   "$STAGE/usr/share/fcitx5/themes/lufly/highlight.png"
install -m 644 data/theme/lufly-dark/theme.conf      "$STAGE/usr/share/fcitx5/themes/lufly-dark/theme.conf"
install -m 644 data/theme/lufly-dark/panel.png       "$STAGE/usr/share/fcitx5/themes/lufly-dark/panel.png"
install -m 644 data/theme/lufly-dark/highlight.png   "$STAGE/usr/share/fcitx5/themes/lufly-dark/highlight.png"

INSTALLED_SIZE=$(du -sk "$STAGE" | cut -f1)

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: ledao <ledao@users.noreply.github.com>
Depends: fcitx5, libc6, libstdc++6, libgcc-s1
Installed-Size: $INSTALLED_SIZE
Description: 小鹭音形输入法（fcitx5 前端）
 定长音形输入法：双拼两键 + 形码两键，词组简语与全码。
 Rust 引擎经 C ABI 静态链接进 fcitx5 addon。
EOF

install -m 755 data/postinst "$STAGE/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$STAGE"
echo "OK: $PWD/${STAGE}.deb"
