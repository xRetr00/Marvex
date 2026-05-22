use std::{
    io::{Read, Write},
    net::TcpStream,
    time::Duration,
};

use serde_json::Value;

#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

pub fn http_get(host: &str, port: u16, path: &str, token: Option<&str>) -> Result<HttpResponse, String> {
    request("GET", host, port, path, token, None)
}

pub fn http_post_json(host: &str, port: u16, path: &str, token: Option<&str>, body: &Value) -> Result<HttpResponse, String> {
    request("POST", host, port, path, token, Some(&body.to_string()))
}

fn request(method: &str, host: &str, port: u16, path: &str, token: Option<&str>, body: Option<&str>) -> Result<HttpResponse, String> {
    if !matches!(host, "127.0.0.1" | "localhost" | "::1") {
        return Err("loopback host required".to_string());
    }
    let mut stream = TcpStream::connect((host, port)).map_err(|err| format!("connect failed: {err}"))?;
    stream.set_read_timeout(Some(Duration::from_secs(20))).ok();
    stream.set_write_timeout(Some(Duration::from_secs(5))).ok();
    let body_text = body.unwrap_or("");
    let auth = token.map(|value| format!("Authorization: Bearer {value}\r\n")).unwrap_or_default();
    let content = if body.is_some() {
        format!("Content-Type: application/json\r\nContent-Length: {}\r\n", body_text.len())
    } else {
        String::new()
    };
    let request = format!("{method} {path} HTTP/1.1\r\nHost: {host}:{port}\r\nAccept: application/json\r\n{auth}{content}Connection: close\r\n\r\n{body_text}");
    stream.write_all(request.as_bytes()).map_err(|err| format!("write failed: {err}"))?;
    let mut response = String::new();
    stream.read_to_string(&mut response).map_err(|err| format!("read failed: {err}"))?;
    parse_response(&response)
}

pub fn parse_response(response: &str) -> Result<HttpResponse, String> {
    let (head, body) = response.split_once("\r\n\r\n").ok_or_else(|| "invalid HTTP response".to_string())?;
    let status = head
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok())
        .ok_or_else(|| "missing HTTP status".to_string())?;
    Ok(HttpResponse { status, body: body.to_string() })
}

#[cfg(test)]
mod tests {
    use super::parse_response;

    #[test]
    fn parses_status_and_body() {
        let response = parse_response("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}").expect("response");
        assert_eq!(response.status, 200);
        assert_eq!(response.body, "{}");
    }
}
