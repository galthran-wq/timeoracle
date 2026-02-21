use crate::buffer::EventBuffer;
use crate::config::Config;
use crate::error::{DaemonError, Result};
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;

const MAX_BACKOFF_SECS: u64 = 300; // 5 minutes
const MAX_BUFFER_EVENTS: usize = 100_000;
const CLEANUP_AGE_DAYS: u32 = 7;

pub async fn run(
    config: Config,
    buffer: Arc<Mutex<EventBuffer>>,
    mut shutdown_rx: broadcast::Receiver<()>,
) -> Result<()> {
    let client = reqwest::Client::new();
    let flush_interval = tokio::time::Duration::from_secs(config.flush_interval_secs);
    let mut interval = tokio::time::interval(flush_interval);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

    let mut backoff_secs: u64 = 0;

    loop {
        tokio::select! {
            _ = shutdown_rx.recv() => {
                tracing::info!("Sync task received shutdown signal");
                // Final flush attempt
                let _ = flush_once(&config, &buffer, &client).await;
                break;
            }
            _ = interval.tick() => {
                if backoff_secs > 0 {
                    tracing::debug!("Backing off for {backoff_secs}s");
                    tokio::select! {
                        _ = tokio::time::sleep(tokio::time::Duration::from_secs(backoff_secs)) => {}
                        _ = shutdown_rx.recv() => {
                            let _ = flush_once(&config, &buffer, &client).await;
                            break;
                        }
                    }
                }

                match flush_once(&config, &buffer, &client).await {
                    Ok(flushed) => {
                        if flushed > 0 {
                            tracing::info!("Flushed {flushed} events to server");
                        }
                        backoff_secs = 0;
                    }
                    Err(DaemonError::TokenExpired) => {
                        tracing::warn!("Auth token expired — please re-login");
                        backoff_secs = MAX_BACKOFF_SECS; // Wait longer on auth errors
                    }
                    Err(e) => {
                        tracing::warn!("Sync failed: {e}");
                        backoff_secs = std::cmp::min(
                            if backoff_secs == 0 { 1 } else { backoff_secs * 2 },
                            MAX_BACKOFF_SECS,
                        );
                    }
                }

                // Periodic cleanup
                if let Ok(buf) = buffer.lock() {
                    let _ = buf.cleanup_old(CLEANUP_AGE_DAYS);
                    let _ = buf.cleanup_excess(MAX_BUFFER_EVENTS);
                }
            }
        }
    }

    Ok(())
}

async fn flush_once(
    config: &Config,
    buffer: &Arc<Mutex<EventBuffer>>,
    client: &reqwest::Client,
) -> Result<usize> {
    let batch = {
        let buf = buffer
            .lock()
            .map_err(|e| DaemonError::Buffer(format!("Lock poisoned: {e}")))?;
        buf.read_batch(config.flush_batch_size)?
    };

    if batch.is_empty() {
        return Ok(0);
    }

    let token = config
        .auth_token
        .as_ref()
        .ok_or(DaemonError::Auth("No auth token".into()))?;

    if crate::auth::is_token_expired(token) {
        return Err(DaemonError::TokenExpired);
    }

    let events: Vec<_> = batch.iter().map(|(_, event)| event).collect();
    let ids: Vec<String> = batch.iter().map(|(id, _)| id.clone()).collect();

    let resp = client
        .post(format!("{}/api/activity/events", config.server_url))
        .bearer_auth(token)
        .json(&events)
        .send()
        .await?;

    let status = resp.status();
    if status == reqwest::StatusCode::UNAUTHORIZED {
        return Err(DaemonError::TokenExpired);
    }

    if !status.is_success() {
        let body = resp.text().await.unwrap_or_default();
        return Err(DaemonError::Sync(format!(
            "Server returned {status}: {body}"
        )));
    }

    // Delete flushed events
    let buf = buffer
        .lock()
        .map_err(|e| DaemonError::Buffer(format!("Lock poisoned: {e}")))?;
    buf.delete_batch(&ids)?;

    Ok(ids.len())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::{ActivityEvent, WindowInfo};
    use axum::{routing::post, Json, Router};
    use std::sync::atomic::{AtomicU16, Ordering};
    use tempfile::TempDir;

    fn test_config_with_url(url: &str, token: &str) -> Config {
        Config {
            server_url: url.to_string(),
            auth_token: Some(token.to_string()),
            flush_batch_size: 10,
            flush_interval_secs: 1,
            ..Config::default()
        }
    }

    fn make_test_token() -> String {
        let header = base64url_encode(b"{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        let payload = base64url_encode(
            format!("{{\"sub\":\"test\",\"exp\":{}}}", chrono::Utc::now().timestamp() + 86400).as_bytes(),
        );
        format!("{header}.{payload}.fakesig")
    }

    fn base64url_encode(input: &[u8]) -> String {
        let table = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut result = String::new();
        let mut i = 0;
        while i < input.len() {
            let b0 = input[i] as u32;
            let b1 = if i + 1 < input.len() { input[i + 1] as u32 } else { 0 };
            let b2 = if i + 2 < input.len() { input[i + 2] as u32 } else { 0 };
            let triple = (b0 << 16) | (b1 << 8) | b2;
            result.push(table[((triple >> 18) & 0x3F) as usize] as char);
            result.push(table[((triple >> 12) & 0x3F) as usize] as char);
            if i + 1 < input.len() {
                result.push(table[((triple >> 6) & 0x3F) as usize] as char);
            }
            if i + 2 < input.len() {
                result.push(table[(triple & 0x3F) as usize] as char);
            }
            i += 3;
        }
        result.replace('+', "-").replace('/', "_").trim_end_matches('=').to_string()
    }

    fn test_buffer() -> (TempDir, Arc<Mutex<EventBuffer>>) {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("test.db");
        let buf = EventBuffer::open(&path).unwrap();
        (dir, Arc::new(Mutex::new(buf)))
    }

    fn insert_test_events(buffer: &Arc<Mutex<EventBuffer>>, count: usize) {
        let buf = buffer.lock().unwrap();
        for _ in 0..count {
            buf.insert(&ActivityEvent::window_change(WindowInfo {
                app_name: "Test".into(),
                window_title: "Window".into(),
                url: None,
            })).unwrap();
        }
    }

    /// Spawn an axum mock HTTP server that returns the given status code.
    async fn spawn_mock_server(status_code: u16) -> String {
        let status = Arc::new(AtomicU16::new(status_code));
        let app = Router::new().route(
            "/api/activity/events",
            post({
                let status = status.clone();
                move |_body: Json<serde_json::Value>| {
                    let code = status.load(Ordering::SeqCst);
                    async move {
                        (
                            axum::http::StatusCode::from_u16(code).unwrap_or(axum::http::StatusCode::INTERNAL_SERVER_ERROR),
                            Json(serde_json::json!({"status": "ok"})),
                        )
                    }
                }
            }),
        );

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.ok();
        });
        // Give the server a moment to start accepting connections
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

        format!("http://{addr}")
    }


    #[tokio::test(flavor = "multi_thread")]
    async fn test_flush_success() {
        let url = spawn_mock_server(200).await;
        let token = make_test_token();
        let config = test_config_with_url(&url, &token);
        let (_dir, buffer) = test_buffer();
        insert_test_events(&buffer, 3);

        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let flushed = flush_once(&config, &buffer, &client).await.unwrap();

        assert_eq!(flushed, 3);
        assert_eq!(buffer.lock().unwrap().count().unwrap(), 0);
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn test_flush_server_error_retains_events() {
        let url = spawn_mock_server(500).await;
        let token = make_test_token();
        let config = test_config_with_url(&url, &token);
        let (_dir, buffer) = test_buffer();
        insert_test_events(&buffer, 3);

        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let result = flush_once(&config, &buffer, &client).await;

        assert!(result.is_err());
        assert_eq!(buffer.lock().unwrap().count().unwrap(), 3, "Events should be retained on failure");
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn test_flush_401_returns_token_expired() {
        let url = spawn_mock_server(401).await;
        let token = make_test_token();
        let config = test_config_with_url(&url, &token);
        let (_dir, buffer) = test_buffer();
        insert_test_events(&buffer, 1);

        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let result = flush_once(&config, &buffer, &client).await;

        assert!(matches!(result, Err(DaemonError::TokenExpired)));
        assert_eq!(buffer.lock().unwrap().count().unwrap(), 1, "Events retained on auth error");
    }

    #[tokio::test]
    async fn test_flush_empty_buffer() {
        let token = make_test_token();
        let config = test_config_with_url("http://127.0.0.1:1", &token);
        let (_dir, buffer) = test_buffer();

        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let flushed = flush_once(&config, &buffer, &client).await.unwrap();

        assert_eq!(flushed, 0);
    }

    #[tokio::test]
    async fn test_flush_no_token() {
        let config = Config {
            auth_token: None,
            ..Config::default()
        };
        let (_dir, buffer) = test_buffer();
        insert_test_events(&buffer, 1);

        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let result = flush_once(&config, &buffer, &client).await;

        assert!(result.is_err());
    }
}
