//! 候选窗 —— 置顶不抢焦点的 Win32 弹窗，贴光标横排显示当前页候选。
//!
//! 皮肤对齐 macOS 版定稿（CandidateWindow.swift，用户逐项裁定）：
//! 白底 + 圆角描边窗，首位浅灰圆角底纹（非实心高亮块），
//! 每项三分段「序号.词 剩余编码」——序号 13pt（首位黑/其余浅灰）、
//! 词 17pt 黑、剩余编码 12pt 品牌青绿，基线对齐。
//! Win11 用 DWM 系统圆角+描边，Win10 退化为自绘方角描边；阴影走 CS_DROPSHADOW。
#![allow(non_snake_case)]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Dwm::{
    DwmSetWindowAttribute, DWMWA_WINDOW_CORNER_PREFERENCE, DWM_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND,
};
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::*;

const CLASS_NAME: PCWSTR = w!("LuflyCandWnd");

// 布局常量对齐 macOS CandidateView（pt 值按 96dpi 当 px 用）
const PAD_X: i32 = 10; // 左右内边距
const GAP: i32 = 12; // 横排项间距
const VPAD: i32 = 5; // 上下内边距
const BASELINE_EXTRA: i32 = 2; // 基线相对 (VPAD + ascent) 再抬的量
const HL_OVERHANG: i32 = 6; // 首位底纹左右越界
const HL_RADIUS: i32 = 4; // 首位底纹圆角

// 配色（macOS 亮色定稿）；COLORREF = 0x00BBGGRR
const COLOR_BG: COLORREF = COLORREF(0x00FFFFFF); // 白底
const COLOR_HL: COLORREF = COLORREF(0x00ECECEC); // 首位底纹：systemGray 15% 叠白底
const COLOR_WORD: COLORREF = COLORREF(0x00000000); // 词：黑
const COLOR_LABEL_DIM: COLORREF = COLORREF(0x00868686); // 非首位序号：secondaryLabel 近似
const COLOR_SUFFIX: COLORREF = COLORREF(0x00698005); // 剩余编码品牌青绿 rgb(5,128,105)
const COLOR_FRAME: COLORREF = COLORREF(0x00CCCCCC); // Win10 无 DWM 圆角时的自绘描边

/// 单条候选（edit_session 构造，三分段独立样式）
pub struct CandItem {
    pub label: String,
    pub word: String,
    pub suffix: String,
    pub hl: bool,
}

/// 量好宽度的行（绘制数据）
struct CandRow {
    label: String,
    word: String,
    suffix: String,
    label_w: i32,
    word_w: i32,
    suffix_w: i32,
    hl: bool,
}

static DATA: Mutex<Vec<CandRow>> = Mutex::new(Vec::new());

/// DWM 圆角是否生效（决定 WM_PAINT 要不要自绘描边）
static DWM_ROUNDED: AtomicBool = AtomicBool::new(false);

/// HFONT 句柄存 isize（raw pointer 非 Send，不能直接放 static Mutex）
static FONT_WORD: Mutex<isize> = Mutex::new(0);
static FONT_LABEL: Mutex<isize> = Mutex::new(0);
static FONT_SUFFIX: Mutex<isize> = Mutex::new(0);

fn make_font(size: i32) -> HFONT {
    unsafe {
        CreateFontW(
            -size,
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
        )
    }
}

fn font_word() -> HFONT {
    let mut f = FONT_WORD.lock().unwrap();
    if *f == 0 {
        *f = make_font(17).0 as isize;
    }
    HFONT(*f as *mut _)
}

fn font_label() -> HFONT {
    let mut f = FONT_LABEL.lock().unwrap();
    if *f == 0 {
        *f = make_font(13).0 as isize;
    }
    HFONT(*f as *mut _)
}

fn font_suffix() -> HFONT {
    let mut f = FONT_SUFFIX.lock().unwrap();
    if *f == 0 {
        *f = make_font(12).0 as isize;
    }
    HFONT(*f as *mut _)
}

/// Win11 DWM 系统圆角（自带系统描边）；Win10/失败返回 false，走自绘方角描边
fn round_corners(hwnd: HWND) -> bool {
    unsafe {
        DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            &DWMWCP_ROUND as *const _ as *const core::ffi::c_void,
            std::mem::size_of::<DWM_WINDOW_CORNER_PREFERENCE>() as u32,
        )
        .is_ok()
    }
}

fn ensure_class() -> bool {
    static DONE: std::sync::Once = std::sync::Once::new();
    let mut ok = true;
    DONE.call_once(|| unsafe {
        let hinstance = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let wc = WNDCLASSW {
            style: CS_SAVEBITS | CS_DROPSHADOW,
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
            DWM_ROUNDED.store(round_corners(hwnd), Ordering::Relaxed);
            self.hwnd = Some(hwnd);
            Some(hwnd)
        }
    }

    /// 显示当前页候选并贴到光标矩形（caret 为屏幕坐标）。
    /// items: 三分段「序号. 词 剩余编码」（首项 hl=true 浅灰底纹）。
    pub fn show(&mut self, items: Vec<CandItem>, caret: RECT) {
        if items.is_empty() {
            self.hide();
            return;
        }
        let Some(hwnd) = self.ensure() else {
            return;
        };
        unsafe {
            // 量每个分段宽度（各用各的字体），横排布局
            let hdc = GetDC(Some(hwnd));
            let mut rows: Vec<CandRow> = Vec::with_capacity(items.len());
            for it in items {
                let measure = |f: HFONT, s: &str| -> i32 {
                    let old = SelectObject(hdc, f.into());
                    let mut size = SIZE::default();
                    let wide: Vec<u16> = s.encode_utf16().collect();
                    let _ = GetTextExtentPoint32W(hdc, &wide, &mut size);
                    SelectObject(hdc, old);
                    size.cx
                };
                rows.push(CandRow {
                    label_w: measure(font_label(), &it.label),
                    word_w: measure(font_word(), &it.word),
                    suffix_w: measure(font_suffix(), &it.suffix),
                    label: it.label,
                    word: it.word,
                    suffix: it.suffix,
                    hl: it.hl,
                });
            }
            let (word_h, _) = text_metrics(hdc, font_word());
            let _ = ReleaseDC(Some(hwnd), hdc);

            // 行高 = 词字体高 + 基线富余 + 上下边距（对齐 macOS fittingSize）
            let width: i32 = rows
                .iter()
                .map(|r| r.label_w + r.word_w + r.suffix_w)
                .sum::<i32>()
                + GAP * (rows.len() as i32 - 1).max(0)
                + PAD_X * 2;
            let height = word_h + BASELINE_EXTRA + VPAD * 2;
            {
                let mut data = DATA.lock().unwrap();
                *data = rows;
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

/// 选入字体并取 TEXTMETRIC (height, ascent)
unsafe fn text_metrics(hdc: HDC, f: HFONT) -> (i32, i32) {
    let old = SelectObject(hdc, f.into());
    let mut tm = TEXTMETRICW::default();
    let _ = GetTextMetricsW(hdc, &mut tm);
    SelectObject(hdc, old);
    (tm.tmHeight, tm.tmAscent)
}

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            let data = DATA.lock().unwrap();
            let mut rc_client = RECT::default();
            let _ = GetClientRect(hwnd, &mut rc_client);

            // 先填整窗底色（WM_ERASEBKGND 假装擦了，这里必须真擦，否则脏内存）
            let bg = CreateSolidBrush(COLOR_BG);
            let _ = FillRect(hdc, &rc_client, bg);
            let _ = DeleteObject(bg.into());

            let (_, word_asc) = text_metrics(hdc, font_word());
            let baseline = VPAD + BASELINE_EXTRA + word_asc;
            SetBkMode(hdc, TRANSPARENT);

            // 首位浅灰圆角底纹：覆盖整行高（上下到边内 1px）、左右越界 HL_OVERHANG
            // （对齐 macOS draw()，防边缘漏底）；RoundRect 配 NULL_PEN 只填不描
            let hl_brush = CreateSolidBrush(COLOR_HL);
            let old_pen = SelectObject(hdc, GetStockObject(NULL_PEN).into());
            let mut x = PAD_X;
            for r in data.iter() {
                let w = r.label_w + r.word_w + r.suffix_w;
                if r.hl {
                    let _ = RoundRect(
                        hdc,
                        x - HL_OVERHANG,
                        1,
                        x + w + HL_OVERHANG,
                        rc_client.bottom - 1,
                        HL_RADIUS * 2,
                        HL_RADIUS * 2,
                    );
                }
                x += w + GAP;
            }
            SelectObject(hdc, old_pen);
            let _ = DeleteObject(hl_brush.into());

            // 三分段文字：基线对齐，序号（首位黑/其余浅灰）、词黑、剩码青绿
            let mut x = PAD_X;
            for r in data.iter() {
                let (_, label_asc) = text_metrics(hdc, font_label());
                let (_, suffix_asc) = text_metrics(hdc, font_suffix());

                let old = SelectObject(hdc, font_label().into());
                SetTextColor(hdc, if r.hl { COLOR_WORD } else { COLOR_LABEL_DIM });
                let _ = TextOutW(hdc, x, baseline - label_asc, &r.label.encode_utf16().collect::<Vec<u16>>());
                SelectObject(hdc, font_word().into());
                SetTextColor(hdc, COLOR_WORD);
                let _ = TextOutW(hdc, x + r.label_w, baseline - word_asc, &r.word.encode_utf16().collect::<Vec<u16>>());
                if r.suffix_w > 0 {
                    SelectObject(hdc, font_suffix().into());
                    SetTextColor(hdc, COLOR_SUFFIX);
                    let _ = TextOutW(
                        hdc,
                        x + r.label_w + r.word_w,
                        baseline - suffix_asc,
                        &r.suffix.encode_utf16().collect::<Vec<u16>>(),
                    );
                }
                SelectObject(hdc, old);
                x += r.label_w + r.word_w + r.suffix_w + GAP;
            }

            // Win10 无 DWM 圆角：自绘 1px 描边（Win11 由 DWM 系统描边，不叠加）
            if !DWM_ROUNDED.load(Ordering::Relaxed) {
                draw_frame(hdc, rc_client);
            }

            let _ = EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_ERASEBKGND => LRESULT(1),
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

/// 1px 方角描边（Win10 fallback）
unsafe fn draw_frame(hdc: HDC, rc: RECT) {
    let brush = CreateSolidBrush(COLOR_FRAME);
    let edges = [
        RECT { left: rc.left, top: rc.top, right: rc.right, bottom: rc.top + 1 },
        RECT { left: rc.left, top: rc.bottom - 1, right: rc.right, bottom: rc.bottom },
        RECT { left: rc.left, top: rc.top, right: rc.left + 1, bottom: rc.bottom },
        RECT { left: rc.right - 1, top: rc.top, right: rc.right, bottom: rc.bottom },
    ];
    for e in edges {
        let _ = FillRect(hdc, &e, brush);
    }
    let _ = DeleteObject(brush.into());
}
