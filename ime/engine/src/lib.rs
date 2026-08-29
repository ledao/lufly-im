//! 小鹭音形输入法核心引擎（平台无关）
//!
//! 码表: `ime/tools/build_dict.py` 从 Rime dict.yaml 编译出的二进制
//! 行为: 定长音形 —— 双拼 2 键 + 形码 2 键; 一简(1键)、二简(2键)、
//!       词组 4 码(简语) / 6 码(全码: 双拼4 + 首末形码)、多字词 8 码以上。
//!       6 码及以上偶数长度命中全码时自动上屏; 4 码靠空格/顶字上屏。

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
        // 短前缀可能命中几十万条；select_nth 选出前 100 再排序，O(n) 而非 O(n log n)
        for group in [&mut exact, &mut rest] {
            if group.len() > MAX_CANDIDATES {
                group.select_nth_unstable_by_key(MAX_CANDIDATES - 1, |&i| {
                    self.entries[i as usize].rank
                });
                group.truncate(MAX_CANDIDATES);
            }
            group.sort_unstable_by_key(|&i| self.entries[i as usize].rank);
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

    /// 喂入一个按键，返回需要上屏的文本（顶字/选词/自动上屏）。
    ///
    /// 按键语义:
    /// - `a..z`  进编码缓冲（死码时先顶出当前首选）
    /// - 空格    上屏首选
    /// - `1..9`  选候选
    /// - `\u{8}` 退格
    /// - `\u{1b}`清空缓冲
    /// - 其他    忽略（标点/符号处理属于前端职责）
    pub fn key(&mut self, c: char) -> Option<String> {
        match c {
            'a'..='z' => self.push_letter(c),
            ' ' => {
                let text = self.top_text()?;
                self.input.clear();
                self.invalidate();
                Some(text)
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
            // 6 码及以上偶数长度命中全码 → 自动上屏（词组/多字词）
            let n = self.input.len();
            if n >= 6 && n % 2 == 0 {
                if let Some(text) = self.exact_top_text() {
                    self.input.clear();
                    return Some(text);
                }
            }
            return None;
        }

        // 死码：顶出当前首选，新键重新开始
        let commit = self.top_text();
        self.input.clear();
        self.input.push(c);
        commit
    }

    fn exact_top_text(&self) -> Option<String> {
        let start = self.prefix_start(&self.input);
        let e = &self.entries[start];
        if e.code == self.input {
            Some(e.text.clone())
        } else {
            None
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
    fn dead_key_bumps_previous() {
        let mut e = demo_engine();
        for c in "debu".chars() {
            e.key(c);
        }
        assert_eq!(e.input(), "debu");
        // 后续按键 "qq" 无前缀 → 顶出 4 码单字"的"
        assert_eq!(e.key('q'), Some("的".into()));
        assert_eq!(e.input(), "q");
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
    fn no_prefix_after_single_falls_back() {
        let mut e = demo_engine();
        e.key('n'); // "ni" 有二简
        // nz 无前缀 → 顶出一简/二简首选
        let commit = e.key('z');
        assert_eq!(commit.as_deref(), Some("你"));
        assert_eq!(e.input(), "z");
    }
}
