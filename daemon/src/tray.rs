use crate::config::Config;

#[cfg(target_os = "linux")]
pub fn run(config: Config) -> anyhow::Result<()> {
    use crate::buffer::EventBuffer;
    use crate::engine::{DaemonStatus, EngineCommand};
    use std::sync::{Arc, Mutex};
    use tray_icon::TrayIconBuilder;
    use muda::{Menu as MudaMenu, MenuItem, PredefinedMenuItem};

    gtk::init().map_err(|e| anyhow::anyhow!("GTK init failed: {e}"))?;

    let (shutdown_tx, _shutdown_rx) = tokio::sync::broadcast::channel::<()>(1);
    let (cmd_tx, cmd_rx) = tokio::sync::mpsc::channel::<EngineCommand>(32);
    let (status_tx, status_rx) = tokio::sync::watch::channel(DaemonStatus::default());

    let buffer_path = Config::buffer_db_path()?;
    let buffer = Arc::new(Mutex::new(EventBuffer::open(&buffer_path)?));

    // Build tray menu using muda
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

    // Create tray icon with fallback solid-color icon
    let icon = create_fallback_icon();
    let _tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip("TimeOracle")
        .with_icon(icon)
        .build()
        .map_err(|e| anyhow::anyhow!("Failed to create tray icon: {e}"))?;

    // Spawn background tokio runtime
    let rt = tokio::runtime::Runtime::new()?;
    let config_clone = config.clone();
    let buffer_clone = buffer.clone();
    let shutdown_tx_clone = shutdown_tx.clone();

    std::thread::spawn(move || {
        rt.block_on(async move {
            let mut shutdown_rx = shutdown_tx_clone.subscribe();

            let engine_handle = {
                let config = config_clone.clone();
                let buffer = buffer_clone.clone();
                let shutdown_rx = shutdown_tx_clone.subscribe();
                tokio::spawn(async move {
                    crate::engine::run(config, buffer, cmd_rx, status_tx, shutdown_rx).await
                })
            };

            let sync_handle = {
                let config = config_clone.clone();
                let buffer = buffer_clone.clone();
                let shutdown_rx = shutdown_tx_clone.subscribe();
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

    // Poll for menu events and status updates
    let pause_item_id = pause_item.id().clone();
    let quit_item_id = quit_item.id().clone();
    let mut is_paused = false;

    let status_rx_clone = status_rx.clone();
    gtk::glib::timeout_add_local(std::time::Duration::from_millis(100), move || {
        if let Ok(event) = muda::MenuEvent::receiver().try_recv() {
            if event.id == pause_item_id {
                is_paused = !is_paused;
                if is_paused {
                    let _ = cmd_tx.blocking_send(EngineCommand::Pause);
                    pause_item.set_text("Resume Tracking");
                } else {
                    let _ = cmd_tx.blocking_send(EngineCommand::Resume);
                    pause_item.set_text("Pause Tracking");
                }
            } else if event.id == quit_item_id {
                let _ = shutdown_tx.send(());
                gtk::main_quit();
                return gtk::glib::ControlFlow::Break;
            }
        }

        let status = status_rx_clone.borrow();
        status_item.set_text(&format!("Status: {}", status.state));
        let server_text = if status.server_connected {
            "Server: Connected".to_string()
        } else {
            format!("Server: Disconnected ({} buffered)", status.events_buffered)
        };
        server_item.set_text(&server_text);

        gtk::glib::ControlFlow::Continue
    });

    gtk::main();
    Ok(())
}

#[cfg(not(target_os = "linux"))]
pub fn run(_config: Config) -> anyhow::Result<()> {
    anyhow::bail!("System tray is only supported on Linux. Use --headless mode on this platform.");
}

#[cfg(target_os = "linux")]
fn create_fallback_icon() -> tray_icon::Icon {
    let size = 16u32;
    let mut rgba = Vec::with_capacity((size * size * 4) as usize);
    for _ in 0..size * size {
        rgba.extend_from_slice(&[0x4C, 0xAF, 0x50, 0xFF]); // Material green
    }
    tray_icon::Icon::from_rgba(rgba, size, size).expect("Failed to create fallback icon")
}
