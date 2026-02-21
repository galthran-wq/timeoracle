use crate::error::{DaemonError, Result};
use std::path::PathBuf;

pub fn install() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        install_systemd()?;
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
        .join("timeoracle-daemon.service"))
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
Description=TimeOracle Activity Tracking Daemon
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
    println!("Enable with: systemctl --user enable --now timeoracle-daemon");
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

#[cfg(target_os = "macos")]
fn launchd_plist_path() -> Result<PathBuf> {
    let home = std::env::var("HOME")
        .map_err(|_| DaemonError::Config("HOME not set".into()))?;
    Ok(PathBuf::from(home)
        .join("Library")
        .join("LaunchAgents")
        .join("com.timeoracle.daemon.plist"))
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
    <string>com.timeoracle.daemon</string>
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
    <string>/tmp/timeoracle-daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/timeoracle-daemon.err</string>
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
