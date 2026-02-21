use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "timeoracle-daemon", about = "TimeOracle activity tracking daemon")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand, Debug)]
pub enum Command {
    /// Start the daemon
    Run {
        /// Run without system tray (headless mode)
        #[arg(long)]
        headless: bool,

        /// Path to config file
        #[arg(long)]
        config: Option<PathBuf>,
    },

    /// Login to the TimeOracle server
    Login {
        /// Server URL
        #[arg(long, default_value = "http://localhost:8000")]
        server_url: String,
    },

    /// Install/uninstall as a system service
    Install {
        /// Remove the service instead of installing
        #[arg(long)]
        uninstall: bool,
    },

    /// Show daemon status
    Status,
}
