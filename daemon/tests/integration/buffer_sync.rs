use std::sync::Arc;
use std::sync::atomic::{AtomicU16, Ordering};
use tempfile::TempDir;

use axum::{routing::post, Json, Router};
use digitalgulag_daemon::buffer::EventBuffer;
use digitalgulag_daemon::events::ActivityEvent;

use crate::common;

fn make_buffer() -> (TempDir, EventBuffer) {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("integration_test.db");
    let buf = EventBuffer::open(&path).unwrap();
    (dir, buf)
}

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
                        axum::http::StatusCode::from_u16(code)
                            .unwrap_or(axum::http::StatusCode::INTERNAL_SERVER_ERROR),
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
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
    format!("http://{addr}")
}

#[tokio::test(flavor = "multi_thread")]
async fn test_full_pipeline_insert_flush_empty() {
    let url = spawn_mock_server(200).await;
    let token = common::make_test_token();
    let (_dir, buffer) = make_buffer();

    for _ in 0..5 {
        buffer.insert(&common::make_test_event()).unwrap();
    }
    assert_eq!(buffer.count().unwrap(), 5);

    let batch = buffer.read_batch(100).unwrap();
    let events: Vec<&ActivityEvent> = batch.iter().map(|(_, e)| e).collect();
    let ids: Vec<String> = batch.iter().map(|(id, _)| id.clone()).collect();

    let client = reqwest::Client::builder().no_proxy().build().unwrap();
    let resp = client
        .post(format!("{url}/api/activity/events"))
        .bearer_auth(&token)
        .json(&events)
        .send()
        .await
        .unwrap();

    assert!(resp.status().is_success());
    buffer.delete_batch(&ids).unwrap();
    assert_eq!(buffer.count().unwrap(), 0);
}

#[tokio::test(flavor = "multi_thread")]
async fn test_retry_on_server_failure() {
    let url_500 = spawn_mock_server(500).await;
    let token = common::make_test_token();
    let (_dir, buffer) = make_buffer();
    buffer.insert(&common::make_test_event()).unwrap();

    let batch = buffer.read_batch(100).unwrap();
    let events: Vec<&ActivityEvent> = batch.iter().map(|(_, e)| e).collect();

    let client = reqwest::Client::builder().no_proxy().build().unwrap();
    let resp = client
        .post(format!("{url_500}/api/activity/events"))
        .bearer_auth(&token)
        .json(&events)
        .send()
        .await
        .unwrap();

    assert!(!resp.status().is_success());
    assert_eq!(buffer.count().unwrap(), 1);

    let url_200 = spawn_mock_server(200).await;
    let resp = client
        .post(format!("{url_200}/api/activity/events"))
        .bearer_auth(&token)
        .json(&events)
        .send()
        .await
        .unwrap();

    assert!(resp.status().is_success());
    let ids: Vec<String> = batch.iter().map(|(id, _)| id.clone()).collect();
    buffer.delete_batch(&ids).unwrap();
    assert_eq!(buffer.count().unwrap(), 0);
}

#[tokio::test(flavor = "multi_thread")]
async fn test_auth_expired_handling() {
    let url = spawn_mock_server(401).await;
    let token = common::make_test_token();
    let (_dir, buffer) = make_buffer();
    buffer.insert(&common::make_test_event()).unwrap();

    let batch = buffer.read_batch(100).unwrap();
    let events: Vec<&ActivityEvent> = batch.iter().map(|(_, e)| e).collect();

    let client = reqwest::Client::builder().no_proxy().build().unwrap();
    let resp = client
        .post(format!("{url}/api/activity/events"))
        .bearer_auth(&token)
        .json(&events)
        .send()
        .await
        .unwrap();

    assert_eq!(resp.status().as_u16(), 401);
    assert_eq!(buffer.count().unwrap(), 1);
}
