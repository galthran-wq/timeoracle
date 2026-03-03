use std::process::Command;

fn main() {
    let describe = Command::new("git")
        .args(["describe", "--tags", "--match", "daemon-v*", "--always", "--dirty"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .unwrap_or_else(|| "unknown".into());

    let describe = describe.trim();

    let version = describe
        .strip_prefix("daemon-v")
        .unwrap_or(describe)
        .to_string();

    println!("cargo:rustc-env=DAEMON_VERSION={version}");
    println!("cargo:rerun-if-changed=../.git/HEAD");
    println!("cargo:rerun-if-changed=../.git/refs/");
}
