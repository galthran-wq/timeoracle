#[cfg(target_os = "linux")]
mod linux_x11_tests {
    use timeoracle_daemon::capture::ActivitySource;

    #[test]
    fn test_x11_connection() {
        if std::env::var("DISPLAY").is_err() {
            // Skip on headless CI
            return;
        }

        let source = timeoracle_daemon::capture::linux_x11::X11Source::new();
        assert!(source.is_ok(), "X11 source should connect when DISPLAY is set");
    }

    #[test]
    fn test_x11_get_active_window() {
        if std::env::var("DISPLAY").is_err() {
            return;
        }

        let source = match timeoracle_daemon::capture::linux_x11::X11Source::new() {
            Ok(s) => s,
            Err(_) => return, // Can't connect, skip
        };

        // Should not panic — may return None if no window manager is running
        let result = source.get_active_window();
        assert!(result.is_ok(), "get_active_window should not error");
    }
}
