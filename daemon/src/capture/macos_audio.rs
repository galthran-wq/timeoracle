use crate::capture::AudioSource;
use crate::error::Result;
use crate::events::AudioInfo;

pub struct MacOSAudioSource;

impl MacOSAudioSource {
    pub fn new() -> Self {
        tracing::warn!("macOS audio capture is not yet supported");
        Self
    }
}

impl AudioSource for MacOSAudioSource {
    fn get_active_audio(&self) -> Result<AudioInfo> {
        Ok(AudioInfo::default())
    }
}
