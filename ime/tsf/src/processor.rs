//! TIP 核心：ITfTextInputProcessor + ITfKeyEventSink + ITfCompositionSink
//!
//! 按键流: OnKeyDown → 引擎状态机 → 编辑会话
//!   - commit  → 会话中写最终文本并结束 composition
//!   - 编码非空 → 无 composition 则建立、有则刷新回显
//!   - 退格删空 → 结束 composition 清除回显
use std::sync::{Arc, Mutex};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::TextServices::*;

use lufly_engine::Engine;

use crate::edit_session::{EditSession, SessionKind};

/// 线程共享状态（TIP 与各编辑会话共用）
pub struct Shared {
    pub thread_mgr: Option<ITfThreadMgr>,
    pub client_id: u32,
    pub composition: Option<ITfComposition>,
    pub composition_sink: Option<ITfCompositionSink>,
    pub engine: Engine,
    pub pending_commit: String,
}

#[implement(ITfTextInputProcessor, ITfKeyEventSink, ITfCompositionSink)]
pub struct LuflyTsf {
    pub shared: Arc<Mutex<Shared>>,
}

impl LuflyTsf {
    pub fn new() -> Self {
        static DICT: &[u8] = include_bytes!("../../data/xiaolu_lu_lu.bin");
        let engine = Engine::load(DICT).expect("embedded dict must be valid");
        Self {
            shared: Arc::new(Mutex::new(Shared {
                thread_mgr: None,
                client_id: 0,
                composition: None,
                composition_sink: None,
                engine,
                pending_commit: String::new(),
            })),
        }
    }

    fn request_session(&self, kind: SessionKind) -> Result<()> {
        let shared = self.shared.lock().unwrap();
        let tm = shared
            .thread_mgr
            .as_ref()
            .ok_or_else(|| Error::from_hresult(E_FAIL))?;
        let dim = unsafe { tm.GetFocus() }?;
        let ctx = unsafe { dim.GetBase() }?;
        let session: ITfEditSession = EditSession::new(self.shared.clone(), kind).into();
        let hr = unsafe { ctx.RequestEditSession(shared.client_id, &session, TF_ES_READWRITE)? };
        if hr.is_ok() {
            Ok(())
        } else {
            Err(Error::from_hresult(hr))
        }
    }
}

impl ITfTextInputProcessor_Impl for LuflyTsf_Impl {
    fn Activate(&self, ptim: Ref<'_, ITfThreadMgr>, tid: u32) -> Result<()> {
        let tm = ptim
            .as_ref()
            .ok_or_else(|| Error::from_hresult(E_INVALIDARG))?
            .clone();

        let sink: ITfCompositionSink = self.to_interface();
        let key_sink: ITfKeyEventSink = self.to_interface();
        {
            let mut shared = self.shared.lock().unwrap();
            shared.thread_mgr = Some(tm.clone());
            shared.client_id = tid;
            shared.composition_sink = Some(sink);
        }

        unsafe {
            let keystroke: ITfKeystrokeMgr = tm.cast()?;
            keystroke.AdviseKeyEventSink(tid, &key_sink, true)?;
        }
        Ok(())
    }

    fn Deactivate(&self) -> Result<()> {
        let mut shared = self.shared.lock().unwrap();
        if let Some(tm) = &shared.thread_mgr {
            unsafe {
                let keystroke: ITfKeystrokeMgr = tm.cast()?;
                let _ = keystroke.UnadviseKeyEventSink(shared.client_id);
            }
        }
        shared.thread_mgr = None;
        shared.composition = None;
        shared.engine.reset();
        Ok(())
    }
}

impl ITfKeyEventSink_Impl for LuflyTsf_Impl {
    fn OnSetFocus(&self, _pfocused: BOOL) -> Result<()> {
        Ok(())
    }

    fn OnPreservedKey(&self, _pic: Ref<'_, ITfContext>, _rguid: *const GUID) -> Result<BOOL> {
        Ok(FALSE)
    }

    fn OnTestKeyDown(
        &self,
        _pic: Ref<'_, ITfContext>,
        _wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        // 不预占按键，由 OnKeyDown 决定是否吞键
        Ok(FALSE)
    }

    fn OnKeyDown(
        &self,
        _pic: Ref<'_, ITfContext>,
        wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        let vk = VIRTUAL_KEY(wparam.0 as u16);
        let has_input = !self.shared.lock().unwrap().engine.is_empty();

        let key_char = match vk {
            VK_SPACE => Some(' '),
            VK_BACK => Some('\u{8}'),
            VK_ESCAPE => Some('\u{1b}'),
            k if (0x30..=0x39).contains(&(k.0 as u32)) => {
                // 数字键: 有编码时是选词键(1..9), 否则透传
                if has_input {
                    Some((b'1' + (k.0 as u8 - 0x30) - 1) as char)
                } else {
                    None
                }
            }
            k if (0x41..=0x5A).contains(&(k.0 as u32)) => {
                Some((b'a' + (k.0 as u8 - b'A')) as char)
            }
            _ => None,
        };

        let Some(c) = key_char else {
            return Ok(FALSE);
        };

        let (commit, was_composing, input_after) = {
            let mut shared = self.shared.lock().unwrap();
            let commit = shared.engine.key(c);
            let composing = shared.composition.is_some();
            let input = shared.engine.input().to_string();
            (commit, composing, input)
        };

        if commit.is_some() || (was_composing && input_after.is_empty()) {
            // 上屏(或退格删空 → 写空文本收尾清除回显)
            {
                let mut shared = self.shared.lock().unwrap();
                shared.pending_commit = commit.unwrap_or_default();
            }
            self.request_session(SessionKind::Commit)?;
        } else if !input_after.is_empty() {
            let is_composing = self.shared.lock().unwrap().composition.is_some();
            self.request_session(if is_composing {
                SessionKind::Update
            } else {
                SessionKind::Start
            })?;
        }
        Ok(TRUE)
    }

    fn OnTestKeyUp(
        &self,
        _pic: Ref<'_, ITfContext>,
        _wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        Ok(FALSE)
    }

    fn OnKeyUp(
        &self,
        _pic: Ref<'_, ITfContext>,
        _wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        Ok(FALSE)
    }
}

impl ITfCompositionSink_Impl for LuflyTsf_Impl {
    fn OnCompositionTerminated(
        &self,
        _ecwrite: u32,
        _pcomposition: Ref<'_, ITfComposition>,
    ) -> Result<()> {
        // composition 被外部终止(用户点击别处等) → 丢弃输入缓冲
        let mut shared = self.shared.lock().unwrap();
        shared.composition = None;
        shared.engine.reset();
        Ok(())
    }
}
