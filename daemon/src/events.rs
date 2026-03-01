use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct WindowInfo {
    pub app_name: String,
    pub window_title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AudioPlaybackState {
    Playing,
    Paused,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AudioStream {
    pub app_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub artist: Option<String>,
    pub state: AudioPlaybackState,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub volume_percent: Option<u8>,
    pub muted: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct AudioInfo {
    pub streams: Vec<AudioStream>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    WindowChange,
    Heartbeat,
    IdleStart,
    IdleEnd,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActivityEvent {
    pub id: Uuid,
    pub event_type: EventType,
    pub timestamp: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_info: Option<WindowInfo>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub idle_duration_secs: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_info: Option<AudioInfo>,
}

impl ActivityEvent {
    pub fn window_change(window: WindowInfo, audio: Option<AudioInfo>) -> Self {
        Self {
            id: Uuid::new_v4(),
            event_type: EventType::WindowChange,
            timestamp: Utc::now(),
            window_info: Some(window),
            idle_duration_secs: None,
            audio_info: audio,
        }
    }

    pub fn heartbeat(window: WindowInfo, audio: Option<AudioInfo>) -> Self {
        Self {
            id: Uuid::new_v4(),
            event_type: EventType::Heartbeat,
            timestamp: Utc::now(),
            window_info: Some(window),
            idle_duration_secs: None,
            audio_info: audio,
        }
    }

    pub fn idle_start() -> Self {
        Self {
            id: Uuid::new_v4(),
            event_type: EventType::IdleStart,
            timestamp: Utc::now(),
            window_info: None,
            idle_duration_secs: None,
            audio_info: None,
        }
    }

    pub fn idle_end(idle_duration_secs: u64) -> Self {
        Self {
            id: Uuid::new_v4(),
            event_type: EventType::IdleEnd,
            timestamp: Utc::now(),
            window_info: None,
            idle_duration_secs: Some(idle_duration_secs),
            audio_info: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_window_change_event() {
        let window = WindowInfo {
            app_name: "Firefox".into(),
            window_title: "GitHub".into(),
            url: Some("https://github.com".into()),
        };
        let event = ActivityEvent::window_change(window.clone(), None);
        assert_eq!(event.event_type, EventType::WindowChange);
        assert_eq!(event.window_info.as_ref().unwrap(), &window);
        assert!(event.idle_duration_secs.is_none());
        assert!(event.audio_info.is_none());
    }

    #[test]
    fn test_heartbeat_event() {
        let window = WindowInfo {
            app_name: "VSCode".into(),
            window_title: "main.rs".into(),
            url: None,
        };
        let event = ActivityEvent::heartbeat(window, None);
        assert_eq!(event.event_type, EventType::Heartbeat);
        assert!(event.window_info.is_some());
    }

    #[test]
    fn test_idle_events() {
        let start = ActivityEvent::idle_start();
        assert_eq!(start.event_type, EventType::IdleStart);
        assert!(start.window_info.is_none());
        assert!(start.idle_duration_secs.is_none());

        let end = ActivityEvent::idle_end(600);
        assert_eq!(end.event_type, EventType::IdleEnd);
        assert_eq!(end.idle_duration_secs, Some(600));
    }

    #[test]
    fn test_serde_roundtrip() {
        let window = WindowInfo {
            app_name: "Firefox".into(),
            window_title: "Test".into(),
            url: Some("https://example.com".into()),
        };
        let event = ActivityEvent::window_change(window, None);
        let json = serde_json::to_string(&event).unwrap();
        let deserialized: ActivityEvent = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.id, event.id);
        assert_eq!(deserialized.event_type, event.event_type);
        assert_eq!(deserialized.window_info, event.window_info);
    }

    #[test]
    fn test_serde_roundtrip_with_audio() {
        let window = WindowInfo {
            app_name: "Firefox".into(),
            window_title: "YouTube".into(),
            url: None,
        };
        let audio = AudioInfo {
            streams: vec![AudioStream {
                app_name: "Spotify".into(),
                title: Some("Test Song".into()),
                artist: Some("Test Artist".into()),
                state: AudioPlaybackState::Playing,
                volume_percent: Some(75),
                muted: false,
            }],
        };
        let event = ActivityEvent::window_change(window, Some(audio));
        let json = serde_json::to_string(&event).unwrap();
        let deserialized: ActivityEvent = serde_json::from_str(&json).unwrap();
        let audio_info = deserialized.audio_info.unwrap();
        assert_eq!(audio_info.streams.len(), 1);
        assert_eq!(audio_info.streams[0].app_name, "Spotify");
        assert_eq!(audio_info.streams[0].title.as_deref(), Some("Test Song"));
        assert_eq!(audio_info.streams[0].state, AudioPlaybackState::Playing);
    }

    #[test]
    fn test_event_type_serde() {
        let json = serde_json::to_string(&EventType::WindowChange).unwrap();
        assert_eq!(json, "\"window_change\"");

        let json = serde_json::to_string(&EventType::IdleStart).unwrap();
        assert_eq!(json, "\"idle_start\"");

        let back: EventType = serde_json::from_str("\"heartbeat\"").unwrap();
        assert_eq!(back, EventType::Heartbeat);
    }

    #[test]
    fn test_window_info_url_skip_none() {
        let w = WindowInfo {
            app_name: "Terminal".into(),
            window_title: "bash".into(),
            url: None,
        };
        let json = serde_json::to_string(&w).unwrap();
        assert!(!json.contains("url"));
    }
}
