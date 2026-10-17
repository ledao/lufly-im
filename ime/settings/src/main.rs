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

use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tao::window::WindowBuilder;
use wry::http::Request;
use wry::WebViewBuilder;

mod bridge;

fn main() {
    // 单实例：已有设置窗在跑就直接退出（不做激活前台的花活，第一版够用）
    if single_instance() {
        return;
    }
    // --page=dict：从托盘「用户词典…」进入时直接落到词库页。
    // 白名单校验——值会被 replace 进 HTML 的 JS 字符串字面量，
    // 含引号的任意值 = 脚本注入面（虽然只是本地设置程序，仍然要堵）
    let initial_page = std::env::args()
        .nth(1)
        .and_then(|a| a.strip_prefix("--page=").map(|s| s.to_string()))
        .filter(|s| matches!(s.as_str(), "keys" | "look" | "dict" | "adv"))
        .unwrap_or_default();

    let html = include_str!("../ui/index.html").replace("__INITIAL_PAGE__", &initial_page);

    let event_loop = EventLoopBuilder::<String>::with_user_event().build();
    let proxy = event_loop.create_proxy();
    let window = WindowBuilder::new()
        .with_title("小鹭音形 · 设置")
        .with_inner_size(tao::dpi::LogicalSize::new(840.0, 580.0))
        .with_min_inner_size(tao::dpi::LogicalSize::new(720.0, 500.0))
        .build(&event_loop)
        .expect("create window");

    let ipc = move |req: Request<String>| {
        // JS 侧 payload 是 JSON 字符串；转发到主循环处理（handler 内拿不到 webview）
        let _ = proxy.send_event(req.body().clone());
    };

    let webview = WebViewBuilder::new()
        .with_html(html)
        .with_ipc_handler(ipc)
        .build(&window);

    let webview = match webview {
        Ok(v) => v,
        Err(e) => {
            // 最常见原因：系统无 WebView2 运行时（老 LTSC/精简系统）
            let msg = format!(
                "设置界面无法启动（{}）。\n\n缺少 WebView2 运行时时，请从微软官网下载安装：\n\
                 https://developer.microsoft.com/microsoft-edge/webview2/\n\n\
                 输入法本身不受影响，仍可正常使用。",
                e
            );
            eprintln!("{msg}");
            bridge::message_box(&msg, "小鹭音形");
            return;
        }
    };

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            Event::UserEvent(msg) => {
                let resp = bridge::handle(&msg);
                if let Some(json) = resp {
                    let _ = webview.evaluate_script(&format!(
                        "window.__bridge && window.__bridge({json})"
                    ));
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

/// 命名互斥体单实例。CreateMutexW「已存在」也返回有效句柄、只能靠
/// GetLastError 区分（其线程局部状态易被污染，不可靠），故用
/// OpenMutexW **按返回值**探测：打得开 = 已有实例；Err = 首例，再创建。
fn single_instance() -> bool {
    use windows::Win32::Foundation::CloseHandle;
    use windows::Win32::System::Threading::{
        CreateMutexW, OpenMutexW, SYNCHRONIZATION_ACCESS_RIGHTS,
    };
    unsafe {
        let name: Vec<u16> = "LuflyCfgMutex\0".encode_utf16().collect();
        let p = windows::core::PCWSTR(name.as_ptr());
        if let Ok(h) = OpenMutexW(SYNCHRONIZATION_ACCESS_RIGHTS(0x0010_0000), false, p) {
            let _ = CloseHandle(h);
            return true; // 已有设置窗在跑
        }
        let _ = CreateMutexW(None, true, p);
        false
    }
}
