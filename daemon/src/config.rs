use crate::error::{DaemonError, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_server_url")]
    pub server_url: String,

    #[serde(default)]
    pub auth_token: Option<String>,

    #[serde(default = "default_poll_interval")]
    pub poll_interval_secs: u64,

    #[serde(default = "default_heartbeat_interval")]
    pub heartbeat_interval_secs: u64,

    #[serde(default = "default_idle_threshold")]
    pub idle_threshold_secs: u64,

    #[serde(default = "default_flush_interval")]
    pub flush_interval_secs: u64,

    #[serde(default = "default_flush_batch_size")]
    pub flush_batch_size: usize,

    #[serde(default)]
    pub ignore_apps: Vec<String>,

    #[serde(default = "default_log_level")]
    pub log_level: String,
}

fn default_server_url() -> String {
    "http://localhost:8000".into()
}
fn default_poll_interval() -> u64 {
    5
}
fn default_heartbeat_interval() -> u64 {
    300
}
fn default_idle_threshold() -> u64 {
    300
}
fn default_flush_interval() -> u64 {
    30
}
fn default_flush_batch_size() -> usize {
    100
}
fn default_log_level() -> String {
    "info".into()
}

impl Default for Config {
    fn default() -> Self {
        Self {
            server_url: default_server_url(),
            auth_token: None,
            poll_interval_secs: default_poll_interval(),
            heartbeat_interval_secs: default_heartbeat_interval(),
            idle_threshold_secs: default_idle_threshold(),
            flush_interval_secs: default_flush_interval(),
            flush_batch_size: default_flush_batch_size(),
            ignore_apps: Vec::new(),
            log_level: default_log_level(),
        }
    }
}

impl Config {
    pub fn config_dir() -> Result<PathBuf> {
        let home = std::env::var("HOME")
            .map_err(|_| DaemonError::Config("HOME environment variable not set".into()))?;
        Ok(PathBuf::from(home).join(".timeoracle"))
    }

    pub fn default_config_path() -> Result<PathBuf> {
        Ok(Self::config_dir()?.join("config.toml"))
    }

    pub fn load(path: &Path) -> Result<Self> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let content = std::fs::read_to_string(path)?;
        let config: Config = toml::from_str(&content)?;
        config.validate()?;
        Ok(config)
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let content = toml::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }

    fn validate(&self) -> Result<()> {
        if self.poll_interval_secs == 0 {
            return Err(DaemonError::Config(
                "poll_interval_secs must be > 0".into(),
            ));
        }
        if self.heartbeat_interval_secs == 0 {
            return Err(DaemonError::Config(
                "heartbeat_interval_secs must be > 0".into(),
            ));
        }
        if self.idle_threshold_secs == 0 {
            return Err(DaemonError::Config(
                "idle_threshold_secs must be > 0".into(),
            ));
        }
        if self.flush_interval_secs == 0 {
            return Err(DaemonError::Config(
                "flush_interval_secs must be > 0".into(),
            ));
        }
        if self.flush_batch_size == 0 {
            return Err(DaemonError::Config(
                "flush_batch_size must be > 0".into(),
            ));
        }
        Ok(())
    }

    pub fn buffer_db_path() -> Result<PathBuf> {
        Ok(Self::config_dir()?.join("buffer.db"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_defaults() {
        let config = Config::default();
        assert_eq!(config.server_url, "http://localhost:8000");
        assert_eq!(config.poll_interval_secs, 5);
        assert_eq!(config.heartbeat_interval_secs, 300);
        assert_eq!(config.idle_threshold_secs, 300);
        assert_eq!(config.flush_interval_secs, 30);
        assert_eq!(config.flush_batch_size, 100);
        assert!(config.ignore_apps.is_empty());
        assert_eq!(config.log_level, "info");
        assert!(config.auth_token.is_none());
    }

    #[test]
    fn test_toml_roundtrip() {
        let config = Config {
            server_url: "https://example.com".into(),
            auth_token: Some("test-token".into()),
            poll_interval_secs: 10,
            heartbeat_interval_secs: 600,
            idle_threshold_secs: 120,
            flush_interval_secs: 60,
            flush_batch_size: 50,
            ignore_apps: vec!["slack".into(), "discord".into()],
            log_level: "debug".into(),
        };
        let toml_str = toml::to_string_pretty(&config).unwrap();
        let parsed: Config = toml::from_str(&toml_str).unwrap();
        assert_eq!(parsed.server_url, config.server_url);
        assert_eq!(parsed.auth_token, config.auth_token);
        assert_eq!(parsed.poll_interval_secs, config.poll_interval_secs);
        assert_eq!(parsed.ignore_apps, config.ignore_apps);
    }

    #[test]
    fn test_partial_toml_uses_defaults() {
        let toml_str = r#"server_url = "https://myserver.com""#;
        let config: Config = toml::from_str(toml_str).unwrap();
        assert_eq!(config.server_url, "https://myserver.com");
        assert_eq!(config.poll_interval_secs, 5); // default
        assert!(config.auth_token.is_none()); // default
    }

    #[test]
    fn test_save_and_load() {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("config.toml");

        let config = Config {
            auth_token: Some("my-jwt".into()),
            ..Config::default()
        };
        config.save(&path).unwrap();

        let loaded = Config::load(&path).unwrap();
        assert_eq!(loaded.auth_token, Some("my-jwt".into()));
        assert_eq!(loaded.server_url, "http://localhost:8000");
    }

    #[test]
    fn test_load_nonexistent_returns_default() {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("nonexistent.toml");
        let config = Config::load(&path).unwrap();
        assert_eq!(config.server_url, "http://localhost:8000");
    }

    #[test]
    fn test_validation_zero_poll_interval() {
        let toml_str = "poll_interval_secs = 0";
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("config.toml");
        std::fs::write(&path, toml_str).unwrap();
        let result = Config::load(&path);
        assert!(result.is_err());
    }

    #[test]
    fn test_creates_parent_dirs_on_save() {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("sub").join("dir").join("config.toml");
        let config = Config::default();
        config.save(&path).unwrap();
        assert!(path.exists());
    }

    #[test]
    fn test_empty_toml_gives_defaults() {
        let config: Config = toml::from_str("").unwrap();
        assert_eq!(config.poll_interval_secs, 5);
        assert_eq!(config.flush_batch_size, 100);
    }
}
