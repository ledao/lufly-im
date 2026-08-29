//! 小鹭音形引擎测试 REPL。
//!
//! 用法:
//!   lufly-cli.exe [dict路径]        # 交互: 每行输入一个按键序列, 逐键回放
//!   按键约定: 字母/数字/空格 按字面; `<` = 退格; `!` = 清空; `:q` 退出
use std::io::{BufRead, Write};
use std::path::PathBuf;

use lufly_engine::Engine;

fn default_dict() -> PathBuf {
    // ime/cli → ime/data
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("data")
        .join("xiaolu_he_he.bin")
}

fn main() {
    let dict_path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(default_dict);

    let dict = std::fs::read(&dict_path).unwrap_or_else(|e| {
        eprintln!(
            "读取码表失败 {}: {e}\n请先运行: python ime/tools/build_dict.py",
            dict_path.display()
        );
        std::process::exit(1);
    });
    let mut engine = Engine::load(&dict).unwrap_or_else(|e| {
        eprintln!("加载码表失败: {e}");
        std::process::exit(1);
    });
    println!(
        "小鹭音形 REPL（码表 {} 条）。每行输入按键序列；`<`=退格 `!`=清空 `:q`=退出",
        dict.len()
    );

    let stdin = std::io::stdin();
    let mut line = String::new();
    loop {
        line.clear();
        print!("> ");
        std::io::stdout().flush().ok();
        if stdin.lock().read_line(&mut line).unwrap_or(0) == 0 {
            break;
        }
        let line = line.trim_end_matches(['\r', '\n']);
        if line == ":q" {
            break;
        }
        let mut committed = String::new();
        for c in line.chars() {
            match c {
                '<' => {
                    engine.key('\u{8}');
                }
                '!' => {
                    engine.key('\u{1b}');
                }
                ch => {
                    if let Some(text) = engine.key(ch) {
                        committed.push_str(&text);
                    }
                }
            }
            let input = engine.input();
            print!("  [{input:>8}]");
            let cands = engine.candidates();
            if cands.is_empty() {
                print!(" (无候选)");
            } else {
                for (i, cand) in cands.iter().take(5).enumerate() {
                    let mark = if cand.exact { "" } else { "~" };
                    print!(" {}. {}{}", i + 1, cand.text, mark);
                }
            }
            println!();
        }
        if !committed.is_empty() {
            println!("== 上屏: {committed}");
        }
    }
}
