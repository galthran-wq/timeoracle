use crate::buffer::EventBuffer;
use crate::capture::{ActivitySource, AudioSource, IdleDetector};
use crate::config::Config;
use crate::error::Result;
use crate::events::{ActivityEvent, AudioInfo, WindowInfo};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::{broadcast, mpsc, watch};

#[derive(Debug, Clone)]
pub enum EngineCommand {
    Pause,
    Resume,
    Quit,
}

#[derive(Debug, Clone, Default)]
pub struct DaemonStatus {
    pub state: DaemonState,
    pub events_buffered: usize,
    pub server_connected: bool,
    pub auth_ok: bool,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub enum DaemonState {
    #[default]
    Capturing,
    Paused,
    Idle,
}

impl std::fmt::Display for DaemonState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DaemonState::Capturing => write!(f, "Capturing"),
            DaemonState::Paused => write!(f, "Paused"),
            DaemonState::Idle => write!(f, "Idle"),
        }
    }
}

pub async fn run(
    config: Config,
    buffer: Arc<Mutex<EventBuffer>>,
    mut cmd_rx: mpsc::Receiver<EngineCommand>,
    status_tx: watch::Sender<DaemonStatus>,
    mut shutdown_rx: broadcast::Receiver<()>,
) -> Result<()> {
    let source = crate::capture::create_activity_source();
    let idle_detector = crate::capture::create_idle_detector();
    let audio_source = crate::capture::create_audio_source(&config);
    run_with(
        config,
        buffer,
        &*source,
        &*idle_detector,
        audio_source.as_deref(),
        &mut cmd_rx,
        &status_tx,
        &mut shutdown_rx,
    )
    .await
}

pub async fn run_with(
    config: Config,
    buffer: Arc<Mutex<EventBuffer>>,
    source: &dyn ActivitySource,
    idle_detector: &dyn IdleDetector,
    audio_source: Option<&dyn AudioSource>,
    cmd_rx: &mut mpsc::Receiver<EngineCommand>,
    status_tx: &watch::Sender<DaemonStatus>,
    shutdown_rx: &mut broadcast::Receiver<()>,
) -> Result<()> {
    let mut paused = false;
    let mut was_idle = false;
    let mut idle_started_at: Option<Instant> = None;
    let mut last_window: Option<WindowInfo> = None;
    let mut last_change_time = Instant::now();
    let poll_duration = tokio::time::Duration::from_secs(config.poll_interval_secs);

    let mut interval = tokio::time::interval(poll_duration);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

    loop {
        tokio::select! {
            _ = shutdown_rx.recv() => {
                tracing::info!("Engine received shutdown signal");
                break;
            }
            Some(cmd) = cmd_rx.recv() => {
                match cmd {
                    EngineCommand::Pause => {
                        paused = true;
                        update_status(status_tx, &buffer, DaemonState::Paused);
                        tracing::info!("Engine paused");
                    }
                    EngineCommand::Resume => {
                        paused = false;
                        update_status(status_tx, &buffer, DaemonState::Capturing);
                        tracing::info!("Engine resumed");
                    }
                    EngineCommand::Quit => {
                        tracing::info!("Engine received quit command");
                        break;
                    }
                }
            }
            _ = interval.tick() => {
                if paused {
                    continue;
                }

                // Check idle
                let idle_secs = idle_detector.get_idle_seconds().unwrap_or(0);
                let is_idle = idle_secs >= config.idle_threshold_secs;

                if is_idle && !was_idle {
                    // Transition to idle
                    was_idle = true;
                    let now = Instant::now();
                    let idle_start = now
                        .checked_sub(Duration::from_secs(idle_secs))
                        .unwrap_or(now);
                    idle_started_at = Some(idle_start);
                    let event = ActivityEvent::idle_start();
                    store_event(&buffer, &event);
                    update_status(status_tx, &buffer, DaemonState::Idle);
                    tracing::debug!("User went idle ({idle_secs}s)");
                    continue;
                }

                if !is_idle && was_idle {
                    // Transition from idle
                    was_idle = false;
                    let idle_duration_secs = idle_started_at
                        .take()
                        .map(|start| start.elapsed().as_secs())
                        .unwrap_or(idle_secs);
                    let event = ActivityEvent::idle_end(idle_duration_secs);
                    store_event(&buffer, &event);
                    last_window = None; // Force re-capture
                    last_change_time = Instant::now();
                    update_status(status_tx, &buffer, DaemonState::Capturing);
                    tracing::debug!("User returned from idle");
                }

                if is_idle {
                    continue;
                }

                // Capture active window
                let window = match source.get_active_window() {
                    Ok(Some(w)) => w,
                    Ok(None) => continue,
                    Err(e) => {
                        tracing::warn!("Failed to get active window: {e}");
                        continue;
                    }
                };

                // Check ignore list
                if config.ignore_apps.iter().any(|app| {
                    window.app_name.to_lowercase().contains(&app.to_lowercase())
                }) {
                    continue;
                }

                // Diff against last window
                let changed = match &last_window {
                    Some(last) => last != &window,
                    None => true,
                };

                if changed {
                    let audio_info = capture_audio(audio_source);
                    let event = ActivityEvent::window_change(window.clone(), audio_info);
                    store_event(&buffer, &event);
                    last_window = Some(window);
                    last_change_time = Instant::now();
                    update_status(status_tx, &buffer, DaemonState::Capturing);
                } else {
                    // Same window — check heartbeat
                    let elapsed = last_change_time.elapsed().as_secs();
                    if elapsed >= config.heartbeat_interval_secs {
                        let audio_info = capture_audio(audio_source);
                        let event = ActivityEvent::heartbeat(window, audio_info);
                        store_event(&buffer, &event);
                        last_change_time = Instant::now();
                    }
                }
            }
        }
    }

    Ok(())
}

fn store_event(buffer: &Arc<Mutex<EventBuffer>>, event: &ActivityEvent) {
    match buffer.lock() {
        Ok(buf) => {
            if let Err(e) = buf.insert(event) {
                tracing::error!("Failed to buffer event: {e}");
            }
        }
        Err(e) => {
            tracing::error!("Failed to lock buffer: {e}");
        }
    }
}

fn capture_audio(audio_source: Option<&dyn AudioSource>) -> Option<AudioInfo> {
    audio_source.and_then(|src| match src.get_active_audio() {
        Ok(info) if !info.streams.is_empty() => Some(info),
        Ok(_) => None,
        Err(e) => {
            tracing::debug!("Audio capture failed: {e}");
            None
        }
    })
}

fn update_status(
    status_tx: &watch::Sender<DaemonStatus>,
    buffer: &Arc<Mutex<EventBuffer>>,
    state: DaemonState,
) {
    let events_buffered = buffer.lock().ok().and_then(|b| b.count().ok()).unwrap_or(0);
    let _ = status_tx.send(DaemonStatus {
        state,
        events_buffered,
        server_connected: false, // Updated by sync task
        auth_ok: true,
        ..Default::default()
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::capture::{MockActivitySource, MockAudioSource, MockIdleDetector};
    use crate::events::{AudioPlaybackState, AudioStream, EventType};
    use std::sync::atomic::{AtomicU64, Ordering};
    use tempfile::TempDir;
    use tokio::sync::{broadcast, mpsc, watch};

    fn test_config() -> Config {
        Config {
            poll_interval_secs: 1,
            heartbeat_interval_secs: 3,
            idle_threshold_secs: 10,
            ignore_apps: vec!["ignored-app".into()],
            ..Config::default()
        }
    }

    fn test_buffer() -> (TempDir, Arc<Mutex<EventBuffer>>) {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("test.db");
        let buf = EventBuffer::open(&path).unwrap();
        (dir, Arc::new(Mutex::new(buf)))
    }

    struct SharedIdleSeconds(AtomicU64);
    impl SharedIdleSeconds {
        fn new(val: u64) -> Arc<Self> {
            Arc::new(Self(AtomicU64::new(val)))
        }
        fn set(&self, val: u64) {
            self.0.store(val, Ordering::SeqCst);
        }
        fn get(&self) -> u64 {
            self.0.load(Ordering::SeqCst)
        }
    }

    #[tokio::test]
    async fn test_window_change_detected() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Firefox".into(),
                window_title: "GitHub".into(),
                url: Some("https://github.com".into()),
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        // Run engine for a short time then shut down
        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        let count = buffer.lock().unwrap().count().unwrap();
        assert!(count >= 1, "Expected at least 1 event, got {count}");

        let events = buffer.lock().unwrap().read_batch(10).unwrap();
        assert_eq!(events[0].1.event_type, EventType::WindowChange);
    }

    #[tokio::test]
    async fn test_same_window_no_duplicate() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Terminal".into(),
                window_title: "bash".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        // Wait for multiple ticks
        tokio::time::sleep(tokio::time::Duration::from_millis(2500)).await;
        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        // Should only have 1 WindowChange, not one per tick
        let events = buffer.lock().unwrap().read_batch(100).unwrap();
        let window_changes: Vec<_> = events
            .iter()
            .filter(|(_, e)| e.event_type == EventType::WindowChange)
            .collect();
        assert_eq!(
            window_changes.len(),
            1,
            "Same window should not produce duplicates"
        );
    }

    #[tokio::test]
    async fn test_ignore_list() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Ignored-App".into(),
                window_title: "secret".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        assert_eq!(
            buffer.lock().unwrap().count().unwrap(),
            0,
            "Ignored app should produce no events"
        );
    }

    #[tokio::test]
    async fn test_idle_transitions() {
        let config = Config {
            poll_interval_secs: 1,
            idle_threshold_secs: 5,
            ..test_config()
        };
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let idle_secs = SharedIdleSeconds::new(0);
        let idle_secs_clone = idle_secs.clone();

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Editor".into(),
                window_title: "file.rs".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle
            .expect_get_idle_seconds()
            .returning(move || Ok(idle_secs_clone.get()));

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        // First tick: active, should get WindowChange
        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;

        // Go idle
        idle_secs.set(10);
        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;

        // Return from idle
        idle_secs.set(0);
        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;

        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        let events = buffer.lock().unwrap().read_batch(100).unwrap();
        let types: Vec<EventType> = events.iter().map(|(_, e)| e.event_type.clone()).collect();

        assert!(
            types.contains(&EventType::WindowChange),
            "Should have WindowChange"
        );
        assert!(
            types.contains(&EventType::IdleStart),
            "Should have IdleStart"
        );
        assert!(types.contains(&EventType::IdleEnd), "Should have IdleEnd");
        let idle_end = events
            .iter()
            .find(|(_, e)| e.event_type == EventType::IdleEnd)
            .unwrap();
        let idle_duration = idle_end.1.idle_duration_secs.unwrap_or(0);
        assert!(
            idle_duration >= 10,
            "Idle duration should include time since last input"
        );
    }

    #[tokio::test]
    async fn test_pause_resume() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "App".into(),
                window_title: "Window".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        // Let it capture one event
        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let count_before = buffer.lock().unwrap().count().unwrap();
        assert!(count_before >= 1);

        // Pause
        cmd_tx.send(EngineCommand::Pause).await.unwrap();
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        assert_eq!(status_rx.borrow().state, DaemonState::Paused);

        let count_paused = buffer.lock().unwrap().count().unwrap();
        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let count_still_paused = buffer.lock().unwrap().count().unwrap();
        assert_eq!(count_paused, count_still_paused, "No events while paused");

        // Resume
        cmd_tx.send(EngineCommand::Resume).await.unwrap();
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        assert_eq!(status_rx.borrow().state, DaemonState::Capturing);

        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn test_quit_command() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (_shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "App".into(),
                window_title: "Win".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                None,
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        cmd_tx.send(EngineCommand::Quit).await.unwrap();

        // Should exit cleanly
        let result = tokio::time::timeout(tokio::time::Duration::from_secs(2), handle).await;
        assert!(result.is_ok(), "Engine should quit promptly");
    }

    #[tokio::test]
    async fn test_audio_info_attached_to_events() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Firefox".into(),
                window_title: "GitHub".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let mut mock_audio = MockAudioSource::new();
        mock_audio.expect_get_active_audio().returning(|| {
            Ok(AudioInfo {
                streams: vec![AudioStream {
                    app_name: "Spotify".into(),
                    title: Some("Test Song".into()),
                    artist: Some("Test Artist".into()),
                    state: AudioPlaybackState::Playing,
                    volume_percent: Some(75),
                    muted: false,
                }],
            })
        });

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                Some(&mock_audio),
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        let events = buffer.lock().unwrap().read_batch(10).unwrap();
        assert!(!events.is_empty());
        let audio = events[0]
            .1
            .audio_info
            .as_ref()
            .expect("Should have audio_info");
        assert_eq!(audio.streams.len(), 1);
        assert_eq!(audio.streams[0].app_name, "Spotify");
        assert_eq!(audio.streams[0].title.as_deref(), Some("Test Song"));
    }

    #[tokio::test]
    async fn test_audio_error_does_not_block_capture() {
        let config = test_config();
        let (_dir, buffer) = test_buffer();
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(1);
        let (_cmd_tx, mut cmd_rx) = mpsc::channel(32);
        let (status_tx, _status_rx) = watch::channel(DaemonStatus::default());

        let mut mock_source = MockActivitySource::new();
        mock_source.expect_get_active_window().returning(|| {
            Ok(Some(WindowInfo {
                app_name: "Editor".into(),
                window_title: "file.rs".into(),
                url: None,
            }))
        });

        let mut mock_idle = MockIdleDetector::new();
        mock_idle.expect_get_idle_seconds().returning(|| Ok(0));

        let mut mock_audio = MockAudioSource::new();
        mock_audio.expect_get_active_audio().returning(|| {
            Err(crate::error::DaemonError::Config(
                "audio unavailable".into(),
            ))
        });

        let buffer_clone = buffer.clone();
        let handle = tokio::spawn(async move {
            run_with(
                config,
                buffer_clone,
                &mock_source,
                &mock_idle,
                Some(&mock_audio),
                &mut cmd_rx,
                &status_tx,
                &mut shutdown_rx,
            )
            .await
        });

        tokio::time::sleep(tokio::time::Duration::from_millis(1500)).await;
        let _ = shutdown_tx.send(());
        handle.await.unwrap().unwrap();

        let count = buffer.lock().unwrap().count().unwrap();
        assert!(
            count >= 1,
            "Window events should still be captured despite audio errors"
        );
        let events = buffer.lock().unwrap().read_batch(10).unwrap();
        assert!(
            events[0].1.audio_info.is_none(),
            "Audio info should be None on error"
        );
    }
}
