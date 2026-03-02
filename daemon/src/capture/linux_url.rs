use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;
use zbus::blocking::Connection;
use zbus::zvariant::{OwnedObjectPath, OwnedValue};

static ATSPI_WARNED: AtomicBool = AtomicBool::new(false);
static ATSPI_CONN: OnceLock<Option<Connection>> = OnceLock::new();

const ROLE_TOOL_BAR: u32 = 57;
const ROLE_ENTRY: u32 = 19;

enum BrowserType {
    Firefox,
    Chromium,
}

fn detect_browser(app_name: &str) -> Option<BrowserType> {
    let lower = app_name.to_lowercase();
    let tokens: Vec<&str> = lower
        .split(|c: char| !c.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .collect();
    if tokens.iter().any(|token| *token == "firefox") {
        return Some(BrowserType::Firefox);
    }
    if tokens.iter().any(|token| {
        matches!(
            *token,
            "chrome" | "chromium" | "brave" | "edge" | "vivaldi" | "opera"
        )
    }) {
        return Some(BrowserType::Chromium);
    }
    None
}

pub fn get_browser_url(app_name: &str, pid: u32) -> Option<String> {
    let browser_type = detect_browser(app_name)?;
    let conn = ATSPI_CONN.get_or_init(|| {
        let c = connect_atspi();
        if c.is_none() && !ATSPI_WARNED.swap(true, Ordering::Relaxed) {
            tracing::warn!("AT-SPI2 bus unavailable — URL extraction disabled");
        }
        c
    });
    let conn = conn.as_ref()?;

    let app_bus = find_app_by_pid(conn, pid)?;
    let toolbar_name = match browser_type {
        BrowserType::Firefox => "Navigation",
        BrowserType::Chromium => "",
    };

    find_url_in_toolbar(conn, &app_bus, toolbar_name, 6).filter(|u| is_url(u))
}

fn is_url(s: &str) -> bool {
    let s = s.trim();
    s.starts_with("http://")
        || s.starts_with("https://")
        || s.starts_with("file://")
        || s.starts_with("about:")
        || s.starts_with("chrome://")
        || s.starts_with("edge://")
        || s.starts_with("brave://")
        || s.starts_with("vivaldi://")
        || s.starts_with("opera://")
}

fn connect_atspi() -> Option<Connection> {
    let session = Connection::session().ok()?;
    let reply = session
        .call_method(
            Some("org.a11y.Bus"),
            "/org/a11y/atspi/bus",
            Some("org.a11y.Bus"),
            "GetAddress",
            &(),
        )
        .ok()?;
    let address: String = reply.body().deserialize().ok()?;
    let addr: zbus::Address = address.parse().ok()?;
    zbus::blocking::connection::Builder::address(addr)
        .ok()?
        .build()
        .ok()
}

fn find_app_by_pid(conn: &Connection, target_pid: u32) -> Option<String> {
    let reply = conn
        .call_method(
            Some("org.a11y.atspi.Registry"),
            "/org/a11y/atspi/accessible/root",
            Some("org.a11y.atspi.Accessible"),
            "GetChildren",
            &(),
        )
        .ok()?;
    let children: Vec<(String, OwnedObjectPath)> = reply.body().deserialize().ok()?;

    for (bus_name, _) in &children {
        if bus_pid(conn, bus_name) == Some(target_pid) {
            return Some(bus_name.to_string());
        }
    }
    None
}

fn bus_pid(conn: &Connection, bus_name: &str) -> Option<u32> {
    let reply = conn
        .call_method(
            Some("org.freedesktop.DBus"),
            "/org/freedesktop/DBus",
            Some("org.freedesktop.DBus"),
            "GetConnectionUnixProcessID",
            &(bus_name,),
        )
        .ok()?;
    reply.body().deserialize().ok()
}

fn get_children(conn: &Connection, dest: &str, path: &str) -> Option<Vec<(String, String)>> {
    let reply = conn
        .call_method(
            Some(dest),
            path,
            Some("org.a11y.atspi.Accessible"),
            "GetChildren",
            &(),
        )
        .ok()?;
    let children: Vec<(String, OwnedObjectPath)> = reply.body().deserialize().ok()?;
    Some(
        children
            .into_iter()
            .map(|(name, path): (String, OwnedObjectPath)| (name, path.to_string()))
            .collect(),
    )
}

fn get_role(conn: &Connection, dest: &str, path: &str) -> Option<u32> {
    let reply = conn
        .call_method(
            Some(dest),
            path,
            Some("org.a11y.atspi.Accessible"),
            "GetRole",
            &(),
        )
        .ok()?;
    reply.body().deserialize().ok()
}

fn get_accessible_name(conn: &Connection, dest: &str, path: &str) -> Option<String> {
    let reply = conn
        .call_method(
            Some(dest),
            path,
            Some("org.freedesktop.DBus.Properties"),
            "Get",
            &("org.a11y.atspi.Accessible", "Name"),
        )
        .ok()?;
    let value: OwnedValue = reply.body().deserialize().ok()?;
    String::try_from(value).ok()
}

fn get_text_content(conn: &Connection, dest: &str, path: &str) -> Option<String> {
    let reply = conn
        .call_method(
            Some(dest),
            path,
            Some("org.a11y.atspi.Text"),
            "GetCharacterCount",
            &(),
        )
        .ok()?;
    let count: i32 = reply.body().deserialize().ok()?;
    if count <= 0 || count > 4096 {
        return None;
    }

    let reply = conn
        .call_method(
            Some(dest),
            path,
            Some("org.a11y.atspi.Text"),
            "GetText",
            &(0i32, count),
        )
        .ok()?;
    let text: String = reply.body().deserialize().ok()?;
    if text.is_empty() {
        None
    } else {
        Some(text)
    }
}

fn find_url_in_toolbar(
    conn: &Connection,
    bus_name: &str,
    toolbar_name: &str,
    max_depth: u32,
) -> Option<String> {
    let children = get_children(conn, bus_name, "/org/a11y/atspi/accessible/root")?;
    for (_, frame_path) in &children {
        if let Some(url) = search_tree(conn, bus_name, frame_path, toolbar_name, max_depth, false) {
            return Some(url);
        }
    }
    None
}

fn search_tree(
    conn: &Connection,
    bus_name: &str,
    path: &str,
    toolbar_name: &str,
    depth: u32,
    in_toolbar: bool,
) -> Option<String> {
    if depth == 0 {
        return None;
    }

    let role = get_role(conn, bus_name, path)?;

    if in_toolbar && role == ROLE_ENTRY {
        return get_text_content(conn, bus_name, path);
    }

    let entering_toolbar = role == ROLE_TOOL_BAR
        && (toolbar_name.is_empty()
            || get_accessible_name(conn, bus_name, path)
                .map(|n| n == toolbar_name)
                .unwrap_or(false));

    let children = get_children(conn, bus_name, path)?;
    for (_, child_path) in &children {
        if let Some(url) = search_tree(
            conn,
            bus_name,
            child_path,
            toolbar_name,
            depth - 1,
            in_toolbar || entering_toolbar,
        ) {
            return Some(url);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_browser_firefox() {
        assert!(matches!(
            detect_browser("firefox"),
            Some(BrowserType::Firefox)
        ));
        assert!(matches!(
            detect_browser("Firefox"),
            Some(BrowserType::Firefox)
        ));
        assert!(matches!(
            detect_browser("firefox-esr"),
            Some(BrowserType::Firefox)
        ));
    }

    #[test]
    fn test_detect_browser_chromium() {
        assert!(matches!(
            detect_browser("google-chrome"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("Google Chrome"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("chromium"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("brave-browser"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("Brave Browser"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("microsoft-edge"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("vivaldi"),
            Some(BrowserType::Chromium)
        ));
        assert!(matches!(
            detect_browser("opera"),
            Some(BrowserType::Chromium)
        ));
    }

    #[test]
    fn test_detect_browser_none() {
        assert!(detect_browser("Terminal").is_none());
        assert!(detect_browser("VSCode").is_none());
        assert!(detect_browser("Slack").is_none());
    }

    #[test]
    fn test_is_url() {
        assert!(is_url("https://github.com"));
        assert!(is_url("http://localhost:3000"));
        assert!(is_url("file:///home/user/doc.html"));
        assert!(is_url("about:config"));
        assert!(is_url("chrome://settings"));
        assert!(is_url("edge://settings"));
        assert!(is_url("brave://settings"));
        assert!(is_url("vivaldi://settings"));
        assert!(is_url("opera://settings"));
        assert!(!is_url(""));
        assert!(!is_url("github.com"));
        assert!(!is_url("search query"));
    }
}
