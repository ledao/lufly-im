//! COM CLSID / Language Profile GUID 常量
#![allow(dead_code)]
use windows::core::GUID;

/// 输入法 TIP 的 COM 类 ID
pub const CLSID_LUFLY_TIP: GUID = GUID::from_u128(0x2E168808_0490_43E1_9481_F2662BB32954);
/// 输入法语言档（简体中文 0x0804 下的小鹭档）
/// 0.5.0 换新 GUID：旧档 {DC8B6C80-...} 的乱码名字曾被 ctfmon 缓存复活，换档斩断
pub const GUID_LUFLY_PROFILE: GUID = GUID::from_u128(0x7C3A1E92_5D4F_4B68_9A2C_E1F0B3D4A5C6);

pub const IME_NAME: &str = "小鹭音形";
