use crate::config::Config;

#[cfg(any(target_os = "linux", target_os = "macos"))]
use crate::buffer::EventBuffer;
#[cfg(any(target_os = "linux", target_os = "macos"))]
use crate::engine::{DaemonStatus, EngineCommand};
#[cfg(any(target_os = "linux", target_os = "macos"))]
use muda::{Menu as MudaMenu, MenuId, MenuItem, PredefinedMenuItem};
#[cfg(any(target_os = "linux", target_os = "macos"))]
use std::sync::{Arc, Mutex};
#[cfg(any(target_os = "linux", target_os = "macos"))]
use tray_icon::TrayIconBuilder;

#[cfg(any(target_os = "linux", target_os = "macos"))]
struct TrayState {
    pause_item: MenuItem,
    status_item: MenuItem,
    server_item: MenuItem,
    pause_item_id: MenuId,
    quit_item_id: MenuId,
    is_paused: bool,
    cmd_tx: tokio::sync::mpsc::Sender<EngineCommand>,
    shutdown_tx: tokio::sync::broadcast::Sender<()>,
    status_rx: tokio::sync::watch::Receiver<DaemonStatus>,
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn create_fallback_icon() -> tray_icon::Icon {
    let size = 16u32;
    let mut rgba = Vec::with_capacity((size * size * 4) as usize);
    for _ in 0..size * size {
        rgba.extend_from_slice(&[0x4C, 0xAF, 0x50, 0xFF]);
    }
    tray_icon::Icon::from_rgba(rgba, size, size).expect("Failed to create fallback icon")
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn build_tray() -> anyhow::Result<(
    TrayState,
    tokio::sync::mpsc::Receiver<EngineCommand>,
    tokio::sync::watch::Sender<DaemonStatus>,
    Arc<Mutex<EventBuffer>>,
    tray_icon::TrayIcon,
)> {
    let (shutdown_tx, _shutdown_rx) = tokio::sync::broadcast::channel::<()>(1);
    let (cmd_tx, cmd_rx) = tokio::sync::mpsc::channel::<EngineCommand>(32);
    let (status_tx, status_rx) = tokio::sync::watch::channel(DaemonStatus::default());

    let buffer_path = Config::buffer_db_path()?;
    let buffer = Arc::new(Mutex::new(EventBuffer::open(&buffer_path)?));

    let menu = MudaMenu::new();
    let status_item = MenuItem::new("Status: Starting...", false, None);
    let server_item = MenuItem::new("Server: Unknown", false, None);
    let pause_item = MenuItem::new("Pause Tracking", true, None);
    let sync_item = MenuItem::new("Sync Now", false, None);
    let quit_item = MenuItem::new("Quit", true, None);

    menu.append(&status_item).ok();
    menu.append(&server_item).ok();
    menu.append(&PredefinedMenuItem::separator()).ok();
    menu.append(&pause_item).ok();
    menu.append(&sync_item).ok();
    menu.append(&PredefinedMenuItem::separator()).ok();
    menu.append(&quit_item).ok();

    let icon = create_fallback_icon();
    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip("TimeOracle")
        .with_icon(icon)
        .build()
        .map_err(|e| anyhow::anyhow!("Failed to create tray icon: {e}"))?;

    let pause_item_id = pause_item.id().clone();
    let quit_item_id = quit_item.id().clone();

    let state = TrayState {
        pause_item,
        status_item,
        server_item,
        pause_item_id,
        quit_item_id,
        is_paused: false,
        cmd_tx,
        shutdown_tx,
        status_rx,
    };

    Ok((state, cmd_rx, status_tx, buffer, tray))
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn spawn_background_runtime(
    config: Config,
    buffer: Arc<Mutex<EventBuffer>>,
    cmd_rx: tokio::sync::mpsc::Receiver<EngineCommand>,
    status_tx: tokio::sync::watch::Sender<DaemonStatus>,
    shutdown_tx: &tokio::sync::broadcast::Sender<()>,
) {
    let rt = tokio::runtime::Runtime::new().expect("Failed to create tokio runtime");
    let shutdown_tx = shutdown_tx.clone();

    std::thread::spawn(move || {
        rt.block_on(async move {
            let mut shutdown_rx = shutdown_tx.subscribe();

            let engine_handle = {
                let config = config.clone();
                let buffer = buffer.clone();
                let shutdown_rx = shutdown_tx.subscribe();
                tokio::spawn(async move {
                    crate::engine::run(config, buffer, cmd_rx, status_tx, shutdown_rx).await
                })
            };

            let sync_handle = {
                let config = config.clone();
                let buffer = buffer.clone();
                let shutdown_rx = shutdown_tx.subscribe();
                tokio::spawn(async move {
                    crate::sync::run(config, buffer, shutdown_rx).await
                })
            };

            tokio::select! {
                _ = shutdown_rx.recv() => {}
                r = engine_handle => { if let Err(e) = r { tracing::error!("Engine error: {e}"); } }
                r = sync_handle => { if let Err(e) = r { tracing::error!("Sync error: {e}"); } }
            }
        });
    });
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn poll_and_update(state: &mut TrayState) -> bool {
    if let Ok(event) = muda::MenuEvent::receiver().try_recv() {
        if event.id == state.pause_item_id {
            state.is_paused = !state.is_paused;
            if state.is_paused {
                let _ = state.cmd_tx.blocking_send(EngineCommand::Pause);
                state.pause_item.set_text("Resume Tracking");
            } else {
                let _ = state.cmd_tx.blocking_send(EngineCommand::Resume);
                state.pause_item.set_text("Pause Tracking");
            }
        } else if event.id == state.quit_item_id {
            let _ = state.shutdown_tx.send(());
            return false;
        }
    }

    let status = state.status_rx.borrow();
    state
        .status_item
        .set_text(&format!("Status: {}", status.state));
    let server_text = if status.server_connected {
        "Server: Connected".to_string()
    } else {
        format!("Server: Disconnected ({} buffered)", status.events_buffered)
    };
    state.server_item.set_text(&server_text);

    true
}

#[cfg(target_os = "linux")]
pub fn run(config: Config) -> anyhow::Result<()> {
    gtk::init().map_err(|e| anyhow::anyhow!("GTK init failed: {e}"))?;

    let (mut state, cmd_rx, status_tx, buffer, _tray) = build_tray()?;
    spawn_background_runtime(config, buffer, cmd_rx, status_tx, &state.shutdown_tx);

    gtk::glib::timeout_add_local(std::time::Duration::from_millis(100), move || {
        if poll_and_update(&mut state) {
            gtk::glib::ControlFlow::Continue
        } else {
            gtk::main_quit();
            gtk::glib::ControlFlow::Break
        }
    });

    gtk::main();
    Ok(())
}

#[cfg(target_os = "macos")]
pub fn run(config: Config) -> anyhow::Result<()> {
    use objc2::MainThreadMarker;
    use objc2_app_kit::{NSApplication, NSApplicationActivationPolicy};
    use objc2_foundation::{NSDate, NSDefaultRunLoopMode, NSRunLoop};

    let mtm = MainThreadMarker::new()
        .ok_or_else(|| anyhow::anyhow!("must be called from the main thread"))?;

    let app = NSApplication::sharedApplication(mtm);
    app.setActivationPolicy(NSApplicationActivationPolicy::Accessory);

    let (mut state, cmd_rx, status_tx, buffer, _tray) = build_tray()?;
    spawn_background_runtime(config, buffer, cmd_rx, status_tx, &state.shutdown_tx);

    let run_loop = NSRunLoop::currentRunLoop();
    loop {
        let date = unsafe { NSDate::dateWithTimeIntervalSinceNow(0.1) };
        unsafe {
            run_loop.runMode_beforeDate(NSDefaultRunLoopMode, &date);
        }
        if !poll_and_update(&mut state) {
            break;
        }
    }

    Ok(())
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn run(_config: Config) -> anyhow::Result<()> {
    anyhow::bail!(
        "System tray is only supported on Linux and macOS. Use --headless mode on this platform."
    );
}
