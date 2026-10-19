#!/usr/bin/env bash
# 编译 fcitx5 插件: Rust 引擎(staticlib) + C++ addon → build/liblufly.so
# 前置: cargo、g++、fcitx5 开发头文件(libfcitx5core-dev 等)
set -euo pipefail
cd "$(dirname "$0")"
IME_ROOT="$(cd .. && pwd)"
# 容器（pack-legacy.sh）里用独立 CARGO_TARGET_DIR，避免与宿主新基座的产物混用
TARGET_DIR="${CARGO_TARGET_DIR:-$IME_ROOT/target}"

cargo build --release -p lufly-capi --manifest-path "$IME_ROOT/Cargo.toml"

# Ubuntu/Debian 把 fcitx5 头文件按版本分层装在 /usr/include/Fcitx5/ 下
# （Arch 等发行版则是 /usr/include/fcitx5，两种都兼容）
FCITX5_INC="/usr/include/Fcitx5"
[ -d "$FCITX5_INC" ] || FCITX5_INC="/usr/include/fcitx5"

mkdir -p build
# fcitx5 5.1.x 日志宏用 std::source_location（C++20）；GCC 11+（Ubuntu 22.04 起）直接 c++20。
# buster 容器（pack-legacy.sh）的 g++ 8 只认 c++2a 拼写（配 fcitx5 5.0.5 头文件足够）——按能力探测。
CXX_STD=c++17
for s in c++20 c++2a; do
    echo 'int main(){return 0;}' | g++ -std=$s -x c++ - -o /dev/null 2>/dev/null && { CXX_STD=$s; break; }
done
g++ -std=$CXX_STD -O2 -shared -fPIC -fvisibility=hidden \
    -I "$FCITX5_INC/Core" -I "$FCITX5_INC/Utils" -I "$FCITX5_INC/Config" \
    -I "$FCITX5_INC" -I src \
    -o build/liblufly.so \
    src/lufly.cpp \
    "$TARGET_DIR/release/liblufly_capi.a" \
    -l:libFcitx5Core.so.7 -l:libFcitx5Utils.so.2 \
    -lpthread -ldl -lm

echo "OK: $(pwd)/build/liblufly.so"

