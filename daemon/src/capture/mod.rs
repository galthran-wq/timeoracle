use crate::error::Result;
use crate::events::WindowInfo;

#[cfg(test)]
use mockall::automock;

#[cfg_attr(test, automock)]
pub trait ActivitySource: Send + Sync {
    fn get_active_window(&self) -> Result<Option<WindowInfo>>;
}

#[cfg_attr(test, automock)]
pub trait IdleDetector: Send + Sync {
    fn get_idle_seconds(&self) -> Result<u64>;
}

#[cfg(target_os = "linux")]
pub mod linux_x11;
#[cfg(target_os = "linux")]
pub mod linux_wayland;
#[cfg(target_os = "macos")]
pub mod macos;
pub mod idle;

/// Create the appropriate ActivitySource for the current platform.
pub fn create_activity_source() -> Box<dyn ActivitySource> {
    #[cfg(target_os = "linux")]
    {
        if std::env::var("DISPLAY").is_ok() {
            match linux_x11::X11Source::new() {
                Ok(source) => return Box::new(source),
                Err(e) => {
                    tracing::warn!("Failed to create X11 source: {e}, trying Wayland");
                }
            }
        }
        Box::new(linux_wayland::WaylandSource::new())
    }

    #[cfg(target_os = "macos")]
    {
        Box::new(macos::MacOSSource::new())
    }

    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    {
        compile_error!("Unsupported platform");
    }
}

/// Create the idle detector for the current platform.
pub fn create_idle_detector() -> Box<dyn IdleDetector> {
    Box::new(idle::SystemIdleDetector::new())
}
