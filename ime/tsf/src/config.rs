//! 用户设置（%APPDATA%\lufly\config.json，lufly-settings.exe 写入）。
//!
//! - 全字段带默认值：缺文件/缺字段/损坏 = 现行为，老版本升级零迁移。
//! - 进程级一份（所有线程的 Shared 共读），Config: Copy 极小，
//!   读走副本不加 Arc。
//! - 热更新：复用用户词典的 1s mtime 轮询（processor 的
//!   check_user_reload 顺带调 check_reload），改完最迟 1s 生效。
//! - 本模块不调 crate::log（log 开关本身读这里，避免依赖环）。
use std::sync::{Mutex, RwLock};
use std::time::SystemTime;

use serde::Deserialize;

#[derive(Deserialize, Clone, Copy, Debug, PartialEq)]
#[serde(default)]
pub struct Config {
    /// 默认启动模式：true = 英文直通（密码友好）
    pub default_ascii: bool,
    /// 候选页大小（3..=9；数字键 1-N 选词，;'[] 固定选 2-5）
    pub page_size: usize,
    /// Shift 单击切中英
    pub shift_toggle: bool,
    /// 自动造词（连续全码上屏自动成词）
    pub auto_word: bool,
    /// 候选词字号（96dpi 基准；序号/剩余编码按同差值缩放）
    pub cand_font_size: i32,
    /// 候选显示「词 剩余编码」后缀
    pub cand_show_suffix: bool,
    /// 诊断日志（%APPDATA%\lufly\tsf.log）；LUFLY_LOG=1 环境变量强制开
    pub log: bool,
}

impl Default for Config {
    fn default() -> Self {
        DEFAULT
    }
}

const DEFAULT: Config = Config {
    default_ascii: false,
    page_size: 5,
    shift_toggle: true,
    auto_word: true,
    cand_font_size: 17,
    cand_show_suffix: true,
    log: false,
};

static CONFIG: RwLock<Config> = RwLock::new(DEFAULT);
static MTIME: Mutex<Option<SystemTime>> = Mutex::new(None);

/// 当前配置（副本）。读锁内 memcpy，按键路径无感。
pub fn get() -> Config {
    *CONFIG.read().unwrap_or_else(std::sync::PoisonError::into_inner)
}

pub fn path() -> Option<std::path::PathBuf> {
    std::env::var("APPDATA")
        .ok()
        .map(|app| std::path::PathBuf::from(app).join("lufly").join("config.json"))
}

/// 进程内首次使用时从磁盘加载（LuflyTsf::new 调一次）
pub fn init() {
    *MTIME.lock().unwrap_or_else(std::sync::PoisonError::into_inner) = None;
    check_reload();
}

/// mtime 变了才重读（设置端原子写 = tmp+rename，读到的是完整文件）。
/// 多线程各自从按键路径进来也无妨：重读幂等，竞争窗口只多读一次。
pub fn check_reload() {
    let Some(p) = path() else {
        return;
    };
    let Ok(meta) = std::fs::metadata(&p) else {
        return; // 无文件 = 全默认，不用动
    };
    let mtime = meta.modified().ok();
    let mut m = MTIME.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
    if *m == mtime {
        return;
    }
    let Ok(bytes) = std::fs::read(&p) else {
        return;
    };
    let cfg = serde_json::from_slice::<Config>(&bytes).unwrap_or(DEFAULT);
    // 越界值钳回安全区（文件被手改坏也不至于打不了字）
    let cfg = Config {
        page_size: cfg.page_size.clamp(1, 9),
        cand_font_size: cfg.cand_font_size.clamp(12, 28),
        ..cfg
    };
    *CONFIG.write().unwrap_or_else(std::sync::PoisonError::into_inner) = cfg;
    *m = mtime;
}
