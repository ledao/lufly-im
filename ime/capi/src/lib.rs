//! 小鹭音形引擎 C ABI 封装。
//!
//! 供 C/C++ 前端（fcitx5 addon 等）静态链接。所有返回的字符串指针均为
//! 内部缓存借用：**在下一次对该 engine 句柄的任意调用之前有效**。
//!
//! 典型按键流程:
//!   1. `lufly_key(handle, ch)` → 返回上屏文本（可能为 NULL）
//!   2. `lufly_refresh(handle)`  → 刷新预编辑/候选缓存
//!   3. 读 `lufly_input` / `lufly_candidate_count` / `lufly_candidate_*`
//!
//! 线程模型: 句柄非线程安全，调用方需自行串行化（fcitx5 单线程回调即可）。

use std::char;
use std::ffi::CString;
use std::os::raw::{c_char, c_int};

use lufly_engine::Engine;

pub struct LuflyEngine {
    engine: Engine,
    /// 上屏文本缓存（`lufly_key` 返回的指针指向这里）
    commit: Option<CString>,
    /// 预编辑串缓存
    input: CString,
    /// 候选缓存: (文本, 是否完全命中)
    cands: Vec<(CString, bool)>,
}

impl LuflyEngine {
    fn refresh(&mut self) {
        self.input = CString::new(self.engine.input().as_bytes())
            .unwrap_or_else(|_| CString::new("").unwrap());
        self.cands = self
            .engine
            .candidates()
            .into_iter()
            .map(|c| {
                (
                    CString::new(c.text.as_bytes()).unwrap_or_default(),
                    c.exact,
                )
            })
            .collect();
    }
}

/// 加载二进制码表。失败返回 NULL。
///
/// # Safety
/// `dict` 须指向至少 `len` 字节可读内存。
#[no_mangle]
pub unsafe extern "C" fn lufly_new(dict: *const u8, len: usize) -> *mut LuflyEngine {
    if dict.is_null() {
        return std::ptr::null_mut();
    }
    let bytes = std::slice::from_raw_parts(dict, len);
    match Engine::load(bytes) {
        Ok(engine) => {
            let mut e = Box::new(LuflyEngine {
                engine,
                commit: None,
                input: CString::new("").unwrap(),
                cands: Vec::new(),
            });
            e.refresh();
            Box::into_raw(e)
        }
        Err(_) => std::ptr::null_mut(),
    }
}

/// # Safety
/// `handle` 须为 `lufly_new` 返回值，且只能 free 一次。
#[no_mangle]
pub unsafe extern "C" fn lufly_free(handle: *mut LuflyEngine) {
    if !handle.is_null() {
        drop(Box::from_raw(handle));
    }
}

/// 喂入一个按键（Unicode 码位）。返回需上屏的文本，无上屏返回 NULL。
///
/// # Safety
/// `handle` 须有效。返回指针在下次调用前有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_key(handle: *mut LuflyEngine, ch: u32) -> *const c_char {
    let e = &mut *handle;
    let c = match char::from_u32(ch) {
        Some(c) => c,
        None => return std::ptr::null(),
    };
    e.commit = e
        .engine
        .key(c)
        .and_then(|s| CString::new(s.as_bytes()).ok());
    e.refresh();
    e.commit
        .as_ref()
        .map(|s| s.as_ptr())
        .unwrap_or(std::ptr::null())
}

/// 清空编码缓冲（composition 被终止）。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_reset(handle: *mut LuflyEngine) {
    (*handle).engine.reset();
    (*handle).refresh();
}

/// 刷新预编辑/候选缓存（按键或 reset 之后调用）。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_refresh(handle: *mut LuflyEngine) {
    (*handle).refresh();
}

/// 当前编码缓冲。空缓冲时按键应透传为英文。
///
/// # Safety
/// `handle` 须有效。返回指针在下次调用前有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_input(handle: *mut LuflyEngine) -> *const c_char {
    (*handle).input.as_ptr()
}

/// 候选数量。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_candidate_count(handle: *mut LuflyEngine) -> c_int {
    (*handle).cands.len() as c_int
}

/// 第 `idx` 个候选文本（0 起，越界返回 NULL）。
///
/// # Safety
/// `handle` 须有效。返回指针在下次调用前有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_candidate_text(handle: *mut LuflyEngine, idx: c_int) -> *const c_char {
    let e = &mut *handle;
    e.cands
        .get(idx as usize)
        .map(|(s, _)| s.as_ptr())
        .unwrap_or(std::ptr::null())
}

/// 第 `idx` 个候选是否编码完全命中（非前缀扩展）。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_candidate_exact(handle: *mut LuflyEngine, idx: c_int) -> c_int {
    let e = &mut *handle;
    match e.cands.get(idx as usize) {
        Some((_, exact)) => *exact as c_int,
        None => 0,
    }
}
