#!/usr/bin/env bash
# 编译 fcitx5 插件: Rust 引擎(staticlib) + C++ addon → build/liblufly.so
# 前置: cargo、g++、fcitx5 开发头文件(libfcitx5core-dev 等)
set -euo pipefail
cd "$(dirname "$0")"
IME_ROOT="$(cd .. && pwd)"

cargo build --release -p lufly-capi --manifest-path "$IME_ROOT/Cargo.toml"

# Ubuntu/Debian 把 fcitx5 头文件按版本分层装在 /usr/include/Fcitx5/ 下
# （Arch 等发行版则是 /usr/include/fcitx5，两种都兼容）
FCITX5_INC="/usr/include/Fcitx5"
[ -d "$FCITX5_INC" ] || FCITX5_INC="/usr/include/fcitx5"

mkdir -p build
g++ -std=c++17 -shared -fPIC -fvisibility=hidden \
    -I "$FCITX5_INC/Core" -I "$FCITX5_INC/Utils" -I "$FCITX5_INC/Config" \
    -I "$FCITX5_INC" -I src \
    -o build/liblufly.so \
    src/lufly.cpp \
    "$IME_ROOT/target/release/liblufly_capi.a" \
    -l:libFcitx5Core.so.7 -l:libFcitx5Utils.so.2 \
    -lpthread -ldl -lm

echo "OK: $(pwd)/build/liblufly.so"

