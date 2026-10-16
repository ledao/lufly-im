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
use windows::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress};
use windows::Win32::UI::HiDpi::{
    GetDpiForMonitor, MDT_EFFECTIVE_DPI, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
};
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

// ---- 高 DPI：布局按光标所在显示器的有效 DPI 缩放（96dpi 基准值 × dpi/96）----

/// 当前绘制数据对应的 DPI（show() 写入，paint/hit_item 读取，保证同一坐标系）
static DATA_DPI: Mutex<u32> = Mutex::new(96);

/// 线程级 PMv2 切换是否可用（首次 enter() 判定）。
/// 不可用（Win10 1607 前老系统）时必须禁用 DPI 缩放：窗口仍在系统
/// 虚拟化渲染路径上（画进 96dpi 面再整体拉伸），此时再按显示器 DPI
/// 放大内容 = 双重缩放，窗口会过大。
static PMV2_OK: AtomicBool = AtomicBool::new(true);

/// 96dpi 基准值按显示器 DPI 缩放
fn sc(v: i32, dpi: u32) -> i32 {
    v * dpi as i32 / 96
}

/// 光标点所在显示器的有效 DPI（跟随系统缩放设置）。
/// PMv2 不可用时固定 96（见 PMV2_OK 注释）；取不到也按 96。
fn dpi_for_point(pt: POINT) -> u32 {
    if !PMV2_OK.load(Ordering::Relaxed) {
        return 96;
    }
    unsafe {
        let hmon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
        if hmon.is_invalid() {
            return 96;
        }
        let (mut dx, mut dy) = (0u32, 0u32);
        if GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI, &mut dx, &mut dy).is_ok() && dx > 0 {
            dx
        } else {
            96
        }
    }
}

/// 临时把当前线程切到 Per-Monitor V2 DPI 感知（Drop 还原）。
/// TIP 跑在宿主进程 UI 线程上，不能改进程级感知，只能线程级临时切换：
/// 候选窗的 GetTextExt 定位、量宽、SetWindowPos 必须同处物理像素坐标系，
/// 否则高 DPI 屏上坐标被虚拟化、窗口被系统拉伸（小/糊）。
/// Win10 1607 前无此 API（GetProcAddress 兜底）：老系统维持旧行为。
pub struct PmDpiGuard {
    old: Option<isize>,
}

impl PmDpiGuard {
    pub fn enter() -> Self {
        unsafe {
            // 返回值 = 切换前的旧上下文；NULL(0) = 切换失败（老系统无此 API、
            // 或上下文非法）——没切成就无需还原，drop 直接跳过。
            // 同时记入 PMV2_OK：失败时 dpi_for_point 固定 96，防双重缩放
            let old = GetProcAddress(GetModuleHandleW(w!("user32.dll")).unwrap_or_default(), s!("SetThreadDpiAwarenessContext"))
                .map(|f| {
                    let f: unsafe extern "system" fn(isize) -> isize = std::mem::transmute(f);
                    f(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2.0 as isize)
                })
                .filter(|old| *old != 0);
            PMV2_OK.store(old.is_some(), Ordering::Relaxed);
            Self { old }
        }
    }
}

impl Drop for PmDpiGuard {
    fn drop(&mut self) {
        let Some(old) = self.old else { return };
        unsafe {
            if let Some(f) = GetProcAddress(
                GetModuleHandleW(w!("user32.dll")).unwrap_or_default(),
                s!("SetThreadDpiAwarenessContext"),
            ) {
                let f: unsafe extern "system" fn(isize) -> isize = std::mem::transmute(f);
                f(old);
            }
        }
    }
}

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

/// HFONT 句柄存 isize（raw pointer 非 Send，不能直接放 static Mutex）。
/// 按 DPI 各缓存一枚：跨显示器拖动（DPI 变化）时删除重建。
static FONT_WORD: Mutex<(u32, isize)> = Mutex::new((96, 0));
static FONT_LABEL: Mutex<(u32, isize)> = Mutex::new((96, 0));
static FONT_SUFFIX: Mutex<(u32, isize)> = Mutex::new((96, 0));

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

/// 取 DPI 对应的缓存字体（slot: (dpi, 句柄)，base = 96dpi 基准字号）
fn cached_font(slot: &Mutex<(u32, isize)>, base: i32, dpi: u32) -> HFONT {
    let mut s = slot.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
    if s.0 != dpi || s.1 == 0 {
        if s.1 != 0 {
            unsafe {
                let _ = DeleteObject(HFONT(s.1 as *mut _).into());
            }
        }
        *s = (dpi, make_font(sc(base, dpi)).0 as isize);
    }
    HFONT(s.1 as *mut _)
}

fn font_word(dpi: u32) -> HFONT {
    cached_font(&FONT_WORD, 17, dpi)
}

fn font_label(dpi: u32) -> HFONT {
    cached_font(&FONT_LABEL, 13, dpi)
}

fn font_suffix(dpi: u32) -> HFONT {
    cached_font(&FONT_SUFFIX, 12, dpi)
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
            // 光标点所在显示器的有效 DPI；本次绘制/命中测试都按它缩放
            let dpi = dpi_for_point(POINT { x: caret.left, y: caret.top });
            *DATA_DPI.lock().unwrap_or_else(std::sync::PoisonError::into_inner) = dpi;

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
                    label_w: measure(font_label(dpi), &it.label),
                    word_w: measure(font_word(dpi), &it.word),
                    suffix_w: measure(font_suffix(dpi), &it.suffix),
                    label: it.label,
                    word: it.word,
                    suffix: it.suffix,
                    hl: it.hl,
                });
            }
            let (word_h, _) = text_metrics(hdc, font_word(dpi));
            let _ = ReleaseDC(Some(hwnd), hdc);

            // 行高 = 词字体高 + 基线富余 + 上下边距（对齐 macOS fittingSize）
            let width: i32 = rows
                .iter()
                .map(|r| r.label_w + r.word_w + r.suffix_w)
                .sum::<i32>()
                + sc(GAP, dpi) * (rows.len() as i32 - 1).max(0)
                + sc(PAD_X, dpi) * 2;
            let height = word_h + sc(BASELINE_EXTRA, dpi) + sc(VPAD, dpi) * 2;
            {
                let mut data = DATA.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
                *data = rows;
            }

            // 贴光标下方，放不下翻到上方，钳到工作区。
            // 已显示则钉住原位置：候选窗从出现起不随输入移动（对齐 fcitx5）
            let pinned = IsWindowVisible(hwnd).as_bool();
            let mut x = caret.left;
            let mut y = caret.bottom + sc(2, dpi); // 与光标的间隙也按 DPI 缩放
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
                    y = caret.top - height - sc(2, dpi);
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

    /// 销毁窗口（Deactivate 用）。只 hide 不够: 窗口存活期间系统仍会派发
    /// 消息到 wndproc，若此后 DLL 被卸载就是访问违例（虽已禁止卸载，
    /// Deactivate 仍应彻底收尾，不留无主窗口）
    pub fn destroy(&mut self) {
        if let Some(hwnd) = self.hwnd.take() {
            unsafe {
                let _ = DestroyWindow(hwnd);
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

/// 命中测试: 与绘制同款横排布局走一遍 x 偏移，返回命中候选的页内下标
fn hit_item(px: i32) -> Option<usize> {
    let data = DATA.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
    let dpi = *DATA_DPI.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
    let mut x = sc(PAD_X, dpi);
    for (i, r) in data.iter().enumerate() {
        let w = r.label_w + r.word_w + r.suffix_w;
        if px >= x && px < x + w {
            return Some(i);
        }
        x += w + sc(GAP, dpi);
    }
    None
}

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        // SampleIME 同款: 显式不激活。不能落到 DefWindowProc——它对可点击的
        // 弹窗可能走系统默认激活路径，在部分应用（TSF 锁/CUAS）里引发卡死
        WM_MOUSEACTIVATE => LRESULT(MA_NOACTIVATE as isize),
        // 触屏/UWP（Pointer 输入路径）同款不激活: 本 TIP 注册了 IMMERSIVESUPPORT，
        // 会加载进 UWP 应用，Pointer 激活同样不能落默认处理
        WM_POINTERACTIVATE => LRESULT(PA_NOACTIVATE as isize),
        // 鼠标消息全部自消化（SampleIME 同款，绝不透传 DefWindowProc）。
        // 点击候选 = 等价按数字键选词；点空白处仅吞掉
        WM_LBUTTONDOWN => {
            let px = ((lp.0 & 0xFFFF) as u16) as i16 as i32;
            if let Some(item) = hit_item(px) {
                crate::processor::cand_click(item);
            }
            LRESULT(0)
        }
        WM_LBUTTONUP | WM_RBUTTONDOWN | WM_RBUTTONUP | WM_MBUTTONDOWN | WM_MBUTTONUP => LRESULT(0),
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            let data = DATA.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
            let dpi = *DATA_DPI.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
            let mut rc_client = RECT::default();
            let _ = GetClientRect(hwnd, &mut rc_client);

            // 先填整窗底色（WM_ERASEBKGND 假装擦了，这里必须真擦，否则脏内存）
            let bg = CreateSolidBrush(COLOR_BG);
            let _ = FillRect(hdc, &rc_client, bg);
            let _ = DeleteObject(bg.into());

            let (_, word_asc) = text_metrics(hdc, font_word(dpi));
            let baseline = sc(VPAD, dpi) + sc(BASELINE_EXTRA, dpi) + word_asc;
            SetBkMode(hdc, TRANSPARENT);

            // 首位浅灰圆角底纹：覆盖整行高（上下到边内 1px）、左右越界 HL_OVERHANG
            // （对齐 macOS draw()，防边缘漏底）；RoundRect 配 NULL_PEN 只填不描。
            // RoundRect 用「当前选入 DC 的刷子」填充——hl_brush 必须 SelectObject，
            // 否则走 DC 默认 WHITE_BRUSH，白底上画白块（曾因此底纹不可见）
            let hl_brush = CreateSolidBrush(COLOR_HL);
            let old_pen = SelectObject(hdc, GetStockObject(NULL_PEN).into());
            let old_brush = SelectObject(hdc, hl_brush.into());
            let mut x = sc(PAD_X, dpi);
            for r in data.iter() {
                let w = r.label_w + r.word_w + r.suffix_w;
                if r.hl {
                    let _ = RoundRect(
                        hdc,
                        x - sc(HL_OVERHANG, dpi),
                        1,
                        x + w + sc(HL_OVERHANG, dpi),
                        rc_client.bottom - 1,
                        sc(HL_RADIUS, dpi) * 2,
                        sc(HL_RADIUS, dpi) * 2,
                    );
                }
                x += w + sc(GAP, dpi);
            }
            SelectObject(hdc, old_brush);
            SelectObject(hdc, old_pen);
            let _ = DeleteObject(hl_brush.into());

            // 三分段文字：基线对齐，序号（首位黑/其余浅灰）、词黑、剩码青绿
            let mut x = sc(PAD_X, dpi);
            for r in data.iter() {
                let (_, label_asc) = text_metrics(hdc, font_label(dpi));
                let (_, suffix_asc) = text_metrics(hdc, font_suffix(dpi));

                let old = SelectObject(hdc, font_label(dpi).into());
                SetTextColor(hdc, if r.hl { COLOR_WORD } else { COLOR_LABEL_DIM });
                let _ = TextOutW(hdc, x, baseline - label_asc, &r.label.encode_utf16().collect::<Vec<u16>>());
                SelectObject(hdc, font_word(dpi).into());
                SetTextColor(hdc, COLOR_WORD);
                let _ = TextOutW(hdc, x + r.label_w, baseline - word_asc, &r.word.encode_utf16().collect::<Vec<u16>>());
                if r.suffix_w > 0 {
                    SelectObject(hdc, font_suffix(dpi).into());
                    SetTextColor(hdc, COLOR_SUFFIX);
                    let _ = TextOutW(
                        hdc,
                        x + r.label_w + r.word_w,
                        baseline - suffix_asc,
                        &r.suffix.encode_utf16().collect::<Vec<u16>>(),
                    );
                }
                SelectObject(hdc, old);
                x += r.label_w + r.word_w + r.suffix_w + sc(GAP, dpi);
            }

            // Win10 无 DWM 圆角：自绘 1px 描边（Win11 由 DWM 系统描边，不叠加）
            if !DWM_ROUNDED.load(Ordering::Relaxed) {
                draw_frame(hdc, rc_client, dpi);
            }

            let _ = EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_ERASEBKGND => LRESULT(1),
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

/// 自绘方角描边（Win10 fallback），线宽随 DPI
unsafe fn draw_frame(hdc: HDC, rc: RECT, dpi: u32) {
    let lw = sc(1, dpi).max(1);
    let brush = CreateSolidBrush(COLOR_FRAME);
    let edges = [
        RECT { left: rc.left, top: rc.top, right: rc.right, bottom: rc.top + lw },
        RECT { left: rc.left, top: rc.bottom - lw, right: rc.right, bottom: rc.bottom },
        RECT { left: rc.left, top: rc.top, right: rc.left + lw, bottom: rc.bottom },
        RECT { left: rc.right - lw, top: rc.top, right: rc.right, bottom: rc.bottom },
    ];
    for e in edges {
        let _ = FillRect(hdc, &e, brush);
    }
    let _ = DeleteObject(brush.into());
}
