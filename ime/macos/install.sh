#!/usr/bin/env bash
# 开发用快捷安装: 委托 app 自带的非交互安装（落位 + TIS 注册）。
# 等价于用户在 dmg 里双击 Lufly.app 点「安装」。
# 卸载: "$APP_SRC/Contents/MacOS/Lufly" --uninstall（或 dmg 双击 → 卸载）。
set -euo pipefail
cd "$(dirname "$0")"

APP_SRC="build/Lufly.app"
[ -d "$APP_SRC" ] || { echo "先运行 ./build.sh"; exit 1; }

"$APP_SRC/Contents/MacOS/Lufly" --install

echo "下一步: 系统设置 → 键盘 → 输入法（简体中文分类）→ 添加「小鹭音形」"
echo "若列表里没有它: 注销并重新登录后再试（TIS 缓存，同 Windows ctfmon 坑）"
echo
echo "诊断日志: tail -f ~/Library/Logs/lufly.log"
