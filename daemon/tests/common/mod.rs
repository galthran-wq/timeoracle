use timeoracle_daemon::events::{ActivityEvent, WindowInfo};

pub fn make_test_event() -> ActivityEvent {
    ActivityEvent::window_change(WindowInfo {
        app_name: "TestApp".into(),
        window_title: "Test Window".into(),
        url: None,
    })
}

pub fn make_test_token() -> String {
    let header = base64url_encode(b"{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
    let exp = chrono::Utc::now().timestamp() + 86400;
    let payload = base64url_encode(
        format!("{{\"sub\":\"test\",\"exp\":{exp}}}").as_bytes(),
    );
    format!("{header}.{payload}.fakesig")
}

pub fn base64url_encode(input: &[u8]) -> String {
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
    result.replace('+', "-").replace('/', "_").trim_end_matches('=').to_string()
}
