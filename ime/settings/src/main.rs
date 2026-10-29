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
use tao::window::WindowBuilder;
use wry::http::Request;
use wry::WebViewBuilder;

mod bridge;

fn main() {
    // 单实例：已有设置窗在跑就直接退出（不做激活前台的花活，第一版够用）
    if single_instance() {
        return;
    }
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

    let html = include_str!("../ui/index.html").replace("__INITIAL_PAGE__", &initial_page);

    let event_loop = EventLoopBuilder::<String>::with_user_event().build();
    let proxy = event_loop.create_proxy();
    let window = match WindowBuilder::new()
        .with_title("小鹭音形 · 设置")
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
