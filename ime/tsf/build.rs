//! 构建脚本: 把天鹅图标嵌入 DLL 资源（任务栏/输入法切换器显示用；
//! AddLanguageProfile 的 icon 参数指向本 DLL + index 0）

fn main() {
    // 资源只在 Windows 目标编译；lufly.ico 由 fcitx5/data/lufly.png 转换而来
    if std::env::var("CARGO_CFG_WINDOWS").is_ok() {
        match winresource::WindowsResource::new().set_icon("lufly.ico").compile() {
            Ok(()) => {}
            Err(e) => {
                // 缺 rc.exe 等工具链问题时不要阻塞编译，只是没图标
                println!("cargo:warning=embed icon failed: {e}");
            }
        }
    }
}
