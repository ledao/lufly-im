# lufly-im

小鹭音形：自研顶功音形输入法。纯 Rust 引擎（`ime/engine`）+ 平台前端：
Linux fcitx5（`ime/fcitx5`）、Windows TSF（`ime/tsf`），macOS 为下一目标。

## 架构约定

- 引擎（`ime/engine`）是纯数据、平台无关的（可跨线程）；按键状态机、标点、造词等前端逻辑**逐功能对齐 fcitx5 版**（`ime/fcitx5/src/lufly.cpp` 是参照真源）。新平台前端只做薄壳：按键协议适配 + UI。
- 移植或对齐功能时，逐行比对 fcitx5 实现，不要凭记忆重写。
- 引擎码表 **v2 格式**（`LUFLYD02`，`ime/tools/build_dict.py` 产物）：文件内嵌「(数据偏移, rank) × N」索引区，引擎把整个文件 mmap/托管拷贝后按索引借用（`meta_of`/`ranges_of`），**堆上零索引**；加载时逐条校验索引指向、记录边界与 UTF-8（损坏文件加载期拒绝，查询期免判空）。实测（1.37M 条目、`cargo run -p lufly-engine --example mem` + vmmap）：mmap 路径（`lufly_new_file`，macOS 在用）进程物理占用 **~1.5MB**——码表 32.5MB 全是干净文件页，内存压力下系统直接丢弃；堆拷贝路径（`lufly_new`）≈ 文件自身大小、无引擎额外开销。历史教训：v0 每条目两个 String 曾把码表放大成 ~140MB 常驻。**MAGIC 升级 = 旧 bin 全平台不兼容**：改格式须重跑 build_dict.py 并重编各端（fcitx5 `install.sh`/`pack.sh`、TSF `include_bytes!`、macOS `build.sh` 都直接取 `ime/data/`）。

## Windows TSF（ime/tsf）非显而易见的坑

- **注册必须走 COM API**（ITfInputProcessorProfiles + ITfCategoryMgr），手写 CTF 注册表键会导致设置界面名字空白/键盘列表缺失；六个类别（TIP_KEYBOARD、INPUTMODECOMPARTMENT、UIELEMENTENABLED、IMMERSIVESUPPORT、SYSTRAYSUPPORT、DISPLAYATTRIBUTEPROVIDER）缺一不可，缺 INPUTMODECOMPARTMENT 会被现代应用禁用。
- **AddLanguageProfile 的名字/图标串必须 NUL 结尾**：CTF 存 Description 时不按 cch 截断、按 NUL 读，未补 NUL 会混入堆垃圾显示乱码（图标路径恰好踩在归零缓冲上才侥幸正常）。
- **ctfmon 会缓存并复活旧注册数据**（乱码/幽灵条目删了又回来）：换 profile GUID 才能斩断；任务栏图标有系统缓存，注销刷新。
- **按键决策必须在 OnTestKeyDown 阶段完成**（对齐 weasel `_ProcessKeyEvent`：Test 时跑完整状态机并执行，OnKeyDown 只回放缓存判定，不二次决策）。「Test 返回 TRUE 但 OnKeyDown 放行」的键在 CUAS 应用（企业微信）被系统吃掉后**不回注、凭空消失**——Edge 等 TSF 感知应用会回注，造成「别处正常、仅企业微信坏」的假象（实例：空缓冲退格无效）。同键多次 Test（WORD 2010 x64 类应用）需缓存判定、只决策一次；只缓存 TRUE，FALSE 键系统不会路由 OnKeyDown。
- 大码表（43MB）不能在 Activate 里同步解析（堵死切换输入法）：后台线程预载 + 全局槽，首次按键兜底同步加载。
- ctfmon 锁旧 DLL 导致安装 write 拒绝：装到**版本号子目录** + 装前 regsvr32 /u + taskkill ctfmon + Delete /REBOOTOK。
- windows-rs 0.61：`#[implement]` 的 trait 实现写在生成的 `Xxx_Impl` 上（不是原结构体）；COM 的 (指针, 长度) 参数对映射成 `&[u16]` 切片；VARIANT 手工构造要 explicit deref（`(*v.Anonymous.Anonymous).vt = VT_I4`）；接口指针非 Send，放全局槽需 newtype 包装。
- 任务栏「中/EN」模式图标：ITfLangBarItemButton 且 **guidItem 必须用系统保留的 `GUID_LBI_INPUTMODE`**——任务栏只收纳这一项，自定义 GUID 只会进默认隐藏的经典浮动语言栏（参考 weasel `WeaselTSF/LanguageBar.cpp`）；图标变化时 `ITfLangBarItemSink::OnUpdate(TF_LBI_ICON)`。搜狗那种「logo+模式」双图标里的 logo 是其私有托盘（Shell_NotifyIcon），非 TSF 能力。
- **32 位应用读 WOW6432Node 视图**：微信/企业微信（WXWork.exe）/QQ 主程序多为 32 位，只注册 x64 视图时 TIP 在这些进程根本装不进去（无任何报错，仅 64 位子进程能加载）；必须 x86/x64 双 DLL，各自用对应位数的 regsvr32 注册（32 位安装器里 x64 走 `$WINDIR\Sysnative`，x86 走 `SysWOW64`），DeleteRegKey/ReadRegStr 要 `SetRegView` 切视图。
- **CUAS 应用自愈要挂「线程默认 HIMC」而不是 ImmCreateContext 新造的**：新建上下文 CUAS 不认、fOpen=false，挂上后按键照样绕过 TIP；默认上下文用临时窗口 `ImmGetContext` 取（无显式关联的窗口返回的就是它，TIP 激活后由 CUAS 托管）。企业微信 5.x（Flutter）会断开焦点窗口的 IME 关联，只能进程内定时体检重挂。
- 诊断日志写 `%APPDATA%\lufly\tsf.log`（每行带 pid 前缀——多进程共写，无 pid 无法归因）；「有/无 OnKeyDown」是定位按键链路问题的关键证据。

## 打包（NSIS，lufly.nsi）

- MUI2 向导 + `ManifestDPIAware`；编码坑：**.nsi 用 UTF-8 BOM，LicenseData 用 UTF-16 LE BOM**，否则 Bad text encoding / 中文乱码。
- 页面顺序：欢迎 → 许可协议（点「我拒绝」退出安装）→ 目录 → 安装 → 完成。
- regsvr32 /s 会静默失败：装完回读注册表（Description）校验，失败弹明确提示。
- 升级安装列表里每个历史版本号都要出现在反注册与清理清单中。

## macOS 打包（ime/macos）

- 分发 = **双击安装器式 dmg**（dmg 内只有 Lufly.app + 安装说明.txt）：双击 → 弹内置 Installer → 「安装」→ 落位 `~/Library/Input Methods` + `TISRegisterInputSource` 免注销注册 → 系统设置添加。**曾用拖拽式**（Lufly.app + 「输入法」替身，清歌同款），实证缺陷：拖拽路径无代码可执行、注册全靠 TIS 自动扫描，彻底删除重装后 TIS 缓存不认同 Bundle ID → 输入法消失且无任何报错（2026-09 实测）；且拖拽会在 `/Library/Input Methods` 留残留，Installer 现会请求管理员密码清理（osascript with administrator privileges）。曾试过独立 Bundle ID 安装器 app 与 pkg 向导，均被否。
- dmg 窗口要布置**背景引导图**（"双击「Lufly」开始安装"，`tools/mkdmgbg.swift` 生成）+ AppleScript 定位图标——裸 dmg 用户不知道要双击安装（用户反馈）。**样式持久化坑**：必须先建可写 UDRW → 挂载 → Finder 布置（写 .DS_Store）→ 卸载 → `hdiutil convert` 成 UDZO；直接对 UDZO 布置是只读卷，样式静默丢失。
- **TIS 注册元数据有缓存**: 系统设置里显示的名称/图标是首次注册时缓存的；改 Info.plist/InfoPlist.strings 后盘上元数据已正确（可用 `TISGetInputSourceProperty(kTISPropertyLocalizedName)` 程序化验证），但设置界面要**注销重登**才刷新；若重登/重启都不行，终极手段 = 换 bundle/mode ID 斩缓存（同 TSF 换 profile GUID 教训），代价是用户需重新添加一次。
- **同 Bundle ID 单实例坑**: 输入法本体常驻后台时，Finder 双击另一份同 ID 的 Lufly.app 只会"激活"运行中实例、不启动新进程（无窗口、无报错、无崩溃日志）——拖拽安装不受影响，双击下载的 app 时要想到这一层。
- app 双入口保留：bundle 路径含 `/Input Methods/` = 输入法模式，否则 = 安装窗（src/Installer.swift）；`Lufly --install` 非交互安装（install.sh 即委托它）。
- pkg 的 `--install-location "~"` 不展开：文件落到字面 `~` 目录而 installer 仍报 success——装完必须实测验证落位。
- 输入法列表显示 mode ID 原文 = 缺 `Resources/<lang>.lproj/InfoPlist.strings`，且 mode ID 要作为其中的 key（fcitx5-macos/Squirrel 同款）。
- **图标两条硬坑（2026-09-02 全链路实证，`tools/mkiconpdf.swift` 头注释同步）**：
  ① 图标文件**词干不能与 lufly.icns 撞名**——TIS 按扩展名无关的 `imageForResource:` 查找，词干 "lufly" 会命中 icns → 菜单栏图标占位方块（曾误判为矢量/位图/缓存问题，换内容对照实验才定位，真因就这一个），故命名 menu_icon.pdf；
  ② **必须经 CGPDFContext 生成标准结构 PDF，不能手写极简 PDF**——Ctrl+Space 切换器 HUD 由**远端视图服务**渲染（TextInputUIMacHelper `TUINSCursorUIController`/ViewBridge，反汇编+_selectCurrentInputSource 崩溃栈实证），它消化不了手写的 4 对象未压缩 PDF：菜单栏（NSImage 路径）正常、切换器白方块；换 CG 生成的 PDF（内嵌 Flate 位图）两端全通。HUD 磁贴数据与 TIS 的 IconImageURL/IconRef 均无关（后者对所有源都为 NULL）。
  调试手段：ObjC 运行时反射 dump 私有框架（dlopen + objc_copyClassNamesForImage + class_copyMethodList），共享缓存二进制可从进程内存抠字符串；lldb attach 自建 dlopen 宿主进程可反汇编任意私有方法。
- **安装器不做主动注册（TISRegisterInputSource）**：实测自动注册出的输入法条目能出现在列表里但打不了字，用户仍须「− 删除 + ＋ 添加」手动来一遍，白注册还留坏条目（用户裁定）。安装器只落位 + 弹指引（含先减后加提示）。

## 标点半角规则变更（三端已同步，fcitx5/TSF 待发版）

用户裁定：标点上下文半角只由数字触发——`lastCls == 1`（3.14 / 1,000）或 Ctrl+0 强制；
字母后（含 miss 英文缓冲）一律全角（中英混排「Mac，很好用」不再出半角逗号）。
旧逻辑为 数字+英文（lastCls!=0）+miss 都半角，三端已全部改为新条件：

- macOS：已实现并实测（含 punctErased：空缓冲退格删掉已上屏字符后，下一标点无视 lastCls 恢复全角）。
- fcitx5（Linux）：`src/lufly.cpp` 标点分支已同步（punctErased 原有，作用范围收窄到数字），未重新构建——下次构建即生效。
- TSF（Windows）：`src/processor.rs` 已同步（已过 x86_64-pc-windows-msvc cargo check，未出 DLL）——发版时注意更新说明。

## 码表 v2 升级（fcitx5/TSF 待重编上线）

引擎码表格式已升级 v2（MAGIC `LUFLYD01`→`LUFLYD02`）：文件内嵌「(数据偏移, rank) × N」索引，引擎整体 mmap/托管后按索引借用、**堆上零索引**；`ime/data/xiaolu_he_he.bin`（32.5MiB/137.3万条）与 `xiaolu_fuzhu.bin` 已重新生成。实测（vmmap）：mmap 路径进程物理占用 **~1.5MB**（码表全为可回收干净文件页），旧 v0 约 140MB；同方案本机对比 Rime/Squirrel 常驻 27.9MB。**C ABI 除新增 `lufly_new_file`（mmap 加载）外不变**，前端逻辑零改动，重编即接入：

- fcitx5（Linux）：重跑 `build.sh` → `install.sh` 即可（build.sh 本就全路径链 `liblufly_capi.a`，不受 capi 改动影响）。**已部署机器必须升级 `/usr/share/fcitx5/lufly/*.bin`**——旧 bin 加载直接报 "bad dict: invalid magic"，不会静默出错词。快速回归：`cargo run -p lufly-cli` REPL 跑几组键序。
- TSF（Windows）：`processor.rs` 的 `include_bytes!` 已指向新 bin，重编 DLL + NSIS 即可；升级安装注意覆盖旧码表。
- capi crate-type 收窄为仅 staticlib（cdylib 移除）：cdylib 与 .a 并存时 `-llufly_capi` 会被链接器挑中 dylib，留下指向 `target/` 的绝对路径 install_name，跨机器分发 dyld 起不来（macOS 踩过，已修）。新端接入一律全路径链 `.a`（fcitx5/macOS 的 build.sh 均已如此）。
- 引擎自测工具：`cargo test -p lufly-engine`（23 例）；`cargo run -p lufly-engine --example mem` + vmmap（内存）；`ime/macos/tools/engtest.c`（C API 打字流）。

## 词库源 sqlite 同步（2026-09-03 已闭环）

码表的正源是 `lufly/sys_data/sys_table.sqlite`（wordphonetable，含各双拼变体列，**本机已有**：2026-05-06 从另一台机器拷来、gitignore 掉 *.sqlite），`rime_*/​*.dict.yaml` 由 `scripts/generate_rime*.py` 从它生成，bin 再由 build_dict.py 编译。「阈值」yù 音当时库不在手边，只手改了 yaml + 重建 bin，现已回填源库：

- wordphonetable 插入「阈值」行：`full='yu zhi', xhe/zrm/lu='yuvi', priority=6, bingji='yyvj'`（镜像「阀值」favi/fuvj 结构；bingji=首字并击+尾字并击，阈=yy、值=vj）
- 重跑 `scripts/generate_rime_xhe_phone_xhe_shape.py`：生成 yaml 与手改内容一致（排序落位不同属正常——生成器按优先级排序），「阀值」三行保留（错写形式，用户习惯用）；以生成结果为准重编两枚 bin
- 词组 yaml 三行变体（yuvi/yuvim/yuvimr）是生成器从单行 sqlite 记录自动展开的（generator.py `generate_full_words` + 写出时 `encode[0:-2]`/`[0:-1]`/全码），**源库只需一行**；生成脚本依赖 peewee/pypinyin/toolz/tqdm
- 加字词的完整链路现在是：改 sqlite → 跑 generate_rime*.py → 跑 `ime/tools/build_dict.py`（无参一次编两枚）→ TSF 重编 DLL（include_bytes!）+ fcitx5/macOS 拷新 bin

## 工作方式

- **未经用户明确允许，不得 git commit / git push**：改完代码停在本地改动并告知用户，提交与否、何时提交由用户决定；一次允许不代表后续都允许。
- 涉及未验证的系统 API 行为**不要凭猜测下结论**：直接读真实开源实现（PIME/libIME2、rime/weasel、本仓库 fcitx5 端）。raw.githubusercontent.com 直连抓源码最可靠；WebSearch 结果曾被污染不可用。
- 用户以终端用户身份实测：交付**双击可用的安装包**而非脚本；安装器观感按商业软件标准（图标、DPI、许可页、完成页文案）。
