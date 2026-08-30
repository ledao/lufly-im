//! 中英模式提示浮窗 —— Shift 切换时在屏幕右下角闪现「中 / EN」，约 1 秒自动消失。
//!
//! 对齐 fcitx5 的模式切换视觉反馈（托盘图标/标签随中英变化）；
//! Windows 现代语言栏不显示第三方状态，用轻量浮窗替代。
#![allow(non_snake_case)]

use std::sync::Mutex;

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::*;

const CLASS_NAME: PCWSTR = w!("LuflyStatusWnd");
const TIMER_ID: usize = 1;
const SHOW_MS: u32 = 1000;
const WND_SIZE: i32 = 44;

/// hwnd 存 isize（HWND 非 Send）
static HWND_SLOT: Mutex<isize> = Mutex::new(0);
/// HFONT 存 isize（同 cand.rs 限制）
static FONT: Mutex<isize> = Mutex::new(0);

fn font() -> HFONT {
    let mut f = FONT.lock().unwrap();
    if *f == 0 {
        unsafe {
            let h = CreateFontW(
                -22,
                0,
                0,
                0,
                FW_SEMIBOLD.0 as i32,
                0,
                0,
                0,
                DEFAULT_CHARSET,
                OUT_DEFAULT_PRECIS,
                CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY,
                DEFAULT_PITCH.0 as u32,
                w!("Microsoft YaHei"),
            );
            *f = h.0 as isize;
        }
    }
    HFONT(*f as *mut _)
}

fn ensure_window() -> Option<HWND> {
    let cached = *HWND_SLOT.lock().unwrap();
    if cached != 0 {
        let h = HWND(cached as *mut _);
        if !h.is_invalid() {
            return Some(h);
        }
    }
    unsafe {
        let hinstance = GetModuleHandleW(PCWSTR::null()).ok()?;
        let wc = WNDCLASSW {
            style: CS_SAVEBITS,
            lpfnWndProc: Some(wnd_proc),
            hInstance: hinstance.into(),
            hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(),
            lpszClassName: CLASS_NAME,
            ..Default::default()
        };
        RegisterClassW(&wc);
        let hwnd = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            CLASS_NAME,
            w!(""),
            WS_POPUP,
            0,
            0,
            WND_SIZE,
            WND_SIZE,
            None,
            None,
            Some(hinstance.into()),
            None,
        )
        .ok()?;
        // 圆角
        let rgn = CreateRoundRectRgn(0, 0, WND_SIZE + 1, WND_SIZE + 1, 12, 12);
        let _ = SetWindowRgn(hwnd, Some(rgn), true);
        *HWND_SLOT.lock().unwrap() = hwnd.0 as isize;
        Some(hwnd)
    }
}

/// 模式切换提示: ascii=true 显示 EN，false 显示 中
pub fn flash(ascii: bool) {
    let Some(hwnd) = ensure_window() else {
        return;
    };
    unsafe {
        // 底色深灰、白字，文本存进窗口属性（SetProp 字符串键）
        let text: &str = if ascii { "EN" } else { "中" };
        let prop_name = w!("luflyText");
        let vec: Vec<u16> = text.encode_utf16().collect();
        let _ = SetPropW(hwnd, prop_name, Some(HANDLE(Box::into_raw(Box::new(vec)) as *mut _)));

        // 屏幕工作区右下角
        let mut mi = MONITORINFO {
            cbSize: std::mem::size_of::<MONITORINFO>() as u32,
            ..Default::default()
        };
        let mut pt = POINT::default();
        let _ = GetCursorPos(&mut pt);
        let hmon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
        let (mut x, mut y) = (0, 0);
        if !hmon.is_invalid() && GetMonitorInfoW(hmon, &mut mi).as_bool() {
            x = mi.rcWork.right - WND_SIZE - 48;
            y = mi.rcWork.bottom - WND_SIZE - 48;
        }
        let _ = SetWindowPos(
            hwnd,
            Some(HWND_TOPMOST),
            x,
            y,
            WND_SIZE,
            WND_SIZE,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        );
        let _ = InvalidateRect(Some(hwnd), None, true);
        let _ = SetTimer(Some(hwnd), TIMER_ID, SHOW_MS, None);
    }
}

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_TIMER => {
            unsafe {
                let _ = KillTimer(Some(hwnd), TIMER_ID);
                let _ = ShowWindow(hwnd, SW_HIDE);
            }
            LRESULT(0)
        }
        WM_PAINT => unsafe {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            // 深灰底
            let bg = CreateSolidBrush(COLORREF(0x303030));
            let _ = FillRect(hdc, &ps.rcPaint, bg);
            let _ = DeleteObject(bg.into());
            // 白字居中
            let prop_name = w!("luflyText");
            let raw = GetPropW(hwnd, prop_name);
            if !raw.is_invalid() {
                let vec = &*(raw.0 as *mut Vec<u16>);
                let old = SelectObject(hdc, font().into());
                SetBkMode(hdc, TRANSPARENT);
                SetTextColor(hdc, COLORREF(0xFFFFFF));
                let mut size = SIZE::default();
                let _ = GetTextExtentPoint32W(hdc, vec.as_slice(), &mut size);
                let x = (WND_SIZE - size.cx) / 2;
                let y = (WND_SIZE - size.cy) / 2;
                let _ = TextOutW(hdc, x, y, vec.as_slice());
                SelectObject(hdc, old);
            }
            let _ = EndPaint(hwnd, &ps);
            LRESULT(0)
        },
        WM_ERASEBKGND => LRESULT(1),
        _ => unsafe { DefWindowProcW(hwnd, msg, wp, lp) },
    }
}
