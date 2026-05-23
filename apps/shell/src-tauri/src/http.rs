use std::time::Duration;

use serde_json::Value;

#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

fn loopback_ok(host: &str) -> bool {
    matches!(host, "127.0.0.1" | "localhost" | "::1")
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|err| format!("http client init failed: {err}"))
}

pub async fn http_get(host: &str, port: u16, path: &str, token: Option<&str>) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client()?.get(url).header("Accept", "application/json");
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await.map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let body = resp.text().await.map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body })
}

pub async fn http_post_json(host: &str, port: u16, path: &str, token: Option<&str>, body: &Value) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client()?.post(url).header("Accept", "application/json").json(body);
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await.map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let text = resp.text().await.map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body: text })
}

#[cfg(test)]
mod tests {
    use super::loopback_ok;

    #[test]
    fn only_loopback_hosts_allowed() {
        assert!(loopback_ok("127.0.0.1"));
        assert!(loopback_ok("localhost"));
        assert!(!loopback_ok("example.com"));
    }
}
