use crate::capture::ActivitySource;
use crate::error::Result;
use crate::events::WindowInfo;

/// macOS stub — not yet implemented.
pub struct MacOSSource;

impl MacOSSource {
    pub fn new() -> Self {
        tracing::warn!("macOS capture is not yet implemented");
        Self
    }
}

impl ActivitySource for MacOSSource {
    fn get_active_window(&self) -> Result<Option<WindowInfo>> {
        Ok(None)
    }
}
