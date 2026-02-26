mod auth;
mod buffer;
mod capture;
mod cli;
mod config;
mod engine;
mod error;
mod events;
mod service;
mod sync;
mod tray;

use clap::Parser;
use cli::{Cli, Command};
use config::Config;
use tracing_subscriber::EnvFilter;

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    let command = cli.command.unwrap_or(Command::Run { headless: false, config: None });

    match command {
        Command::Run { headless, config: config_path } => {
            let config_path = config_path
                .unwrap_or_else(|| Config::default_config_path().expect("Cannot determine config path"));
            let config = Config::load(&config_path)?;

            init_tracing(&config.log_level);
            tracing::info!("Starting TimeOracle daemon");

            if headless {
                if config.auth_token.is_none() {
                    anyhow::bail!("Not logged in. Run `timeoracle-daemon login` first.");
                }
                run_headless(config)?;
            } else {
                run_with_tray(config)?;
            }
        }
        Command::Login { server_url } => {
            let config_path = Config::default_config_path()?;
            let rt = tokio::runtime::Runtime::new()?;
            rt.block_on(auth::login(&server_url, &config_path))?;
        }
        Command::Install { uninstall } => {
            if uninstall {
                service::uninstall()?;
            } else {
                service::install()?;
            }
        }
        Command::Status => {
            show_status()?;
        }
    }

    Ok(())
}

fn init_tracing(log_level: &str) {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .init();
}

fn run_headless(config: Config) -> anyhow::Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async {
        let (shutdown_tx, shutdown_rx) = tokio::sync::broadcast::channel::<()>(1);
        let (cmd_tx, cmd_rx) = tokio::sync::mpsc::channel::<engine::EngineCommand>(32);
        let (status_tx, status_rx) = tokio::sync::watch::channel(engine::DaemonStatus::default());

        let _ = status_rx; // Not used in headless mode

        // Spawn signal handler
        let shutdown_tx_clone = shutdown_tx.clone();
        tokio::spawn(async move {
            tokio::signal::ctrl_c().await.ok();
            tracing::info!("Received Ctrl+C, shutting down...");
            let _ = shutdown_tx_clone.send(());
        });

        let buffer_path = Config::buffer_db_path()?;
        let buffer = std::sync::Arc::new(std::sync::Mutex::new(
            buffer::EventBuffer::open(&buffer_path)?,
        ));

        // Spawn engine
        let engine_handle = {
            let config = config.clone();
            let buffer = buffer.clone();
            let shutdown_rx = shutdown_tx.subscribe();
            tokio::spawn(async move {
                engine::run(config, buffer, cmd_rx, status_tx, shutdown_rx).await
            })
        };

        // Spawn sync task
        let sync_handle = {
            let config = config.clone();
            let buffer = buffer.clone();
            let shutdown_rx = shutdown_tx.subscribe();
            tokio::spawn(async move {
                sync::run(config, buffer, shutdown_rx).await
            })
        };

        let _ = cmd_tx; // Drop command sender — no tray to send commands
        let _ = shutdown_rx;

        tokio::select! {
            r = engine_handle => { r??; }
            r = sync_handle => { r??; }
        }

        Ok(())
    })
}

fn run_with_tray(config: Config) -> anyhow::Result<()> {
    tray::run(config)
}

fn show_status() -> anyhow::Result<()> {
    let config_path = Config::default_config_path()?;
    let config = Config::load(&config_path)?;

    println!("TimeOracle Daemon Status");
    println!("========================");
    println!("Config: {}", config_path.display());
    println!("Server: {}", config.server_url);

    match &config.auth_token {
        Some(token) => {
            if auth::is_token_expired(token) {
                println!("Auth: Token expired — run `timeoracle-daemon login`");
            } else {
                println!("Auth: Logged in");
            }
        }
        None => println!("Auth: Not logged in"),
    }

    let buffer_path = Config::buffer_db_path()?;
    if buffer_path.exists() {
        match buffer::EventBuffer::open(&buffer_path) {
            Ok(buf) => match buf.count() {
                Ok(count) => println!("Buffer: {count} events pending"),
                Err(e) => println!("Buffer: error reading ({e})"),
            },
            Err(e) => println!("Buffer: error opening ({e})"),
        }
    } else {
        println!("Buffer: no database");
    }

    Ok(())
}
