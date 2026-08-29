//! IClassFactory：regsvr32 / CTF 激活 TIP 时创建 LuflyTsf 实例
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::System::Com::*;

use crate::processor::LuflyTsf;

#[implement(IClassFactory)]
pub struct ClassFactory;

impl IClassFactory_Impl for ClassFactory_Impl {
    fn CreateInstance(
        &self,
        punkouter: Ref<'_, IUnknown>,
        riid: *const GUID,
        ppvobject: *mut *mut core::ffi::c_void,
    ) -> Result<()> {
        if !punkouter.is_null() {
            return Err(Error::from_hresult(CLASS_E_NOAGGREGATION));
        }
        let tip: IUnknown = LuflyTsf::new().into();
        unsafe { tip.query(riid, ppvobject).ok() }
    }

    fn LockServer(&self, _flock: BOOL) -> Result<()> {
        Ok(())
    }
}
