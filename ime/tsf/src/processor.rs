//! TIP 核心：ITfTextInputProcessor + ITfKeyEventSink + ITfCompositionSink
//!
//! 按键状态机与 fcitx5 前端（lufly.cpp）逐功能对齐：
//!   - 顶功挂起（全码唯一不立即上屏，下一键顶出/空格确认）
//!   - 候选窗（页大小 5、1-5 与 ;'[] 选词、PageUp/Down/-/=Tab/Shift+Tab 翻页）
//!   - 标点全角化 + 上下文半角（3.14 / hello.）+ Ctrl+0 强制半角
//!   - Shift 单击切中英文（编码中先原样上屏字母）
//!   - ` 拼音反查（fuzhu.bin）
//!   - Shift+4/Shift+\ 选次选候选、抬键补 。/，
//!   - ojc 加词（候选窗内选字→编码，全程无弹窗）
//!   - 连续全码打字自动造词（≥2 字成词）
//!   - 词频自学习 + 用户词典（%APPDATA%\lufly\user_dict.txt，64 次落盘 + 热重载）
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime};

/// 按键分类结果（在持锁段内计算，放锁后执行编辑会话）
enum Act {
    /// 无（键透传）
    Pass,
    /// 吃掉键，不产生任何 UI 变化
    Eat,
    /// 吃掉键并写文本（文本可空=清屏收尾）
    Commit(String),
    /// 吃掉键并显示/刷新回显与候选窗
    Compose,
    /// 吃掉键并写文本后继续显示回显（顶功顶出等）
    CommitAndCompose(String),
    /// 写文本后放行原按键（英文上屏/顶出首选后原字符自然插入）
    CommitThenPass(String),
}

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::TextServices::*;

use lufly_engine::Engine;

use crate::cand::CandWindow;
use crate::edit_session::{EditSession, SessionKind};
use crate::state::{chinese_punct, State};

/// 候选页大小: 对齐 fcitx5 横排风格，数字 1-6 对应本页 6 个候选。
pub const PAGE_SIZE: usize = 6;

/// 用户词典落盘间隔（与 capi USER_FLUSH_INTERVAL 一致）
const USER_FLUSH_INTERVAL: u32 = 64;

/// 线程共享状态（TIP 与各编辑会话共用）
pub struct Shared {
    pub thread_mgr: Option<ITfThreadMgr>,
    pub client_id: u32,
    pub composition: Option<ITfComposition>,
    pub composition_sink: Option<ITfCompositionSink>,
    pub engine: Option<Engine>,
    /// 拼音反查码表（懒加载，无热更新）
    pub rev: Option<Engine>,
    pub st: State,
    /// Commit 会话要写文本（含清屏收尾的空串）
    pub pending_commit: String,
    /// 组词回显文本（Start/Update 会话读取）
    pub preedit: String,
    /// 候选快照: (文本, 全码)，供候选窗显示「词 剩余编码」
    pub cands: Vec<(String, String)>,
    pub cand_win: CandWindow,
    /// 用户词典路径；None = 学习只在内存
    pub user_path: Option<PathBuf>,
    /// 上次落盘时的 user_ops 基线
    pub saved_ops: u32,
    /// 用户词典热重载: 节流 + mtime
    pub last_user_check: Option<Instant>,
    pub user_mtime: Option<SystemTime>,
    /// 语言栏托盘项（logo + 中/EN 模式按钮），Deactivate 时 RemoveItem
    pub langbar: Vec<ITfLangBarItem>,
}

impl Shared {

    /// 主码表懒加载: Activate 里后台预载，首次按键兜底同步加载，
    /// 避免 DllGetClassObject/Activate 同步解析 43MB 阻塞输入切换
    pub fn ensure_engine(&mut self) -> bool {
        if self.engine.is_some() {
            return true;
        }
        // 先取后台预载结果
        if let Some(mut e) = crate::take_preload() {
            self.attach_user_dict(&mut e);
            self.engine = Some(e);
            return true;
        }
        static MAIN_DICT: &[u8] = include_bytes!("../../data/xiaolu_he_he.bin");
        match Engine::load(MAIN_DICT) {
            Ok(mut e) => {
                self.attach_user_dict(&mut e);
                self.engine = Some(e);
                true
            }
            Err(_) => false,
        }
    }

    fn attach_user_dict(&mut self, e: &mut Engine) {
        if let Some(p) = &self.user_path {
            if let Ok(b) = std::fs::read(p) {
                e.load_user(&b);
            }
            self.user_mtime = std::fs::metadata(p).ok().and_then(|m| m.modified().ok());
        }
        self.saved_ops = 0;
    }

    /// 主引擎（调用前须 ensure_engine 成功）
    fn main_engine(&mut self) -> &mut Engine {
        self.engine.as_mut().unwrap()
    }

    /// 当前按键上下文应使用的引擎（反查=rev，普通=主引擎）
    pub fn active_engine(&mut self) -> &mut Engine {
        if self.st.reverse && self.rev.is_some() {
            self.rev.as_mut().unwrap()
        } else {
            self.engine.as_mut().unwrap()
        }
    }

    /// 把编码重放进引擎（恢复该会话状态，切换反查/撤销挂起后用）
    fn replay(&mut self, buffer: &str) {
        let eng = self.active_engine();
        eng.reset();
        for c in buffer.chars() {
            eng.key(c);
        }
    }

    /// 引擎 input 与前端 buffer 不一致时重放（反查切换后等）
    fn sync_engine(&mut self) {
        let buffer = self.st.buffer.clone();
        let eng_input = self.active_engine().input().to_string();
        if eng_input != buffer {
            self.replay(&buffer);
        }
    }

    /// 自动造词: 用户连续以 4 键全码打字上屏时，把这些字拼成自动词。
    /// 例: 连续全码打「乐」「乐」→ 造出 lelemb → 乐乐。断链 = 任何非
    /// 「单字+4码」的上屏。词长上限 4 字。
    fn note_auto_commit(&mut self, code: &str, text: &str) {
        if code.len() != 4 || text.chars().count() != 1 {
            self.st.auto_buf.clear();
            return;
        }
        self.st.auto_buf.push_str(text);
        let n = self.st.auto_buf.chars().count();
        if n < 2 {
            return;
        }
        if n > 4 {
            self.st.auto_buf.clear();
            return;
        }
        let word = self.st.auto_buf.clone();
        if let Ok(d) = self.main_engine().derive_word_code(&word) {
            if self.main_engine().add_user_word(&d, &word).is_ok() {
                self.maybe_flush_user();
            }
        }
    }

    /// 用户词典落盘（有变更且够 64 次才写；写临时文件后原子 rename）
    fn maybe_flush_user(&mut self) {
        self.flush_user(false);
    }

    pub fn flush_user(&mut self, force: bool) -> bool {
        let Some(path) = self.user_path.clone() else {
            return false;
        };
        if !force && self.main_engine().user_ops().wrapping_sub(self.saved_ops) < USER_FLUSH_INTERVAL {
            return false;
        }
        let bytes = self.main_engine().save_user();
        let tmp = path.with_extension("txt.tmp");
        let ok = std::fs::create_dir_all(path.parent().unwrap_or(Path::new("."))).is_ok()
            && std::fs::write(&tmp, &bytes).is_ok()
            && std::fs::rename(&tmp, &path).is_ok();
        if ok {
            self.saved_ops = self.main_engine().user_ops();
        }
        ok
    }

    /// 用户词典热重载: ojc/其他端追加词后文件变化时合并（1s 节流）
    fn check_user_reload(&mut self) {
        let Some(path) = self.user_path.clone() else {
            return;
        };
        if self.last_user_check.is_some_and(|t| t.elapsed().as_secs() < 1) {
            return;
        }
        self.last_user_check = Some(Instant::now());
        let Ok(meta) = std::fs::metadata(&path) else {
            return;
        };
        let mtime = meta.modified().ok();
        if mtime == self.user_mtime {
            return;
        }
        self.user_mtime = mtime;
        if let Ok(bytes) = std::fs::read(&path) {
            self.main_engine().load_user(&bytes);
            self.saved_ops = self.main_engine().user_ops();
        }
    }

    /// 懒加载拼音反查码表
    pub fn ensure_rev(&mut self) -> bool {
        if self.rev.is_some() {
            return true;
        }
        static FUZHU: &[u8] = include_bytes!("../../data/xiaolu_fuzhu.bin");
        self.rev = Engine::load(FUZHU).ok();
        self.rev.is_some()
    }

    /// ojc 加词·选字: 选中候选追加进词槽，留在选字阶段继续选下一个字
    fn append_add_word(&mut self, text: &str) {
        self.st.add_word.push_str(text);
        self.st.buffer.clear();
        self.st.reverse = false;
        self.st.add_stage = 1;
        self.replay("");
    }

    /// 选字完成 → 编码阶段: derive 固定查主码表（反查态的 eng 是 fuzhu）
    fn finish_add_word(&mut self) {
        let word = self.st.add_word.clone();
        self.st.add_code = self.main_engine().derive_word_code(&word).unwrap_or_default();
        self.st.buffer.clear();
        self.st.reverse = false;
        self.st.add_stage = 2;
        self.replay("");
    }
}

/// 组词回显文本（对齐 fcitx5 updateUI 的 preedit 组装）
fn build_preedit(st: &State, eng_input: &str) -> String {
    if st.add_stage == 2 {
        return format!("加词:{} · 编码:{}", st.add_word, st.add_code);
    }
    if st.buffer.is_empty() {
        let mut s = String::new();
        if st.add_stage == 1 {
            s.push_str(&format!("加词:{}", st.add_word));
        }
        s.push_str(&st.pending);
        return s;
    }
    let mut s = String::new();
    if st.add_stage == 1 {
        s.push_str(&format!("加词:{}·", st.add_word));
    }
    if st.reverse {
        s.push('`');
    }
    s.push_str(&st.pending);
    s.push_str(eng_input);
    s
}

#[implement(ITfTextInputProcessor, ITfKeyEventSink, ITfCompositionSink)]
pub struct LuflyTsf {
    pub shared: Arc<Mutex<Shared>>,
}

impl LuflyTsf {
    pub fn new() -> Self {
        // 用户词典: %APPDATA%\lufly\user_dict.txt（存在则加载）
        let user_path = std::env::var("APPDATA")
            .ok()
            .map(|app| PathBuf::from(app).join("lufly").join("user_dict.txt"));
        let shared = Shared {
            thread_mgr: None,
            client_id: 0,
            composition: None,
            composition_sink: None,
            engine: None, // 懒加载（ensure_engine），避免构造时阻塞输入切换
            rev: None,
            st: State::default(),
            pending_commit: String::new(),
            preedit: String::new(),
            cands: Vec::new(),
            cand_win: CandWindow::new(),
            user_path,
            saved_ops: 0,
            last_user_check: None,
            user_mtime: None,
            langbar: Vec::new(),
        };

        Self {
            shared: Arc::new(Mutex::new(shared)),
        }
    }

    /// 按键处理主入口（镜像 fcitx5 keyEvent；返回 TRUE=吃键）
    fn handle_key(&self, vk: VIRTUAL_KEY) -> BOOL {
        let shift = unsafe { GetKeyState(VK_SHIFT.0 as i32) as u16 } & 0x8000 != 0;
        let ctrl = unsafe { GetKeyState(VK_CONTROL.0 as i32) as u16 } & 0x8000 != 0;
        let alt = unsafe { GetKeyState(VK_MENU.0 as i32) as u16 } & 0x8000 != 0;

        let is_shift = vk == VK_SHIFT || vk == VK_LSHIFT || vk == VK_RSHIFT;

        let act = {
            let mut s = self.shared.lock().unwrap();
            compute_action(&mut s, vk, shift, ctrl, alt, is_shift)
        };
        self.exec_act(act)
    }

    fn request_session_kind(&self, text: &str, kind: SessionKind) -> Result<()> {
        {
            let mut s = self.shared.lock().unwrap();
            s.pending_commit = text.to_owned();
            // 预计算回显（Commit 会话也会按需隐藏候选窗）
            let input = s.active_engine().input().to_string();
            s.preedit = build_preedit(&s.st, &input);
        }
        self.request_session(kind)
    }

    fn request_compose(&self) -> Result<()> {
        // Start 或 Update 由 composition 是否存在决定
        let kind = {
            let mut s = self.shared.lock().unwrap();
            let input = s.active_engine().input().to_string();
            s.preedit = build_preedit(&s.st, &input);
            // 候选快照（含反查引擎），供候选窗显示「词 剩余编码」
            s.cands = if s.st.buffer.is_empty() {
                Vec::new()
            } else {
                s.active_engine()
                    .candidates()
                    .iter()
                    .map(|c| (c.text.clone(), c.code.clone()))
                    .collect()
            };
            if s.composition.is_some() {
                SessionKind::Update
            } else {
                SessionKind::Start
            }
        };
        self.request_session(kind)
    }

    fn request_session(&self, kind: SessionKind) -> Result<()> {
        // 注意: 不能持锁调 RequestEditSession —— 同步编辑会话回调里会再次
        // 加锁（DoEditSession），否则死锁。
        let (tm, cid) = {
            let s = self.shared.lock().unwrap();
            let tm = s
                .thread_mgr
                .as_ref()
                .ok_or_else(|| Error::from_hresult(E_FAIL))?
                .clone();
            (tm, s.client_id)
        };
        let dim = unsafe { tm.GetFocus() }?;
        let ctx = unsafe { dim.GetBase() }?;
        let session: ITfEditSession = EditSession::new(self.shared.clone(), kind).into();
        // 对齐 weasel: ASYNCDONTCARE|READWRITE（纯 READWRITE 无同步语义，
        // 部分应用会拒绝请求）
        let hr = unsafe { ctx.RequestEditSession(cid, &session, TF_ES_ASYNCDONTCARE | TF_ES_READWRITE)? };
        if hr.is_ok() {
            Ok(())
        } else {
            crate::log(&format!("RequestEditSession failed: 0x{:08X}", hr.0 as u32));
            Err(Error::from_hresult(hr))
        }
    }
}

/// 中文模式下 IME 可能处理的键（Test 阶段据此声明接管）
fn wants_key(vk: VIRTUAL_KEY) -> bool {
    match vk.0 {
        // 字母 / 数字 / OEM 标点
        0x41..=0x5A | 0x30..=0x39 | 0xBA..=0xC0 | 0xDB..=0xDE => true,
        // Space Back Return Tab Esc Capital PgUp PgDn
        0x20 | 0x08 | 0x0D | 0x09 | 0x1B | 0x14 | 0x21 | 0x22 => true,
        // Shift（单击切中英）
        0x10 | 0xA0 | 0xA1 => true,
        _ => false,
    }
}

/// 持锁段内的按键决策（返回动作；对齐 lufly.cpp keyEvent 的分支顺序）
fn compute_action(
    s: &mut Shared,
    vk: VIRTUAL_KEY,
    shift: bool,
    ctrl: bool,
    alt: bool,
    is_shift: bool,
) -> Act {


    // ---- 抬键逻辑在 OnKeyUp（Shift 单击 / $| 待补标点），这里只管按下 ----

    // 修饰键: Shift 记录单击（空编码时用于切换中英），其余透传
    if is_shift {
        s.st.shift_armed = true;
        return Act::Pass;
    }
    // 任何其他按下键解除 Shift 单击武装、作废待补标点
    s.st.shift_armed = false;
    s.st.pending_punct = None;

    // 带组合修饰键的按键一律透传；Ctrl+0 例外: 切换标点强制半角
    if ctrl {
        if vk.0 == 0x30 && !shift {
            s.st.ascii_punct = !s.st.ascii_punct;
            return Act::Eat;
        }
        return Act::Pass;
    }
    if alt {
        return Act::Pass;
    }
    // 英文模式: 一律透传，Shift 单击切回中文（OnKeyUp）
    if s.st.ascii {
        return Act::Pass;
    }

    // 主码表懒加载（首次按键兜底；正常已被 Activate 后台线程预载）
    if !s.ensure_engine() {
        return Act::Pass;
    }
    // 用户词典热重载（升级码表/其他端加词后自动生效）
    s.check_user_reload();

    let ch = match key_char(vk, shift) {
        Some(c) => c,
        // 非字符键（F 键/方向键等）: 不消费、不破坏缓冲
        None => return Act::Pass,
    };
    // 字母只有不按 Shift 时才是编码键（Shift+字母 = 大写英文，透传）
    let is_letter = !shift && ch.is_ascii_lowercase();

    // ---- ojc 加词·编码阶段 (stage2): 编辑编码，回车/空格确认 ----
    if s.st.add_stage == 2 {
        return match ch {
            '\u{1b}' => {
                s.st.cancel_add_word();
                Act::Commit(String::new())
            }
            '\u{8}' => {
                if s.st.add_code.is_empty() {
                    s.st.add_stage = 1; // 码删空: 退回选词阶段
                } else {
                    s.st.add_code.pop();
                }
                Act::Compose
            }
            '\n' | ' ' => {
                if s.st.add_code.chars().count() < 2 {
                    return Act::Compose; // 编码太短: 等待继续输入
                }
                let (code, word) = (s.st.add_code.clone(), s.st.add_word.clone());
                if s.main_engine().add_user_word(&code, &word).is_ok() {
                    s.flush_user(false);
                    s.st.cancel_add_word();
                    s.st.last_cls = 0;
                    Act::Commit(word) // 保存成功: 词直接上屏（立即可用）
                } else {
                    s.st.cancel_add_word();
                    Act::Commit(String::new())
                }
            }
            c if c.is_ascii_lowercase() => {
                s.st.add_code.push(c);
                Act::Compose
            }
            _ => Act::Eat, // 加词编辑中吞掉其他简单键，防误触
        };
    }

    // ---- ` 进入拼音反查（对齐 rime reverse_lookup prefix）----
    if !s.st.reverse && ch == '`' && s.st.buffer.is_empty() {
        if s.ensure_rev() {
            s.st.reverse = true;
            return Act::Compose;
        }
        return Act::Pass; // 码表缺失: ` 透传
    }

    // 反查切换后引擎与 buffer 不同步时重放（TSF 引擎常驻，等价 fcitx5 replay）
    s.sync_engine();

    // 候选快照（含全码，供选词与显示「词 剩余编码」）
    let cands: Vec<(String, String)> = s
        .active_engine()
        .candidates()
        .iter()
        .map(|c| (c.text.clone(), c.code.clone()))
        .collect();
    let n_cands = cands.len();
    let has_menu = !s.st.buffer.is_empty() && n_cands > 0;
    let miss = !has_menu && !s.st.buffer.is_empty();
    let page = s.st.page;
    let has_next_page = (page + 1) * PAGE_SIZE < n_cands;
    let has_prev_page = page > 0;

    // ---- 翻页: PageUp/Down、- 前翻 = 后翻、Tab 后翻 Shift+Tab 前翻 ----
    if !s.st.buffer.is_empty() {
        let tab = vk == VK_TAB;
        if tab && miss {
            return Act::Pass; // miss 透传（英文输入中，不清屏）
        }
        let page_prev = ch == '-' || (tab && shift) || vk == VK_PRIOR;
        let page_next = ch == '=' || (tab && !shift) || vk == VK_NEXT;
        if (page_prev || page_next) && has_menu {
            if page_next && has_next_page {
                s.st.page += 1;
                return Act::Compose;
            }
            if page_prev && has_prev_page {
                s.st.page -= 1;
                return Act::Compose;
            }
            // - = Tab 到头/单页: 消费不动作（防半角 - = 漏进文档）；
            // PageUp/PageDown 保持透传（非简单键，应用自处理）
            if vk != VK_PRIOR && vk != VK_NEXT {
                return Act::Eat;
            }
        }
        // Caps_Lock: 清空缓冲（rime send Escape）
        if vk == VK_CAPITAL {
            s.st.buffer.clear();
            s.st.reverse = false;
            s.st.cancel_add_word();
            return Act::Commit(String::new());
        }
    }

    // ---- 选词: 数字 1-5 与 ; ' [ ] = 第2/3/4/5（对齐 rime key_binder）----
    let mut sel: i32 = -1;
    let mut digit_sel = false;
    if !shift && matches!(ch, '1'..='6') {
        sel = (ch as u8 - b'1') as i32;
        digit_sel = true;
    } else if ch == ';' {
        sel = 1;
    } else if ch == '\'' {
        sel = 2;
    } else if ch == '[' {
        sel = 3;
    } else if ch == ']' {
        sel = 4;
    }
    if sel >= 0 && !s.st.buffer.is_empty() && has_menu {
        let idx = sel as usize + page * PAGE_SIZE;
        if idx < n_cands {
            let text = cands[idx].0.clone();
            if s.st.add_stage == 1 {
                // 加词·选字阶段: 选中的字进词槽，继续选下一个字
                s.append_add_word(&text);
                return Act::Compose;
            }
            let code = s.st.buffer.clone();
            s.active_engine().learn(&code, &text);
            s.note_auto_commit(&code, &text);
            s.st.last_cls = 0;
            s.st.buffer.clear();
            s.st.reverse = false;
            s.st.page = 0;
            return Act::Commit(text);
        }
        if digit_sel {
            return Act::Eat; // 数字越界: 消费不动作
        }
        // ;'[] 越界: 落到标点顶字
    }

    // ---- $ / |: 选次选候选，抬键补 。 / ，（对齐 rime dollar/bar 绑定）----
    if (ch == '$' || ch == '|') && !s.st.buffer.is_empty() && has_menu {
        let idx = 1 + page * PAGE_SIZE;
        if idx < n_cands {
            let text = cands[idx].0.clone();
            if s.st.add_stage == 1 {
                s.append_add_word(&text);
                return Act::Compose;
            }
            let code = s.st.buffer.clone();
            s.active_engine().learn(&code, &text);
            s.note_auto_commit(&code, &text);
            s.st.last_cls = 0;
            s.st.buffer.clear();
            s.st.reverse = false;
            s.st.page = 0;
            s.st.pending_punct = Some(if ch == '$' { "。" } else { "，" });
            return Act::Commit(text);
        }
    }

    // ---- 空格: 上屏首选 / 确认挂起字 ----
    if ch == ' ' {
        if s.st.buffer.is_empty() {
            if !s.st.pending.is_empty() {
                let (code, text) =
                    (s.st.pending_code.clone(), s.st.pending.clone());
                if s.st.add_stage == 1 {
                    s.st.add_word.push_str(&text); // 加词中: 挂起字进词槽
                } else {
                    s.main_engine().learn(&code, &text);
                    s.note_auto_commit(&code, &text);
                    s.maybe_flush_user();
                }
                s.st.pending.clear();
                s.st.pending_code.clear();
                s.st.last_cls = 0;
                return if s.st.add_stage == 1 {
                    Act::Compose
                } else {
                    Act::Commit(text)
                };
            }
            if s.st.reverse {
                s.st.reverse = false; // 反查空缓冲: 空格退出反查
                return Act::Commit(String::new());
            }
            return Act::Pass; // 空缓冲透传
        }
        if s.st.add_stage == 1 && has_menu {
            let text = cands[0].0.clone();
            // 加词·选字阶段: 空格选中首选进词槽，不提交
            s.append_add_word(&text);
            return Act::Compose;
        }
        // 挂起字随空格一并上屏（顶功后接空格 = 确认挂起字 + 首选）
        let mut out = String::new();
        if !s.st.pending.is_empty() {
            let (pcode, ptext) = (s.st.pending_code.clone(), s.st.pending.clone());
            s.note_auto_commit(&pcode, &ptext);
            out.push_str(&ptext);
            s.st.pending.clear();
            s.st.pending_code.clear();
        }
        if has_menu {
            let text = cands[0].0.clone();
            let code = s.st.buffer.clone();
            s.active_engine().learn(&code, &text);
            s.note_auto_commit(&code, &text);
            out.push_str(&text);
        }
        s.st.last_cls = 0;
        s.st.buffer.clear();
        s.st.reverse = false;
        s.st.page = 0;
        // 有候选 = 挂起字+首选；无候选 = 仅挂起字（或空 = 清屏收尾）
        return Act::Commit(out);
    }

    // ---- 回车 ----
    if vk == VK_RETURN {
        if s.st.add_stage == 1 {
            if !s.st.buffer.is_empty() {
                // 编码中回车 = 反悔（字母上屏退出）
                s.st.cancel_add_word();
                let letters = std::mem::take(&mut s.st.buffer);
                s.st.last_cls = 2;
                s.st.reverse = false;
                return Act::Commit(letters);
            }
            // 空缓冲回车 = 完成选字（挂起字一并入槽）→ 编码阶段
            if !s.st.pending.is_empty() {
                let t = s.st.pending.clone();
                s.st.add_word.push_str(&t);
                s.st.pending.clear();
                s.st.pending_code.clear();
            }
            if s.st.add_word.is_empty() {
                s.st.cancel_add_word(); // 一个字都没选: 视为取消
            } else {
                s.finish_add_word();
            }
            s.st.reverse = false;
            return Act::Compose;
        }
        if s.st.buffer.is_empty() {
            if !s.st.pending.is_empty() {
                let t = std::mem::take(&mut s.st.pending);
                s.st.pending_code.clear();
                s.st.auto_buf.clear(); // 回车换行 = 断链
                return Act::CommitAndCompose(t); // 挂起字先送出，Enter 本身透传
            }
            return Act::Pass; // 换行照常
        }
        s.st.cancel_add_word(); // 回车上屏字母 = 反悔退出加词
        // 挂起字随回车一并上屏，编码原样跟上
        let mut out = String::new();
        if !s.st.pending.is_empty() {
            let (pcode, ptext) = (s.st.pending_code.clone(), s.st.pending.clone());
            s.note_auto_commit(&pcode, &ptext);
            out.push_str(&ptext);
            s.st.pending.clear();
            s.st.pending_code.clear();
        }
        out.push_str(&std::mem::take(&mut s.st.buffer));
        s.st.last_cls = 2;
        s.st.reverse = false;
        return Act::Commit(out);
    }

    // ---- 退格 ----
    if vk == VK_BACK {
        if s.st.buffer.is_empty() {
            if !s.st.pending.is_empty() {
                // 撤销顶功挂起: 恢复原编码供继续编辑
                s.st.buffer = s.st.pending_code.clone();
                s.st.pending.clear();
                s.st.pending_code.clear();
                let b = s.st.buffer.clone();
                s.replay(&b);
                return Act::Compose;
            }
            if s.st.reverse {
                s.st.reverse = false; // 退过 ` 本身: 退出反查
                return Act::Commit(String::new());
            }
            if s.st.add_stage == 1 {
                if !s.st.add_word.is_empty() {
                    // 删词槽最后一个字（String::pop 按 UTF-8 边界弹出）
                    s.st.add_word.pop();
                } else {
                    s.st.cancel_add_word(); // 退无可退: 退出加词
                }
                return Act::Compose;
            }
            return Act::Pass;
        }
        s.st.buffer.pop();
        let b = s.st.buffer.clone();
        s.replay(&b);
        return Act::Compose;
    }

    // ---- Esc ----
    if vk == VK_ESCAPE {
        if s.st.buffer.is_empty() {
            if s.st.add_stage == 1 {
                s.st.cancel_add_word(); // 选字中 Esc: 取消加词
                return Act::Commit(String::new());
            }
            if s.st.reverse {
                s.st.reverse = false;
                return Act::Commit(String::new());
            }
            return Act::Pass;
        }
        s.st.buffer.clear();
        s.st.reverse = false;
        s.st.cancel_add_word();
        return Act::Commit(String::new());
    }

    // ---- 字母: 进编码缓冲（含顶功挂起逻辑）----
    if is_letter {
        let mut pushed_out = String::new();
        if !s.st.pending.is_empty() {
            // 顶功: 下一字词的首键把挂起字顶出（快打全程不用空格）。
            // 挂起字必须真正写入文档（Commit），不能只留在回显里
            let (code, text) = (s.st.pending_code.clone(), s.st.pending.clone());
            if s.st.add_stage == 1 {
                s.st.add_word.push_str(&text); // 加词中顶进词槽而非上屏
            } else {
                s.note_auto_commit(&code, &text);
                pushed_out = text;
            }
            s.st.pending.clear();
            s.st.pending_code.clear();
            s.st.last_cls = 0;
        }
        let prev = s.st.buffer.clone();
        let auto = {
            let eng = s.active_engine();
            eng.key(ch) // 全码唯一(6/8/10…偶数)时返回 Some → 挂起
        };
        s.st.buffer = s.active_engine().input().to_string();
        if let Some(text) = auto {
            s.st.pending = text;
            s.st.pending_code = format!("{}{}", prev, ch);
        }
        // ojc: 命令引导符 o + jc(加词声母) → 进入加词·选词阶段
        if s.st.buffer == "ojc" {
            s.st.buffer.clear();
            s.st.reverse = false;
            s.st.add_stage = 1;
            s.replay("");
        }
        if pushed_out.is_empty() {
            return Act::Compose;
        }
        // 顶出的字上屏，同时新编码开新 composition
        return Act::CommitAndCompose(pushed_out);
    }

    // ---- 标点: 中文全角化（对齐 rime punctuator half_shape）----
    // 上下文半角: 前一字符是数字/英文、miss 携带英文、或 Ctrl+0 强制时，
    // 标点不映射、原样透传（编码中仍先顶字）—— 3.14 / hello. / english,
    if s.st.add_stage == 1 {
        s.st.add_stage = 0; // 标点退出加词（视为反悔），照常处理标点
    }
    let composing = !s.st.buffer.is_empty();
    let half_punct = s.st.ascii_punct || s.st.last_cls != 0 || miss;
    let punct = if half_punct {
        None
    } else {
        chinese_punct(ch, &mut s.st.dq_open, &mut s.st.sq_open).map(str::to_owned)
    };
    if let Some(p) = punct {
        let mut out = String::new();
        if !s.st.pending.is_empty() {
            // 挂起字随标点顶出
            let (code, text) = (s.st.pending_code.clone(), s.st.pending.clone());
            s.note_auto_commit(&code, &text);
            out.push_str(&text);
            s.st.pending.clear();
            s.st.pending_code.clear();
        }
        if miss {
            out.push_str(&s.st.buffer); // 英文原样上屏
        } else if composing && has_menu {
            let text = cands[0].0.clone();
            let code = s.st.buffer.clone();
            s.active_engine().learn(&code, &text);
            s.note_auto_commit(&code, &text);
            out.push_str(&text);
        }
        s.st.buffer.clear();
        s.st.reverse = false;
        s.st.page = 0;
        out.push_str(&p);
        s.st.auto_buf.clear(); // 标点 = 断链
        s.st.last_cls = 0;
        return Act::Commit(out);
    }
    // 未映射的简单键（含按上下文放行的半角标点）:
    // 加词选字阶段吞掉（不上屏英文/符号，退格或 Esc 处理）；miss 时透传
    // 不清屏（英文继续）；编码中顶出首选后放行原字符。
    if composing {
        if s.st.add_stage == 1 {
            return Act::Eat;
        }
        if miss {
            let mut letters = std::mem::take(&mut s.st.buffer);
            // 挂起字随英文一并上屏
            if !s.st.pending.is_empty() {
                let (pcode, ptext) = (s.st.pending_code.clone(), s.st.pending.clone());
                s.note_auto_commit(&pcode, &ptext);
                letters.insert_str(0, &ptext);
                s.st.pending.clear();
                s.st.pending_code.clear();
            }
            s.st.reverse = false;
            s.st.last_cls = 2;
            s.st.auto_buf.clear(); // 英文 = 断链
            s.replay(""); // 同步清引擎缓冲
            return Act::CommitThenPass(letters); // 英文上屏，原字符放行
        }
        let mut text = cands[0].0.clone();
        let code = s.st.buffer.clone();
        s.active_engine().learn(&code, &text);
        s.note_auto_commit(&code, &text);
        // 挂起字随首选一并顶出
        if !s.st.pending.is_empty() {
            let (pcode, ptext) = (s.st.pending_code.clone(), s.st.pending.clone());
            s.note_auto_commit(&pcode, &ptext);
            text.insert_str(0, &ptext);
            s.st.pending.clear();
            s.st.pending_code.clear();
        }
        s.st.buffer.clear();
        s.st.reverse = false;
        s.st.last_cls = 0;
        s.st.auto_buf.clear(); // 透传的原字符插在字间 = 断链
        s.replay("");
        return Act::CommitThenPass(text); // 顶出首选，原字符放行
    }
    // 空缓冲透传的数字: 记录上下文（3.14 / 1,000 后续标点保持半角）
    if ch.is_ascii_digit() && !shift {
        s.st.last_cls = 1;
    }
    Act::Pass
}

/// VK → 实际字符（含 Shift 变体），对齐 fcitx5 keysym 语义。
/// 返回 None: 非字符键或 Shift+字母（大写英文，透传）。
fn key_char(vk: VIRTUAL_KEY, shift: bool) -> Option<char> {
    let v = vk.0;
    match v {
        // 控制键: 状态机（空格上屏/回车反悔/退格/翻页/Esc/Caps）依赖这些映射。
        // 缺了它们会在 key_char 处直接 Pass，后面的分支全部不可达
        0x20 => Some(' '),            // Space: 上屏首选
        0x0D => Some('\n'),           // Return
        0x08 => Some('\u{8}'),        // Backspace
        0x09 => Some('\t'),           // Tab: 翻页
        0x1B => Some('\u{1b}'),       // Esc
        0x14 => Some('\u{14}'),       // Capital: 清缓冲
        0x21 => Some('\u{21}'),       // PgUp: 前翻
        0x22 => Some('\u{22}'),       // PgDn: 后翻
        // 字母: 小写进编码；Shift+字母 = 大写英文 → 返回大写字符，
        // 走"未映射简单键"分支（编码中顶字后放行，对齐 fcitx5）
        0x41..=0x5A => {
            let c = (b'a' + ((v - 0x41) as u8)) as char;
            Some(if shift { c.to_ascii_uppercase() } else { c })
        }
        // 数字（Shift = 符号）
        0x30..=0x39 => {
            let d = (v - 0x30) as u8;
            Some(if shift {
                match d {
                    1 => '!', 2 => '@', 3 => '#', 4 => '$', 5 => '%',
                    6 => '^', 7 => '&', 8 => '*', 9 => '(', 0 => ')',
                    _ => return None,
                }
            } else {
                (b'0' + d) as char
            })
        }
        // OEM 标点键
        0xBA => Some(if shift { ':' } else { ';' }),
        0xBB => Some(if shift { '+' } else { '=' }),
        0xBC => Some(if shift { '<' } else { ',' }),
        0xBD => Some(if shift { '_' } else { '-' }),
        0xBE => Some(if shift { '>' } else { '.' }),
        0xBF => Some(if shift { '?' } else { '/' }),
        0xC0 => Some(if shift { '~' } else { '`' }),
        0xDB => Some(if shift { '{' } else { '[' }),
        0xDC => Some(if shift { '|' } else { '\\' }),
        0xDD => Some(if shift { '}' } else { ']' }),
        0xDE => Some(if shift { '"' } else { '\'' }),
        _ => None,
    }
}

impl LuflyTsf {
    /// 执行决策（按键按下/抬起共用）
    fn exec_act(&self, act: Act) -> BOOL {
        match act {
            Act::Pass => BOOL(0),
            Act::Eat => BOOL(1),
            Act::Commit(text) => {
                let _ = self.request_session_kind(&text, SessionKind::Commit);
                BOOL(1)
            }
            Act::Compose => {
                let _ = self.request_compose();
                BOOL(1)
            }
            Act::CommitAndCompose(text) => {
                let _ = self.request_session_kind(&text, SessionKind::Commit);
                let _ = self.request_compose();
                BOOL(1)
            }
            Act::CommitThenPass(text) => {
                let _ = self.request_session_kind(&text, SessionKind::Commit);
                BOOL(0) // 原字符自然插入
            }
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

        // 语言栏托盘项（对齐 weasel/微软拼音：logo + 中/EN 模式双图标）
        match tm.cast::<ITfLangBarItemMgr>() {
            Ok(mgr) => {
                let logo_btn: ITfLangBarItemButton = crate::langbar::LangItem::new(
                    crate::langbar::Kind::Logo,
                    crate::langbar::GUID_LBI_LOGO,
                    self.shared.clone(),
                )
                .into();
                let mode_btn: ITfLangBarItemButton = crate::langbar::LangItem::new(
                    crate::langbar::Kind::Mode,
                    crate::langbar::GUID_LBI_MODE,
                    self.shared.clone(),
                )
                .into();
                let logo = logo_btn.cast::<ITfLangBarItem>();
                let mode = mode_btn.cast::<ITfLangBarItem>();
                let mut items = Vec::new();
                if let (Ok(logo), Ok(mode)) = (logo, mode) {
                    unsafe {
                        if mgr.AddItem(&logo).is_ok() {
                            items.push(logo);
                        }
                        if mgr.AddItem(&mode).is_ok() {
                            items.push(mode);
                        }
                    }
                }
                self.shared.lock().unwrap().langbar = items;
            }
            Err(e) => crate::log(&format!("langbar mgr: {e}")),
        }

        // 后台预载主码表（不阻塞 Activate；首次按键由 ensure_engine 兜底）
        std::thread::spawn(|| {
            static MAIN_DICT: &[u8] = include_bytes!("../../data/xiaolu_he_he.bin");
            let e = lufly_engine::Engine::load(MAIN_DICT).ok();
            crate::log(&format!("engine preload: {}", e.is_some()));
            crate::store_preload(e);
        });
        crate::log("Activate ok");
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
        // 移除语言栏托盘项
        if !shared.langbar.is_empty() {
            if let Some(tm) = &shared.thread_mgr {
                if let Ok(mgr) = tm.cast::<ITfLangBarItemMgr>() {
                    for it in &shared.langbar {
                        unsafe {
                            let _ = mgr.RemoveItem(it);
                        }
                    }
                }
            }
            shared.langbar.clear();
        }
        crate::langbar::clear_sink();
        // 用户词典落盘（与 fcitx5 析构 lufly_user_flush 对齐）
        shared.flush_user(true);
        shared.thread_mgr = None;
        shared.composition = None;
        if let Some(e) = shared.engine.as_mut() {
            e.reset();
        }
        shared.st.reset();
        shared.cand_win.hide();
        Ok(())
    }
}

impl ITfKeyEventSink_Impl for LuflyTsf_Impl {
    fn OnSetFocus(&self, pfocused: BOOL) -> Result<()> {
        if !pfocused.as_bool() {
            // 失焦（切窗口/切文档）: 关候选窗、清输入缓冲。
            // 候选窗钉住后不会自己消失，必须在这里收尾
            let mut shared = self.shared.lock().unwrap();
            shared.composition = None;
            if let Some(e) = shared.engine.as_mut() {
                e.reset();
            }
            shared.st.reset();
            shared.cand_win.hide();
            crate::log("focus lost: reset");
        }
        Ok(())
    }

    fn OnPreservedKey(&self, _pic: Ref<'_, ITfContext>, _rguid: *const GUID) -> Result<BOOL> {
        Ok(FALSE)
    }

    fn OnTestKeyDown(
        &self,
        _pic: Ref<'_, ITfContext>,
        wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        // TSF 按键协议: Test 返回 TRUE 才会回调 OnKeyDown（OnKeyDown 的返回
        // 值才决定是否吞键）。中文模式下声明接管可能处理的键。
        // Shift 不受 ascii 门控: 英文模式下也要收 Shift 单击（切回中文）
        let vk = VIRTUAL_KEY(wparam.0 as u16);
        let is_shift = vk == VK_SHIFT || vk == VK_LSHIFT || vk == VK_RSHIFT;
        let shift = unsafe { GetKeyState(VK_SHIFT.0 as i32) as u16 } & 0x8000 != 0;
        let ctrl = unsafe { GetKeyState(VK_CONTROL.0 as i32) as u16 } & 0x8000 != 0;
        let alt = unsafe { GetKeyState(VK_MENU.0 as i32) as u16 } & 0x8000 != 0;
        let ascii = self.shared.lock().unwrap().st.ascii;

        let want = !alt
            && (!ctrl || (vk.0 == 0x30 && !shift)) // Ctrl+0 切标点半角
            && (is_shift || (!ascii && wants_key(vk)));
        Ok(BOOL(want as i32))
    }

    fn OnKeyDown(
        &self,
        _pic: Ref<'_, ITfContext>,
        wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        let vk = VIRTUAL_KEY(wparam.0 as u16);
        crate::log(&format!("OnKeyDown vk=0x{:02X}", vk.0));
        Ok(self.handle_key(vk))
    }

    fn OnTestKeyUp(
        &self,
        _pic: Ref<'_, ITfContext>,
        wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        // Shift 单击（切中英）与 $/| 抬键补标点需要在 OnKeyUp 里收尾。
        // Shift 不受 ascii 门控: 英文模式下单击 Shift 切回中文
        let vk = VIRTUAL_KEY(wparam.0 as u16);
        let is_shift = vk == VK_SHIFT || vk == VK_LSHIFT || vk == VK_RSHIFT;
        let ascii = self.shared.lock().unwrap().st.ascii;
        let want = is_shift
            || (!ascii
                && (vk.0 == 0x34 || vk == VK_OEM_5)
                && self.shared.lock().unwrap().st.pending_punct.is_some());
        Ok(BOOL(want as i32))
    }

    fn OnKeyUp(
        &self,
        _pic: Ref<'_, ITfContext>,
        wparam: WPARAM,
        _lparam: LPARAM,
    ) -> Result<BOOL> {
        let vk = VIRTUAL_KEY(wparam.0 as u16);
        let is_shift = vk == VK_SHIFT || vk == VK_LSHIFT || vk == VK_RSHIFT;

        let mut new_ascii: Option<bool> = None;
        let act = {
            let mut s = self.shared.lock().unwrap();
            let st = &mut s.st;
            if is_shift && st.shift_armed {
                // Shift 单击（其后无其他键）: 切换中/英文模式；
                // 编码中先原样上屏字母再转英文（对齐常见输入法手感）
                st.shift_armed = false;
                st.cancel_add_word(); // 切换模式即退出加词
                if !st.buffer.is_empty() {
                    let letters = std::mem::take(&mut st.buffer);
                    st.last_cls = 2;
                    st.reverse = false;
                    st.ascii = true; // 编码中必为中文态: 定向转英文
                    new_ascii = Some(true);
                    crate::log("switch to EN (in coding)");
                    Act::Commit(letters)
                } else {
                    let out = std::mem::take(&mut st.pending);
                    if !out.is_empty() {
                        st.pending_code.clear(); // 挂起字随模式切换落地
                    }
                    st.auto_buf.clear(); // 切英文模式 = 断链
                    st.reverse = false;
                    st.last_cls = 0;
                    st.ascii = !st.ascii;
                    new_ascii = Some(st.ascii);
                    crate::log(&format!("switch to {}", if st.ascii { "EN" } else { "CN" }));
                    Act::Commit(out)
                }
            } else if st.pending_punct.is_some()
                && (vk.0 == 0x34 || vk == VK_OEM_5)
            {
                // $/|: 按下时已选次选候选，抬键补标点（对齐 rime Release+dollar/bar）。
                // 兼容先松 Shift 的情况（此时 VK 变回 4 / backslash）
                let punct = st.pending_punct.take().unwrap();
                st.auto_buf.clear(); // 标点 = 断链
                st.last_cls = 0;
                Act::Commit(punct.to_owned())
            } else {
                Act::Pass
            }
        };
        if let Some(ascii) = new_ascii {
            // 模式切换视觉反馈（对齐 fcitx5 托盘图标变化）
            crate::status::flash(ascii);
            // 同步系统模式格 + 刷新任务栏「中/EN」图标
            {
                let s = self.shared.lock().unwrap();
                crate::langbar::set_conversion(&s, ascii);
            }
            crate::langbar::notify_mode_changed();
        }
        Ok(self.exec_act(act))
    }
}

impl ITfCompositionSink_Impl for LuflyTsf_Impl {
    fn OnCompositionTerminated(
        &self,
        _ecwrite: u32,
        _pcomposition: Ref<'_, ITfComposition>,
    ) -> Result<()> {
        // 对齐 weasel: 正常 EndComposition（尤其空 composition）也会触发本回调
        // （"Silly M$"）。只丢 composition 句柄；仍在 composing（有输入缓冲/
        // 挂起字）时保留全部输入状态，下个按键重建 composition。只有真正空闲
        // 才清状态——否则第二字母就"全没了"。
        let mut shared = self.shared.lock().unwrap();
        shared.composition = None;
        let composing = !shared.st.buffer.is_empty() || !shared.st.pending.is_empty();
        if composing {
            crate::log("comp terminated (external), keep composing state");
        } else {
            if let Some(e) = shared.engine.as_mut() {
                e.reset();
            }
            shared.st.reset();
            shared.cand_win.hide();
            crate::log("comp terminated (idle), reset");
        }
        Ok(())
    }
}
