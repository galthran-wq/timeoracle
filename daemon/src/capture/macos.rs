use crate::capture::ActivitySource;
use crate::error::Result;
use crate::events::WindowInfo;
use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, Ordering};

use objc2_app_kit::NSWorkspace;
use objc2_core_foundation::{CFDictionary, CFNumber, CFString};
use objc2_core_graphics::{
    kCGWindowLayer, kCGWindowName, kCGWindowOwnerPID, CGWindowListCopyWindowInfo,
    CGWindowListOption,
};

static SCREEN_RECORDING_WARNED: AtomicBool = AtomicBool::new(false);

pub struct MacOSSource {
    url_capture: bool,
}

impl MacOSSource {
    pub fn new(url_capture: bool) -> Self {
        tracing::info!("macOS capture initialized (NSWorkspace + CGWindowList)");
        Self { url_capture }
    }

    fn get_frontmost_app(&self) -> Option<(String, i32)> {
        let workspace = NSWorkspace::sharedWorkspace();
        let app = workspace.frontmostApplication()?;

        let name = app.localizedName()?;
        let pid = app.processIdentifier();
        if pid <= 0 {
            return None;
        }

        Some((name.to_string(), pid))
    }

    fn get_window_title_for_pid(&self, target_pid: i32) -> Option<String> {
        let options =
            CGWindowListOption::OptionOnScreenOnly | CGWindowListOption::ExcludeDesktopElements;
        let window_list = CGWindowListCopyWindowInfo(options, 0)?;

        let count = window_list.len();
        let mut found_window = false;

        for i in 0..count {
            let dict_ptr = unsafe { window_list.value_at_index(i as isize) };
            if dict_ptr.is_null() {
                continue;
            }
            let dict = unsafe { &*(dict_ptr as *const CFDictionary) };

            let (pid_key, layer_key, name_key) =
                unsafe { (&*kCGWindowOwnerPID, &*kCGWindowLayer, &*kCGWindowName) };

            let pid = cf_dict_get_i32(dict, pid_key);
            if pid != Some(target_pid) {
                continue;
            }

            if cf_dict_get_i32(dict, layer_key).unwrap_or(-1) != 0 {
                continue;
            }

            found_window = true;

            if let Some(title) = cf_dict_get_string(dict, name_key) {
                if !title.is_empty() {
                    return Some(title);
                }
            }
        }

        if found_window && !SCREEN_RECORDING_WARNED.swap(true, Ordering::Relaxed) {
            tracing::warn!(
                "Window titles unavailable — grant Screen Recording permission to digitalgulag \
                 in System Settings > Privacy & Security > Screen Recording"
            );
        }

        None
    }
}

fn cf_dict_get_i32(dict: &CFDictionary, key: &CFString) -> Option<i32> {
    let ptr = unsafe { dict.value(key as *const CFString as *const c_void) };
    if ptr.is_null() {
        return None;
    }
    unsafe { &*(ptr as *const CFNumber) }.as_i32()
}

fn cf_dict_get_string(dict: &CFDictionary, key: &CFString) -> Option<String> {
    let ptr = unsafe { dict.value(key as *const CFString as *const c_void) };
    if ptr.is_null() {
        return None;
    }
    Some(unsafe { &*(ptr as *const CFString) }.to_string())
}

fn get_browser_url(app_name: &str) -> Option<String> {
    let script = jxa_url_script(app_name)?;
    let mut child = std::process::Command::new("osascript")
        .args(["-l", "JavaScript", "-e", &script])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .spawn()
        .ok()?;

    let timeout = std::time::Duration::from_millis(500);
    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    return None;
                }
                break;
            }
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    tracing::debug!("osascript timed out for {app_name}");
                    return None;
                }
                std::thread::sleep(std::time::Duration::from_millis(10));
            }
            Err(_) => return None,
        }
    }

    let output = child.wait_with_output().ok()?;
    let url = String::from_utf8(output.stdout).ok()?.trim().to_string();
    if url.is_empty() {
        return None;
    }
    Some(url)
}

fn escape_jxa_string(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn jxa_url_script(app_name: &str) -> Option<String> {
    let lower = app_name.to_lowercase();
    let escaped = escape_jxa_string(app_name);

    if lower == "safari" {
        return Some(format!(
            "Application(\"{}\").windows[0].currentTab.url()",
            escaped,
        ));
    }

    let is_chromium = lower
        .split(|c: char| !c.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .any(|token| {
            matches!(
                token,
                "chrome" | "chromium" | "brave" | "edge" | "vivaldi" | "opera" | "arc"
            )
        });

    if is_chromium {
        return Some(format!(
            "Application(\"{}\").windows[0].activeTab.url()",
            escaped,
        ));
    }

    None
}

impl ActivitySource for MacOSSource {
    fn get_active_window(&self) -> Result<Option<WindowInfo>> {
        let (app_name, pid) = match self.get_frontmost_app() {
            Some(info) => info,
            None => return Ok(None),
        };

        let window_title = self.get_window_title_for_pid(pid).unwrap_or_default();

        let url = if self.url_capture {
            get_browser_url(&app_name)
        } else {
            None
        };

        Ok(Some(WindowInfo {
            app_name,
            window_title,
            url,
        }))
    }
}
