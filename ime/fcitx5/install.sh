#!/usr/bin/env bash
# 安装插件到本机（.so 需 sudo，其余用户级）。
# 前置: 先跑 ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

FCITX_LIB_DIR="/usr/lib/x86_64-linux-gnu/fcitx5"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

[ -f build/liblufly.so ] || { echo "先运行 ./build.sh"; exit 1; }

# 1. 插件库（fcitx5 的 addon 目录编译期写死，需要 sudo —— 唯一一步 sudo）
sudo install -m 644 build/liblufly.so "$FCITX_LIB_DIR/liblufly.so"

# 2. addon 描述 + 输入法条目（用户级 XDG 数据目录即可）
mkdir -p "$DATA_HOME/fcitx5/addon" "$DATA_HOME/fcitx5/inputmethod" "$DATA_HOME/fcitx5/lufly"
install -m 644 data/lufly-addon.conf "$DATA_HOME/fcitx5/addon/lufly.conf"
install -m 644 data/lufly-im.conf "$DATA_HOME/fcitx5/inputmethod/lufly.conf"

# 3. 码表
install -m 644 ../data/xiaolu_he_he.bin "$DATA_HOME/fcitx5/lufly/dict.bin"

echo "已安装:"
echo "  $FCITX_LIB_DIR/liblufly.so"
echo "  $DATA_HOME/fcitx5/addon/lufly.conf"
echo "  $DATA_HOME/fcitx5/inputmethod/lufly.conf"
echo "  $DATA_HOME/fcitx5/lufly/dict.bin"
echo
echo "下一步: 重启 fcitx5，然后在 fcitx5-configtool 里把「小鹭音形」加到输入法列表。"
