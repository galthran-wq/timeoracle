use crate::capture::ActivitySource;
use crate::error::Result;
use crate::events::WindowInfo;

/// Wayland stub — active window capture is not supported on Wayland
/// without compositor-specific protocols (e.g., wlr-foreign-toplevel).
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
