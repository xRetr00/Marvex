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

/// Client for SSE streaming turns. Uses no overall request timeout: a reasoning
/// model can stream for minutes, and a whole-request deadline would abort a
/// healthy stream mid-flight (surfacing as "error decoding response body").
/// Liveness is handled at the call site via the cancel channel; the connect
/// timeout still guards a dead server.
fn streaming_client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(5))
        .build()
        .map_err(|err| format!("http client init failed: {err}"))
}

pub struct LoopbackHttpClient {
    host: String,
    port: u16,
    client: reqwest::Client,
}

impl LoopbackHttpClient {
    pub fn new(host: &str, port: u16, timeout: Duration) -> Result<Self, String> {
        if !loopback_ok(host) {
            return Err("loopback host required".to_string());
        }
        Ok(Self {
            host: host.to_string(),
            port,
            client: client(timeout)?,
        })
    }

    pub fn url(&self, path: &str) -> Result<reqwest::Url, String> {
        reqwest::Url::parse(&format!("http://{}:{}{}", self.host, self.port, path))
            .map_err(|err| format!("invalid local URL: {err}"))
    }

    async fn get(&self, path: &str, token: Option<&str>) -> Result<HttpResponse, String> {
        let mut req = self
            .client
            .get(self.url(path)?)
            .header("Accept", "application/json");
        if let Some(token) = token {
            req = req.bearer_auth(token);
        }
        response_from_request(req).await
    }

    async fn post_json(
        &self,
        path: &str,
        token: Option<&str>,
        body: &Value,
    ) -> Result<HttpResponse, String> {
        let mut req = self
            .client
            .post(self.url(path)?)
            .header("Accept", "application/json")
            .json(body);
        if let Some(token) = token {
            req = req.bearer_auth(token);
        }
        response_from_request(req).await
    }

    async fn delete(&self, path: &str, token: Option<&str>) -> Result<HttpResponse, String> {
        let mut req = self
            .client
            .delete(self.url(path)?)
            .header("Accept", "application/json");
        if let Some(token) = token {
            req = req.bearer_auth(token);
        }
        response_from_request(req).await
    }
}

async fn response_from_request(req: reqwest::RequestBuilder) -> Result<HttpResponse, String> {
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
    LoopbackHttpClient::new(host, port, timeout)?
        .get(path, token)
        .await
}

pub async fn http_post_json_with_timeout(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
    body: &Value,
    timeout: Duration,
) -> Result<HttpResponse, String> {
    LoopbackHttpClient::new(host, port, timeout)?
        .post_json(path, token, body)
        .await
}

pub async fn http_delete_with_timeout(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
    timeout: Duration,
) -> Result<HttpResponse, String> {
    LoopbackHttpClient::new(host, port, timeout)?
        .delete(path, token)
        .await
}

/// Open a streaming POST (docs/TODO/06): returns the raw reqwest Response so the
/// caller can read the SSE body incrementally via `Response::chunk()`. Loopback
/// only. Non-2xx responses are read fully and returned as an error string.
pub async fn open_post_stream(
    host: &str,
    port: u16,
    path: &str,
    token: Option<&str>,
    body: &Value,
    _timeout: Duration,
) -> Result<reqwest::Response, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let client = streaming_client()?;
    let url = reqwest::Url::parse(&format!("http://{host}:{port}{path}"))
        .map_err(|err| format!("invalid local URL: {err}"))?;
    let mut req = client
        .post(url)
        .header("Accept", "text/event-stream")
        // Read the SSE bytes verbatim; auto-decompression of a chunked stream
        // can fail to decode at a flush boundary.
        .header("Accept-Encoding", "identity")
        .json(body);
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req
        .send()
        .await
        .map_err(|err| format!("stream request failed: {err}"))?;
    let status = resp.status();
    if !status.is_success() {
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("stream http {}: {body}", status.as_u16()));
    }
    Ok(resp)
}

#[cfg(test)]
mod tests {
    use super::{
        loopback_ok, LoopbackHttpClient, CONTROL_POST_HTTP_TIMEOUT, DEFAULT_HTTP_TIMEOUT,
        TURN_HTTP_TIMEOUT,
    };
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

    #[test]
    fn loopback_http_client_builds_local_urls_and_rejects_remote_hosts() {
        let client = LoopbackHttpClient::new("127.0.0.1", 8765, DEFAULT_HTTP_TIMEOUT)
            .expect("loopback client");

        assert_eq!(
            client.url("/health").expect("url").as_str(),
            "http://127.0.0.1:8765/health"
        );
        assert!(LoopbackHttpClient::new("example.com", 8765, DEFAULT_HTTP_TIMEOUT).is_err());
    }
}
