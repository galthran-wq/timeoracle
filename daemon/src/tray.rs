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
    stats_item_id: MenuId,
    quit_item_id: MenuId,
    is_paused: bool,
    cmd_tx: tokio::sync::mpsc::Sender<EngineCommand>,
    shutdown_tx: tokio::sync::broadcast::Sender<()>,
    status_rx: tokio::sync::watch::Receiver<DaemonStatus>,
    #[cfg(target_os = "macos")]
    stats_window: macos_stats::StatsWindow,
    #[cfg(target_os = "linux")]
    stats_window: linux_stats::StatsWindow,
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
    let stats_item = MenuItem::new("Show Stats", true, None);
    let quit_item = MenuItem::new("Quit", true, None);

    menu.append(&status_item).ok();
    menu.append(&server_item).ok();
    menu.append(&PredefinedMenuItem::separator()).ok();
    menu.append(&pause_item).ok();
    menu.append(&sync_item).ok();
    menu.append(&stats_item).ok();
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
    let stats_item_id = stats_item.id().clone();
    let quit_item_id = quit_item.id().clone();

    let state = TrayState {
        pause_item,
        status_item,
        server_item,
        pause_item_id,
        stats_item_id,
        quit_item_id,
        is_paused: false,
        cmd_tx,
        shutdown_tx,
        status_rx,
        #[cfg(target_os = "macos")]
        stats_window: macos_stats::StatsWindow::default(),
        #[cfg(target_os = "linux")]
        stats_window: linux_stats::StatsWindow::default(),
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
        } else if event.id == state.stats_item_id {
            state.stats_window.show();
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

    state.stats_window.update(&status);

    true
}

// ---------------------------------------------------------------------------
// macOS login window
// ---------------------------------------------------------------------------

#[cfg(target_os = "macos")]
mod macos_login {
    use crate::config::Config;
    use objc2::rc::Retained;
    use objc2::MainThreadOnly;
    use objc2_app_kit::{
        NSApplication, NSApplicationActivationPolicy, NSBackingStoreType, NSButton, NSColor,
        NSEvent, NSEventMask, NSFont, NSSecureTextField, NSTextField, NSWindow,
        NSWindowStyleMask,
    };
    use objc2_foundation::{
        MainThreadMarker, NSDate, NSDefaultRunLoopMode, NSPoint, NSRect, NSSize, NSString,
    };
    use std::sync::mpsc;

    enum LoginResult {
        Success,
        Error(String),
    }

    pub fn show_login_and_wait(config: &Config) -> anyhow::Result<Config> {
        let mtm = MainThreadMarker::new()
            .ok_or_else(|| anyhow::anyhow!("must be called from the main thread"))?;

        let app = NSApplication::sharedApplication(mtm);
        app.setActivationPolicy(NSApplicationActivationPolicy::Accessory);

        let window = unsafe {
            NSWindow::initWithContentRect_styleMask_backing_defer(
                NSWindow::alloc(mtm),
                NSRect::new(NSPoint::new(100.0, 100.0), NSSize::new(380.0, 220.0)),
                NSWindowStyleMask::Titled | NSWindowStyleMask::Closable,
                NSBackingStoreType::Buffered,
                false,
            )
        };
        unsafe { window.setReleasedWhenClosed(false) };
        window.setTitle(&NSString::from_str("TimeOracle — Login"));
        window.center();

        let content_view = unsafe { window.contentView() }.unwrap();

        let label_font = NSFont::boldSystemFontOfSize(13.0);
        let field_font = NSFont::systemFontOfSize(13.0);

        let make_label = |text: &str, y: f64| -> Retained<NSTextField> {
            let field = NSTextField::labelWithString(&NSString::from_str(text), mtm);
            field.setFrame(NSRect::new(
                NSPoint::new(20.0, y),
                NSSize::new(90.0, 22.0),
            ));
            field.setFont(Some(&label_font));
            field
        };

        let make_field = |text: &str, y: f64| -> Retained<NSTextField> {
            let field = NSTextField::textFieldWithString(&NSString::from_str(text), mtm);
            field.setFrame(NSRect::new(
                NSPoint::new(120.0, y),
                NSSize::new(240.0, 22.0),
            ));
            field.setFont(Some(&field_font));
            field
        };

        let server_label = make_label("Server URL", 165.0);
        let server_field = make_field(&config.server_url, 165.0);
        let email_label = make_label("Email", 125.0);
        let email_field = make_field("", 125.0);
        let pass_label = make_label("Password", 85.0);
        let pass_field = unsafe {
            NSSecureTextField::initWithFrame(
                NSSecureTextField::alloc(mtm),
                NSRect::new(NSPoint::new(120.0, 85.0), NSSize::new(240.0, 22.0)),
            )
        };
        pass_field.setFont(Some(&field_font));

        let error_label = NSTextField::labelWithString(&NSString::from_str(""), mtm);
        error_label.setFrame(NSRect::new(
            NSPoint::new(20.0, 50.0),
            NSSize::new(340.0, 22.0),
        ));
        error_label.setTextColor(Some(&NSColor::systemRedColor()));
        error_label.setFont(Some(&NSFont::systemFontOfSize(12.0)));

        let login_btn = unsafe { NSButton::buttonWithTitle_target_action(
            &NSString::from_str("Login"),
            None,
            None,
            mtm,
        ) };
        login_btn.setFrame(NSRect::new(
            NSPoint::new(280.0, 15.0),
            NSSize::new(80.0, 30.0),
        ));

        unsafe {
            content_view.addSubview(&server_label);
            content_view.addSubview(&server_field);
            content_view.addSubview(&email_label);
            content_view.addSubview(&email_field);
            content_view.addSubview(&pass_label);
            content_view.addSubview(&pass_field);
            content_view.addSubview(&error_label);
            content_view.addSubview(&login_btn);
        }

        window.makeKeyAndOrderFront(None);
        #[allow(deprecated)]
        app.activateIgnoringOtherApps(true);
        app.finishLaunching();

        let (tx, rx) = mpsc::channel::<LoginResult>();
        let mut login_pending = false;
        let mut was_btn_pressed = false;
        let mut logged_in = false;
        let mut quit = false;
        let mode = unsafe { NSDefaultRunLoopMode };

        loop {
            let expiration = NSDate::dateWithTimeIntervalSinceNow(0.05);
            let event = app.nextEventMatchingMask_untilDate_inMode_dequeue(
                NSEventMask::Any,
                Some(&expiration),
                mode,
                true,
            );
            if let Some(ref event) = event {
                app.sendEvent(event);
            }

            if !window.isVisible() {
                quit = true;
                break;
            }

            if !login_pending && !was_btn_pressed {
                let mouse_loc = unsafe { NSEvent::mouseLocation() };
                let btn_frame = login_btn.frame();
                let win_frame = window.frame();
                let abs_x = mouse_loc.x - win_frame.origin.x;
                let abs_y = mouse_loc.y - win_frame.origin.y;
                let content_y = abs_y;

                if let Some(ref event) = event {
                    let event_type = unsafe { event.r#type() };
                    if event_type == objc2_app_kit::NSEventType::LeftMouseUp
                        && abs_x >= btn_frame.origin.x
                        && abs_x <= btn_frame.origin.x + btn_frame.size.width
                        && content_y >= btn_frame.origin.y
                        && content_y <= btn_frame.origin.y + btn_frame.size.height
                    {
                        was_btn_pressed = true;
                    }
                }
            }

            if was_btn_pressed && !login_pending {
                was_btn_pressed = false;
                let server_url = server_field.stringValue().to_string();
                let email = email_field.stringValue().to_string();
                let password = pass_field.stringValue().to_string();

                if server_url.is_empty() || email.is_empty() || password.is_empty() {
                    error_label.setStringValue(&NSString::from_str("All fields are required"));
                    continue;
                }

                login_btn.setEnabled(false);
                login_btn.setTitle(&NSString::from_str("Logging in..."));
                error_label.setStringValue(&NSString::from_str(""));
                login_pending = true;

                let tx = tx.clone();
                let config_path = Config::default_config_path().unwrap();
                std::thread::spawn(move || {
                    let rt = tokio::runtime::Runtime::new().unwrap();
                    let result = rt.block_on(crate::auth::login_with_credentials(
                        &server_url,
                        &email,
                        &password,
                        &config_path,
                    ));
                    match result {
                        Ok(()) => { let _ = tx.send(LoginResult::Success); }
                        Err(e) => { let _ = tx.send(LoginResult::Error(format!("{e}"))); }
                    }
                });
            }

            if let Ok(result) = rx.try_recv() {
                match result {
                    LoginResult::Success => {
                        logged_in = true;
                        window.orderOut(None);
                        break;
                    }
                    LoginResult::Error(msg) => {
                        error_label.setStringValue(&NSString::from_str(&msg));
                        login_btn.setEnabled(true);
                        login_btn.setTitle(&NSString::from_str("Login"));
                        login_pending = false;
                    }
                }
            }
        }

        if !logged_in {
            if quit {
                std::process::exit(0);
            }
            anyhow::bail!("Login cancelled");
        }

        let config_path = Config::default_config_path()?;
        let config = Config::load(&config_path)?;
        Ok(config)
    }
}

// ---------------------------------------------------------------------------
// macOS stats window
// ---------------------------------------------------------------------------

#[cfg(target_os = "macos")]
mod macos_stats {
    use crate::engine::DaemonStatus;
    use objc2::rc::Retained;
    use objc2::MainThreadOnly;
    use objc2_app_kit::{
        NSApplication, NSBackingStoreType, NSColor, NSFont, NSTextField, NSWindow,
        NSWindowStyleMask,
    };
    use objc2_foundation::{MainThreadMarker, NSPoint, NSRect, NSSize, NSString};

    pub struct StatsWindow {
        window: Option<Retained<NSWindow>>,
        status_label: Option<Retained<NSTextField>>,
        server_label: Option<Retained<NSTextField>>,
        buffered_label: Option<Retained<NSTextField>>,
    }

    impl Default for StatsWindow {
        fn default() -> Self {
            Self {
                window: None,
                status_label: None,
                server_label: None,
                buffered_label: None,
            }
        }
    }

    impl StatsWindow {
        pub fn init(&mut self, mtm: MainThreadMarker) {
            let window = unsafe {
                NSWindow::initWithContentRect_styleMask_backing_defer(
                    NSWindow::alloc(mtm),
                    NSRect::new(NSPoint::new(100.0, 100.0), NSSize::new(300.0, 150.0)),
                    NSWindowStyleMask::Titled
                        | NSWindowStyleMask::Closable
                        | NSWindowStyleMask::Miniaturizable,
                    NSBackingStoreType::Buffered,
                    false,
                )
            };
            unsafe { window.setReleasedWhenClosed(false) };
            window.setTitle(&NSString::from_str("TimeOracle"));
            window.center();

            let content_view = window.contentView().unwrap();

            let bold_font = NSFont::boldSystemFontOfSize(13.0);
            let value_font = NSFont::systemFontOfSize(13.0);
            let label_color = NSColor::secondaryLabelColor();
            let value_color = NSColor::labelColor();

            let rows: [(&str, f64); 3] = [
                ("Status", 100.0),
                ("Server", 65.0),
                ("Buffered", 30.0),
            ];

            let mut value_fields = Vec::new();

            for (text, y) in &rows {
                let label = Self::make_label(
                    &NSString::from_str(text),
                    NSRect::new(NSPoint::new(20.0, *y), NSSize::new(80.0, 20.0)),
                    &bold_font,
                    &label_color,
                    mtm,
                );
                content_view.addSubview(&label);

                let value = Self::make_label(
                    &NSString::from_str("—"),
                    NSRect::new(NSPoint::new(110.0, *y), NSSize::new(170.0, 20.0)),
                    &value_font,
                    &value_color,
                    mtm,
                );
                content_view.addSubview(&value);
                value_fields.push(value);
            }

            self.status_label = Some(value_fields.remove(0));
            self.server_label = Some(value_fields.remove(0));
            self.buffered_label = Some(value_fields.remove(0));
            self.window = Some(window);
        }

        fn make_label(
            text: &NSString,
            frame: NSRect,
            font: &NSFont,
            color: &NSColor,
            mtm: MainThreadMarker,
        ) -> Retained<NSTextField> {
            let field = NSTextField::labelWithString(text, mtm);
            field.setFrame(frame);
            field.setFont(Some(font));
            field.setTextColor(Some(color));
            field
        }

        pub fn show(&self) {
            if let Some(ref window) = self.window {
                window.makeKeyAndOrderFront(None);
                let app = NSApplication::sharedApplication(
                    MainThreadMarker::new().expect("must be main thread"),
                );
                #[allow(deprecated)]
                app.activateIgnoringOtherApps(true);
            }
        }

        pub fn update(&self, status: &DaemonStatus) {
            if let Some(ref label) = self.status_label {
                label.setStringValue(&NSString::from_str(&format!("{}", status.state)));
            }
            if let Some(ref label) = self.server_label {
                let text = if status.server_connected {
                    "Connected"
                } else {
                    "Disconnected"
                };
                label.setStringValue(&NSString::from_str(text));
            }
            if let Some(ref label) = self.buffered_label {
                label.setStringValue(&NSString::from_str(&format!(
                    "{} events",
                    status.events_buffered
                )));
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Linux login window
// ---------------------------------------------------------------------------

#[cfg(target_os = "linux")]
mod linux_login {
    use crate::config::Config;
    use gtk::prelude::*;
    use std::sync::mpsc;

    enum LoginResult {
        Success,
        Error(String),
    }

    pub fn show_login_and_wait(config: &Config) -> anyhow::Result<Config> {
        let window = gtk::Window::new(gtk::WindowType::Toplevel);
        window.set_title("TimeOracle — Login");
        window.set_default_size(350, 220);
        window.set_resizable(false);
        window.set_position(gtk::WindowPosition::Center);

        let grid = gtk::Grid::new();
        grid.set_row_spacing(10);
        grid.set_column_spacing(12);
        grid.set_margin_top(20);
        grid.set_margin_bottom(20);
        grid.set_margin_start(20);
        grid.set_margin_end(20);

        let server_label = gtk::Label::new(Some("Server URL"));
        server_label.set_halign(gtk::Align::Start);
        let server_entry = gtk::Entry::new();
        server_entry.set_text(&config.server_url);
        server_entry.set_hexpand(true);
        grid.attach(&server_label, 0, 0, 1, 1);
        grid.attach(&server_entry, 1, 0, 1, 1);

        let email_label = gtk::Label::new(Some("Email"));
        email_label.set_halign(gtk::Align::Start);
        let email_entry = gtk::Entry::new();
        email_entry.set_hexpand(true);
        grid.attach(&email_label, 0, 1, 1, 1);
        grid.attach(&email_entry, 1, 1, 1, 1);

        let pass_label = gtk::Label::new(Some("Password"));
        pass_label.set_halign(gtk::Align::Start);
        let pass_entry = gtk::Entry::new();
        pass_entry.set_visibility(false);
        pass_entry.set_input_purpose(gtk::InputPurpose::Password);
        pass_entry.set_hexpand(true);
        grid.attach(&pass_label, 0, 2, 1, 1);
        grid.attach(&pass_entry, 1, 2, 1, 1);

        let error_label = gtk::Label::new(None);
        error_label.set_markup("<span foreground='red'></span>");
        error_label.set_halign(gtk::Align::Start);
        error_label.set_line_wrap(true);
        grid.attach(&error_label, 0, 3, 2, 1);

        let login_btn = gtk::Button::with_label("Login");
        login_btn.set_halign(gtk::Align::End);
        grid.attach(&login_btn, 1, 4, 1, 1);

        window.add(&grid);
        window.show_all();

        let (tx, rx) = mpsc::channel::<LoginResult>();

        let server_entry_clone = server_entry.clone();
        let email_entry_clone = email_entry.clone();
        let pass_entry_clone = pass_entry.clone();
        let login_btn_clone = login_btn.clone();

        login_btn.connect_clicked(move |_| {
            let server_url = server_entry_clone.text().to_string();
            let email = email_entry_clone.text().to_string();
            let password = pass_entry_clone.text().to_string();

            if server_url.is_empty() || email.is_empty() || password.is_empty() {
                let _ = tx.send(LoginResult::Error("All fields are required".into()));
                return;
            }

            login_btn_clone.set_sensitive(false);
            login_btn_clone.set_label("Logging in...");

            let tx = tx.clone();
            let config_path = Config::default_config_path().unwrap();
            std::thread::spawn(move || {
                let rt = tokio::runtime::Runtime::new().unwrap();
                let result = rt.block_on(crate::auth::login_with_credentials(
                    &server_url,
                    &email,
                    &password,
                    &config_path,
                ));
                match result {
                    Ok(()) => { let _ = tx.send(LoginResult::Success); }
                    Err(e) => { let _ = tx.send(LoginResult::Error(format!("{e}"))); }
                }
            });
        });

        let window_clone = window.clone();
        let error_label_clone = error_label.clone();
        let login_btn_poll = login_btn.clone();
        let logged_in = std::rc::Rc::new(std::cell::Cell::new(false));
        let logged_in_clone = logged_in.clone();

        window.connect_delete_event(|_, _| {
            gtk::main_quit();
            gtk::glib::Propagation::Proceed
        });

        gtk::glib::timeout_add_local(std::time::Duration::from_millis(50), move || {
            if let Ok(result) = rx.try_recv() {
                match result {
                    LoginResult::Success => {
                        logged_in_clone.set(true);
                        window_clone.hide();
                        gtk::main_quit();
                        return gtk::glib::ControlFlow::Break;
                    }
                    LoginResult::Error(msg) => {
                        error_label_clone.set_markup(&format!(
                            "<span foreground='red'>{}</span>",
                            gtk::glib::markup_escape_text(&msg)
                        ));
                        login_btn_poll.set_sensitive(true);
                        login_btn_poll.set_label("Login");
                    }
                }
            }
            gtk::glib::ControlFlow::Continue
        });

        gtk::main();

        if !logged_in.get() {
            anyhow::bail!("Login cancelled");
        }

        let config_path = Config::default_config_path()?;
        let config = Config::load(&config_path)?;
        Ok(config)
    }
}

// ---------------------------------------------------------------------------
// Linux stats window
// ---------------------------------------------------------------------------

#[cfg(target_os = "linux")]
mod linux_stats {
    use crate::engine::DaemonStatus;
    use gtk::prelude::*;

    pub struct StatsWindow {
        window: Option<gtk::Window>,
        status_label: Option<gtk::Label>,
        server_label: Option<gtk::Label>,
        buffered_label: Option<gtk::Label>,
    }

    impl Default for StatsWindow {
        fn default() -> Self {
            Self {
                window: None,
                status_label: None,
                server_label: None,
                buffered_label: None,
            }
        }
    }

    impl StatsWindow {
        pub fn init(&mut self) {
            let window = gtk::Window::new(gtk::WindowType::Toplevel);
            window.set_title("TimeOracle");
            window.set_default_size(300, 150);
            window.set_resizable(false);

            window.connect_delete_event(|w, _| {
                w.hide();
                gtk::glib::Propagation::Stop
            });

            let grid = gtk::Grid::new();
            grid.set_row_spacing(8);
            grid.set_column_spacing(16);
            grid.set_margin_top(20);
            grid.set_margin_bottom(20);
            grid.set_margin_start(20);
            grid.set_margin_end(20);

            let rows = ["Status", "Server", "Buffered"];
            let mut value_labels = Vec::new();

            for (i, name) in rows.iter().enumerate() {
                let header = gtk::Label::new(None);
                header.set_markup(&format!("<b>{name}</b>"));
                header.set_halign(gtk::Align::Start);
                grid.attach(&header, 0, i as i32, 1, 1);

                let value = gtk::Label::new(Some("—"));
                value.set_halign(gtk::Align::Start);
                value.set_hexpand(true);
                grid.attach(&value, 1, i as i32, 1, 1);

                value_labels.push(value);
            }

            window.add(&grid);

            self.status_label = Some(value_labels.remove(0));
            self.server_label = Some(value_labels.remove(0));
            self.buffered_label = Some(value_labels.remove(0));
            self.window = Some(window);
        }

        pub fn show(&self) {
            if let Some(ref window) = self.window {
                window.show_all();
                window.present();
            }
        }

        pub fn update(&self, status: &DaemonStatus) {
            if let Some(ref label) = self.status_label {
                label.set_text(&format!("{}", status.state));
            }
            if let Some(ref label) = self.server_label {
                let text = if status.server_connected {
                    "Connected"
                } else {
                    "Disconnected"
                };
                label.set_text(text);
            }
            if let Some(ref label) = self.buffered_label {
                label.set_text(&format!("{} events", status.events_buffered));
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Linux
// ---------------------------------------------------------------------------

#[cfg(target_os = "linux")]
pub fn run(config: Config) -> anyhow::Result<()> {
    gtk::init().map_err(|e| anyhow::anyhow!("GTK init failed: {e}"))?;

    let config = if config.auth_token.is_none() {
        linux_login::show_login_and_wait(&config)?
    } else {
        config
    };

    let (mut state, cmd_rx, status_tx, buffer, _tray) = build_tray()?;
    spawn_background_runtime(config, buffer, cmd_rx, status_tx, &state.shutdown_tx);

    state.stats_window.init();

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

// ---------------------------------------------------------------------------
// macOS
// ---------------------------------------------------------------------------

#[cfg(target_os = "macos")]
pub fn run(config: Config) -> anyhow::Result<()> {
    use objc2_app_kit::{NSApplication, NSApplicationActivationPolicy, NSEventMask};
    use objc2_foundation::{MainThreadMarker, NSDate, NSDefaultRunLoopMode, NSRunLoop};

    let needs_login = config.auth_token.is_none();
    let config = if needs_login {
        macos_login::show_login_and_wait(&config)?
    } else {
        config
    };

    let mtm = MainThreadMarker::new()
        .ok_or_else(|| anyhow::anyhow!("must be called from the main thread"))?;

    let app = NSApplication::sharedApplication(mtm);
    app.setActivationPolicy(NSApplicationActivationPolicy::Accessory);

    let (mut state, cmd_rx, status_tx, buffer, _tray) = build_tray()?;
    spawn_background_runtime(config, buffer, cmd_rx, status_tx, &state.shutdown_tx);

    state.stats_window.init(mtm);

    if !needs_login {
        app.finishLaunching();
    }

    let mode = unsafe { NSDefaultRunLoopMode };
    let run_loop = NSRunLoop::currentRunLoop();

    loop {
        let expiration = NSDate::dateWithTimeIntervalSinceNow(0.1);
        let event = app.nextEventMatchingMask_untilDate_inMode_dequeue(
            NSEventMask::Any,
            Some(&expiration),
            mode,
            true,
        );
        if let Some(ref event) = event {
            app.sendEvent(event);
        }
        run_loop.runMode_beforeDate(mode, &expiration);
        if !poll_and_update(&mut state) {
            break;
        }
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Unsupported platforms
// ---------------------------------------------------------------------------

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn run(_config: Config) -> anyhow::Result<()> {
    anyhow::bail!(
        "System tray is only supported on Linux and macOS. Use --headless mode on this platform."
    );
}
