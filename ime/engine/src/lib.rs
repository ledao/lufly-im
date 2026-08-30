//! 小鹭音形输入法核心引擎（平台无关）
//!
//! 码表: `ime/tools/build_dict.py` 从 Rime dict.yaml 编译出的二进制
//! 行为: 定长音形 —— 双拼 2 键 + 形码 2 键; 一简(1键)、二简(2键)、
//!       词组 4 码(简语) / 6 码(全码: 双拼4 + 首末形码)、多字词 8 码以上。
//!       6 码及以上偶数长度命中全码时自动上屏; 4 码靠空格/顶字上屏。

use std::collections::HashMap;
use std::fmt;

const MAGIC: &[u8; 8] = b"LUFLYD01";

const MAX_CANDIDATES: usize = 100;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate {
    pub text: String,
    /// 码表行序，越小越优先
    pub rank: u32,
    /// 编码完全命中（区别于前缀扩展）
    pub exact: bool,
}

impl fmt::Display for Candidate {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.text)
    }
}

#[derive(Debug)]
struct Entry {
    code: String,
    text: String,
    rank: u32,
}

/// 输入法引擎。持有一个按键缓冲（编码串），通过 [`Engine::key`] 逐键喂入。
pub struct Engine {
    entries: Vec<Entry>, // 按 code 字典序排列
    input: String,
    /// 候选缓存：与 input 同步（input 一变即失效）。
    cache: Vec<Candidate>,
    cache_valid: bool,
    /// 用户词典: (编码, 词) → 上屏次数。次数多者在其编码的 exact 候选组内
    /// 排到前面（词频自学习提权）。只影响排序，不影响结构性行为
    /// （全码唯一判定/自动上屏仍按码表词条数，学得再多也不改变顶功）。
    user: HashMap<(String, String), u32>,
    /// 用户自定义词（ojc 加词）: (编码, 词) 清单，按 code 序。
    /// 加载时作为新词条插入 entries（rank 0，同码组内最前），
    /// 这里只留清单供 save_user 输出与 reload 幂等去重。
    user_words: Vec<(String, String)>,
    /// learn 累计次数（自上次 load_user 起）。前端/capi 据此决定落盘时机。
    user_ops: u32,
}

impl Engine {
    /// 从二进制码表加载（`build_dict.py` 产物）。
    pub fn load(dict: &[u8]) -> Result<Self, String> {
        if dict.len() < 12 || &dict[..8] != MAGIC {
            return Err("bad dict: invalid magic".into());
        }
        let count = u32::from_le_bytes(dict[8..12].try_into().unwrap()) as usize;
        let mut pos = 12usize;
        let mut entries = Vec::with_capacity(count);
        for _ in 0..count {
            if pos + 1 > dict.len() {
                return Err("bad dict: truncated".into());
            }
            let code_len = dict[pos] as usize;
            pos += 1;
            if pos + code_len > dict.len() {
                return Err("bad dict: truncated".into());
            }
            let code = String::from_utf8_lossy(&dict[pos..pos + code_len]).into_owned();
            pos += code_len;
            if pos + 1 > dict.len() {
                return Err("bad dict: truncated".into());
            }
            let text_len = dict[pos] as usize;
            pos += 1;
            if pos + text_len + 4 > dict.len() {
                return Err("bad dict: truncated".into());
            }
            let text = String::from_utf8_lossy(&dict[pos..pos + text_len]).into_owned();
            pos += text_len;
            let rank = u32::from_le_bytes(dict[pos..pos + 4].try_into().unwrap());
            pos += 4;
            entries.push(Entry { code, text, rank });
        }
        Ok(Engine {
            entries,
            input: String::new(),
            cache: Vec::new(),
            cache_valid: false,
            user: HashMap::new(),
            user_words: Vec::new(),
            user_ops: 0,
        })
    }

    /// 便于测试/嵌入方构造
    #[cfg(test)]
    pub fn from_entries(mut entries: Vec<(String, String, u32)>) -> Self {
        entries.sort_by(|a, b| a.0.cmp(&b.0));
        Engine {
            entries: entries
                .into_iter()
                .map(|(code, text, rank)| Entry { code, text, rank })
                .collect(),
            input: String::new(),
            cache: Vec::new(),
            cache_valid: false,
            user: HashMap::new(),
            user_words: Vec::new(),
            user_ops: 0,
        }
    }

    /// 当前编码缓冲（预编辑串）
    pub fn input(&self) -> &str {
        &self.input
    }

    /// 编码缓冲是否为空（为空时按键应透传为英文）
    pub fn is_empty(&self) -> bool {
        self.input.is_empty()
    }

    /// 清空缓冲（composition 被外部终止等场景）
    pub fn reset(&mut self) {
        self.input.clear();
        self.invalidate();
    }

    fn invalidate(&mut self) {
        self.cache_valid = false;
        self.cache.clear();
    }

    /// 当前候选列表：完全命中在前，其余按码表行序。
    ///
    /// 结果按 input 缓存；input 未变时重复调用零开销（前端每键会取多次）。
    pub fn candidates(&mut self) -> &[Candidate] {
        if !self.cache_valid {
            self.cache = self.compute_candidates();
            self.cache_valid = true;
        }
        &self.cache
    }

    /// 记录一次真实上屏: 用户以 `code` 选定了 `text`。此后该词条在其编码的
    /// exact 候选组内排到未学词条之前（次数多的更靠前），用于词频自学习。
    ///
    /// 注意: 只影响排序，不影响结构性行为——全码唯一判定/自动上屏仍按
    /// 码表词条数，学得再多也不会让撞码词条自动上屏。
    pub fn learn(&mut self, code: &str, text: &str) {
        if code.is_empty() || text.is_empty() {
            return;
        }
        let n = self
            .user
            .entry((code.to_owned(), text.to_owned()))
            .or_insert(0);
        *n = n.saturating_add(1);
        self.user_ops = self.user_ops.wrapping_add(1);
        self.invalidate();
    }

    /// learn 累计次数（自上次 [`Engine::load_user`] 起），调用方据此决定
    /// 何时调用 save_user 落盘。
    pub fn user_ops(&self) -> u32 {
        self.user_ops
    }

    /// 用户词典序列化: 每行 `code|text|count`，自定义词末尾多一列 `w`；
    /// 按 (code, text) 排序（确定性输出，便于 diff/同步）。文件本身是
    /// 纯文本，可手工编辑。编码只含小写字母、词为中文，`|` 不会与之冲突。
    pub fn save_user(&self) -> Vec<u8> {
        let mut rows: Vec<(&str, &str, u32, bool)> = self
            .user
            .iter()
            .map(|((c, t), n)| (c.as_str(), t.as_str(), *n, false))
            .collect();
        for (c, t) in &self.user_words {
            let n = self.user.get(&(c.clone(), t.clone())).copied().unwrap_or(1);
            rows.push((c.as_str(), t.as_str(), n.max(1), true));
        }
        rows.sort_unstable();
        let mut out = String::with_capacity(rows.len() * 24);
        for (c, t, n, w) in rows {
            out.push_str(c);
            out.push('|');
            out.push_str(t);
            out.push('|');
            out.push_str(&n.to_string());
            if w {
                out.push_str("|w");
            }
            out.push('\n');
        }
        out.into_bytes()
    }

    /// 加载 [`Engine::save_user`] 产物。坏行（手工编辑损坏）跳过不报错；
    /// **合并语义**: 覆盖磁盘已有 (code,text) 的计数，内存里磁盘没有的
    /// 学习记录保留（热重载时磁盘新行与内存增量互不丢失）。
    /// 自定义词（w 列）作为新词条插入 entries——rank 0 使其在同码组内
    /// 最前，候选/miss/唯一性判定自动生效。重复加载幂等（去重）。
    pub fn load_user(&mut self, data: &[u8]) {
        let text = String::from_utf8_lossy(data);
        for line in text.lines() {
            let line = line.trim_end_matches('\r');
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let mut it = line.split('|');
            let (Some(code), Some(word), Some(n)) = (it.next(), it.next(), it.next())
            else {
                continue;
            };
            let flag = it.next();
            if it.next().is_some() {
                continue;
            }
            // 第四列（可选）: 仅接受 w（自定义词标记）
            let is_word = match flag {
                None => false,
                Some("w") => true,
                _ => continue,
            };
            let Ok(n) = n.parse::<u32>() else {
                continue;
            };
            if code.is_empty() || word.is_empty() || n == 0 {
                continue;
            }
            self.user
                .insert((code.to_owned(), word.to_owned()), n);
            if is_word {
                self.insert_user_word(code, word);
            }
        }
        self.user_ops = 0;
        self.invalidate();
    }

    /// 自定义词入列并插入主码表（rank 0 → 同码组内最前）。幂等。
    fn insert_user_word(&mut self, code: &str, word: &str) {
        let pair = (code.to_owned(), word.to_owned());
        match self
            .user_words
            .binary_search_by(|p| p.0.as_str().cmp(code).then(p.1.as_str().cmp(word)))
        {
            Ok(_) => return, // 已存在: 只刷新计数，不重复插入
            Err(pos) => self.user_words.insert(pos, pair),
        }
        // entries 按 code 字典序，插到同码块开头（partition_point 首个 >= code 处）
        let at = self
            .entries
            .partition_point(|e| e.code.as_str() < code);
        self.entries.insert(
            at,
            Entry {
                code: code.to_owned(),
                text: word.to_owned(),
                rank: 0,
            },
        );
    }

    /// 添加自定义词（ojc 加词）: 词条立即插入主码表生效（rank 0 同码组
    /// 最前），计数记 1，user_ops+1（走常规落盘策略）。
    pub fn add_user_word(&mut self, code: &str, text: &str) -> Result<(), String> {
        if code.is_empty() || text.is_empty() {
            return Err("编码或词为空".into());
        }
        if !code.bytes().all(|b| b.is_ascii_lowercase()) || code.len() < 2 {
            return Err("编码须为 2 位以上小写字母".into());
        }
        if text.contains('|') || text.contains('\n') {
            return Err("词不能含 | 或换行".into());
        }
        // or_insert: 词已存在（重复 ojc/自动造词再触发）时保留已学习的
        // 词频，不归零
        self.user
            .entry((code.to_owned(), text.to_owned()))
            .or_insert(1);
        self.insert_user_word(code, text);
        self.user_ops = self.user_ops.wrapping_add(1);
        self.invalidate();
        Ok(())
    }

    /// 反查一个字的 4 码全码（双拼2+形码2），取码表行序最靠前者。
    /// 码表没有该字（或无全码）返回 None。
    pub fn char_full_code(&self, ch: char) -> Option<&str> {
        self.entries
            .iter()
            .filter(|e| {
                e.text.len() == ch.len_utf8()
                    && e.text.starts_with(ch)
                    && e.code.len() == 4
            })
            .min_by_key(|e| e.rank)
            .map(|e| e.code.as_str())
    }

    /// 为一个词推导默认全码（加词用）:
    /// - 单字词: 该字 4 码全码（双拼2+形码2）
    /// - 2 字词: 首末字双拼(2+2) + 首末字形码各 1 键，共 6 码
    ///   （与码表一致: 这个=vegezp）
    /// - 3 字以上: 每字双拼 + 首末形码各 1 键，共 2N+2 码（3字=8 码）
    /// 任一字查不到全码时返回 Err(说明)。
    pub fn derive_word_code(&self, word: &str) -> Result<String, String> {
        let chars: Vec<char> = word.chars().collect();
        match chars.len() {
            0 => Err("空词".into()),
            1 => self
                .char_full_code(chars[0])
                .map(str::to_owned)
                .ok_or_else(|| format!("「{}」不在码表（无全码）", chars[0])),
            _ => {
                let codes: Vec<Option<&str>> =
                    chars.iter().map(|&ch| self.char_full_code(ch)).collect();
                if let Some((i, None)) = codes.iter().enumerate().find(|(_, c)| c.is_none()) {
                    return Err(format!("「{}」不在码表（无全码）", chars[i]));
                }
                let codes: Vec<&str> = codes.into_iter().map(Option::unwrap).collect();
                let sp: String = codes.iter().map(|c| &c[..2]).collect();
                let mut out = String::with_capacity(sp.len() + 2);
                out.push_str(&sp);
                out.push_str(&codes[0][2..3]); // 首字形码 1 键
                out.push_str(&codes[codes.len() - 1][2..3]); // 末字形码 1 键
                Ok(out)
            }
        }
    }

    fn compute_candidates(&self) -> Vec<Candidate> {
        if self.input.is_empty() {
            return Vec::new();
        }
        let start = self.prefix_start(&self.input);
        // 只收集索引并按组排序，截断后再物化字符串，避免全量克隆
        let mut exact: Vec<u32> = Vec::new();
        let mut rest: Vec<u32> = Vec::new();
        for (i, e) in self.entries[start..].iter().enumerate() {
            if !e.code.starts_with(&self.input) {
                break;
            }
            if e.code.len() == self.input.len() {
                &mut exact
            } else {
                &mut rest
            }
            .push((start + i) as u32);
        }
        // 用户词频提权（exact 组）: 学习次数多者靠前，其次按码表行序。
        // 打包成 u64 键避免比较器里反复查表: 高 32 位 = !次数（0 次 → 全 1，
        // 退化为纯行序，与无用户词典时排序完全一致），低 32 位 = 行序。
        if !self.user.is_empty() && !exact.is_empty() {
            let mut keyed: Vec<(u64, u32)> = exact
                .iter()
                .map(|&i| {
                    let e = &self.entries[i as usize];
                    let c = self
                        .user
                        .get(&(e.code.clone(), e.text.clone()))
                        .copied()
                        .unwrap_or(0);
                    (((!(c as u64)) << 32) | e.rank as u64, i)
                })
                .collect();
            if keyed.len() > MAX_CANDIDATES {
                keyed.select_nth_unstable_by_key(MAX_CANDIDATES - 1, |k| k.0);
                keyed.truncate(MAX_CANDIDATES);
            }
            keyed.sort_unstable_by_key(|k| k.0);
            exact = keyed.into_iter().map(|(_, i)| i).collect();

            // rest 组不受词频影响，仍按行序截取排序
            if rest.len() > MAX_CANDIDATES {
                rest.select_nth_unstable_by_key(MAX_CANDIDATES - 1, |&i| {
                    self.entries[i as usize].rank
                });
                rest.truncate(MAX_CANDIDATES);
            }
            rest.sort_unstable_by_key(|&i| self.entries[i as usize].rank);
        } else {
            // 短前缀可能命中几十万条；select_nth 选出前 100 再排序，
            // O(n) 而非 O(n log n)
            for group in [&mut exact, &mut rest] {
                if group.len() > MAX_CANDIDATES {
                    group.select_nth_unstable_by_key(MAX_CANDIDATES - 1, |&i| {
                        self.entries[i as usize].rank
                    });
                    group.truncate(MAX_CANDIDATES);
                }
                group.sort_unstable_by_key(|&i| self.entries[i as usize].rank);
            }
        }
        exact.reserve(rest.len());
        exact.append(&mut rest);
        exact.truncate(MAX_CANDIDATES);
        // 同文本去重（同一词常有多个编码变体），保留 rank 最小的首个
        let mut seen = std::collections::HashSet::with_capacity(64);
        exact.into_iter()
            .filter(|&i| seen.insert(self.entries[i as usize].text.as_str()))
            .map(|i| {
                let e = &self.entries[i as usize];
                Candidate {
                    text: e.text.clone(),
                    rank: e.rank,
                    exact: e.code.len() == self.input.len(),
                }
            })
            .collect()
    }

    /// 首选文本（exact 优先，否则前缀第一个）
    pub fn top_text(&mut self) -> Option<String> {
        self.candidates().first().map(|c| c.text.clone())
    }

    /// 喂入一个按键，返回需要上屏的文本（选词/自动上屏）。
    ///
    /// 按键语义:
    /// - `a..z`  进编码缓冲；编码 miss 时不顶字，字母原样累积（输英文）
    /// - 空格    上屏首选；无候选（miss/空缓冲）时清屏
    /// - `1..9`  选候选
    /// - `\u{8}` 退格（回到有效编码后恢复候选）
    /// - `\u{1b}`清空缓冲
    /// - 其他    忽略（标点/符号处理属于前端职责）
    pub fn key(&mut self, c: char) -> Option<String> {
        match c {
            'a'..='z' => self.push_letter(c),
            ' ' => {
                // miss 时 top_text 为 None → 清屏不上屏
                let text = self.top_text();
                self.input.clear();
                self.invalidate();
                text
            }
            '1'..='9' => {
                let idx = c as usize - '1' as usize;
                let text = self.candidates().get(idx)?.text.clone();
                self.input.clear();
                self.invalidate();
                Some(text)
            }
            '\u{8}' => {
                self.input.pop();
                self.invalidate();
                None
            }
            '\u{1b}' => {
                self.input.clear();
                self.invalidate();
                None
            }
            _ => None,
        }
    }

    fn push_letter(&mut self, c: char) -> Option<String> {
        let mut next = String::with_capacity(self.input.len() + 1);
        next.push_str(&self.input);
        next.push(c);
        self.invalidate();

        if self.has_prefix(&next) {
            self.input = next;
            // 6/8/10… 偶数全码唯一 → 自动上屏（对齐 rime auto_select_pattern；
            // auto_select 只在唯一候选时生效）。4/5 码只显示候选。
            let n = self.input.len();
            if n >= 6 && n % 2 == 0 {
                if let Some(text) = self.unique_exact_text() {
                    self.input.clear();
                    return Some(text);
                }
            }
            return None;
        }

        // 编码 miss: 不顶字 —— 用户可能在输入英文。字母原样累积:
        // 空格清屏 / 回车(前端)上屏英文 / 退格回到有效编码后恢复候选
        self.input = next;
        None
    }

    /// 全码唯一命中: 编码恰为某词条全码、且无其他词条共用该编码。
    fn unique_exact_text(&self) -> Option<String> {
        let start = self.prefix_start(&self.input);
        let e = self.entries.get(start)?;
        if e.code != self.input {
            return None;
        }
        match self.entries.get(start + 1) {
            Some(n) if n.code == self.input => None, // 编码撞车，等用户手选
            _ => Some(e.text.clone()),
        }
    }

    fn prefix_start(&self, prefix: &str) -> usize {
        self.entries.partition_point(|e| e.code.as_str() < prefix)
    }

    fn has_prefix(&self, prefix: &str) -> bool {
        let s = self.prefix_start(prefix);
        s < self.entries.len() && self.entries[s].code.starts_with(prefix)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn demo_engine() -> Engine {
        // (code, text, rank) 模拟小码表
        Engine::from_entries(vec![
            ("q".into(), "去".into(), 0),
            ("de".into(), "的".into(), 1),
            ("debu".into(), "的".into(), 2), // 单字全码: 双拼 de + 形码 bu
            ("ni".into(), "你".into(), 3),
            ("nihc".into(), "你好".into(), 4), // 4码简语词
            ("vege".into(), "这个".into(), 5), // 4码简语词
            ("vegezp".into(), "这个".into(), 6), // 6码全码词
            ("vegezr".into(), "这个".into(), 7),
            ("yige".into(), "一个".into(), 8),
            ("yigeap".into(), "一个".into(), 9),
            ("yiger".into(), "一个".into(), 12), // 5 码唯一: 全码自动上屏
            ("veui".into(), "这是".into(), 10),
        ])
    }

    #[test]
    fn load_rejects_bad_magic() {
        assert!(Engine::load(b"XXXXXXXXXX").is_err());
    }

    #[test]
    fn simple_input_prefix_candidates() {
        let mut e = demo_engine();
        e.key('n');
        e.key('i');
        assert_eq!(e.input(), "ni");
        let cands = e.candidates();
        assert_eq!(cands[0].text, "你"); // 二简
        assert!(cands.iter().any(|c| c.text == "你好"));
    }

    #[test]
    fn space_commits_top() {
        let mut e = demo_engine();
        for c in "de".chars() {
            e.key(c);
        }
        assert_eq!(e.key(' '), Some("的".into()));
        assert!(e.is_empty());
    }

    #[test]
    fn four_code_word_needs_space() {
        let mut e = demo_engine();
        for c in "nihc".chars() {
            e.key(c);
        }
        // 4 码不自动上屏
        assert_eq!(e.input(), "nihc");
        assert_eq!(e.key(' '), Some("你好".into()));
    }

    #[test]
    fn six_code_auto_commit() {
        let mut e = demo_engine();
        for c in "vegezp".chars() {
            let commit = e.key(c);
            if c == 'p' {
                assert_eq!(commit, Some("这个".into()), "6码全码应自动上屏");
            } else {
                assert_eq!(commit, None);
            }
        }
        assert!(e.is_empty());
    }

    #[test]
    fn dead_key_keeps_input() {
        let mut e = demo_engine();
        for c in "debu".chars() {
            e.key(c);
        }
        assert_eq!(e.input(), "debu");
        // 后续按键无前缀 → 不顶字，原样累积（用户可能在输英文）
        assert_eq!(e.key('q'), None);
        assert_eq!(e.input(), "debuq");
        assert!(e.candidates().is_empty());
    }

    #[test]
    fn digit_selects_candidate() {
        let mut e = demo_engine();
        for c in "de".chars() {
            e.key(c);
        }
        // 候选: 的(二简 exact) ... debu 的(exact)。选第 2 个候选 "2"
        let cands = e.candidates();
        if cands.len() > 1 {
            let expect = cands[1].text.clone();
            assert_eq!(e.key('2'), Some(expect));
        }
    }

    #[test]
    fn backspace_and_escape() {
        let mut e = demo_engine();
        for c in "deb".chars() {
            e.key(c);
        }
        // "de" 有二简、"deb" 是 "debu" 的前缀，均合法
        assert_eq!(e.input(), "deb");
        e.key('\u{8}');
        assert_eq!(e.input(), "de");
        e.key('\u{1b}');
        assert!(e.is_empty());
    }

    #[test]
    fn miss_keeps_input_for_english() {
        let mut e = demo_engine();
        for c in "debu".chars() {
            e.key(c); // "的" 4 码全码: 唯一但不自动上屏
        }
        assert_eq!(e.input(), "debu");
        // debux miss: 不顶字，字母原样累积（可能正在输英文）
        assert_eq!(e.key('x'), None);
        assert_eq!(e.input(), "debux");
        assert!(e.candidates().is_empty());
        e.key('k');
        assert_eq!(e.input(), "debuxk");
        // 退格回到有效编码后候选恢复
        e.key('\u{8}');
        e.key('\u{8}');
        assert_eq!(e.input(), "debu");
        assert!(!e.candidates().is_empty());
        // miss 状态下空格 = 清屏，不上屏任何文本
        assert_eq!(e.key('x'), None);
        assert_eq!(e.key(' '), None);
        assert!(e.is_empty());
    }

    #[test]
    fn five_code_needs_space() {
        let mut e = demo_engine();
        for c in "yige".chars() {
            assert_eq!(e.key(c), None, "4 码不自动上屏");
        }
        // 5 码唯一也不自动上屏（对齐 rime: 只有 6/8/10… 偶数全码才自动）
        assert_eq!(e.key('r'), None);
        assert_eq!(e.input(), "yiger");
        assert_eq!(e.key(' '), Some("一个".into()));
        assert!(e.is_empty());
    }

    fn two_way_engine() -> Engine {
        // 同码两词: 行序在前的默认排前
        Engine::from_entries(vec![
            ("ni".into(), "你".into(), 0),
            ("ni".into(), "尼".into(), 1),
        ])
    }

    /// two_way_engine 且已敲入 "ni"
    fn typed_two_way() -> Engine {
        let mut e = two_way_engine();
        e.key('n');
        e.key('i');
        e
    }

    #[test]
    fn learn_promotes_within_same_code() {
        // 行序在前的默认排前
        let mut e = typed_two_way();
        assert_eq!(e.candidates()[0].text, "你");
        // 学习后反超（learn 后缓存失效，须重新敲码）
        let mut e2 = two_way_engine();
        e2.learn("ni", "尼");
        e2.key('n');
        e2.key('i');
        assert_eq!(e2.candidates()[0].text, "尼");
        // 学习别的码不影响本码排序
        let mut e3 = two_way_engine();
        e3.learn("nix", "呢");
        e3.key('n');
        e3.key('i');
        assert_eq!(e3.candidates()[0].text, "你");
    }

    #[test]
    fn learn_order_follows_count() {
        let mut e = two_way_engine();
        e.learn("ni", "你");
        e.learn("ni", "尼");
        e.learn("ni", "尼");
        e.key('n');
        e.key('i');
        assert_eq!(e.candidates()[0].text, "尼", "次数多者靠前");
    }

    #[test]
    fn learn_does_not_break_unique_autocommit() {
        // 全码唯一判定是结构性的: 学得再多也不让撞码词条自动上屏
        let mut e = two_way_engine();
        for _ in 0..10 {
            e.learn("ni", "尼");
        }
        e.key('n');
        e.key('i');
        assert_eq!(e.input(), "ni", "撞码不自动上屏");
    }

    #[test]
    fn user_dict_roundtrip() {
        let mut e = two_way_engine();
        e.learn("ni", "你");
        e.learn("ni", "尼");
        e.learn("ni", "尼");
        let bytes = e.save_user();
        // 按 (code, text) 码点序: 你 U+4F60 < 尼 U+5C3C
        assert_eq!(String::from_utf8(bytes.clone()).unwrap(), "ni|你|1\nni|尼|2\n");

        let mut f = two_way_engine();
        f.load_user(&bytes);
        assert_eq!(f.user_ops(), 0, "加载后视为已落盘基线");
        assert_eq!(f.save_user(), bytes, "序列化确定（可 diff）");
        f.key('n');
        f.key('i');
        assert_eq!(f.candidates()[0].text, "尼");
    }

    #[test]
    fn load_user_skips_bad_lines() {
        let mut e = two_way_engine();
        e.load_user("# comment\nni|尼|abc\nbroken\nni||3\nni|尼|5\nni|你|1|x\n\n".as_bytes());
        assert_eq!(e.user.get(&("ni".into(), "尼".into())), Some(&5));
        assert!(e.user.get(&("ni".into(), "你".into())).is_none());
        e.key('n');
        e.key('i');
        assert_eq!(e.candidates()[0].text, "尼");
    }

    // ---- 用户自定义词（ojc 加词）----

    fn demo_full_engine() -> Engine {
        // 含单字全码(4码)与小词表，用于 derive/加词测试
        Engine::from_entries(vec![
            ("debu".into(), "的".into(), 2),
            ("duob".into(), "多".into(), 10),
            ("duoo".into(), "朵".into(), 11),
            ("nihc".into(), "你好".into(), 4),
            ("niky".into(), "你".into(), 3),
            ("haiz".into(), "好".into(), 5),
            ("ni".into(), "你".into(), 0),
        ])
    }

    #[test]
    fn user_word_becomes_candidate() {
        let mut e = demo_full_engine();
        e.load_user("duoduobb|多多|1|w\n".as_bytes());
        // 未敲满时作为候选出现（rank0 组内最前）
        for c in "duoduob".chars() {
            e.key(c);
        }
        assert_eq!(e.candidates()[0].text, "多多");
        // 敲满 8 码全码唯一 → 自动上屏（与静态词同规则）
        let commit = e.key('b');
        assert_eq!(commit, Some("多多".into()), "全码唯一自动上屏");
        assert!(e.is_empty());
    }

    #[test]
    fn user_word_fixes_miss() {
        let mut e = demo_full_engine();
        for c in "zzzz".chars() {
            e.key(c);
        }
        assert!(e.candidates().is_empty(), "未加词时 miss");
        e.reset();
        e.load_user("zzzz|自主词|1|w\n".as_bytes());
        for c in "zzzz".chars() {
            e.key(c);
        }
        assert_eq!(e.candidates()[0].text, "自主词", "加词救活 miss");
    }

    #[test]
    fn user_word_collision_blocks_autocommit() {
        // 与已有词同码 → 撞码，不自动上屏（结构判定计入自定义词）
        let mut e = demo_full_engine();
        e.load_user("duob|多哆|1|w\n".as_bytes());
        for c in "duob".chars() {
            e.key(c);
        }
        assert_eq!(e.input(), "duob", "撞码不自动上屏");
        assert_eq!(e.candidates()[0].text, "多哆", "rank0 排前");
    }

    #[test]
    fn user_word_reload_idempotent() {
        let mut e = demo_full_engine();
        e.load_user("zzzz|自主词|1|w\n".as_bytes());
        e.load_user("zzzz|自主词|1|w\n".as_bytes());
        assert_eq!(e.user_words.len(), 1);
        let n = e
            .entries
            .iter()
            .filter(|en| en.text == "自主词")
            .count();
        assert_eq!(n, 1, "重复加载不重复插入");
    }

    #[test]
    fn user_word_roundtrip_keeps_w_flag() {
        let mut e = demo_full_engine();
        e.learn("ni", "你");
        e.load_user("zzzz|自主词|1|w\n".as_bytes());
        let bytes = e.save_user();
        let s = String::from_utf8(bytes.clone()).unwrap();
        assert!(s.contains("zzzz|自主词|1|w"));
        assert!(s.contains("ni|你|1\n"));

        // 全新引擎加载 → 自定义词仍在
        let mut f = demo_full_engine();
        f.load_user(&bytes);
        f.key('z');
        f.key('z');
        f.key('z');
        f.key('z');
        assert_eq!(f.candidates()[0].text, "自主词");
    }

    #[test]
    fn derive_word_code_rules() {
        let e = demo_full_engine();
        // 单字: 4 码全码
        assert_eq!(e.derive_word_code("的").unwrap(), "debu");
        // 2 字词: 双拼4 + 首末形码各 1 键（你=niky, 好=haiz → niha ki）
        assert_eq!(e.derive_word_code("你好").unwrap(), "nihaki");
        assert!(e.derive_word_code("不存在的字").is_err());
        assert_eq!(e.derive_word_code("").unwrap_err(), "空词");
    }

    #[test]
    fn add_user_word_immediate_usable() {
        let mut e = demo_full_engine();
        e.add_user_word("dodoxx", "多多").unwrap();
        assert_eq!(e.user_words.len(), 1);
        let mut cmt = None;
        for c in "dodoxx".chars() {
            cmt = e.key(c);
        }
        assert_eq!(cmt.as_deref(), Some("多多"), "6码唯一自动上屏");
        assert!(e.is_empty());
        // 校验: 非法编码被拒
        assert!(e.add_user_word("D1", "词").is_err());
        assert!(e.add_user_word("abc", "").is_err());
        // save 带 w 列
        assert!(String::from_utf8(e.save_user())
            .unwrap()
            .contains("dodoxx|多多|1|w"));
    }
}
