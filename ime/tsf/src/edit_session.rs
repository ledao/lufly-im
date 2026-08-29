//! ITfEditSession 回调：TSF 的所有文档修改都必须发生在编辑会话内。
//! 三种会话：Start(建立 composition) / Update(刷新回显文本) / Commit(写最终文本并结束)。
use std::sync::{Arc, Mutex};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::UI::TextServices::*;

use crate::processor::Shared;

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

impl ITfEditSession_Impl for EditSession_Impl {
    fn DoEditSession(&self, ec: u32) -> Result<()> {
        let mut shared = self.shared.lock().unwrap();
        let tm = shared
            .thread_mgr
            .as_ref()
            .ok_or_else(|| Error::from_hresult(E_FAIL))?;
        // focus 的单位是 document manager, 再取其 base context
        let dim = unsafe { tm.GetFocus() }?;
        let ctx = unsafe { dim.GetBase() }?;

        match self.kind {
            SessionKind::Start => {
                let range = unsafe { ctx.GetStart(ec)? };
                let ctx_comp: ITfContextComposition = ctx.cast()?;
                let sink = shared
                    .composition_sink
                    .clone()
                    .ok_or_else(|| Error::from_hresult(E_FAIL))?;
                let composition = unsafe { ctx_comp.StartComposition(ec, &range, &sink)? };
                let text = utf16(shared.engine.input());
                unsafe { range.SetText(ec, 0, &text)? };
                shared.composition = Some(composition);
            }
            SessionKind::Update => {
                let text = utf16(shared.engine.input());
                if let Some(comp) = &shared.composition {
                    let range = unsafe { comp.GetRange()? };
                    unsafe { range.SetText(ec, 0, &text)? };
                }
            }
            SessionKind::Commit => {
                let text = std::mem::take(&mut shared.pending_commit);
                if let Some(comp) = shared.composition.take() {
                    let range = unsafe { comp.GetRange()? };
                    let wide = utf16(&text);
                    unsafe { range.SetText(ec, 0, &wide)? };
                    unsafe { comp.EndComposition(ec)? };
                } else if !text.is_empty() {
                    // 无 composition 时的兜底: 在插入点直接写文本
                    let range = unsafe { ctx.GetStart(ec)? };
                    let wide = utf16(&text);
                    unsafe { range.SetText(ec, 0, &wide)? };
                }
            }
        }
        Ok(())
    }
}
