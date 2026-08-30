//! 语言栏托盘项 —— 对齐 weasel CLangBarItemButton（TF_LBI_STYLE_SHOWNINTRAY）。
//! 两个托盘项：
//!   1. 小鹭 logo（静态指示，点击暂无动作）
//!   2. 中/EN 模式按钮（左键 = Shift 单击同款切换；图标随模式刷新）
//!
//! 图标以文件方式加载（LR_LOADFROMFILE），与 DLL 同目录，
//! 由安装器落盘：lufly.ico（logo）/ lufly-zh.ico / lufly-en.ico。
#![allow(non_snake_case)]

use std::sync::{Arc, Mutex};

use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::System::Variant::{VARIANT, VT_I4};
use windows::Win32::UI::TextServices::*;
use windows::Win32::UI::WindowsAndMessaging::*;

/// 托盘项 GUID（仅需与 TIP 内唯一）
pub const GUID_LBI_LOGO: GUID = GUID::from_u128(0x6F4A9B2E_3C8D_4E71_A5F6_1D2B3C4D5E6F);
pub const GUID_LBI_MODE: GUID = GUID::from_u128(0x8C7D6E5F_4A3B_4F29_B1A0_9F8E7D6C5B4A);

const ICON_LOGO: &str = "lufly.ico";
const ICON_ZH: &str = "lufly-zh.ico";
const ICON_EN: &str = "lufly-en.ico";

const ITEM_COOKIE: u32 = 0x4C46; // "LF"

/// 模式项的刷新回调句柄：系统经 AdviseSink 把 ITfLangBarItemSink 交给我们，
/// 图标变化时调 OnUpdate(TF_LBI_ICON)，系统会回头取新 GetIcon。
/// Shift 切换路径拿不到按钮实例，走这个全局槽。
/// COM 接口指针实际只在 STA 线程使用，包装成 Send 以放全局槽。
struct SendSink(ITfLangBarItemSink);
unsafe impl Send for SendSink {}
static MODE_SINK: Mutex<Option<SendSink>> = Mutex::new(None);

#[derive(Clone, Copy, PartialEq)]
pub enum Kind {
    Logo,
    Mode,
}

#[implement(ITfLangBarItemButton, ITfSource)]
pub struct LangItem {
    kind: Kind,
    guid_item: GUID,
    shared: Arc<Mutex<crate::processor::Shared>>,
}

impl LangItem {
    pub fn new(
        kind: Kind,
        guid_item: GUID,
        shared: Arc<Mutex<crate::processor::Shared>>,
    ) -> Self {
        Self { kind, guid_item, shared }
    }

    fn desc(&self) -> &'static str {
        match self.kind {
            Kind::Logo => "小鹭音形",
            Kind::Mode => "小鹭音形 中英",
        }
    }

    fn icon_file(&self) -> &'static str {
        match self.kind {
            Kind::Logo => ICON_LOGO,
            Kind::Mode => {
                let en = self.shared.lock().unwrap().st.ascii;
                if en {
                    ICON_EN
                } else {
                    ICON_ZH
                }
            }
        }
    }
}

impl ITfLangBarItemButton_Impl for LangItem_Impl {
    fn OnClick(&self, click: TfLBIClick, _pt: &POINT, _prcarea: *const RECT) -> Result<()> {
        if click != TF_LBI_CLK_LEFT || self.kind != Kind::Mode {
            return Ok(()); // logo 点击暂无动作；右键忽略
        }
        // 与 Shift 单击同款切换（空闲路径）：断链、翻转、闪浮窗、刷新图标
        let new_ascii = {
            let mut s = self.shared.lock().unwrap();
            s.st.pending.clear();
            s.st.auto_buf.clear();
            s.st.reverse = false;
            s.st.last_cls = 0;
            s.st.ascii = !s.st.ascii;
            s.st.ascii
        };
        crate::status::flash(new_ascii);
        crate::log(&format!(
            "langbar switch to {}",
            if new_ascii { "EN" } else { "CN" }
        ));
        {
            let s = self.shared.lock().unwrap();
            set_conversion(&s, new_ascii);
        }
        notify_mode_changed();
        Ok(())
    }

    fn InitMenu(&self, _pmenu: windows_core::Ref<'_, ITfMenu>) -> Result<()> {
        Ok(()) // 无菜单样式，不会被调
    }

    fn OnMenuSelect(&self, _wid: u32) -> Result<()> {
        Ok(())
    }

    fn GetIcon(&self) -> Result<HICON> {
        let Some(dir) = crate::dll_dir() else {
            return Err(Error::from_hresult(E_FAIL));
        };
        let path = dir.join(self.icon_file());
        let mut path_w: Vec<u16> = path.as_os_str().to_string_lossy().encode_utf16().collect();
        path_w.push(0);
        let h = unsafe {
            LoadImageW(
                None,
                PCWSTR(path_w.as_ptr()),
                IMAGE_ICON,
                GetSystemMetrics(SM_CXSMICON),
                GetSystemMetrics(SM_CYSMICON),
                LR_LOADFROMFILE,
            )
        }?;
        Ok(HICON(h.0))
    }

    fn GetText(&self) -> Result<BSTR> {
        Ok(BSTR::from(self.desc()))
    }
}

// ITfLangBarItem（父接口）
impl ITfLangBarItem_Impl for LangItem_Impl {
    fn GetInfo(&self, pinfo: *mut TF_LANGBARITEMINFO) -> Result<()> {
        let info = unsafe { pinfo.as_mut() }.ok_or_else(|| Error::from_hresult(E_POINTER))?;
        info.clsidService = crate::guids::CLSID_LUFLY_TIP;
        info.guidItem = self.guid_item;
        info.dwStyle = TF_LBI_STYLE_BTN_BUTTON | TF_LBI_STYLE_SHOWNINTRAY;
        info.ulSort = match self.kind {
            Kind::Logo => 1,
            Kind::Mode => 2,
        };
        info.szDescription = [0; 32];
        let desc: Vec<u16> = self.desc().encode_utf16().collect();
        let n = desc.len().min(31);
        info.szDescription[..n].copy_from_slice(&desc[..n]);
        Ok(())
    }

    fn GetStatus(&self) -> Result<u32> {
        Ok(0)
    }

    fn Show(&self, _fshow: BOOL) -> Result<()> {
        Ok(())
    }

    fn GetTooltipString(&self) -> Result<BSTR> {
        Ok(BSTR::from(match self.kind {
            Kind::Logo => "小鹭音形输入法",
            Kind::Mode => "点击切换中/英文",
        }))
    }
}

// ITfSource：系统经它把 ITfLangBarItemSink 挂进来
impl ITfSource_Impl for LangItem_Impl {
    fn AdviseSink(
        &self,
        riid: *const GUID,
        punk: windows_core::Ref<'_, IUnknown>,
    ) -> Result<u32> {
        let riid = unsafe { riid.as_ref() }.ok_or_else(|| Error::from_hresult(E_POINTER))?;
        if *riid != ITfLangBarItemSink::IID {
            return Err(Error::from_hresult(HRESULT(0x80040202u32 as i32))); // CONNECT_E_CANNOTCONNECT
        }
        let sink: ITfLangBarItemSink = punk
            .as_ref()
            .ok_or_else(|| Error::from_hresult(E_POINTER))?
            .cast()?;
        if self.kind == Kind::Mode {
            *MODE_SINK.lock().unwrap() = Some(SendSink(sink));
        }
        Ok(ITEM_COOKIE)
    }

    fn UnadviseSink(&self, dwcookie: u32) -> Result<()> {
        if dwcookie == ITEM_COOKIE && self.kind == Kind::Mode {
            *MODE_SINK.lock().unwrap() = None;
        }
        Ok(())
    }
}

/// Shift 切换后刷新任务栏模式图标
pub fn notify_mode_changed() {
    let sink = MODE_SINK.lock().unwrap().as_ref().map(|w| w.0.clone());
    if let Some(s) = sink {
        unsafe {
            let _ = s.OnUpdate(TF_LBI_ICON | TF_LBI_STATUS);
        }
    }
}

/// 反注册时清掉全局 sink，避免悬挂
pub fn clear_sink() {
    *MODE_SINK.lock().unwrap() = None;
}

/// 同步 GUID_COMPARTMENT_KEYBOARD_INPUTMODE_CONVERSION（对齐 weasel）：
/// 中文 = TF_CONVERSIONMODE_NATIVE，英文 = 0。让系统与应用感知当前模式。
pub fn set_conversion(shared: &crate::processor::Shared, ascii: bool) {
    let Some(tm) = &shared.thread_mgr else {
        return;
    };
    let Ok(cm) = tm.cast::<ITfCompartmentMgr>() else {
        return;
    };
    let Ok(compartment) = (unsafe { cm.GetCompartment(&GUID_COMPARTMENT_KEYBOARD_INPUTMODE_CONVERSION) }) else {
        return;
    };
    let mut v = VARIANT::default();
    unsafe {
        // VT_I4 手工构造（windows-rs 0.61 无 From<u32>）
        (*v.Anonymous.Anonymous).vt = VT_I4;
        (*v.Anonymous.Anonymous).Anonymous.lVal = if ascii { 0 } else { 1 };
        let _ = compartment.SetValue(shared.client_id, &v);
    }
}
