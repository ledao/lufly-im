//! DLL 导出：COM 类工厂入口 + regsvr32 注册/反注册
mod class_factory;
mod edit_session;
mod guids;
mod processor;

use std::ffi::c_void;
use std::sync::atomic::{AtomicPtr, Ordering};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::System::LibraryLoader::GetModuleFileNameW;
use windows::Win32::System::Registry::*;
use windows::Win32::System::SystemServices::DLL_PROCESS_ATTACH;

use class_factory::ClassFactory;
use guids::{CLSID_LUFLY_TIP, GUID_LUFLY_PROFILE, IME_NAME};

static DLL_INSTANCE: AtomicPtr<c_void> = AtomicPtr::new(std::ptr::null_mut());

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
        let factory: IUnknown = ClassFactory.into();
        factory.query(riid, ppv)
    }
}

#[no_mangle]
extern "system" fn DllCanUnloadNow() -> HRESULT {
    S_OK
}

fn dll_path() -> Vec<u16> {
    let mut buf = vec![0u16; 512];
    let hinst = HINSTANCE(DLL_INSTANCE.load(Ordering::SeqCst));
    let len = unsafe { GetModuleFileNameW(Some(hinst.into()), &mut buf) } as usize;
    buf.truncate(len);
    buf
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

fn reg_set_u32(hkey: &HKEY, name: Option<&str>, value: u32) -> Result<()> {
    let name = name.map(HSTRING::from);
    let res = unsafe {
        RegSetValueExW(
            *hkey,
            name.as_ref().map_or(PCWSTR::null(), |n| PCWSTR(n.as_ptr())),
            Some(0),
            REG_DWORD,
            Some(&value.to_le_bytes()),
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

/// TIP 类别（系统通用 GUID）
const CAT_TIP_KEYBOARD: &str = "{34745CFF-B564-4C63-BC4F-5FE7EB2946A8}";
const CAT_IMMERSIVE_SUPPORT: &str = "{13A016DF-6C8F-4C47-99EA-9EB1B1C4A9B3}";
const CAT_SYSTRAY_SUPPORT: &str = "{25517FB3-3F9F-4BF5-8C54-51F02C1F9971}";

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

    // 1. COM 类注册
    let clsid_key = format!(r"SOFTWARE\Classes\CLSID\{}", guid_str(&CLSID_LUFLY_TIP));
    let hk = reg_create(&clsid_key)?;
    reg_set_str(&hk, None, IME_NAME)?;
    let inproc = reg_create(&format!(r"{clsid_key}\InprocServer32"))?;
    reg_set_str(&inproc, None, &path_str)?;
    reg_set_str(&inproc, Some("ThreadingModel"), "Apartment")?;
    unsafe { let _ = RegCloseKey(hk); let _ = RegCloseKey(inproc); }

    // 2. CTF TIP 注册
    let tip = reg_create(&tip_key_path())?;
    reg_set_str(&tip, None, IME_NAME)?;

    // 2.1 类别
    for cat in [CAT_TIP_KEYBOARD, CAT_IMMERSIVE_SUPPORT, CAT_SYSTRAY_SUPPORT] {
        let ck = reg_create(&format!(r"{}\Category\Category\{cat}", tip_key_path()))?;
        unsafe { let _ = RegCloseKey(ck); }
        let ik = reg_create(&format!(r"{}\Category\Instance\{cat}", tip_key_path()))?;
        reg_set_str(&ik, None, &path_str)?;
        unsafe { let _ = RegCloseKey(ik); }
    }

    // 2.2 简体中文(0x0804)语言档
    let lp = reg_create(&format!(
        r"{}\LanguageProfile\0x0804\{}",
        tip_key_path(),
        guid_str(&GUID_LUFLY_PROFILE)
    ))?;
    reg_set_str(&lp, Some("Description"), IME_NAME)?;
    reg_set_u32(&lp, Some("Enable"), 1)?;
    reg_set_str(&lp, Some("IconFile"), &path_str)?;
    reg_set_u32(&lp, Some("IconIndex"), 0)?;
    unsafe { let _ = RegCloseKey(lp); let _ = RegCloseKey(tip); }

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
    let r1 = reg_delete_tree(&tip_key_path());
    let r2 = reg_delete_tree(&format!(r"SOFTWARE\Classes\CLSID\{}", guid_str(&CLSID_LUFLY_TIP)));
    if r1 != 0 || r2 != 0 {
        // 键不存在等情形容忍; 只在明确失败时返回错误
    }
    Ok(())
}
