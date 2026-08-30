# lufly-fcitx5 —— 小鹭音形 Linux 前端

fcitx5 输入法引擎插件。引擎逻辑复用 `../engine`（Rust），经 `../capi`
（C ABI staticlib）静态链接进本插件的 C++ addon。

## 结构

- `src/lufly.cpp` —— fcitx5 addon：按键分发、预编辑、候选窗
- `src/lufly_capi.h` —— `lufly-capi` 导出函数的 C 声明
- `data/lufly-addon.conf` —— addon 描述（安装为 `~/.local/share/fcitx5/addon/lufly.conf`）
- `data/lufly-im.conf` —— 输入法条目（安装为 `~/.local/share/fcitx5/inputmethod/lufly.conf`）

## 构建

前置：`cargo`、`g++`、fcitx5 开发头文件、本机装有 fcitx5 运行库：

```bash
sudo apt install -y libfcitx5core-dev libfcitx5config-dev libfcitx5utils-dev
./build.sh     # 产出 build/liblufly.so
```

## 打包 / 安装（推荐）

```bash
./pack.sh                      # 产出 pack/fcitx5-lufly_0.2.0_amd64.deb
sudo apt install ./pack/fcitx5-lufly_0.2.0_amd64.deb
```

**装完即用，无需任何配置**：postinst 会自动把「小鹭音形」追加进本机所有
fcitx5 用户的每个输入法分组；运行中的 fcitx5 监听 profile 文件变化，
即时生效。之后 Ctrl+Space 循环切换输入法即可选到「小鹭音形」。

版本号：`./pack.sh 0.2.0` 或环境变量 `VERSION=x.y.z`。

包内容（dpkg 管理，`sudo apt remove fcitx5-lufly` 即可卸载）：

- `usr/lib/x86_64-linux-gnu/fcitx5/liblufly.so`
- `usr/share/fcitx5/addon/lufly.conf`
- `usr/share/fcitx5/inputmethod/lufly.conf`
- `usr/share/fcitx5/lufly/dict.bin`

> 注意：若之前用 `install.sh` 装过用户级副本，请先删掉，否则会遮住 deb
> 的文件（XDG 用户目录优先于系统目录）：
> ```bash
> rm -f ~/.local/share/fcitx5/addon/lufly.conf \
>       ~/.local/share/fcitx5/inputmethod/lufly.conf \
>       ~/.local/share/fcitx5/lufly/dict.bin
> ```

## 安装（免打包，开发用）

```bash
./install.sh   # .so 装系统 addon 目录（唯一一步 sudo），其余用户级
fcitx5 -r -d   # 重启 fcitx5
```

然后在 `fcitx5-configtool`（输入法设置）里把「小鹭音形」加进当前分组。

## 码表查找顺序

1. `$LUFLY_DICT` 环境变量
2. XDG 数据目录 `lufly/dict.bin`（默认安装到 `~/.local/share/fcitx5/lufly/dict.bin`）

码表由 `../tools/build_dict.py` 生成。

## 按键

| 键 | 行为 |
| --- | --- |
| `a-z` | 进编码缓冲（死码/全码自动顶字上屏） |
| 空格 | 上屏首选 |
| `1-9` | 选当前页候选（每页 9 个，PageUp/PageDown 翻页） |
| 回车 | 编码字母原样上屏 |
| 退格 | 删一码 |
| Esc | 清空缓冲 |
| 标点等 | 不消费、不破坏缓冲（透传） |
| Ctrl/Alt/Super 组合 | 一律透传 |

## 排错

- fcitx5 日志里搜 `lufly:`（码表加载/失败信息）
- 插件没出现：确认 `~/.local/share/fcitx5/addon/lufly.conf` 与
  `/usr/lib/x86_64-linux-gnu/fcitx5/liblufly.so` 都存在，且 `Library=liblufly`
  与文件名一致
- 若不想用 sudo 装 .so，可用 `FCITX_ADDON_DIRS=$HOME/.local/lib/fcitx5/addon`
  环境变量加自定义插件目录（需在 fcitx5 启动前设置，如 `~/.xprofile`）
