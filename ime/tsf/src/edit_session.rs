//! ITfEditSession 回调：TSF 的所有文档修改都必须发生在编辑会话内。
//! 三种会话：Start(建立 composition) / Update(刷新回显文本) / Commit(写最终文本并结束)。
//! 回显文本与候选窗内容对齐 fcitx5 updateUI（预编辑 = 挂起字 + 编码）。
//! composition 管理模式对齐 rime/weasel WeaselTSF/Composition.cpp。
use std::mem::ManuallyDrop;
use std::sync::{Arc, Mutex};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::UI::TextServices::*;

use crate::processor::{Shared, PAGE_SIZE};

#[derive(Clone, Copy, PartialEq)]
pub enum SessionKind {
    Start,
    Update,
    Commit,
}

#[implement(ITfEditSession)]
pub struct EditSession {
    pub shared: Arc<Mutex<Shared>>,
    pub kind: SessionKind,
}

impl EditSession {
    pub fn new(shared: Arc<Mutex<Shared>>, kind: SessionKind) -> Self {
        Self { shared, kind }
    }
}

fn utf16(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

/// SetText 后把选区挪到 range 末尾（weasel CInsertTextEditSession 同款收尾；
/// 不做这步 selection 留在 composition 外，应用可能终止 composition）
unsafe fn collapse_and_select(ctx: &ITfContext, ec: u32, range: &ITfRange) -> Result<()> {
    unsafe {
        range.Collapse(ec, TF_ANCHOR_END)?;
        let mut sel = [TF_SELECTION::default(); 1];
        sel[0].range = ManuallyDrop::new(Some(range.clone()));
        sel[0].style.ase = TF_AE_NONE;
        sel[0].style.fInterimChar = FALSE;
        ctx.SetSelection(ec, &sel)?;
    }
    Ok(())
}

/// 刷新候选窗：贴光标显示当前页「词 剩余编码」，空候选时隐藏
fn update_cand_win(shared: &mut Shared, ec: u32, ctx: &ITfContext) {
    let st_page = shared.st.page;
    let buffer = shared.st.buffer.clone();
    let cands = shared.cands.clone();
    if buffer.is_empty() || cands.is_empty() {
        crate::log(&format!(
            "cand hide (buffer_len={} cands={})",
            buffer.len(),
            cands.len()
        ));
        shared.cand_win.hide();
        return;
    }

    // 光标矩形（composition 起始锚点 → 屏幕坐标；weasel 同款 START 锚）
    let caret = (|| -> Result<RECT> {
        let comp = shared.composition.as_ref().ok_or_else(|| Error::from_hresult(E_FAIL))?;
        let range = unsafe { comp.GetRange()? };
        unsafe { range.Collapse(ec, TF_ANCHOR_START)? };
        let view = unsafe { ctx.GetActiveView()? };
        let mut rect = RECT::default();
        let mut clipped = BOOL::default();
        unsafe { view.GetTextExt(ec, &range, &mut rect, &mut clipped)? };
        if rect.left == 0 && rect.top == 0 {
            return Err(Error::from_hresult(E_FAIL));
        }
        Ok(rect)
    })();
    let Ok(caret) = caret else {
        crate::log("cand hide (GetTextExt failed)");
        shared.cand_win.hide();
        return;
    };

    // 当前页条目: 三分段「序号. 词 剩余编码」（fcitx5 横排风格；已敲前缀不重复；
    // 分段独立样式——皮肤对齐 macOS 定稿，绘制在 cand.rs）
    let start = st_page * PAGE_SIZE;
    let mut items = Vec::with_capacity(PAGE_SIZE);
    for (i, (text, code)) in cands.iter().enumerate().skip(start).take(PAGE_SIZE) {
        let label = format!("{}.", i - start + 1);
        let mut suffix = String::new();
        if code.len() > buffer.len() && code.starts_with(&buffer) {
            suffix.push(' ');
            suffix.push_str(&code[buffer.len()..]);
        }
        items.push(crate::cand::CandItem {
            label,
            word: text.clone(),
            suffix,
            hl: i == start,
        });
    }
    crate::log(&format!("cand show: {} items, rect=({},{},{},{})", items.len(), caret.left, caret.top, caret.right, caret.bottom));
    shared.cand_win.show(items, caret);
}

impl ITfEditSession_Impl for EditSession_Impl {
    fn DoEditSession(&self, ec: u32) -> Result<()> {
        crate::ffi_guard("DoEditSession", || self.do_edit_session(ec))
    }
}

impl EditSession_Impl {
    fn do_edit_session(&self, ec: u32) -> Result<()> {
        let mut shared = self.shared.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        let tm = shared
            .thread_mgr
            .as_ref()
            .ok_or_else(|| Error::from_hresult(E_FAIL))?;
        // focus 的单位是 document manager, 再取其 base context
        let dim = unsafe { tm.GetFocus() }?;
        let ctx = unsafe { dim.GetBase() }?;

        match self.kind {
            SessionKind::Start => {
                // 对齐 weasel CStartCompositionEditSession：
                // 插入点 range 必须经 ITfInsertAtSelection 查询
                let insert: ITfInsertAtSelection = ctx.cast()?;
                let range = unsafe {
                    insert.InsertTextAtSelection(ec, TF_IAS_QUERYONLY, &[])?
                };
                let ctx_comp: ITfContextComposition = ctx.cast()?;
                let sink = shared
                    .composition_sink
                    .clone()
                    .ok_or_else(|| Error::from_hresult(E_FAIL))?;
                let composition = unsafe { ctx_comp.StartComposition(ec, &range, &sink)? };
                let text = utf16(&shared.preedit);
                unsafe {
                    range.SetText(ec, 0, &text)?;
                    collapse_and_select(&ctx, ec, &range)?;
                }
                shared.composition = Some(composition);
                crate::log(&format!("session start ok, preedit={:?}", shared.preedit));
                update_cand_win(&mut shared, ec, &ctx);
            }
            SessionKind::Update => {
                let text = utf16(&shared.preedit);
                if let Some(comp) = &shared.composition {
                    let range = unsafe { comp.GetRange()? };
                    unsafe {
                        range.SetText(ec, 0, &text)?;
                        collapse_and_select(&ctx, ec, &range)?;
                    }
                    crate::log(&format!("session update ok, preedit={:?}", shared.preedit));
                } else {
                    crate::log("session update: no composition!");
                }
                update_cand_win(&mut shared, ec, &ctx);
            }
            SessionKind::Commit => {
                let text = std::mem::take(&mut shared.pending_commit);
                if let Some(comp) = shared.composition.take() {
                    // 先 take 丢所有权再 End（weasel: EndComposition 会同步触发
                    // OnCompositionTerminated，不丢会被误判为外部终止）
                    let range = unsafe { comp.GetRange()? };
                    let wide = utf16(&text);
                    unsafe {
                        range.SetText(ec, 0, &wide)?;
                        collapse_and_select(&ctx, ec, &range)?;
                        comp.EndComposition(ec)?;
                    }
                    crate::log(&format!("session commit ok, text={:?}", text));
                } else if !text.is_empty() {
                    // 无 composition 时的兜底: 在当前选区直接写文本
                    let mut sels = [TF_SELECTION::default(); 1];
                    let mut fetched = 0u32;
                    unsafe { ctx.GetSelection(ec, TF_DEFAULT_SELECTION, &mut sels, &mut fetched)? };
                    if fetched > 0 {
                        // fetched>0 时 range 必有值（TSF 契约）；仍用 if let 防
                        // 意外形状 —— FFI 内 unwrap panic = 崩溃宿主进程
                        if let Some(range) =
                            ManuallyDrop::into_inner(std::mem::take(&mut sels[0].range))
                        {
                            let wide = utf16(&text);
                            unsafe {
                                range.SetText(ec, 0, &wide)?;
                                collapse_and_select(&ctx, ec, &range)?;
                            }
                        }
                    }
                    crate::log(&format!("session commit (no comp), text={:?}", text));
                }
                shared.cand_win.hide();
            }
        }
        Ok(())
    }
}
