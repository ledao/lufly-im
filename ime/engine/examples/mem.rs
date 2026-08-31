//! 内存占用验证: 走真实码表的 mmap 加载路径（与 macOS 输入法进程同款）。
//! 运行: cargo run -p lufly-engine --example mem --release
//! 测量: 打印 pid 后在其 sleep 窗口内 `vmmap <pid>` 看 Physical footprint。
use lufly_engine::Engine;

fn main() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../data/xiaolu_he_he.bin");
    let mut engine = Engine::open_mmap(path).expect("dict");
    for c in "ma".chars() {
        engine.key(c);
    }
    println!("'ma' 候选数 = {}", engine.candidates().len());
    println!("pid = {}", std::process::id());
    std::thread::sleep(std::time::Duration::from_secs(30));
}
