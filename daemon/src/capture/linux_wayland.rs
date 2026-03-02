use crate::capture::ActivitySource;
use crate::error::Result;
use crate::events::WindowInfo;

pub struct WaylandSource;

impl WaylandSource {
    pub fn new() -> Self {
        tracing::warn!("Wayland capture is not yet supported — window tracking will be unavailable");
        Self
    }
}

impl ActivitySource for WaylandSource {
    fn get_active_window(&self) -> Result<Option<WindowInfo>> {
        Ok(None)
    }
}
