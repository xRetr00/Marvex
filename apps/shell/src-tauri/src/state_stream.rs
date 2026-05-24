use std::{
    io::{BufRead, BufReader, Write},
    net::TcpStream,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread,
    time::Duration,
};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AssistantStatusKind {
    Idle,
    Listening,
    Thinking,
    Working,
    UsingTools,
    Mcp,
    Skills,
    SearchingWeb,
    Talking,
    Asking,
    NeedsApproval,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AssistantStateEvent {
    pub schema_version: String,
    pub ts: String,
    pub status: AssistantStatusKind,
    pub detail: Option<String>,
    pub audio_level: f64,
    pub session_ref: Option<String>,
    pub trace_id: Option<String>,
    pub raw_audio_persisted: bool,
}

pub fn start_state_stream(app: AppHandle, token: String, shutdown: Arc<AtomicBool>) {
    thread::spawn(move || {
        while !shutdown.load(Ordering::SeqCst) {
            if let Err(err) = read_state_stream_once(&app, &token, &shutdown) {
                let _ = app.emit(
                    "supervisor-health",
                    format!("state stream unavailable: {err}"),
                );
            }
            thread::sleep(Duration::from_secs(2));
        }
    });
}

fn read_state_stream_once(
    app: &AppHandle,
    token: &str,
    shutdown: &AtomicBool,
) -> Result<(), String> {
    let mut stream =
        TcpStream::connect(("127.0.0.1", 8766)).map_err(|err| format!("connect failed: {err}"))?;
    stream.set_read_timeout(Some(Duration::from_secs(5))).ok();
    let request = format!(
        "GET /control/state/stream HTTP/1.1\r\nHost: 127.0.0.1:8766\r\nAccept: text/event-stream\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|err| format!("write failed: {err}"))?;
    let reader = BufReader::new(stream);
    let mut data_lines = Vec::new();
    for raw in reader.lines() {
        if shutdown.load(Ordering::SeqCst) {
            break;
        }
        let line = raw.map_err(|err| format!("read failed: {err}"))?;
        if let Some(data) = line.strip_prefix("data:") {
            data_lines.push(data.trim().to_string());
        } else if line.trim().is_empty() && !data_lines.is_empty() {
            if let Some(event) = parse_sse_data(&data_lines.join("\n")) {
                let _ = app.emit("assistant-state", event);
            }
            data_lines.clear();
        }
    }
    Ok(())
}

pub fn parse_sse_data(data: &str) -> Option<AssistantStateEvent> {
    let event: AssistantStateEvent = serde_json::from_str(data).ok()?;
    if event.raw_audio_persisted || !(0.0..=1.0).contains(&event.audio_level) {
        return None;
    }
    Some(event)
}

#[cfg(test)]
mod tests {
    use super::{parse_sse_data, AssistantStatusKind};

    #[test]
    fn parses_safe_state_event() {
        let event = parse_sse_data(r#"{"schema_version":"1","ts":"2026-05-22T00:00:00Z","status":"listening","detail":"Wake","audio_level":0.42,"session_ref":null,"trace_id":"trace-1","raw_audio_persisted":false}"#).expect("event");
        assert_eq!(event.status, AssistantStatusKind::Listening);
        assert_eq!(event.audio_level, 0.42);
    }

    #[test]
    fn rejects_raw_audio_persistence() {
        assert!(parse_sse_data(r#"{"schema_version":"1","ts":"2026-05-22T00:00:00Z","status":"listening","detail":null,"audio_level":0.1,"session_ref":null,"trace_id":null,"raw_audio_persisted":true}"#).is_none());
    }
}
