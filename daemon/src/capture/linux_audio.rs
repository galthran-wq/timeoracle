use crate::capture::AudioSource;
use crate::error::Result;
use crate::events::{AudioInfo, AudioPlaybackState, AudioStream};
use pulsectl::controllers::AppControl;
use std::collections::HashMap;

const MAX_STREAMS: usize = 10;
const MAX_STRING_LEN: usize = 200;

pub struct LinuxAudioSource;

impl LinuxAudioSource {
    pub fn new() -> Result<Self> {
        Ok(Self)
    }
}

impl AudioSource for LinuxAudioSource {
    fn get_active_audio(&self) -> Result<AudioInfo> {
        let mpris_streams = get_mpris_streams();
        let pulse_streams = get_pulse_streams();

        let mut pulse_by_app: HashMap<String, AudioStream> = HashMap::new();
        for ps in pulse_streams {
            pulse_by_app.entry(ps.app_name.to_lowercase()).or_insert(ps);
        }

        let mut streams = mpris_streams;
        for stream in &mut streams {
            if let Some(pulse_stream) = pulse_by_app.remove(&stream.app_name.to_lowercase()) {
                if stream.volume_percent.is_none() {
                    stream.volume_percent = pulse_stream.volume_percent;
                }
                if !stream.muted {
                    stream.muted = pulse_stream.muted;
                }
            }
        }
        streams.extend(pulse_by_app.into_values());

        streams.truncate(MAX_STREAMS);
        Ok(AudioInfo { streams })
    }
}

fn get_mpris_streams() -> Vec<AudioStream> {
    let finder = match mpris::PlayerFinder::new() {
        Ok(f) => f,
        Err(e) => {
            tracing::debug!("MPRIS finder error: {e}");
            return Vec::new();
        }
    };

    let players = match finder.find_all() {
        Ok(p) => p,
        Err(e) => {
            tracing::debug!("MPRIS find_all error: {e}");
            return Vec::new();
        }
    };

    let mut streams = Vec::new();
    for player in players {
        let status = match player.get_playback_status() {
            Ok(s) => s,
            Err(_) => continue,
        };

        let state = match status {
            mpris::PlaybackStatus::Playing => AudioPlaybackState::Playing,
            mpris::PlaybackStatus::Paused => AudioPlaybackState::Paused,
            mpris::PlaybackStatus::Stopped => continue,
        };

        let metadata = player.get_metadata().ok();
        let title = metadata
            .as_ref()
            .and_then(|m| m.title().map(|s| truncate(s)));
        let artist = metadata
            .as_ref()
            .and_then(|m| m.artists().map(|a| truncate(&a.join(", "))));

        streams.push(AudioStream {
            app_name: truncate(&player.identity()),
            title,
            artist,
            state,
            volume_percent: None,
            muted: false,
        });
    }
    streams
}

fn get_pulse_streams() -> Vec<AudioStream> {
    let mut handler = match pulsectl::controllers::SinkController::create() {
        Ok(h) => h,
        Err(e) => {
            tracing::debug!("PulseAudio connection error: {e}");
            return Vec::new();
        }
    };

    let apps: Vec<pulsectl::controllers::types::ApplicationInfo> = match handler.list_applications()
    {
        Ok(a) => a,
        Err(e) => {
            tracing::debug!("PulseAudio list_applications error: {e}");
            return Vec::new();
        }
    };

    apps.into_iter()
        .filter(|app| !app.corked)
        .map(|app| {
            let app_name = app
                .proplist
                .get_str("application.name")
                .unwrap_or_else(|| app.name.clone().unwrap_or_else(|| "Unknown".into()));

            let volume_percent = if app.has_volume {
                let avg = app.volume.avg().0;
                Some(
                    ((avg as f64 / 0x10000_u32 as f64) * 100.0)
                        .round()
                        .min(255.0) as u8,
                )
            } else {
                None
            };

            AudioStream {
                app_name: truncate(&app_name),
                title: None,
                artist: None,
                state: AudioPlaybackState::Playing,
                volume_percent,
                muted: app.mute,
            }
        })
        .collect()
}

fn truncate(s: &str) -> String {
    if s.len() <= MAX_STRING_LEN {
        s.to_string()
    } else {
        let mut cutoff = MAX_STRING_LEN - 3;
        while !s.is_char_boundary(cutoff) {
            cutoff -= 1;
        }
        format!("{}...", &s[..cutoff])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_truncate_short() {
        assert_eq!(truncate("hello"), "hello");
    }

    #[test]
    fn test_truncate_long() {
        let long = "a".repeat(300);
        let result = truncate(&long);
        assert_eq!(result.len(), MAX_STRING_LEN);
        assert!(result.ends_with("..."));
    }

    #[test]
    fn test_merge_dedup() {
        let mpris = vec![AudioStream {
            app_name: "Spotify".into(),
            title: Some("Song".into()),
            artist: Some("Artist".into()),
            state: AudioPlaybackState::Playing,
            volume_percent: None,
            muted: false,
        }];

        let pulse = vec![
            AudioStream {
                app_name: "spotify".into(),
                title: None,
                artist: None,
                state: AudioPlaybackState::Playing,
                volume_percent: Some(80),
                muted: false,
            },
            AudioStream {
                app_name: "Firefox".into(),
                title: None,
                artist: None,
                state: AudioPlaybackState::Playing,
                volume_percent: Some(50),
                muted: false,
            },
        ];

        let mut pulse_by_app: HashMap<String, AudioStream> = HashMap::new();
        for ps in pulse {
            pulse_by_app.entry(ps.app_name.to_lowercase()).or_insert(ps);
        }
        let mut streams = mpris;
        for stream in &mut streams {
            if let Some(pulse_stream) = pulse_by_app.remove(&stream.app_name.to_lowercase()) {
                if stream.volume_percent.is_none() {
                    stream.volume_percent = pulse_stream.volume_percent;
                }
                if !stream.muted {
                    stream.muted = pulse_stream.muted;
                }
            }
        }
        streams.extend(pulse_by_app.into_values());

        assert_eq!(streams.len(), 2);
        assert_eq!(streams[0].app_name, "Spotify");
        assert!(streams[0].title.is_some());
        assert_eq!(streams[0].volume_percent, Some(80));
        assert_eq!(streams[1].app_name, "Firefox");
    }
}
