//! COM CLSID / Language Profile GUID 常量
#![allow(dead_code)]
use windows::core::GUID;

/// 输入法 TIP 的 COM 类 ID
pub const CLSID_LUFLY_TIP: GUID = GUID::from_u128(0x2E168808_0490_43E1_9481_F2662BB32954);
/// 输入法语言档（简体中文 0x0804 下的小鹭档）
pub const GUID_LUFLY_PROFILE: GUID = GUID::from_u128(0xDC8B6C80_2DC0_435A_B2E8_9830F5F0F50D);

pub const IME_NAME: &str = "小鹭音形";
