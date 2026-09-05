//! DLL 导出：COM 类工厂入口 + regsvr32 注册/反注册
mod cand;
mod class_factory;
mod edit_session;
mod guids;
mod langbar;
mod processor;
mod state;
mod status;

use std::ffi::c_void;
use std::sync::Mutex;
use std::sync::atomic::{AtomicPtr, Ordering};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::System::Com::*;
use windows::Win32::System::LibraryLoader::GetModuleFileNameW;
use windows::Win32::System::Registry::*;
use windows::Win32::System::SystemServices::DLL_PROCESS_ATTACH;
use windows::Win32::UI::TextServices::{
    CLSID_TF_CategoryMgr, CLSID_TF_InputProcessorProfiles, GUID_TFCAT_DISPLAYATTRIBUTEPROVIDER,
    GUID_TFCAT_TIPCAP_IMMERSIVESUPPORT, GUID_TFCAT_TIPCAP_INPUTMODECOMPARTMENT,
    GUID_TFCAT_TIPCAP_SYSTRAYSUPPORT, GUID_TFCAT_TIPCAP_UIELEMENTENABLED, GUID_TFCAT_TIP_KEYBOARD,
    ITfCategoryMgr, ITfInputProcessorProfiles,
};

use class_factory::ClassFactory;
use guids::{CLSID_LUFLY_TIP, GUID_LUFLY_PROFILE, IME_NAME};

static DLL_INSTANCE: AtomicPtr<c_void> = AtomicPtr::new(std::ptr::null_mut());

/// 后台预载的主码表槽（Engine 是纯数据可跨线程；Shared 含 COM 指针不可）
static PRELOAD: Mutex<Option<lufly_engine::Engine>> = Mutex::new(None);

pub fn take_preload() -> Option<lufly_engine::Engine> {
    PRELOAD.lock().unwrap_or_else(std::sync::PoisonError::into_inner).take()
}

pub fn store_preload(e: Option<lufly_engine::Engine>) {
    *PRELOAD.lock().unwrap_or_else(std::sync::PoisonError::into_inner) = e;
}

/// 诊断日志（%APPDATA%\lufly\tsf.log）：定位激活/按键链路问题用
pub fn log(msg: &str) {
    let Ok(appdata) = std::env::var("APPDATA") else {
        return;
    };
    let dir = std::path::Path::new(&appdata).join("lufly");
    if std::fs::create_dir_all(&dir).is_err() {
        return;
    }
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("tsf.log"))
    {
        use std::io::Write;
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0);
        // 同一日志文件多进程共写（ctfmon/各应用进程都加载本 DLL），pid 前缀必须
        let _ = writeln!(f, "[{ts} pid={}] {msg}", std::process::id());
    }
}

/// FFI 边界兜底: COM 回调内的 panic 一律转错误码并记日志。
/// 本 DLL 注入所有有输入焦点的进程（explorer/UU 远程/微信……），
/// panic 跨 extern "system" 边界 = abort 宿主进程——表现即「任务栏崩溃
/// 重启」「远程软件原地崩」。unwrap/中毒等已逐点消灭，这里是最后防线。
pub fn ffi_guard<T>(what: &str, f: impl FnOnce() -> Result<T>) -> Result<T> {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).unwrap_or_else(|p| {
        let msg = p
            .downcast_ref::<&str>()
            .map(|s| s.to_string())
            .or_else(|| p.downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "?".into());
        log(&format!("PANIC (guarded) in {what}: {msg}"));
        Err(Error::from_hresult(E_FAIL))
    })
}

#[no_mangle]
extern "system" fn DllMain(hinst: HINSTANCE, reason: u32, _reserved: *mut c_void) -> BOOL {
    if reason == DLL_PROCESS_ATTACH {
        DLL_INSTANCE.store(hinst.0, Ordering::SeqCst);
    }
    TRUE
}

#[no_mangle]
extern "system" fn DllGetClassObject(
    rclsid: *const GUID,
    riid: *const GUID,
    ppv: *mut *mut c_void,
) -> HRESULT {
    unsafe {
        if rclsid.is_null() || riid.is_null() || ppv.is_null() {
            return E_INVALIDARG;
        }
        if *rclsid != CLSID_LUFLY_TIP {
            return CLASS_E_CLASSNOTAVAILABLE;
        }
        // 进程身份：区分日志条目来自哪个应用（同一日志文件多进程共写）
        let exe = std::env::current_exe()
            .map(|p| p.display().to_string())
            .unwrap_or_else(|_| "?".into());
        log(&format!("DllGetClassObject pid={} exe={exe}", std::process::id()));
        let factory: IUnknown = ClassFactory.into();
        factory.query(riid, ppv)
    }
}

#[no_mangle]
extern "system" fn DllCanUnloadNow() -> HRESULT {
    // 恒 S_FALSE: 禁止系统中途卸载本 DLL。候选窗/状态浮窗的 wndproc、
    // 全局静态都挂在本模块上，Deactivate 只隐藏不销毁窗口——若允许卸载，
    // 后续窗口消息会跳进已 unmap 的映像，c0000005 杀死宿主进程
    // （事件查看器实证: Faulting module = lufly_tsf.dll_unloaded，
    // explorer/UU 远程崩溃根因）。DLL 常驻到进程退出（本来也按进程缓存），
    // 代价仅 44MB 虚拟映射（码表为共享只读文件页，物理可回收）
    S_FALSE
}

fn dll_path() -> Vec<u16> {
    let mut buf = vec![0u16; 512];
    let hinst = HINSTANCE(DLL_INSTANCE.load(Ordering::SeqCst));
    let len = unsafe { GetModuleFileNameW(Some(hinst.into()), &mut buf) } as usize;
    buf.truncate(len);
    buf
}

/// DLL 所在目录（模式图标文件 lufly-zh.ico / lufly-en.ico 与 DLL 同目录）
pub fn dll_dir() -> Option<std::path::PathBuf> {
    let path = dll_path();
    if path.is_empty() {
        return None;
    }
    let p = std::path::PathBuf::from(String::from_utf16_lossy(&path));
    p.parent().map(|d| d.to_path_buf())
}

fn guid_str(g: &GUID) -> String {
    let d = &g.data4;
    format!(
        "{{{:08X}-{:04X}-{:04X}-{:02X}{:02X}-{:02X}{:02X}{:02X}{:02X}{:02X}{:02X}}}",
        g.data1, g.data2, g.data3, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]
    )
}

fn reg_create(path: &str) -> Result<HKEY> {
    let mut hkey = HKEY::default();
    let path = HSTRING::from(path);
    let res = unsafe {
        RegCreateKeyExW(
            HKEY_LOCAL_MACHINE,
            &path,
            None,
            None,
            REG_OPEN_CREATE_OPTIONS(0),
            KEY_WRITE,
            None,
            &mut hkey,
            None,
        )
    };
    if res.is_err() {
        return Err(Error::from_hresult(HRESULT::from_win32(res.0)));
    }
    Ok(hkey)
}

fn reg_set_str(hkey: &HKEY, name: Option<&str>, value: &str) -> Result<()> {
    let name = name.map(HSTRING::from);
    let mut data: Vec<u8> = value
        .encode_utf16()
        .flat_map(|c| c.to_le_bytes())
        .collect();
    data.extend_from_slice(&[0, 0]);
    let res = unsafe {
        RegSetValueExW(
            *hkey,
            name.as_ref().map_or(PCWSTR::null(), |n| PCWSTR(n.as_ptr())),
            Some(0),
            REG_SZ,
            Some(&data),
        )
    };
    if res.is_err() {
        return Err(Error::from_hresult(HRESULT::from_win32(res.0)));
    }
    Ok(())
}

fn tip_key_path() -> String {
    format!(r"SOFTWARE\Microsoft\CTF\TIP\{}", guid_str(&CLSID_LUFLY_TIP))
}

#[no_mangle]
extern "system" fn DllRegisterServer() -> HRESULT {
    match register_server() {
        Ok(()) => S_OK,
        Err(e) => {
            let _ = unregister_server();
            e.into()
        }
    }
}

fn register_server() -> Result<()> {
    let path = dll_path();
    let path_str = String::from_utf16_lossy(&path);

    // 1. COM 类注册（标准 COM，regsvr32 必需）
    let clsid_key = format!(r"SOFTWARE\Classes\CLSID\{}", guid_str(&CLSID_LUFLY_TIP));
    let hk = reg_create(&clsid_key)?;
    reg_set_str(&hk, None, IME_NAME)?;
    let inproc = reg_create(&format!(r"{clsid_key}\InprocServer32"))?;
    reg_set_str(&inproc, None, &path_str)?;
    reg_set_str(&inproc, Some("ThreadingModel"), "Apartment")?;
    unsafe { let _ = RegCloseKey(hk); let _ = RegCloseKey(inproc); }

    // 2. 语言档与类别: 必须走 TSF COM API（对齐 PIME/libIME2）。
    //    设置界面读 CTF 内部数据，手写 CTF 注册表键不够 —— 名字显示空白、
    //    缺 INPUTMODECOMPARTMENT 类别时输入法会被应用禁用（收不到按键）。
    unsafe {
        CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok()?;

        let profiles: ITfInputProcessorProfiles = CoCreateInstance(
            &CLSID_TF_InputProcessorProfiles, None, CLSCTX_INPROC_SERVER,
        )?;
        profiles.Register(&CLSID_LUFLY_TIP)?;

        // 名字与图标经 AddLanguageProfile 注册（UTF-16）。
        // 实测（0.4.x 注册表取证）：CTF 存 Description 时不按 cch 截断，
        // 而是按 NUL 结尾读 —— 未补 NUL 时名字后混进堆垃圾显示乱码，
        // 所以两个字符串都必须补 NUL 再传（图标路径恰好踩在归零缓冲上才幸免）
        let mut name: Vec<u16> = IME_NAME.encode_utf16().collect();
        name.push(0);
        let mut icon = path.clone();
        icon.push(0);
        profiles.AddLanguageProfile(
            &CLSID_LUFLY_TIP,
            0x0804,
            &GUID_LUFLY_PROFILE,
            &name,
            &icon,
            0,
        )?;

        let categories: ITfCategoryMgr = CoCreateInstance(
            &CLSID_TF_CategoryMgr, None, CLSCTX_INPROC_SERVER,
        )?;
        for cat in [
            GUID_TFCAT_TIP_KEYBOARD,
            GUID_TFCAT_TIPCAP_INPUTMODECOMPARTMENT,
            GUID_TFCAT_TIPCAP_UIELEMENTENABLED,
            GUID_TFCAT_TIPCAP_IMMERSIVESUPPORT,
            GUID_TFCAT_TIPCAP_SYSTRAYSUPPORT,
            GUID_TFCAT_DISPLAYATTRIBUTEPROVIDER,
        ] {
            categories.RegisterCategory(&CLSID_LUFLY_TIP, &cat, &CLSID_LUFLY_TIP)?;
        }
    }

    // 注意：不要再手写 LanguageProfile\0x0804\Enable —— AddLanguageProfile 已建
    // 0x00000804 键，再手写一份 0x0804 会产生重复 profile，语言栏渲染错乱
    Ok(())
}

fn reg_delete_tree(path: &str) -> u32 {
    let p = HSTRING::from(path);
    unsafe { RegDeleteTreeW(HKEY_LOCAL_MACHINE, &p).0 }
}

#[no_mangle]
extern "system" fn DllUnregisterServer() -> HRESULT {
    match unregister_server() {
        Ok(()) => S_OK,
        Err(e) => e.into(),
    }
}

fn unregister_server() -> Result<()> {
    unsafe {
        let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
        if let Ok(categories) = CoCreateInstance::<_, ITfCategoryMgr>(
            &CLSID_TF_CategoryMgr, None, CLSCTX_INPROC_SERVER,
        ) {
            for cat in [
                GUID_TFCAT_TIP_KEYBOARD,
                GUID_TFCAT_TIPCAP_INPUTMODECOMPARTMENT,
                GUID_TFCAT_TIPCAP_UIELEMENTENABLED,
                GUID_TFCAT_TIPCAP_IMMERSIVESUPPORT,
                GUID_TFCAT_TIPCAP_SYSTRAYSUPPORT,
                GUID_TFCAT_DISPLAYATTRIBUTEPROVIDER,
            ] {
                let _ = categories.UnregisterCategory(&CLSID_LUFLY_TIP, &cat, &CLSID_LUFLY_TIP);
            }
        }
        if let Ok(profiles) = CoCreateInstance::<_, ITfInputProcessorProfiles>(
            &CLSID_TF_InputProcessorProfiles, None, CLSCTX_INPROC_SERVER,
        ) {
            let _ = profiles.Unregister(&CLSID_LUFLY_TIP);
        }
    }
    let r1 = reg_delete_tree(&tip_key_path());
    let r2 = reg_delete_tree(&format!(r"SOFTWARE\Classes\CLSID\{}", guid_str(&CLSID_LUFLY_TIP)));
    let _ = (r1, r2);
    Ok(())
}
