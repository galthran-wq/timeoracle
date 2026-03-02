use crate::config::Config;
use crate::error::Result;
use crate::events::{AudioInfo, WindowInfo};

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

#[cfg_attr(test, automock)]
pub trait AudioSource: Send + Sync {
    fn get_active_audio(&self) -> Result<AudioInfo>;
}

#[cfg(target_os = "linux")]
pub mod linux_x11;
#[cfg(target_os = "linux")]
pub mod linux_wayland;
#[cfg(all(target_os = "linux", feature = "audio"))]
pub mod linux_audio;
#[cfg(target_os = "macos")]
pub mod macos;
#[cfg(all(target_os = "macos", feature = "audio"))]
pub mod macos_audio;
pub mod idle;

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

pub fn create_idle_detector() -> Box<dyn IdleDetector> {
    Box::new(idle::SystemIdleDetector::new())
}

pub fn create_audio_source(config: &Config) -> Option<Box<dyn AudioSource>> {
    if !config.audio_capture {
        return None;
    }

    #[cfg(all(target_os = "linux", feature = "audio"))]
    {
        match linux_audio::LinuxAudioSource::new() {
            Ok(source) => return Some(Box::new(source)),
            Err(e) => {
                tracing::warn!("Failed to create audio source: {e}");
                return None;
            }
        }
    }

    #[cfg(all(target_os = "macos", feature = "audio"))]
    {
        return Some(Box::new(macos_audio::MacOSAudioSource::new()));
    }

    #[allow(unreachable_code)]
    None
}
