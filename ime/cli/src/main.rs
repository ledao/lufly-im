//! 小鹭音形引擎测试 REPL / 加词工具。
//!
//! 用法:
//!   lufly-cli [dict路径]            # 交互 REPL: 每行一个按键序列, 逐键回放
//!   lufly-cli addword --word 词 [--code 编码] [--dict 路径] [--user 路径]
//!                                   # ojc 弹窗管线用: 算默认码 + 追加进用户词典
//! 按键约定: 字母/数字/空格 按字面; `<` = 退格; `!` = 清空; `:q` 退出
use std::io::{BufRead, Write};
use std::path::PathBuf;

use lufly_engine::Engine;

fn default_dict() -> PathBuf {
    // 部署态: deb 安装的码表；开发态: ime/data
    let deployed = PathBuf::from("/usr/share/fcitx5/lufly/dict.bin");
    if deployed.exists() {
        return deployed;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("data")
        .join("xiaolu_he_he.bin")
}

fn default_user_dict() -> PathBuf {
    if let Ok(p) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(p).join("lufly/user_dict.txt");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".local/share/lufly/user_dict.txt");
    }
    PathBuf::from("user_dict.txt")
}

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn load_engine_for(args: &[String], what: &str) -> (PathBuf, Engine) {
    let dict_path: PathBuf = arg_value(args, "--dict")
        .map(PathBuf::from)
        .or_else(|| std::env::var("LUFLY_DICT").ok().map(PathBuf::from))
        .unwrap_or_else(default_dict);
    let dict = std::fs::read(&dict_path).unwrap_or_else(|e| {
        eprintln!("{what}: 读取码表失败 {}: {e}", dict_path.display());
        std::process::exit(1);
    });
    let engine = Engine::load(&dict).unwrap_or_else(|e| {
        eprintln!("{what}: 加载码表失败: {e}");
        std::process::exit(1);
    });
    (dict_path, engine)
}

/// derive --word 词: 只推导默认全码输出到 stdout，不写任何文件
/// （加词弹窗在焦点离开词语框时调它自动填编码栏）。
fn run_derive(args: &[String]) {
    let Some(word) = arg_value(args, "--word") else {
        eprintln!("derive: 缺 --word");
        std::process::exit(2);
    };
    let (_, engine) = load_engine_for(args, "derive");
    match engine.derive_word_code(&word) {
        Ok(code) => println!("{code}"),
        Err(e) => {
            eprintln!("derive: {e}");
            std::process::exit(3);
        }
    }
}

fn run_addword(args: &[String]) {
    let Some(word) = arg_value(args, "--word") else {
        eprintln!("addword: 缺 --word");
        std::process::exit(2);
    };
    if word.is_empty() || word.chars().any(|c| c == '|' || c == '\n') {
        eprintln!("addword: 词不能为空且不能含 | 或换行");
        std::process::exit(2);
    }
    let user_code = arg_value(args, "--code").unwrap_or_default();
    if !user_code.is_empty()
        && (user_code.chars().any(|c| !c.is_ascii_lowercase()) || user_code.len() < 2)
    {
        eprintln!("addword: 编码须为 2 位以上小写字母");
        std::process::exit(2);
    }
    let user_path: PathBuf = arg_value(args, "--user")
        .map(PathBuf::from)
        .or_else(|| std::env::var("LUFLY_USER_DICT").ok().map(PathBuf::from))
        .unwrap_or_else(default_user_dict);

    let (_, engine) = load_engine_for(args, "addword");

    // 编码: 用户指定优先，否则按码表规则推导（单字=全码；多字=双拼+首末形码）
    let code = if user_code.is_empty() {
        match engine.derive_word_code(&word) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("addword: {e}；请在弹窗中手动填写编码");
                std::process::exit(3);
            }
        }
    } else {
        user_code
    };

    // 轻量查重: 同 (code,词) 的自定义词已存在则跳过（fcitx5 侧会全量去重落盘）
    if let Ok(text) = std::fs::read_to_string(&user_path) {
        if text.lines().any(|l| {
            let mut it = l.trim_end_matches('\r').split('|');
            it.next() == Some(code.as_str())
                && it.next() == Some(word.as_str())
                && it.next().is_some()
                && it.next() == Some("w")
        }) {
            println!("already");
            return;
        }
    }

    if let Some(parent) = user_path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&user_path)
        .unwrap_or_else(|e| {
            eprintln!("addword: 打开用户词典失败 {}: {e}", user_path.display());
            std::process::exit(1);
        });
    writeln!(f, "{code}|{word}|1|w").unwrap_or_else(|e| {
        eprintln!("addword: 写入失败: {e}");
        std::process::exit(1);
    });
    println!("{code}|{word}");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("addword") => {
            run_addword(&args[2..]);
            return;
        }
        Some("derive") => {
            run_derive(&args[2..]);
            return;
        }
        _ => {}
    }

    let dict_path = args
        .get(1)
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
