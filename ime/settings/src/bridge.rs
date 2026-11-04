//! 桥协议实现：HTML ↔ Rust 的命令处理与 config.json / user_dict.txt 读写。
//! 无 UI 依赖，全部函数可单测。

use std::collections::HashMap;
use std::path::PathBuf;

use serde_json::{json, Value};

/// 与 tsf/src/config.rs 的 DEFAULT 保持同步（main.rs 引给 get 合并用）
pub const DEFAULTS: &str = r#"{
  "version": 1,
  "default_ascii": false,
  "page_size": 5,
  "shift_toggle": true,
  "auto_word": true,
  "cand_font_size": 17,
  "cand_show_suffix": true,
  "log": false
}"#;

/// 允许 set 的白名单（防手滑/注入写坏文件；schema 真源 tsf/src/config.rs）
const WRITABLE: &[&str] = &[
    "default_ascii",
    "page_size",
    "shift_toggle",
    "auto_word",
    "cand_font_size",
    "cand_show_suffix",
    "log",
];

pub fn config_path() -> PathBuf {
    appdata().join("config.json")
}

pub fn dict_path() -> PathBuf {
    appdata().join("user_dict.txt")
}

fn appdata() -> PathBuf {
    std::env::var("APPDATA")
        .map(|a| PathBuf::from(a).join("lufly"))
        .unwrap_or_else(|_| PathBuf::from("."))
}

/// 处理一条 JS 消息，返回应答 JSON（None = 静默不回）。
/// 应答一律回显 cmd——JS 侧据此区分响应，不依赖发送顺序猜测。
pub fn handle(msg: &str) -> Option<String> {
    let v: Value = match serde_json::from_str(msg) {
        Ok(v) => v,
        Err(_) => return Some(err_json("bad json")),
    };
    let cmd = v.get("cmd")?.as_str()?.to_string();
    let out = match cmd.as_str() {
        "get" => cmd_get(),
        "ready" => Some(json!({ "ok": true }).to_string()), // 页面脚本就绪（main 侧消费 pending_page）
        "set" => cmd_set(&v),
        "restore" => cmd_restore(),
        "dict_stats" => Some(json!({ "ok": true, "dict": dict_stats() }).to_string()),
        "dict_export" => cmd_dict_export(),
        "dict_import" => cmd_dict_import(),
        "dict_clear" => cmd_dict_clear(),
        "open_dir" => {
            let _ = std::fs::create_dir_all(appdata());
            open(&appdata());
            Some(json!({ "ok": true }).to_string())
        }
        "open_url" => {
            let url = v.get("url").and_then(|u| u.as_str()).unwrap_or("");
            if url.starts_with("https://") {
                open(PathBuf::from(url));
            }
            Some(json!({ "ok": true }).to_string())
        }
        _ => Some(err_json("unknown cmd")),
    };
    out.map(|s| inject_cmd(s, &cmd))
}

/// 把 cmd 塞进响应对象顶层（应答都是 JSON 对象）
fn inject_cmd(resp: String, cmd: &str) -> String {
    match serde_json::from_str::<Value>(&resp) {
        Ok(mut v) => {
            if let Some(o) = v.as_object_mut() {
                o.insert("cmd".into(), Value::String(cmd.to_string()));
            }
            v.to_string()
        }
        Err(_) => resp,
    }
}

/// 读配置：默认值 + 磁盘覆盖（磁盘优先，未知字段原样保留）
pub fn read_config() -> Value {
    let mut merged: Value = serde_json::from_str(DEFAULTS).unwrap_or_else(|_| json!({}));
    if let Ok(bytes) = std::fs::read(config_path()) {
        if let Ok(disk) = serde_json::from_slice::<Value>(&bytes) {
            if let (Some(m), Some(d)) = (merged.as_object_mut(), disk.as_object()) {
                for (k, v) in d {
                    m.insert(k.clone(), v.clone());
                }
            }
        }
    }
    merged
}

/// 原子写（tmp + rename：TIP 端 mtime 轮询永远读到完整文件）
fn write_config(v: &Value) -> bool {
    let path = config_path();
    if std::fs::create_dir_all(appdata()).is_err() {
        return false;
    }
    let tmp = path.with_extension("json.tmp");
    let data = serde_json::to_vec_pretty(v).unwrap_or_default();
    std::fs::write(&tmp, data).is_ok() && std::fs::rename(&tmp, &path).is_ok()
}

fn cmd_get() -> Option<String> {
    Some(
        json!({
            "ok": true,
            "config": read_config(),
            "meta": meta(),
        })
        .to_string(),
    )
}

fn cmd_set(v: &Value) -> Option<String> {
    let key = v.get("key").and_then(|k| k.as_str()).unwrap_or("");
    if !WRITABLE.contains(&key) {
        return Some(err_json("readonly key"));
    }
    let mut cfg = read_config();
    let Some(obj) = cfg.as_object_mut() else {
        return Some(err_json("config broken"));
    };
    obj.insert(key.to_string(), v.get("value").cloned().unwrap_or(Value::Null));
    if write_config(&cfg) {
        Some(json!({ "ok": true }).to_string())
    } else {
        Some(err_json("write failed"))
    }
}

fn cmd_restore() -> Option<String> {
    let defaults: Value = serde_json::from_str(DEFAULTS).unwrap_or(json!({}));
    if write_config(&defaults) {
        Some(json!({ "ok": true, "config": defaults }).to_string())
    } else {
        Some(err_json("write failed"))
    }
}

fn meta() -> Value {
    let dict = dict_stats();
    json!({
        "version": env!("CARGO_PKG_VERSION"),
        "config_path": config_path().display().to_string(),
        "dict_path": dict_path().display().to_string(),
        "dict": dict,
    })
}

/// 用户词典统计：总行数 / 自定义词（|w）数 / 文件大小
fn dict_stats() -> Value {
    let path = dict_path();
    let Ok(bytes) = std::fs::read(&path) else {
        return json!({ "lines": 0, "words": 0, "bytes": 0, "exists": false });
    };
    let text = String::from_utf8_lossy(&bytes);
    let mut lines = 0usize;
    let mut words = 0usize;
    for l in text.lines() {
        let l = l.trim();
        if l.is_empty() || l.starts_with('#') {
            continue;
        }
        lines += 1;
        if l.ends_with("|w") {
            words += 1;
        }
    }
    json!({ "lines": lines, "words": words, "bytes": bytes.len(), "exists": true })
}

fn cmd_dict_export() -> Option<String> {
    let src = dict_path();
    if !src.exists() {
        return Some(err_json("暂无用户词典（还没有学习记录），先打几个字再来导出吧"));
    }
    let Some(dst) = rfd::FileDialog::new()
        .set_title("导出用户词典")
        .set_file_name("lufly-user-dict.txt")
        .add_filter("文本文件 (*.txt)", &["txt"])
        .save_file()
    else {
        return Some(json!({ "ok": false, "cancelled": true }).to_string());
    };
    match std::fs::copy(&src, &dst) {
        Ok(n) => Some(json!({ "ok": true, "bytes": n, "path": dst.display().to_string() }).to_string()),
        Err(e) => Some(err_json(&e.to_string())),
    }
}

fn cmd_dict_import() -> Option<String> {
    let Some(src) = rfd::FileDialog::new()
        .set_title("导入用户词典")
        .add_filter("文本文件 (*.txt)", &["txt"])
        .pick_file()
    else {
        return Some(json!({ "ok": false, "cancelled": true }).to_string());
    };
    let Ok(imported) = std::fs::read_to_string(&src) else {
        return Some(err_json("读取导入文件失败"));
    };
    // 关键：解析不出任何合法行时绝不落盘。空文件在 TIP 端 reload 是
    // 「清空」语义（clear_user），会把用户已有词库全部抹掉。
    let (imported_rows, bad) = parse_dict(&imported);
    if imported_rows.is_empty() {
        return Some(err_json(
            "导入文件中没有可用的词条，已取消导入（原词库未改动）。\n\
             词典格式为每行：编码|词|次数[|w]",
        ));
    }
    let existing = std::fs::read_to_string(dict_path()).unwrap_or_default();
    let (existing_rows, _) = parse_dict(&existing);
    let merged = merge_rows(&existing_rows, &imported_rows);
    let path = dict_path();
    let _ = std::fs::create_dir_all(appdata());
    let tmp = path.with_extension("txt.tmp");
    // 原子替换：TIP 端 mtime 轮询（≤1s）自动合并进引擎
    if std::fs::write(&tmp, &merged).is_err() || std::fs::rename(&tmp, &path).is_err() {
        return Some(err_json("写入词库文件失败"));
    }
    Some(
        json!({
            "ok": true,
            "added": valid_lines(&merged).saturating_sub(existing_rows.len()),
            "total": valid_lines(&merged),
            "skipped": bad,
            "dict": dict_stats(),
        })
        .to_string(),
    )
}

/// 解析词典行 → (合法行, 坏行数)。坏行跳过。
/// 与引擎 `save_user`/`load_user` 的 code|text|n[|w] 格式严格对齐。
type Row = (String, String, u32, bool);
fn parse_dict(s: &str) -> (Vec<Row>, usize) {
    let mut rows: Vec<Row> = Vec::new();
    let mut bad = 0usize;
    for line in s.lines() {
        let line = line.trim_end_matches('\r');
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut it = line.split('|');
        let (Some(code), Some(word), Some(cnt)) = (it.next(), it.next(), it.next()) else {
            bad += 1;
            continue;
        };
        let flag = match it.next() {
            None => false,
            Some("w") => true,
            _ => { bad += 1; continue; }
        };
        if it.next().is_some() {
            bad += 1;
            continue;
        }
        let Ok(n) = cnt.parse::<u32>() else {
            bad += 1;
            continue;
        };
        if code.is_empty() || word.is_empty() || n == 0 {
            bad += 1;
            continue;
        }
        rows.push((code.to_string(), word.to_string(), n, flag));
    }
    (rows, bad)
}

/// 词典行级合并：同 (code,text,flag) 取更大的 count；保留磁盘学习计数语义。
/// 排序输出（与引擎 save_user 的确定性风格一致）。
fn merge_rows(a: &[Row], b: &[Row]) -> String {
    let mut map: HashMap<(String, String, bool), u32> = HashMap::new();
    for (code, word, n, flag) in a.iter().chain(b.iter()) {
        let e = map
            .entry((code.clone(), word.clone(), *flag))
            .or_insert(0);
        if *n > *e {
            *e = *n;
        }
    }
    let mut rows: Vec<(String, String, u32, bool)> = map
        .into_iter()
        .map(|((c, t, w), n)| (c, t, n, w))
        .collect();
    rows.sort();
    let mut out = String::new();
    for (c, t, n, w) in rows {
        out.push_str(&c);
        out.push('|');
        out.push_str(&t);
        out.push('|');
        out.push_str(&n.to_string());
        if w {
            out.push_str("|w");
        }
        out.push('\n');
    }
    out
}

fn valid_lines(s: &str) -> usize {
    s.lines()
        .filter(|l| !l.trim().is_empty() && !l.trim_start().starts_with('#'))
        .count()
}

fn cmd_dict_clear() -> Option<String> {
    // 确认由 JS 侧做；这里写空文件。TIP 端 reload 判定「空 = clear_user」
    let path = dict_path();
    let _ = std::fs::create_dir_all(appdata());
    let ok = std::fs::write(&path, "").is_ok();
    if ok {
        Some(json!({ "ok": true, "dict": dict_stats() }).to_string())
    } else {
        Some(err_json("write failed"))
    }
}

fn open(p: impl AsRef<std::path::Path>) {
    // explorer 对 URL 参数也能打开浏览器
    let _ = std::process::Command::new("explorer").arg(p.as_ref().as_os_str()).spawn();
}

fn err_json(msg: &str) -> String {
    json!({ "ok": false, "error": msg }).to_string()
}

/// 错误弹窗（WebView2 缺失等致命场景；MessageBoxW）
pub fn message_box(msg: &str, title: &str) {
    use windows::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONWARNING, MB_OK};
    let msg_w: Vec<u16> = msg.encode_utf16().chain(std::iter::once(0)).collect();
    let title_w: Vec<u16> = title.encode_utf16().chain(std::iter::once(0)).collect();
    unsafe {
        MessageBoxW(
            None,
            windows::core::PCWSTR(msg_w.as_ptr()),
            windows::core::PCWSTR(title_w.as_ptr()),
            MB_OK | MB_ICONWARNING,
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merge_takes_bigger_count_and_union() {
        let (a, _) = parse_dict("aa|词一|3\nbb|词二|1|w\n");
        let (b, _) = parse_dict("aa|词一|5\ncc|词三|2|w\n");
        let m = merge_rows(&a, &b);
        assert!(m.contains("aa|词一|5"));
        assert!(m.contains("bb|词二|1|w"));
        assert!(m.contains("cc|词三|2|w"));
        assert_eq!(valid_lines(&m), 3);
    }

    #[test]
    fn import_bad_file_never_produces_empty_dict() {
        // P0 回归：格式不符的文件解析出 0 合法行，调用方必须拒绝落盘
        // （空文件在 TIP 端 = clear_user，会抹掉整本词库）
        let (rows, bad) = parse_dict("这不是词典\nhello world\n");
        assert!(rows.is_empty());
        assert_eq!(bad, 2);
        let (existing, _) = parse_dict("aa|原词|3\n");
        let merged = merge_rows(&existing, &rows);
        assert!(merged.contains("aa|原词|3"), "原词库必须保留");
    }

    #[test]
    fn parse_counts_skipped_bad_lines() {
        let (rows, bad) = parse_dict("aa|好|1\nxx|坏|notnum\nbb|行|2|w\n");
        assert_eq!(bad, 1);
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0], ("aa".into(), "好".into(), 1, false));
        assert_eq!(rows[1], ("bb".into(), "行".into(), 2, true));
    }

    /// schema 真源是 tsf/src/config.rs 的 `const DEFAULT`。编译期把源码
    /// 文本嵌进来做双向比对：加字段/改默认值忘了同步 DEFAULTS 或
    /// WRITABLE，这里立刻红（而不只是「字段存在」的弱检查）。
    #[test]
    fn defaults_match_tsf_schema() {
        const TSF: &str = include_str!("../../tsf/src/config.rs");
        let block = TSF
            .split("const DEFAULT: Config = Config {")
            .nth(1)
            .and_then(|s| s.split("};").next())
            .expect("tsf DEFAULT block not found");
        let mut tsf: std::collections::BTreeMap<&str, &str> = Default::default();
        for line in block.lines() {
            let line = line.trim().trim_end_matches(',');
            if let Some((k, v)) = line.split_once(':') {
                let k = k.trim();
                if !k.is_empty() && !k.starts_with('/') {
                    tsf.insert(k, v.trim());
                }
            }
        }
        let d: Value = serde_json::from_str(DEFAULTS).unwrap();
        let obj = d.as_object().unwrap();

        // 字段集双向相等（忽略 version 这个非设置项）
        let tsf_keys: std::collections::BTreeSet<&str> = tsf.keys().copied().collect();
        let bridge_keys: std::collections::BTreeSet<&str> =
            obj.keys().map(|s| s.as_str()).filter(|k| *k != "version").collect();
        assert_eq!(tsf_keys, bridge_keys, "schema 字段集不一致");
        let writable: std::collections::BTreeSet<&str> = WRITABLE.iter().copied().collect();
        assert_eq!(tsf_keys, writable, "WRITABLE 白名单与 schema 不一致");

        // 默认值逐项相等
        for (k, v) in &tsf {
            let json_v = obj.get(*k).unwrap();
            let expected: Value = match *v {
                "true" => Value::Bool(true),
                "false" => Value::Bool(false),
                n => serde_json::from_str(n).unwrap_or_else(|_| panic!("无法解析 tsf 默认值 {k}={n}")),
            };
            assert_eq!(*json_v, expected, "默认值不一致: {k}");
        }
    }
}
