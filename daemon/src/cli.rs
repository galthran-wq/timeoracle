use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(
    name = "digitalgulag-daemon",
    about = "digitalgulag activity tracking daemon",
    version = env!("DAEMON_VERSION"),
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Command>,
}

#[derive(Subcommand, Debug)]
pub enum Command {
    Run {
        #[arg(long)]
        headless: bool,

        #[arg(long)]
        config: Option<PathBuf>,
    },

    Login {
        #[arg(long, default_value = "http://localhost:8000")]
        server_url: String,
    },

    Install {
        #[arg(long)]
        uninstall: bool,
    },

    Status,
}
