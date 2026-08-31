# lufly-im

小鹭音形：自研顶功音形输入法。纯 Rust 引擎（`ime/engine`）+ 平台前端：
Linux fcitx5（`ime/fcitx5`）、Windows TSF（`ime/tsf`），macOS 为下一目标。

## 架构约定

- 引擎（`ime/engine`）是纯数据、平台无关的（可跨线程）；按键状态机、标点、造词等前端逻辑**逐功能对齐 fcitx5 版**（`ime/fcitx5/src/lufly.cpp` 是参照真源）。新平台前端只做薄壳：按键协议适配 + UI。
- 移植或对齐功能时，逐行比对 fcitx5 实现，不要凭记忆重写。

## Windows TSF（ime/tsf）非显而易见的坑

- **注册必须走 COM API**（ITfInputProcessorProfiles + ITfCategoryMgr），手写 CTF 注册表键会导致设置界面名字空白/键盘列表缺失；六个类别（TIP_KEYBOARD、INPUTMODECOMPARTMENT、UIELEMENTENABLED、IMMERSIVESUPPORT、SYSTRAYSUPPORT、DISPLAYATTRIBUTEPROVIDER）缺一不可，缺 INPUTMODECOMPARTMENT 会被现代应用禁用。
- **AddLanguageProfile 的名字/图标串必须 NUL 结尾**：CTF 存 Description 时不按 cch 截断、按 NUL 读，未补 NUL 会混入堆垃圾显示乱码（图标路径恰好踩在归零缓冲上才侥幸正常）。
- **ctfmon 会缓存并复活旧注册数据**（乱码/幽灵条目删了又回来）：换 profile GUID 才能斩断；任务栏图标有系统缓存，注销刷新。
- **OnTestKeyDown 必须对想接的键返回 TRUE**，否则 OnKeyDown 永远收不到（激活成功≠能打字）。
- 大码表（43MB）不能在 Activate 里同步解析（堵死切换输入法）：后台线程预载 + 全局槽，首次按键兜底同步加载。
- ctfmon 锁旧 DLL 导致安装 write 拒绝：装到**版本号子目录** + 装前 regsvr32 /u + taskkill ctfmon + Delete /REBOOTOK。
- windows-rs 0.61：`#[implement]` 的 trait 实现写在生成的 `Xxx_Impl` 上（不是原结构体）；COM 的 (指针, 长度) 参数对映射成 `&[u16]` 切片；VARIANT 手工构造要 explicit deref（`(*v.Anonymous.Anonymous).vt = VT_I4`）；接口指针非 Send，放全局槽需 newtype 包装。
- 任务栏「中/EN」模式图标：ITfLangBarItemButton 且 **guidItem 必须用系统保留的 `GUID_LBI_INPUTMODE`**——任务栏只收纳这一项，自定义 GUID 只会进默认隐藏的经典浮动语言栏（参考 weasel `WeaselTSF/LanguageBar.cpp`）；图标变化时 `ITfLangBarItemSink::OnUpdate(TF_LBI_ICON)`。搜狗那种「logo+模式」双图标里的 logo 是其私有托盘（Shell_NotifyIcon），非 TSF 能力。
- 诊断日志写 `%APPDATA%\lufly\tsf.log`；「有/无 OnKeyDown」是定位按键链路问题的关键证据。

## 打包（NSIS，lufly.nsi）

- MUI2 向导 + `ManifestDPIAware`；编码坑：**.nsi 用 UTF-8 BOM，LicenseData 用 UTF-16 LE BOM**，否则 Bad text encoding / 中文乱码。
- 页面顺序：欢迎 → 许可协议（点「我拒绝」退出安装）→ 目录 → 安装 → 完成。
- regsvr32 /s 会静默失败：装完回读注册表（Description）校验，失败弹明确提示。
- 升级安装列表里每个历史版本号都要出现在反注册与清理清单中。

## macOS 打包（ime/macos）

- 分发 = **传统拖拽式 dmg**（用户拍板，符合直觉）：dmg 内 Lufly.app + 「输入法」文件夹替身（`ln -s "/Library/Input Methods"`，清歌输入法同款），拖上去输密码装入系统输入法目录；装完注销重登 + 系统设置添加。曾试过独立 Bundle ID 安装器 app 与 pkg 向导，均被否——按 macOS 惯例来。
- **TIS 注册元数据有缓存**: 系统设置里显示的名称/图标是首次注册时缓存的；改 Info.plist/InfoPlist.strings 后盘上元数据已正确（可用 `TISGetInputSourceProperty(kTISPropertyLocalizedName)` 程序化验证），但设置界面要**注销重登**才刷新；若重登/重启都不行，终极手段 = 换 bundle/mode ID 斩缓存（同 TSF 换 profile GUID 教训），代价是用户需重新添加一次。
- **同 Bundle ID 单实例坑**: 输入法本体常驻后台时，Finder 双击另一份同 ID 的 Lufly.app 只会"激活"运行中实例、不启动新进程（无窗口、无报错、无崩溃日志）——拖拽安装不受影响，双击下载的 app 时要想到这一层。
- app 双入口保留：bundle 路径含 `/Input Methods/` = 输入法模式，否则 = 安装窗（src/Installer.swift）；`Lufly --install` 非交互安装（install.sh 即委托它）。
- pkg 的 `--install-location "~"` 不展开：文件落到字面 `~` 目录而 installer 仍报 success——装完必须实测验证落位。
- 输入法列表显示 mode ID 原文 = 缺 `Resources/<lang>.lproj/InfoPlist.strings`，且 mode ID 要作为其中的 key（fcitx5-macos/Squirrel 同款）。

## 工作方式

- **未经用户明确允许，不得 git commit / git push**：改完代码停在本地改动并告知用户，提交与否、何时提交由用户决定；一次允许不代表后续都允许。
- 涉及未验证的系统 API 行为**不要凭猜测下结论**：直接读真实开源实现（PIME/libIME2、rime/weasel、本仓库 fcitx5 端）。raw.githubusercontent.com 直连抓源码最可靠；WebSearch 结果曾被污染不可用。
- 用户以终端用户身份实测：交付**双击可用的安装包**而非脚本；安装器观感按商业软件标准（图标、DPI、许可页、完成页文案）。
