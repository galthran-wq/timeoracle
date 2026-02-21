use crate::config::Config;
use crate::error::{DaemonError, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize)]
struct LoginRequest {
    email: String,
    password: String,
}

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    #[allow(dead_code)]
    token_type: String,
}

/// Perform interactive login: prompt for email/password, POST to server, save token.
pub async fn login(server_url: &str, config_path: &Path) -> Result<()> {
    println!("Logging in to {server_url}");

    print!("Email: ");
    use std::io::Write;
    std::io::stdout().flush()?;

    let mut email = String::new();
    std::io::stdin().read_line(&mut email)?;
    let email = email.trim().to_string();

    let password = rpassword::prompt_password("Password: ")
        .map_err(|e| DaemonError::Auth(format!("Failed to read password: {e}")))?;

    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{server_url}/api/users/login"))
        .json(&LoginRequest { email, password })
        .send()
        .await?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(DaemonError::Auth(format!(
            "Login failed ({status}): {body}"
        )));
    }

    let token_resp: TokenResponse = resp.json().await?;

    let mut config = Config::load(config_path)?;
    config.server_url = server_url.to_string();
    config.auth_token = Some(token_resp.access_token);
    config.save(config_path)?;

    println!("Login successful! Token saved to {}", config_path.display());
    Ok(())
}

/// Check if a JWT token is expired by decoding the payload (without verification).
/// Returns true if expired or unparseable.
pub fn is_token_expired(token: &str) -> bool {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return true;
    }

    // JWT payload is base64url-encoded
    let payload = match base64url_decode(parts[1]) {
        Some(p) => p,
        None => return true,
    };

    let value: serde_json::Value = match serde_json::from_slice(&payload) {
        Ok(v) => v,
        Err(_) => return true,
    };

    let exp = match value.get("exp").and_then(|v| v.as_i64()) {
        Some(e) => e,
        None => return true,
    };

    let now = chrono::Utc::now().timestamp();
    now >= exp
}

fn base64url_decode(input: &str) -> Option<Vec<u8>> {
    // base64url: replace - with +, _ with /, add padding
    let mut s = input.replace('-', "+").replace('_', "/");
    match s.len() % 4 {
        2 => s.push_str("=="),
        3 => s.push('='),
        0 => {}
        _ => return None,
    }
    use std::io::Read;
    let mut decoder = base64_reader(&s)?;
    let mut result = Vec::new();
    decoder.read_to_end(&mut result).ok()?;
    Some(result)
}

fn base64_reader(input: &str) -> Option<std::io::Cursor<Vec<u8>>> {
    // Simple base64 decode without external crate
    let table = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut output = Vec::new();
    let mut buf: u32 = 0;
    let mut bits: u32 = 0;

    for &byte in input.as_bytes() {
        if byte == b'=' {
            break;
        }
        let val = table.iter().position(|&b| b == byte)? as u32;
        buf = (buf << 6) | val;
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            output.push((buf >> bits) as u8);
            buf &= (1 << bits) - 1;
        }
    }

    Some(std::io::Cursor::new(output))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_jwt(exp: i64) -> String {
        let header = base64url_encode(b"{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        let payload = base64url_encode(
            format!("{{\"sub\":\"test\",\"exp\":{exp}}}").as_bytes(),
        );
        format!("{header}.{payload}.fakesignature")
    }

    fn base64url_encode(input: &[u8]) -> String {
        let table = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut result = String::new();
        let mut i = 0;
        while i < input.len() {
            let b0 = input[i] as u32;
            let b1 = if i + 1 < input.len() { input[i + 1] as u32 } else { 0 };
            let b2 = if i + 2 < input.len() { input[i + 2] as u32 } else { 0 };

            let triple = (b0 << 16) | (b1 << 8) | b2;

            result.push(table[((triple >> 18) & 0x3F) as usize] as char);
            result.push(table[((triple >> 12) & 0x3F) as usize] as char);

            if i + 1 < input.len() {
                result.push(table[((triple >> 6) & 0x3F) as usize] as char);
            }
            if i + 2 < input.len() {
                result.push(table[(triple & 0x3F) as usize] as char);
            }

            i += 3;
        }
        // Convert to base64url
        result.replace('+', "-").replace('/', "_").trim_end_matches('=').to_string()
    }

    #[test]
    fn test_valid_non_expired_token() {
        let future = chrono::Utc::now().timestamp() + 3600; // 1 hour from now
        let token = make_jwt(future);
        assert!(!is_token_expired(&token));
    }

    #[test]
    fn test_expired_token() {
        let past = chrono::Utc::now().timestamp() - 3600; // 1 hour ago
        let token = make_jwt(past);
        assert!(is_token_expired(&token));
    }

    #[test]
    fn test_malformed_token() {
        assert!(is_token_expired("not.a.valid.jwt"));
        assert!(is_token_expired(""));
        assert!(is_token_expired("onlyonepart"));
    }

    #[test]
    fn test_token_without_exp() {
        let header = base64url_encode(b"{\"alg\":\"HS256\"}");
        let payload = base64url_encode(b"{\"sub\":\"test\"}");
        let token = format!("{header}.{payload}.sig");
        assert!(is_token_expired(&token)); // no exp = treated as expired
    }

    #[test]
    fn test_token_expiring_now() {
        let now = chrono::Utc::now().timestamp();
        let token = make_jwt(now);
        assert!(is_token_expired(&token)); // now >= exp means expired
    }
}
