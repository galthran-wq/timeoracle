use crate::capture::IdleDetector;
use crate::error::Result;

pub struct SystemIdleDetector;

impl SystemIdleDetector {
    pub fn new() -> Self {
        Self
    }
}

impl IdleDetector for SystemIdleDetector {
    fn get_idle_seconds(&self) -> Result<u64> {
        let idle = user_idle::UserIdle::get_time()
            .map_err(|e| crate::error::DaemonError::Capture(format!("Idle detection failed: {e}")))?;
        Ok(idle.as_seconds() as u64)
    }
}
