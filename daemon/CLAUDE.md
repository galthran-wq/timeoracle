# TimeOracle Daemon

Rust background daemon that captures computer activity (active window, app name, idle state) and sends it to the TimeOracle FastAPI server.

## Architecture

Two-thread model:

- **Main thread**: runs GTK event loop + system tray icon (or just tokio in `--headless` mode)
- **Background thread**: tokio runtime with capture engine, sync task, and signal handler

Communication between threads:
- `mpsc` channel: tray menu → engine (Pause/Resume/Quit commands)
- `watch` channel: engine → tray (status updates)
- `broadcast` channel: shutdown signal

## Module Overview

| File | Purpose |
|------|---------|
| `main.rs` | CLI dispatch, thread orchestration, headless/tray modes |
| `cli.rs` | clap subcommands: `run`, `login`, `install`, `status` |
| `config.rs` | TOML config at `~/.timeoracle/config.toml` with defaults and validation |
| `error.rs` | `DaemonError` enum (thiserror) and `Result` type alias |
| `events.rs` | `ActivityEvent`, `WindowInfo`, `EventType` structs |
| `auth.rs` | Interactive login (POST `/api/users/login`), JWT expiry check |
| `engine.rs` | Core capture loop: poll → idle check → window diff → heartbeat → buffer |
| `buffer.rs` | SQLite (WAL mode) local event buffer at `~/.timeoracle/buffer.db` |
| `sync.rs` | HTTP flush task: batch read from buffer → POST `/api/activity/events` → delete on success |
| `tray.rs` | System tray icon + menu via `tray-icon`/`muda` crates (Linux GTK) |
| `service.rs` | systemd unit / launchd plist generation and install/uninstall |
| `capture/mod.rs` | `ActivitySource` + `IdleDetector` traits with `#[automock]`, factory functions |
| `capture/linux_x11.rs` | X11 window capture via `x11rb` (`_NET_ACTIVE_WINDOW`, `WM_CLASS`, `_NET_WM_NAME`) |
| `capture/linux_wayland.rs` | Stub — returns `None` (Wayland not yet supported) |
| `capture/macos.rs` | Stub — returns `None` (macOS not yet implemented) |
| `capture/idle.rs` | Idle detection via `user-idle` crate |

## Engine Logic (each tick, default 5s)

1. Check idle time → emit `IdleStart`/`IdleEnd` on transitions
2. If idle, skip window capture
3. Get active window via `ActivitySource`
4. Skip if app is in `ignore_apps` list
5. Diff against last window → emit `WindowChange` if different
6. If same window for `heartbeat_interval_secs` (default 300s) → emit `Heartbeat`
7. Write event to SQLite buffer

## Sync Logic

- Every `flush_interval_secs` (default 30s), read a batch from buffer
- POST to `{server_url}/api/activity/events` with Bearer auth
- On success: delete flushed events from buffer
- On failure: exponential backoff (1s → 5min cap)
- On 401: mark auth expired
- Periodic cleanup: max 100k events, auto-delete after 7 days

## Building

```bash
# System dependencies (Ubuntu/Debian)
sudo apt-get install libgtk-3-dev libxss-dev libxdo-dev

# Build
cargo build --release

# Run tests
cargo test
```

## CLI Usage

```bash
timeoracle-daemon login --server-url http://localhost:8000
timeoracle-daemon run              # with system tray
timeoracle-daemon run --headless   # without GUI
timeoracle-daemon status
timeoracle-daemon install          # install systemd service
timeoracle-daemon install --uninstall
```

## Config (`~/.timeoracle/config.toml`)

```toml
server_url = "http://localhost:8000"
auth_token = "eyJ..."
poll_interval_secs = 5
heartbeat_interval_secs = 300
idle_threshold_secs = 300
flush_interval_secs = 30
flush_batch_size = 100
ignore_apps = []
log_level = "info"
```

## Testing

- Unit tests are co-located in each module (`#[cfg(test)] mod tests`)
- Engine tests use `MockActivitySource` + `MockIdleDetector` (mockall)
- Sync tests use axum as a mock HTTP server
- Integration tests in `tests/integration/` cover buffer+sync pipeline and X11 capture
- **Note**: An HTTP proxy is set in this environment (`HTTP_PROXY`). Test HTTP clients must use `reqwest::Client::builder().no_proxy().build()` to avoid routing localhost requests through the proxy.

## Key Dependencies

| Crate | Purpose |
|-------|---------|
| `tokio` | Async runtime |
| `reqwest` (rustls-tls) | HTTP client for server API |
| `rusqlite` (bundled) | SQLite local buffer |
| `x11rb` | X11 window info (Linux) |
| `tray-icon` + `muda` | System tray icon and menu |
| `gtk` | GTK event loop (Linux tray) |
| `user-idle` | Idle detection |
| `clap` (derive) | CLI parsing |
| `serde` + `serde_json` + `toml` | Serialization |
| `chrono` | Timestamps |
| `uuid` | Event IDs |
| `tracing` | Logging |
| `mockall` (dev) | Trait mocking |
| `axum` (dev) | Mock HTTP server for tests |
