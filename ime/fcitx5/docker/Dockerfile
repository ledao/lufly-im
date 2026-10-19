# 「legacy deb」构建环境：Debian 10 (buster) 基座
# 背景：deepin 25 宿主上构建的 deb 引用新 glibc/GLIBCXX 符号，UOS 20（Debian 10 基座）
# 加载不了；本镜像在老基座里构建，产物从 UOS 20 到 deepin 25 全线兼容。
# 用法：./pack-legacy.sh（见同目录脚本），不要手动 docker run。
FROM debian:10

# buster 已 EOL：源切 debian-archive（默认走 tuna 镜像；海外可 --build-arg 换
# https://archive.debian.org）
ARG ARCHIVE_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-archive
RUN set -eux; \
    printf 'deb %s/debian buster main\ndeb %s/debian-security buster/updates main\n' \
        "$ARCHIVE_MIRROR" "$ARCHIVE_MIRROR" > /etc/apt/sources.list; \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive; \
    apt-get update; \
    apt-get install -y --no-install-recommends g++ curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# fcitx5 5.0.5 开发文件（取自 bullseye 池；buster 仓库没有 fcitx5）。
# 只把头文件与 .so 解到系统路径供编译链接——不做依赖解析、不装运行时。
# 链出的 addon 依赖 libFcitx5Core.so.7：fcitx5 5.0（UOS 20）与 5.1（deepin 25）
# 同为此 soname，两头都能加载。选最老的 5.0.5 是为了让引用的符号集最小。
ARG FCITX5_POOL=https://mirrors.tuna.tsinghua.edu.cn/debian/pool/main/f/fcitx5
ARG FCITX5_VER=5.0.5-1
RUN set -eux; \
    for p in libfcitx5core-dev libfcitx5core7 libfcitx5utils-dev libfcitx5utils2 \
             libfcitx5config-dev libfcitx5config6; do \
        curl -fsSLo /tmp/f.deb "$FCITX5_POOL/${p}_${FCITX5_VER}_amd64.deb"; \
        dpkg-deb -x /tmp/f.deb /; \
    done; \
    rm -f /tmp/f.deb; \
    test -d /usr/include/Fcitx5/Core; \
    test -e /usr/lib/x86_64-linux-gnu/libFcitx5Core.so.7

# Rust 工具链（默认 rsproxy.cn 镜像；需要官方源时
# --build-arg RUSTUP_INIT_URL=https://sh.rustup.rs --build-arg RUSTUP_DIST_SERVER=https://static.rust-lang.org）
ARG RUSTUP_INIT_URL=https://rsproxy.cn/rustup-init.sh
ARG RUSTUP_DIST_SERVER=https://rsproxy.cn
ARG RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/cargo \
    PATH=/cargo/bin:$PATH
RUN set -eux; \
    curl -fsSL "$RUSTUP_INIT_URL" | sh -s -- -y --default-toolchain stable --profile minimal; \
    printf '[source.crates-io]\nreplace-with = "rsproxy-sparse"\n[source.rsproxy-sparse]\nregistry = "sparse+https://rsproxy.cn/index/"\n' \
        > /cargo/config.toml; \
    chmod -R a+rwX /cargo
# /cargo、/target 由 pack-legacy.sh 挂 named volume（非 root 运行、增量缓存）；
# 若改了 Rust 版本需 docker volume rm lufly-deb10-cargo 让它重建。
