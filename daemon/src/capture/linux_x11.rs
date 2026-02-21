use crate::capture::ActivitySource;
use crate::error::{DaemonError, Result};
use crate::events::WindowInfo;
use x11rb::connection::Connection;
use x11rb::protocol::xproto::{self, ConnectionExt};
use x11rb::rust_connection::RustConnection;

pub struct X11Source {
    conn: RustConnection,
    root: u32,
}

impl X11Source {
    pub fn new() -> Result<Self> {
        let (conn, screen_num) = RustConnection::connect(None)
            .map_err(|e| DaemonError::Capture(format!("X11 connection failed: {e}")))?;
        let root = conn.setup().roots[screen_num].root;
        Ok(Self { conn, root })
    }

    fn get_active_window_id(&self) -> Result<Option<u32>> {
        let atom = self
            .conn
            .intern_atom(false, b"_NET_ACTIVE_WINDOW")
            .map_err(|e| DaemonError::Capture(format!("intern_atom failed: {e}")))?
            .reply()
            .map_err(|e| DaemonError::Capture(format!("intern_atom reply failed: {e}")))?
            .atom;

        let reply = self
            .conn
            .get_property(false, self.root, atom, xproto::AtomEnum::WINDOW, 0, 1)
            .map_err(|e| DaemonError::Capture(format!("get_property failed: {e}")))?
            .reply()
            .map_err(|e| DaemonError::Capture(format!("get_property reply failed: {e}")))?;

        if reply.value_len == 0 {
            return Ok(None);
        }

        let window_id = u32::from_ne_bytes(
            reply.value[..4]
                .try_into()
                .map_err(|_| DaemonError::Capture("Invalid window ID bytes".into()))?,
        );

        if window_id == 0 {
            return Ok(None);
        }

        Ok(Some(window_id))
    }

    fn get_window_name(&self, window: u32) -> Option<String> {
        // Try _NET_WM_NAME first (UTF-8)
        let utf8_atom = self
            .conn
            .intern_atom(false, b"_NET_WM_NAME")
            .ok()?
            .reply()
            .ok()?
            .atom;
        let utf8_type = self
            .conn
            .intern_atom(false, b"UTF8_STRING")
            .ok()?
            .reply()
            .ok()?
            .atom;

        let reply = self
            .conn
            .get_property(false, window, utf8_atom, utf8_type, 0, 1024)
            .ok()?
            .reply()
            .ok()?;

        if reply.value_len > 0 {
            return String::from_utf8(reply.value).ok();
        }

        // Fallback to WM_NAME
        let reply = self
            .conn
            .get_property(
                false,
                window,
                xproto::AtomEnum::WM_NAME,
                xproto::AtomEnum::STRING,
                0,
                1024,
            )
            .ok()?
            .reply()
            .ok()?;

        if reply.value_len > 0 {
            return String::from_utf8(reply.value).ok();
        }

        None
    }

    fn get_window_class(&self, window: u32) -> Option<String> {
        let reply = self
            .conn
            .get_property(
                false,
                window,
                xproto::AtomEnum::WM_CLASS,
                xproto::AtomEnum::STRING,
                0,
                1024,
            )
            .ok()?
            .reply()
            .ok()?;

        if reply.value_len == 0 {
            return None;
        }

        // WM_CLASS is two null-terminated strings: instance\0class\0
        // We want the class (second part)
        let parts: Vec<&[u8]> = reply.value.split(|&b| b == 0).collect();
        if parts.len() >= 2 {
            String::from_utf8(parts[1].to_vec()).ok()
        } else if !parts.is_empty() {
            String::from_utf8(parts[0].to_vec()).ok()
        } else {
            None
        }
    }
}

impl ActivitySource for X11Source {
    fn get_active_window(&self) -> Result<Option<WindowInfo>> {
        let window_id = match self.get_active_window_id()? {
            Some(id) => id,
            None => return Ok(None),
        };

        let app_name = self
            .get_window_class(window_id)
            .unwrap_or_else(|| "Unknown".into());
        let window_title = self
            .get_window_name(window_id)
            .unwrap_or_else(|| "".into());

        Ok(Some(WindowInfo {
            app_name,
            window_title,
            url: None, // URL extraction requires browser-specific integration
        }))
    }
}
