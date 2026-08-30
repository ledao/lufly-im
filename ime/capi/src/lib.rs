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
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use std::path::PathBuf;

use lufly_engine::Engine;

/// 每累计 N 次学习自动把用户词典写回磁盘（原子替换写，开销 ~KB 级）
const USER_FLUSH_INTERVAL: u32 = 64;

pub struct LuflyEngine {
    engine: Engine,
    /// 上屏文本缓存（`lufly_key` 返回的指针指向这里）
    commit: Option<CString>,
    /// 预编辑串缓存
    input: CString,
    /// 候选缓存: (文本, 全码, 是否完全命中)
    cands: Vec<(CString, CString, bool)>,
    /// 用户词典路径（`lufly_user_open` 设置；未设置则学习不落盘）
    user_path: Option<PathBuf>,
    /// 上次落盘时的 user_ops 基线
    saved_ops: u32,
    /// 推导编码缓存（`lufly_derive_word` 返回的指针指向这里）
    derive: Option<CString>,
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
                    CString::new(c.code.as_bytes()).unwrap_or_default(),
                    c.exact,
                )
            })
            .collect();
    }

    /// 用户词典落盘（`force=false` 时有变更才写；写临时文件后原子 rename）。
    fn flush_user(&mut self, force: bool) -> bool {
        let Some(path) = self.user_path.as_ref() else {
            return false;
        };
        if !force && self.engine.user_ops() == self.saved_ops {
            return false;
        }
        let bytes = self.engine.save_user();
        let tmp = path.with_extension("txt.tmp");
        let parent = path.parent().map(|p| p.to_path_buf()).unwrap_or_default();
        let ok = std::fs::create_dir_all(parent).is_ok()
            && std::fs::write(&tmp, &bytes).is_ok()
            && std::fs::rename(&tmp, path).is_ok();
        if ok {
            self.saved_ops = self.engine.user_ops();
        }
        ok
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
                user_path: None,
                saved_ops: 0,
                derive: None,
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
        .map(|(s, _, _)| s.as_ptr())
        .unwrap_or(std::ptr::null())
}

/// 第 `idx` 个候选的全码（0 起，越界返回 NULL）。
///
/// # Safety
/// `handle` 须有效。返回指针在下次调用前有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_candidate_code(handle: *mut LuflyEngine, idx: c_int) -> *const c_char {
    let e = &mut *handle;
    e.cands
        .get(idx as usize)
        .map(|(_, c, _)| c.as_ptr())
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
        Some((_, _, exact)) => *exact as c_int,
        None => 0,
    }
}

/// 打开用户词典文件（存在则加载）。之后 [`lufly_learn`] 每累计
/// 64 次自动落盘到该路径（写临时文件 + 原子 rename）。
///
/// # Safety
/// `handle` 须有效；`path` 须为合法 C 字符串。
#[no_mangle]
pub unsafe extern "C" fn lufly_user_open(handle: *mut LuflyEngine, path: *const c_char) {
    if handle.is_null() || path.is_null() {
        return;
    }
    let e = &mut *handle;
    let Ok(p) = CStr::from_ptr(path).to_str() else {
        return;
    };
    e.user_path = Some(PathBuf::from(p));
    if let Ok(bytes) = std::fs::read(p) {
        e.engine.load_user(&bytes);
    }
    e.saved_ops = e.engine.user_ops();
}

/// 热重载用户词典（外部进程如 ojc 弹窗管线追加了自定义词）:
/// 合并磁盘最新内容进内存（内存未落盘的学习增量保留），随即全量
/// 原子落盘（顺带去重、把 helper 追加的行规范化）。返回 1 表示有变化。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_user_reload(handle: *mut LuflyEngine) -> c_int {
    if handle.is_null() {
        return 0;
    }
    let e = &mut *handle;
    let Some(path) = e.user_path.as_ref() else {
        return 0;
    };
    let Ok(bytes) = std::fs::read(path) else {
        return 0;
    };
    e.engine.load_user(&bytes);
    e.saved_ops = e.engine.user_ops();
    e.flush_user(true) as c_int
}

/// 强制落盘用户词典（无变更或未打开时什么都不做）。返回 1 表示写了文件。
///
/// # Safety
/// `handle` 须有效。
#[no_mangle]
pub unsafe extern "C" fn lufly_user_flush(handle: *mut LuflyEngine) -> c_int {
    if handle.is_null() {
        return 0;
    }
    (*handle).flush_user(false) as c_int
}

/// 记录一次真实上屏: 用户以 `code` 选定了 `text`（词频自学习）。
/// 累计 64 次自动落盘。
///
/// # Safety
/// `handle`/`code`/`text` 须为有效指针。
#[no_mangle]
pub unsafe extern "C" fn lufly_learn(
    handle: *mut LuflyEngine,
    code: *const c_char,
    text: *const c_char,
) {
    if handle.is_null() || code.is_null() || text.is_null() {
        return;
    }
    let e = &mut *handle;
    let (Ok(code), Ok(text)) = (
        CStr::from_ptr(code).to_str(),
        CStr::from_ptr(text).to_str(),
    ) else {
        return;
    };
    e.engine.learn(code, text);
    if e.engine.user_ops().wrapping_sub(e.saved_ops) >= USER_FLUSH_INTERVAL {
        e.flush_user(false);
    }
}

/// 推导一个词的默认全码（ojc 加词用: 单字=4码全码；多字=双拼+首末形码各1）。
/// 失败返回 NULL。返回指针为内部缓存借用，下次调用前有效。
///
/// # Safety
/// `handle`/`word` 须为有效指针。
#[no_mangle]
pub unsafe extern "C" fn lufly_derive_word(handle: *mut LuflyEngine, word: *const c_char) -> *const c_char {
    if handle.is_null() || word.is_null() {
        return std::ptr::null();
    }
    let e = &mut *handle;
    let Ok(word) = CStr::from_ptr(word).to_str() else {
        return std::ptr::null();
    };
    e.derive = e
        .engine
        .derive_word_code(word)
        .ok()
        .and_then(|s| CString::new(s.as_bytes()).ok());
    e.derive
        .as_ref()
        .map(|s| s.as_ptr())
        .unwrap_or(std::ptr::null())
}

/// 添加自定义词（ojc 加词）: 词条立即生效并强制落盘。成功返回 1。
///
/// # Safety
/// `handle`/`code`/`text` 须为有效指针。
#[no_mangle]
pub unsafe extern "C" fn lufly_user_add_word(
    handle: *mut LuflyEngine,
    code: *const c_char,
    text: *const c_char,
) -> c_int {
    if handle.is_null() || code.is_null() || text.is_null() {
        return 0;
    }
    let e = &mut *handle;
    let (Ok(code), Ok(text)) = (
        CStr::from_ptr(code).to_str(),
        CStr::from_ptr(text).to_str(),
    ) else {
        return 0;
    };
    if e.engine.add_user_word(code, text).is_err() {
        return 0;
    }
    e.flush_user(true) as c_int
}
