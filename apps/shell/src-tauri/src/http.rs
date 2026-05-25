use std::time::Duration;

use serde_json::Value;

pub const DEFAULT_HTTP_TIMEOUT: Duration = Duration::from_secs(15);
pub const TURN_HTTP_TIMEOUT: Duration = Duration::from_secs(120);
pub const CONTROL_POST_HTTP_TIMEOUT: Duration = Duration::from_secs(300);

#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

fn loopback_ok(host: &str) -> bool {
    matches!(host, "127.0.0.1" | "localhost" | "::1")
}

fn client(timeout: Duration) -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(2))
        .timeout(timeout)
        .build()
        .map_err(|err| format!("http client init failed: {err}"))
}

pub async fn http_get(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
) -> Result<HttpResponse, String> {
    http_get_with_timeout(host, port, path, token, DEFAULT_HTTP_TIMEOUT).await
}

pub async fn http_get_with_timeout(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
    timeout: Duration,
) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client(timeout)?
        .get(url)
        .header("Accept", "application/json");
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req
        .send()
        .await
        .map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let body = resp
        .text()
        .await
        .map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body })
}

pub async fn http_post_json_with_timeout(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
    body: &Value,
    timeout: Duration,
) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client(timeout)?
        .post(url)
        .header("Accept", "application/json")
        .json(body);
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req
        .send()
        .await
        .map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let text = resp
        .text()
        .await
        .map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body: text })
}

#[cfg(test)]
mod tests {
    use super::{loopback_ok, CONTROL_POST_HTTP_TIMEOUT, DEFAULT_HTTP_TIMEOUT, TURN_HTTP_TIMEOUT};
    use std::time::Duration;

    #[test]
    fn only_loopback_hosts_allowed() {
        assert!(loopback_ok("127.0.0.1"));
        assert!(loopback_ok("localhost"));
        assert!(!loopback_ok("example.com"));
    }

    #[test]
    fn long_running_shell_requests_have_explicit_timeout_classes() {
        assert_eq!(DEFAULT_HTTP_TIMEOUT, Duration::from_secs(15));
        assert_eq!(TURN_HTTP_TIMEOUT, Duration::from_secs(120));
        assert_eq!(CONTROL_POST_HTTP_TIMEOUT, Duration::from_secs(300));
    }
}
