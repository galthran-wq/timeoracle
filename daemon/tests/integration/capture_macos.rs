#[cfg(target_os = "macos")]
mod macos_tests {
    use digitalgulag_daemon::capture::macos::MacOSSource;
    use digitalgulag_daemon::capture::ActivitySource;

    #[test]
    fn test_macos_source_creation() {
        let _source = MacOSSource::new();
    }

    #[test]
    fn test_macos_get_active_window() {
        if std::env::var("CI").is_ok() {
            // No GUI session in CI — skip
            return;
        }

        let source = MacOSSource::new();
        let result = source.get_active_window();
        assert!(
            result.is_ok(),
            "get_active_window should not error: {:?}",
            result.err()
        );
    }
}
