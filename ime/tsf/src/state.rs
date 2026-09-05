//! 输入会话状态 —— 与 fcitx5 前端 LuflyState 逐字段对齐。
//!
//! 每个 InputContext 焦点对应一份（TSF 简化: 单焦点，全局一份）。

/// 标点全角化映射（对齐 rime punctuator half_shape；引号按对交替）。
/// 返回 None 表示 rime 里也是半角的键。
pub fn chinese_punct(ch: char, dq_open: &mut bool, sq_open: &mut bool) -> Option<&'static str> {
    let s: &str = match ch {
        ',' => "，",
        '.' => "。",
        '<' => "《",
        '>' => "》",
        '/' => "、",
        '?' => "？",
        ';' => "；",
        ':' => "：",
        '\'' => {
            *sq_open = !*sq_open;
            if *sq_open { "‘" } else { "’" }
        }
        '"' => {
            *dq_open = !*dq_open;
            if *dq_open { "“" } else { "”" }
        }
        '\\' => "、",
        '|' => "·",
        '!' => "！",
        '$' => "￥",
        '^' => "……",
        '(' => "（",
        ')' => "）",
        '_' => "——",
        '[' => "「",
        ']' => "」",
        '{' => "『",
        '}' => "』",
        _ => return None,
    };
    Some(s)
}

#[derive(Default)]
pub struct State {
    /// 编码缓冲（引擎 input 之外前端再留一份，miss 时引擎也持有）
    pub buffer: String,
    /// 反查模式: ` 已按下，buffer 为拼音字母（不含 ` 本身）
    pub reverse: bool,
    /// 英文直通模式（Shift 单击切换）
    pub ascii: bool,
    /// Shift 已按下且其后无其他按键（单击切中英）
    pub shift_armed: bool,
    /// Shift+4 / Shift+\ 已选次选候选，抬键时补发标点（"。" / "，"）
    pub pending_punct: Option<&'static str>,
    /// 引号配对状态（“‘ 已开待闭）
    pub dq_open: bool,
    pub sq_open: bool,
    /// 顶功挂起: 全码唯一已自动选字、但未发送，等下一键顶出/空格确认
    pub pending: String,
    /// 挂起对应的编码（退格撤销时恢复）
    pub pending_code: String,
    /// 上一个输出/透传字符的类别（0=中文/其他 1=ASCII 数字 2=ASCII 字母），
    /// 仅数字后的标点保持半角（3.14 / 1,000）；字母后保持全角（用户裁定）
    pub last_cls: i32,
    /// 退格删过已上屏字符（空缓冲透传退格）: 下一个标点无视 last_cls 恢复全角
    /// —— 删掉半角标点重打应得中文（一次性，打字母/数字/标点后清除）
    pub punct_erased: bool,
    /// Ctrl+0 切换: 标点强制半角（对齐 rime ascii_punct）
    pub ascii_punct: bool,
    /// ojc 加词模式: 1=选词阶段 2=编码编辑阶段（0=非加词）
    pub add_stage: u8,
    pub add_word: String,
    pub add_code: String,
    /// ojc 选字记录: 每段 (码, 文本)，码空 = 无效（反查选字）。组词码用
    /// （所见即所得，多音字不踩码表行序）
    pub add_segs: Vec<(String, String)>,
    /// 自动造词: 连续全码(4键)上屏的单字链（UTF-8 拼接），≥2 字即成词。
    /// 任何非「单字+4码」的上屏（简码/选词/标点/英文/回车原样）都断链。
    pub auto_buf: String,
    /// 与 auto_buf 逐字对应的 4 键全码（组词码直接用，不再 derive）
    pub auto_codes: Vec<String>,
    /// 候选当前页（翻页键用）
    pub page: usize,
}

impl State {
    pub fn reset(&mut self) {
        self.buffer.clear();
        self.reverse = false;
        self.shift_armed = false;
        self.pending_punct = None;
        self.pending.clear();
        self.pending_code.clear();
        self.last_cls = 0;
        self.punct_erased = false;
        self.dq_open = false;
        self.sq_open = false;
        self.cancel_add_word();
        self.page = 0;
    }

    pub fn cancel_add_word(&mut self) {
        self.add_stage = 0;
        self.add_word.clear();
        self.add_code.clear();
        self.add_segs.clear();
        self.auto_buf.clear();
        self.auto_codes.clear();
    }
}
