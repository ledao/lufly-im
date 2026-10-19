#!/usr/bin/env bash
# 在 Debian 10 (buster) 容器里打包「legacy deb」——兼容 UOS 20 / deepin 20 等老基座。
# 与宿主直跑的 ./pack.sh（deepin 25 基座产物，适用 deepin 23/25）互不影响。
# 用法: ./pack-legacy.sh [版本号]    产物: pack/fcitx5-lufly_<ver>_amd64_uos20.deb
# 前置: 本机装 docker（sudo apt install docker.io）；首次运行自动构建镜像，之后增量编译。
set -euo pipefail
cd "$(dirname "$0")"
VER="${1:-${VERSION:-0.1.0}}"
IMAGE=lufly-deb10-builder:latest
REPO_ROOT="$(cd ../.. && pwd)"

command -v docker >/dev/null || { echo "未找到 docker，先安装：sudo apt install docker.io"; exit 1; }

docker build -t "$IMAGE" docker

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e CARGO_TARGET_DIR=/target \
    -e VER="$VER" \
    -v "$REPO_ROOT":/src \
    -v lufly-deb10-cargo:/cargo \
    -v lufly-deb10-target:/target \
    -w /src/ime/fcitx5 \
    "$IMAGE" bash -c '
        set -euo pipefail
        ./pack.sh "$VER"
        # 兜底自检：老基座里构建本不该出现超限符号，出现即中止（防环境意外污染产物）
        bad=$(objdump -T build/liblufly.so "$CARGO_TARGET_DIR/release/lufly-cli" \
            | grep -oE "GLIBC(X)?_[0-9.]+" | sort -u \
            | grep -E "^GLIBC_2\.(29|[3-9][0-9])$|^GLIBCXX_3\.4\.(2[6-9]|[3-9][0-9])$" || true)
        if [ -n "$bad" ]; then
            echo "符号版本超出 Debian 10 基座上限（GLIBC_2.28 / GLIBCXX_3.4.25）："
            echo "$bad"
            exit 1
        fi
        echo "符号自检通过：未超出 GLIBC_2.28 / GLIBCXX_3.4.25"
    '

mv -f "pack/fcitx5-lufly_${VER}_amd64.deb" "pack/fcitx5-lufly_${VER}_amd64_uos20.deb"
echo "OK: $PWD/pack/fcitx5-lufly_${VER}_amd64_uos20.deb"
echo "（该包兼容 UOS 20 / deepin 20；deepin 23/25 用宿主 ./pack.sh 出的常规包，或本包亦可）"
