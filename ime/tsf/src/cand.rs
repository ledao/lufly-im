//! 候选窗 —— 置顶不抢焦点的 Win32 弹窗，贴光标横排显示当前页候选。
//!
//! 对齐 fcitx5 横排风格: 页大小 6、单行排列、首选蓝底白字高亮、
//! 每项「序号.词 剩余编码」、跟随文本光标位置。
#![allow(non_snake_case)]

use std::sync::Mutex;

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::*;

const CLASS_NAME: PCWSTR = w!("LuflyCandWnd");
const ROW_H: i32 = 28;
const PADDING: i32 = 5;
const GAP: i32 = 12; // 横排项间距

/// 当前窗内容（进程内单窗，绘制数据放这里）
pub struct CandData {
    /// (显示文本, 高亮, 量得宽度) 列表
    pub items: Vec<(String, bool, i32)>,
}

static DATA: Mutex<CandData> = Mutex::new(CandData { items: Vec::new() });

/// HFONT 句柄存 isize（raw pointer 非 Send，不能直接放 static Mutex）
static FONT: Mutex<isize> = Mutex::new(0);

fn font() -> HFONT {
    let mut f = FONT.lock().unwrap();
    if *f == 0 {
        unsafe {
            let h = CreateFontW(
                -17,
                0,
                0,
                0,
                FW_NORMAL.0 as i32,
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

fn ensure_class() -> bool {
    static DONE: std::sync::Once = std::sync::Once::new();
    let mut ok = true;
    DONE.call_once(|| unsafe {
        let hinstance = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let wc = WNDCLASSW {
            style: CS_SAVEBITS,
            lpfnWndProc: Some(wnd_proc),
            hInstance: hinstance.into(),
            hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(),
            // GetSysColor 返回 COLORREF（真颜色值）；COLOR_WINDOW 本身是索引，
            // 直接当颜色传会得到近黑色刷子（黑框根因）
            hbrBackground: CreateSolidBrush(COLORREF(GetSysColor(COLOR_WINDOW))),
            lpszClassName: CLASS_NAME,
            ..Default::default()
        };
        if RegisterClassW(&wc) == 0 {
            ok = false;
        }
    });
    ok
}

/// 候选窗句柄（进程内单窗，惰性创建）
pub struct CandWindow {
    hwnd: Option<HWND>,
}

impl CandWindow {
    pub fn new() -> Self {
        Self { hwnd: None }
    }

    fn ensure(&mut self) -> Option<HWND> {
        if !ensure_class() {
            return None;
        }
        if self.hwnd.map(|h| !h.is_invalid()).unwrap_or(false) {
            return self.hwnd;
        }
        unsafe {
            let hinstance = GetModuleHandleW(PCWSTR::null()).ok()?;
            let hwnd = CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                CLASS_NAME,
                w!(""),
                WS_POPUP,
                0,
                0,
                10,
                10,
                None,
                None,
                Some(hinstance.into()),
                None,
            )
            .ok()?;
            self.hwnd = Some(hwnd);
            Some(hwnd)
        }
    }

    /// 显示当前页候选并贴到光标矩形（caret 为屏幕坐标）。
    /// items: 已格式化的「序号.词 剩余编码」行（首项高亮）。
    pub fn show(&mut self, items: Vec<(String, bool)>, caret: RECT) {
        if items.is_empty() {
            self.hide();
            return;
        }
        let Some(hwnd) = self.ensure() else {
            return;
        };
        unsafe {
            // 量每个条目宽度，横排布局
            let hdc = GetDC(Some(hwnd));
            let old = SelectObject(hdc, font().into());
            let mut rows: Vec<(String, bool, i32)> = Vec::with_capacity(items.len());
            for (text, hl) in items {
                let mut size = SIZE::default();
                let wide: Vec<u16> = text.encode_utf16().collect();
                let _ = GetTextExtentPoint32W(hdc, &wide, &mut size);
                rows.push((text, hl, size.cx));
            }
            SelectObject(hdc, old);
            let _ = ReleaseDC(Some(hwnd), hdc);

            let n = rows.len() as i32;
            let content: i32 = rows.iter().map(|r| r.2).sum();
            let width = content + GAP * (n - 1) + PADDING * 2;
            let height = ROW_H + PADDING * 2;
            {
                let mut data = DATA.lock().unwrap();
                data.items = rows;
            }

            // 贴光标下方，放不下翻到上方，钳到工作区。
            // 已显示则钉住原位置：候选窗从出现起不随输入移动（对齐 fcitx5）
            let pinned = IsWindowVisible(hwnd).as_bool();
            let mut x = caret.left;
            let mut y = caret.bottom + 2;
            let mut mi = MONITORINFO {
                cbSize: std::mem::size_of::<MONITORINFO>() as u32,
                ..Default::default()
            };
            let pt = POINT {
                x: caret.left,
                y: caret.bottom,
            };
            let hmon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
            if !hmon.is_invalid() && GetMonitorInfoW(hmon, &mut mi).as_bool() {
                let wa = mi.rcWork;
                if x + width > wa.right {
                    x = wa.right - width;
                }
                if y + height > wa.bottom {
                    y = caret.top - height - 2;
                }
                x = x.max(wa.left);
                y = y.max(wa.top);
            }
            let (mut px, mut py) = (x, y);
            if pinned {
                // 钉住: 保留窗口当前位置，只按新内容调尺寸
                let mut rc = RECT::default();
                let _ = GetWindowRect(hwnd, &mut rc);
                px = rc.left;
                py = rc.top;
            }
            let _ = SetWindowPos(
                hwnd,
                Some(HWND_TOPMOST),
                px,
                py,
                width,
                height,
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            );
            let _ = InvalidateRect(Some(hwnd), None, false);
            let _ = UpdateWindow(hwnd);
        }
    }

    pub fn hide(&mut self) {
        if let Some(hwnd) = self.hwnd {
            unsafe {
                let _ = ShowWindow(hwnd, SW_HIDE);
            }
        }
    }
}

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            let data = DATA.lock().unwrap();
            // 先填整窗底色（WM_ERASEBKGND 假装擦了，这里必须真擦，否则脏内存）
            let bg = CreateSolidBrush(COLORREF(GetSysColor(COLOR_WINDOW)));
            let mut rc_client = RECT::default();
            let _ = GetClientRect(hwnd, &mut rc_client);
            let _ = FillRect(hdc, &rc_client, bg);
            let _ = DeleteObject(bg.into());
            let f = font();
            let old = SelectObject(hdc, f.into());
            SetBkMode(hdc, TRANSPARENT);
            let hl_brush = CreateSolidBrush(COLORREF(GetSysColor(COLOR_BTNFACE))); // 灰底
            let y = PADDING;
            let mut x = PADDING;
            for (text, hl, w) in data.items.iter() {
                if *hl {
                    let bg = RECT {
                        left: x - 3,
                        right: x + w + 3,
                        top: 2,
                        bottom: ROW_H + PADDING,
                    };
                    FillRect(hdc, &bg, hl_brush);
                }
                SetTextColor(hdc, COLORREF(0x000000)); // 统一黑字
                let wide: Vec<u16> = text.encode_utf16().collect();
                let _ = TextOutW(hdc, x, y, &wide);
                x += w + GAP;
            }
            let _ = DeleteObject(hl_brush.into());
            SelectObject(hdc, old);
            let _ = EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_ERASEBKGND => LRESULT(1),
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}
