use crate::error::{DaemonError, Result};
use std::path::PathBuf;

pub fn install() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        install_systemd()?;
        install_desktop_entry()?;
    }

    #[cfg(target_os = "macos")]
    {
        install_launchd()?;
    }

    Ok(())
}

pub fn uninstall() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        uninstall_systemd()?;
        uninstall_desktop_entry()?;
    }

    #[cfg(target_os = "macos")]
    {
        uninstall_launchd()?;
    }

    Ok(())
}

#[cfg(target_os = "linux")]
fn systemd_unit_path() -> Result<PathBuf> {
    let home = std::env::var("HOME")
        .map_err(|_| DaemonError::Config("HOME not set".into()))?;
    Ok(PathBuf::from(home)
        .join(".config")
        .join("systemd")
        .join("user")
        .join("digitalgulag-daemon.service"))
}

#[cfg(target_os = "linux")]
fn install_systemd() -> Result<()> {
    let exe = std::env::current_exe()?;
    let unit_path = systemd_unit_path()?;

    if let Some(parent) = unit_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let unit = format!(
        r#"[Unit]
Description=digitalgulag Activity Tracking Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart={exe} run --headless
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
"#,
        exe = exe.display()
    );

    std::fs::write(&unit_path, unit)?;
    println!("Installed systemd unit: {}", unit_path.display());
    println!("Enable with: systemctl --user enable --now digitalgulag-daemon");
    Ok(())
}

#[cfg(target_os = "linux")]
fn uninstall_systemd() -> Result<()> {
    let unit_path = systemd_unit_path()?;
    if unit_path.exists() {
        std::fs::remove_file(&unit_path)?;
        println!("Removed systemd unit: {}", unit_path.display());
        println!("Run: systemctl --user daemon-reload");
    } else {
        println!("No systemd unit found at {}", unit_path.display());
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn install_desktop_entry() -> Result<()> {
    let home = std::env::var("HOME")
        .map_err(|_| DaemonError::Config("HOME not set".into()))?;
    let data_dir = PathBuf::from(&home).join(".local").join("share");

    let desktop_dir = data_dir.join("applications");
    std::fs::create_dir_all(&desktop_dir)?;

    let exe = std::env::current_exe()?;
    let desktop_entry = format!(
        "[Desktop Entry]\n\
         Type=Application\n\
         Name=digitalgulag\n\
         Comment=Activity tracking daemon\n\
         Exec={exe} run\n\
         Icon=digitalgulag-daemon\n\
         Terminal=false\n\
         Categories=Utility;\n\
         StartupNotify=false\n",
        exe = exe.display()
    );
    let desktop_path = desktop_dir.join("digitalgulag-daemon.desktop");
    std::fs::write(&desktop_path, desktop_entry)?;
    println!("Installed desktop entry: {}", desktop_path.display());

    let icon_src = exe
        .parent()
        .and_then(|p| {
            let candidate = p.join("../share/icons/hicolor/128x128/apps/digitalgulag-daemon.png");
            if candidate.exists() { Some(candidate) } else { None }
        });

    if let Some(src) = icon_src {
        let icon_dir = data_dir.join("icons/hicolor/128x128/apps");
        std::fs::create_dir_all(&icon_dir)?;
        let icon_dest = icon_dir.join("digitalgulag-daemon.png");
        std::fs::copy(&src, &icon_dest)?;
        println!("Installed icon: {}", icon_dest.display());
    }

    Ok(())
}

#[cfg(target_os = "linux")]
fn uninstall_desktop_entry() -> Result<()> {
    let home = std::env::var("HOME")
        .map_err(|_| DaemonError::Config("HOME not set".into()))?;
    let data_dir = PathBuf::from(&home).join(".local").join("share");

    let desktop_path = data_dir.join("applications/digitalgulag-daemon.desktop");
    if desktop_path.exists() {
        std::fs::remove_file(&desktop_path)?;
        println!("Removed desktop entry: {}", desktop_path.display());
    }

    let icon_path = data_dir.join("icons/hicolor/128x128/apps/digitalgulag-daemon.png");
    if icon_path.exists() {
        std::fs::remove_file(&icon_path)?;
        println!("Removed icon: {}", icon_path.display());
    }

    Ok(())
}

#[cfg(target_os = "macos")]
fn launchd_plist_path() -> Result<PathBuf> {
    let home = std::env::var("HOME")
        .map_err(|_| DaemonError::Config("HOME not set".into()))?;
    Ok(PathBuf::from(home)
        .join("Library")
        .join("LaunchAgents")
        .join("com.digitalgulag.daemon.plist"))
}

#[cfg(target_os = "macos")]
fn install_launchd() -> Result<()> {
    let exe = std::env::current_exe()?;
    let plist_path = launchd_plist_path()?;

    let plist = format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digitalgulag.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
        <string>run</string>
        <string>--headless</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/digitalgulag-daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/digitalgulag-daemon.err</string>
</dict>
</plist>"#,
        exe = exe.display()
    );

    std::fs::write(&plist_path, plist)?;
    println!("Installed launchd plist: {}", plist_path.display());
    println!("Load with: launchctl load {}", plist_path.display());
    Ok(())
}

#[cfg(target_os = "macos")]
fn uninstall_launchd() -> Result<()> {
    let plist_path = launchd_plist_path()?;
    if plist_path.exists() {
        std::fs::remove_file(&plist_path)?;
        println!("Removed launchd plist: {}", plist_path.display());
    } else {
        println!("No launchd plist found at {}", plist_path.display());
    }
    Ok(())
}
