//! 小鹭音形设置程序（独立进程，WebView2 壳 + 内嵌 HTML UI）。
//!
//! 为什么是独立 exe 而不是住在 TIP DLL 里：DLL 注入所有有输入焦点的进程，
//! 设置窗口的消息循环/panic 都会堵在宿主 UI 线程上——正是「FFI panic 杀宿主」
//! 红线的扩大版。搜狗/小狼毫同构（独立设置进程）。
//!
//! 桥协议（wry ipc）：
//!   JS:  window.ipc.postMessage(JSON.stringify({cmd:"get"}))
//!   Rust 处理后 evaluate_script 回调: window.__bridge(<json>)
//!
//! 配置存储 %APPDATA%\lufly\config.json：JSON 平铺、缺省值合并、tmp+rename
//! 原子写。字段默认值的唯一真源是 tsf/src/config.rs（TIP 侧反序列化），
//! 本文件的 DEFAULTS 必须与它同步。

// release 按 GUI 子系统编译：否则每次从托盘菜单启动都闪一个 cmd 控制台
// （console 子系统进程会被分配新终端）。debug 保留控制台方便看 eprintln。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tao::platform::windows::EventLoopBuilderExtWindows;
use tao::window::WindowBuilder;
use wry::http::Request;
use wry::WebViewBuilder;

mod bridge;

/// 跨进程「激活已有设置窗」消息（第二实例 → 第一实例）。
/// wParam = 页面编号 1..4（对应 keys/look/dict/adv），0 = 仅激活。
const ACTIVATE_MSG: &str = "LuflySettingsActivate";
/// 窗口标题唯一真源：with_title 与 FindWindowW 都取它（改一处即可）
const WINDOW_TITLE: &str = "小鹭音形 · 设置";

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// 跨进程切页请求文件：第二实例在消息泵之外再留一份持久请求。
/// 第一实例页面脚本就绪时读取消费——避免「消息在消息泵启动前发出被丢弃」
/// 的启动竞态（实测：立即启动时 hook 收不到，延迟 3s 才收得到）。
/// 内容 = "页面名 写入时刻(Unix 秒)"：只接受 5 秒内的请求（实测页面
/// 脚本就绪在 1~2 秒内），避免上次异常退出残留的文件让下次正常启动
/// 被意外切页。
fn nav_request_path() -> std::path::PathBuf {
    std::env::var("APPDATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::env::temp_dir())
        .join("lufly")
        .join("settings-nav.txt")
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn write_nav_request(page: &str) {
    let p = nav_request_path();
    if let Some(d) = p.parent() {
        let _ = std::fs::create_dir_all(d);
    }
    let _ = std::fs::write(&p, format!("{page} {}", now_secs()));
}

fn take_nav_request() -> Option<String> {
    let p = nav_request_path();
    let s = std::fs::read_to_string(&p).ok()?;
    let _ = std::fs::remove_file(&p); // 无论是否有效都清掉，避免反复残留
    let mut it = s.trim().split_whitespace();
    let page = it.next()?;
    let ts: u64 = it.next()?.parse().ok()?; // 旧格式（无时间戳）= 丢弃
    if now_secs().saturating_sub(ts) > 5 {
        return None; // 过期残留，不切页
    }
    match page {
        "keys" | "look" | "dict" | "adv" => Some(page.to_string()),
        _ => None,
    }
}

fn activate_msg_id() -> u32 {
    use windows::Win32::UI::WindowsAndMessaging::RegisterWindowMessageW;
    let name = wide(ACTIVATE_MSG);
    unsafe { RegisterWindowMessageW(windows::core::PCWSTR(name.as_ptr())) }
}

/// 页面名 → wParam（与 HTML 的 nav data-page 顺序一致）
fn page_code(s: &str) -> usize {
    match s {
        "keys" => 1,
        "look" => 2,
        "dict" => 3,
        "adv" => 4,
        _ => 0,
    }
}

fn code_page(n: usize) -> &'static str {
    match n {
        1 => "keys",
        2 => "look",
        3 => "dict",
        4 => "adv",
        _ => "",
    }
}

fn main() {
    // GUI 子系统无控制台，panic 默认只进 stderr（= 无输出）→ 用户看到程序
    // 无声消失。兜底：写日志文件 + 弹框，至少留下可反馈的线索。
    install_panic_hook();
    // --page=dict：从托盘「用户词典…」进入时直接落到词库页。
    // 白名单校验——值会被 replace 进 HTML 的 JS 字符串字面量，
    // 含引号的任意值 = 脚本注入面（虽然只是本地设置程序，仍然要堵）
    let initial_page = std::env::args()
        .nth(1)
        .and_then(|a| a.strip_prefix("--page=").map(|s| s.to_string()))
        .filter(|s| matches!(s.as_str(), "keys" | "look" | "dict" | "adv"))
        .unwrap_or_default();

    // 单实例：已有窗口就激活它（含 --page 切页）后退出。
    // 第二实例带 --page=dict 时不能只是「不重复开」——用户点的是
    // 「用户词典…」，必须把已有窗切到词库页，否则像没反应。
    if single_instance(&initial_page) {
        return;
    }

    let html = include_str!("../ui/index.html").replace("__INITIAL_PAGE__", &initial_page);

    let msg_id = activate_msg_id();
    let mut builder = EventLoopBuilder::<String>::with_user_event();
    // hook 在 build() 之前注册、拿不到 EventLoopProxy，用共享槽在
    // build 后回填（消息循环启动前必然已填，无竞态）
    let hook_proxy: std::sync::Arc<std::sync::Mutex<Option<tao::event_loop::EventLoopProxy<String>>>> =
        std::sync::Arc::new(std::sync::Mutex::new(None));
    // 待切页面：第二实例可能在 WebView2 页面脚本就绪前就发来消息，
    // 此时 evaluate_script 里 __go_page 尚未定义、切页会被静默丢弃。
    // 先存下来，页面脚本发 ready 时补发（后被消费的覆盖先到的，符合直觉）。
    // 不用 wry 的 PageLoadEvent::Finished：with_html 走 NavigateToString，
    // NavigationCompleted 不保证触发（实测不触发）。
    let pending_page: std::sync::Arc<std::sync::Mutex<Option<String>>> =
        std::sync::Arc::new(std::sync::Mutex::new(if initial_page.is_empty() {
            None
        } else {
            Some(initial_page.clone())
        }));
    let slot = hook_proxy.clone();
    let pending_for_hook = pending_page.clone();
    builder.with_msg_hook(move |raw| {
        use windows::Win32::UI::WindowsAndMessaging::MSG;
        let m = unsafe { &*(raw as *const MSG) };
        if msg_id != 0 && m.message == msg_id {
            let page = code_page(m.wParam.0);
            // 消息已送达并处理，清掉可能同时存在的持久请求（防残留导致
            // 下次启动被意外切页）
            let _ = std::fs::remove_file(nav_request_path());
            if !page.is_empty() {
                *pending_for_hook
                    .lock()
                    .unwrap_or_else(std::sync::PoisonError::into_inner) = Some(page.to_string());
            }
            if let Some(p) = slot.lock().ok().and_then(|g| g.clone()) {
                let _ = p.send_event(format!("@page:{page}"));
            }
            return true; // 已处理，不派发给 wndproc
        }
        false
    });
    let event_loop = builder.build();
    let proxy = event_loop.create_proxy();
    *hook_proxy.lock().unwrap_or_else(std::sync::PoisonError::into_inner) = Some(proxy.clone());
    let window = match WindowBuilder::new()
        .with_title(WINDOW_TITLE)
        .with_inner_size(tao::dpi::LogicalSize::new(840.0, 580.0))
        .with_min_inner_size(tao::dpi::LogicalSize::new(720.0, 500.0))
        .build(&event_loop)
    {
        Ok(w) => w,
        Err(e) => {
            // GUI 子系统下 panic = 静默消失（用户零信息），必须显式提示
            bridge::message_box(
                &format!("设置窗口创建失败：{e}\n\n输入法本身不受影响，仍可正常使用。"),
                "小鹭音形",
            );
            return;
        }
    };

    let ipc = move |req: Request<String>| {
        // JS 侧 payload 是 JSON 字符串；转发到主循环处理（handler 内拿不到 webview）
        let _ = proxy.send_event(req.body().clone());
    };

    // WebView2 用户数据目录必须显式指到可写位置：默认是 exe 同目录的
    // {exe}.WebView2\，装进 Program Files 后普通权限不可写 →
    // CreateCoreWebView2Environment 报 0x80070005 拒绝访问（开发目录跑
    // 不出、装机必炸的权限路径差异）
    let data_dir = std::env::var("LOCALAPPDATA")
        .map(|d| std::path::PathBuf::from(d).join("lufly").join("settings-data"))
        .unwrap_or_else(|_| std::env::temp_dir().join("lufly-settings-data"));
    let _ = std::fs::create_dir_all(&data_dir);
    let mut web_context = wry::WebContext::new(Some(data_dir));

    let webview = WebViewBuilder::new_with_web_context(&mut web_context)
        .with_html(html)
        .with_ipc_handler(ipc)
        .build(&window);

    let webview = match webview {
        Ok(v) => v,
        Err(e) => {
            // 按错误码分诊，别把权限问题误导成缺运行时
            let es = format!("{e}");
            let hint = if es.contains("0x80070005") {
                "权限被拒绝：若安全软件拦截了 lufly-settings.exe，请放行后重试。".to_string()
            } else if es.contains("0x80070002") {
                "缺少 WebView2 运行时（老 LTSC/精简系统常见），请从微软官网下载安装：\n\
                 https://developer.microsoft.com/microsoft-edge/webview2/"
                    .to_string()
            } else {
                format!("未知错误。若安全软件拦截了 lufly-settings.exe，请放行后重试。\n错误详情：{es}")
            };
            let msg = format!("设置界面无法启动。\n\n{hint}\n\n输入法本身不受影响，仍可正常使用。");
            // GUI 子系统下无 stderr 句柄——eprintln! 写失败会 panic（在
            // message_box 之前，错误提示框就永远弹不出来了），必须容错写
            use std::io::Write;
            let _ = std::io::stderr().write_all(msg.as_bytes());
            bridge::message_box(&msg, "小鹭音形");
            return;
        }
    };

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            Event::UserEvent(msg) => {
                if let Some(page) = msg.strip_prefix("@page:") {
                    if !page.is_empty() {
                        let _ = webview.evaluate_script(&format!(
                            "window.__go_page && window.__go_page({page:?})"
                        ));
                    }
                } else {
                    // 页面脚本就绪：优先消费持久切页请求（启动竞态兜底），
                    // 否则用内存里的 pending（消息在页面加载期到达但
                    // evaluate_script 执行时脚本尚未定义的情形）
                    if msg.contains("\"cmd\":\"ready\"") {
                        let page = take_nav_request().or_else(|| {
                            pending_page
                                .lock()
                                .unwrap_or_else(std::sync::PoisonError::into_inner)
                                .take()
                        });
                        if let Some(page) = page {
                            let _ = webview.evaluate_script(&format!(
                                "window.__go_page && window.__go_page({page:?})"
                            ));
                        }
                    }
                    let resp = bridge::handle(&msg);
                    if let Some(json) = resp {
                        let _ = webview.evaluate_script(&format!(
                            "window.__bridge && window.__bridge({json})"
                        ));
                    }
                }
            }
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            Event::WindowEvent {
                event: WindowEvent::Destroyed,
                ..
            } => *control_flow = ControlFlow::Exit,
            _ => {}
        }
    });
}

/// panic 兜底（GUI 子系统无控制台，默认 panic 用户零感知）。
/// 写 %APPDATA%\lufly\settings-panic.log + 弹框；hook 内不再 panic。
fn install_panic_hook() {
    std::panic::set_hook(Box::new(|info| {
        let msg = format!("设置程序内部错误：\n{info}\n\n输入法本身不受影响。");
        if let Some(dir) = std::env::var("APPDATA").ok().map(std::path::PathBuf::from) {
            let _ = std::fs::create_dir_all(dir.join("lufly"));
            if let Ok(mut f) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(dir.join("lufly").join("settings-panic.log"))
            {
                use std::io::Write;
                let _ = writeln!(f, "[{}] {info}", std::process::id());
            }
        }
        bridge::message_box(&msg, "小鹭音形");
    }));
}

/// 单实例 + 激活已有窗口。CreateMutexW「已存在」也返回有效句柄、只能靠
/// GetLastError 区分（其线程局部状态易被污染，不可靠），故用
/// OpenMutexW **按返回值**探测：打得开 = 已有实例；Err = 首例，再创建。
/// 探测到已有实例时：FindWindowW 找窗口 → 还原/前台 → 自定义消息带页面号
/// （第二实例点「用户词典…」时把已有窗切到词库页，而不是没反应）。
fn single_instance(page: &str) -> bool {
    use windows::core::PCWSTR;
    use windows::Win32::Foundation::{CloseHandle, LPARAM, WPARAM};
    use windows::Win32::System::Threading::{
        CreateMutexW, OpenMutexW, SYNCHRONIZATION_ACCESS_RIGHTS,
    };
    use windows::Win32::UI::WindowsAndMessaging::{
        FindWindowW, IsIconic, PostMessageW, SetForegroundWindow, ShowWindow, SW_RESTORE,
    };
    unsafe {
        let name = wide("LuflyCfgMutex");
        let p = PCWSTR(name.as_ptr());
        if let Ok(h) = OpenMutexW(SYNCHRONIZATION_ACCESS_RIGHTS(0x0010_0000), false, p) {
            let _ = CloseHandle(h);
            // 持久请求先行：不管消息是否送达，已有实例页面就绪时都会读到
            if !page.is_empty() {
                write_nav_request(page);
            }
            let title = wide(WINDOW_TITLE);
            // 第一实例可能刚创建 mutex 但窗口尚未建好（FindWindow 会失败），
            // 短轮询等待窗口出现；找不到也不弹错，静默退出即可
            let mut hwnd = None;
            for _ in 0..20 {
                if let Ok(h) = FindWindowW(PCWSTR::null(), PCWSTR(title.as_ptr())) {
                    if !h.is_invalid() {
                        hwnd = Some(h);
                        break;
                    }
                }
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            if let Some(hwnd) = hwnd {
                if IsIconic(hwnd).as_bool() {
                    let _ = ShowWindow(hwnd, SW_RESTORE);
                }
                let _ = SetForegroundWindow(hwnd);
                let msg = activate_msg_id();
                if msg != 0 {
                    let _ = PostMessageW(Some(hwnd), msg, WPARAM(page_code(page)), LPARAM(0));
                }
            }
            return true; // 已有设置窗在跑
        }
        let _ = CreateMutexW(None, true, p);
        false
    }
}
