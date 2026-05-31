mod http;
mod state_stream;
mod supervisor;
mod token;
mod token_handoff;

#[cfg(windows)]
pub mod service;

use std::{
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    time::{Duration, SystemTime, UNIX_EPOCH},
};

/// Set while an explicit Marvex shutdown is in progress so the main window's
/// CloseRequested handler stops swallowing the close (otherwise quit hangs and
/// the process must be killed from Task Manager).
static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);

use serde::Serialize;
use serde_json::{json, Value};
use supervisor::Supervisor;
use tauri::{
    image::Image, menu::MenuBuilder, tray::TrayIconBuilder, AppHandle, Emitter, Manager,
    WindowEvent,
};
use tauri_plugin_autostart::ManagerExt as AutostartManagerExt;

#[derive(Clone, Serialize)]
struct ShellRuntimeConfig {
    core_base_url: String,
    control_base_url: String,
    auth_token_present: bool,
    token_value_logged: bool,
}

struct ShellState {
    token: String,
    supervisor: Supervisor,
}

const TRAY_ICON_BYTES: &[u8] = include_bytes!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../assets/icon.ico"
));

#[tauri::command]
fn shell_runtime_config() -> ShellRuntimeConfig {
    ShellRuntimeConfig {
        core_base_url: "http://127.0.0.1:8765".to_string(),
        control_base_url: "http://127.0.0.1:8766/control".to_string(),
        auth_token_present: true,
        token_value_logged: false,
    }
}

#[tauri::command]
fn supervisor_status(state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    let state = state
        .lock()
        .map_err(|_| "shell state unavailable".to_string())?;
    Ok(json!(state.supervisor.status.snapshot()))
}

/// Structured first-run/setup status: runtime bootstrap phase, per-service
/// status, an overall `ready` flag, and the runtime manifest when present.
#[tauri::command]
fn get_setup_status(state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    let state = state
        .lock()
        .map_err(|_| "shell state unavailable".to_string())?;
    let snapshot = state.supervisor.status.snapshot();
    let runtime_phase = snapshot
        .get("runtime")
        .cloned()
        .unwrap_or_else(|| "unknown".to_string());
    let runtime_ok = matches!(runtime_phase.as_str(), "ready" | "dev");
    let core_running = snapshot
        .get("core")
        .map(|s| s.starts_with("running"))
        .unwrap_or(false)
        || loopback_port_open(8765);
    let manifest = std::fs::read_to_string(state.supervisor.runtime_manifest_path())
        .ok()
        .and_then(|text| serde_json::from_str::<Value>(&text).ok());
    Ok(json!({
        "schema_version": "1",
        "runtime_phase": runtime_phase,
        "ready": runtime_ok && core_running,
        "launched": state.supervisor.is_launched(),
        "services": snapshot,
        "manifest": manifest,
    }))
}

/// Re-attempt the runtime bootstrap (no-op once services are running). Returns
/// the refreshed setup status.
#[tauri::command]
fn start_setup(state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    {
        let state = state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?;
        state.supervisor.retry_setup();
    }
    get_setup_status(state)
}

/// Alias of `start_setup` for callers that think in terms of "start the backend".
#[tauri::command]
fn start_backend(state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    start_setup(state)
}

/// Health of the Core daemon (loopback /health on 8765).
#[tauri::command]
async fn backend_health(state: tauri::State<'_, Mutex<ShellState>>) -> Result<Value, String> {
    let token = {
        state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?
            .token
            .clone()
    };
    match http::http_get("127.0.0.1", 8765, "/health", Some(&token)).await {
        Ok(response) => {
            let body: Value =
                serde_json::from_str(&response.body).unwrap_or_else(|_| json!({"raw": false}));
            Ok(
                json!({"reachable": response.status == 200, "status_code": response.status, "health": body}),
            )
        }
        Err(err) => Ok(json!({"reachable": false, "error": err})),
    }
}

/// Health of the GUI/shell process itself (always ok while this command runs).
#[tauri::command]
fn gui_health(state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    let snapshot = state
        .lock()
        .map_err(|_| "shell state unavailable".to_string())?
        .supervisor
        .status
        .snapshot();
    let services_running = snapshot
        .iter()
        .filter(|(name, value)| *name != "runtime" && value.starts_with("running"))
        .count();
    Ok(json!({
        "schema_version": "1",
        "component": "marvex-shell",
        "status": "ok",
        "services_running": services_running,
        "runtime_phase": snapshot.get("runtime").cloned().unwrap_or_else(|| "unknown".to_string()),
    }))
}

#[tauri::command]
async fn submit_chat_turn(
    text: String,
    metadata: Option<Value>,
    previous_response_id: Option<String>,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<Value, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("chat text must be non-empty".to_string());
    }
    let (token, session_id) = {
        let guard = state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?;
        (guard.token.clone(), session_id_from_metadata(&metadata))
    };
    let now = monotonic_id();
    let trace_id = format!("trace-shell-chat-{now}");
    let turn_id = format!("turn-shell-chat-{now}");
    let previous_response_id = previous_response_id.and_then(|id| {
        let trimmed = id.trim().to_string();
        (!trimmed.is_empty()).then_some(trimmed)
    });
    let body = json!({
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_lmstudio_responses",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": format!("event-shell-chat-{now}"),
            "session_ref": {"ref_type": "session", "ref_id": session_id},
            "identity_ref": null,
            "user_visible_input": text,
            "assistant_mode": "default",
            "policy_context": {"requested_capabilities": [], "sensitivity": "normal"},
            "metadata": safe_shell_turn_metadata(metadata)
        },
        "model": default_chat_model(),
        "instructions": null,
        "previous_response_id": previous_response_id,
        "resume_approval_id": null,
        "approval_decision": null,
        "provider_options": {}
    });
    let response = http::http_post_json_with_timeout(
        "127.0.0.1",
        8765,
        "/v1/turns",
        Some(&token),
        &body,
        http::TURN_HTTP_TIMEOUT,
    )
    .await?;
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Core response: {err}"))
}

/// Streaming variant of `submit_chat_turn` (docs/TODO/06). Opens the Core SSE
/// endpoint, emits a `chat-stream` Tauri event for each delta/final/error frame
/// (tagged with `turn_id`), and resolves with the terminal `AssistantTurnResult`
/// so callers can reconcile. `submit_chat_turn` stays the non-streaming path.
#[tauri::command]
async fn submit_chat_turn_stream(
    app: AppHandle,
    text: String,
    metadata: Option<Value>,
    previous_response_id: Option<String>,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<Value, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("chat text must be non-empty".to_string());
    }
    let (token, session_id) = {
        let guard = state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?;
        (guard.token.clone(), session_id_from_metadata(&metadata))
    };
    let now = monotonic_id();
    let trace_id = format!("trace-shell-chat-{now}");
    let turn_id = format!("turn-shell-chat-{now}");
    let previous_response_id = previous_response_id.and_then(|id| {
        let trimmed = id.trim().to_string();
        (!trimmed.is_empty()).then_some(trimmed)
    });
    let body = json!({
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_lmstudio_responses",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": format!("event-shell-chat-{now}"),
            "session_ref": {"ref_type": "session", "ref_id": session_id},
            "identity_ref": null,
            "user_visible_input": text,
            "assistant_mode": "default",
            "policy_context": {"requested_capabilities": [], "sensitivity": "normal"},
            "metadata": safe_shell_turn_metadata(metadata)
        },
        "model": default_chat_model(),
        "instructions": null,
        "previous_response_id": previous_response_id,
        "resume_approval_id": null,
        "approval_decision": null,
        "provider_options": {}
    });

    let mut response = http::open_post_stream(
        "127.0.0.1",
        8765,
        "/v1/turns/stream",
        Some(&token),
        &body,
        http::TURN_HTTP_TIMEOUT,
    )
    .await?;

    let mut buffer = String::new();
    let mut final_result: Option<Value> = None;
    loop {
        let chunk = response
            .chunk()
            .await
            .map_err(|err| format!("stream read failed: {err}"))?;
        let Some(bytes) = chunk else { break };
        buffer.push_str(&String::from_utf8_lossy(&bytes));
        while let Some(idx) = buffer.find("\n\n") {
            let frame: String = buffer.drain(..idx + 2).collect();
            let Some(data) = frame.lines().find_map(|line| line.strip_prefix("data:")) else {
                continue;
            };
            let Ok(event) = serde_json::from_str::<Value>(data.trim()) else {
                continue;
            };
            if event.get("type").and_then(|value| value.as_str()) == Some("final") {
                final_result = event.get("result").cloned();
            }
            let _ = app.emit("chat-stream", json!({"turn_id": turn_id, "event": event}));
        }
    }

    final_result.ok_or_else(|| "stream ended without a final result".to_string())
}

fn session_id_from_metadata(metadata: &Option<Value>) -> String {
    if let Some(Value::Object(map)) = metadata {
        if let Some(Value::String(id)) = map.get("session_id") {
            let trimmed = id.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }
    "shell-session".to_string()
}

fn loopback_port_open(port: u16) -> bool {
    let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    TcpStream::connect_timeout(&addr, Duration::from_millis(150)).is_ok()
}

fn default_chat_model() -> String {
    std::env::var("MARVEX_MODEL")
        .or_else(|_| std::env::var("MARVEX_DEFAULT_MODEL"))
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "openrouter/anthropic/claude-3.5-sonnet".to_string())
}

fn safe_shell_turn_metadata(metadata: Option<Value>) -> Value {
    let mut safe = json!({"source": "marvex_shell"});
    let Some(Value::Object(input)) = metadata else {
        return safe;
    };
    for key in [
        "agent_profile_id",
        "persona_profile_id",
        "selected_voice_id",
    ] {
        if let Some(Value::String(value)) = input.get(key) {
            let trimmed = value.trim();
            if !trimmed.is_empty() {
                safe[key] = Value::String(trimmed.to_string());
            }
        }
    }
    safe
}

#[tauri::command]
async fn create_chat_session(
    title: Option<String>,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<Value, String> {
    let token = {
        state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?
            .token
            .clone()
    };
    let response = http::http_post_json_with_timeout(
        "127.0.0.1",
        8766,
        "/control/sessions",
        Some(&token),
        &json!({ "title": title.unwrap_or_else(|| "New chat".to_string()) }),
        http::DEFAULT_HTTP_TIMEOUT,
    )
    .await?;
    serde_json::from_str(&response.body)
        .map_err(|err| format!("invalid Control Plane session response: {err}"))
}

#[tauri::command]
async fn list_chat_sessions(state: tauri::State<'_, Mutex<ShellState>>) -> Result<Value, String> {
    let token = {
        state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?
            .token
            .clone()
    };
    let response = http::http_get("127.0.0.1", 8766, "/control/sessions", Some(&token)).await?;
    serde_json::from_str(&response.body)
        .map_err(|err| format!("invalid Control Plane session list response: {err}"))
}

#[tauri::command]
async fn control_request(
    path: String,
    method: String,
    body: Option<Value>,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<Value, String> {
    if !path.starts_with('/') || path.contains("://") {
        return Err("control path must be local".to_string());
    }
    let token = {
        state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?
            .token
            .clone()
    };
    let full_path = format!("/control{path}");
    let response = if method.eq_ignore_ascii_case("POST") {
        http::http_post_json_with_timeout(
            "127.0.0.1",
            8766,
            &full_path,
            Some(&token),
            &body.unwrap_or_else(|| json!({})),
            http::CONTROL_POST_HTTP_TIMEOUT,
        )
        .await?
    } else {
        http::http_get("127.0.0.1", 8766, &full_path, Some(&token)).await?
    };
    serde_json::from_str(&response.body)
        .map_err(|err| format!("invalid Control Plane response: {err}"))
}

#[tauri::command]
async fn control_plane_entry_url(
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<String, String> {
    let token = {
        state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?
            .token
            .clone()
    };
    fetch_control_plane_entry_url(&token).await
}

async fn fetch_control_plane_entry_url(token: &str) -> Result<String, String> {
    let response = http::http_post_json_with_timeout(
        "127.0.0.1",
        8766,
        "/control/browser-session/leases",
        Some(token),
        &json!({}),
        http::DEFAULT_HTTP_TIMEOUT,
    )
    .await?;
    let payload: Value = serde_json::from_str(&response.body)
        .map_err(|err| format!("invalid Control Plane browser-session lease: {err}"))?;
    let claim_url = payload
        .get("claim_url")
        .and_then(Value::as_str)
        .ok_or_else(|| "Control Plane browser-session lease missing claim_url".to_string())?;
    if !claim_url.starts_with("/control/browser-session/claim?") || claim_url.contains("://") {
        return Err("Control Plane browser-session lease returned unsafe claim URL".to_string());
    }
    Ok(format!("http://127.0.0.1:8766{claim_url}"))
}

/// Shut Marvex down cleanly: stop the locally-supervised backend (no-op in
/// thin-client mode, which must not kill the shared service), close all windows,
/// and exit the process.
#[tauri::command]
fn marvex_shutdown(app: AppHandle, state: tauri::State<Mutex<ShellState>>) -> Result<(), String> {
    SHUTTING_DOWN.store(true, Ordering::SeqCst);
    if let Ok(state) = state.lock() {
        state.supervisor.shutdown();
    }
    for (_label, window) in app.webview_windows() {
        let _ = window.close();
    }
    app.exit(0);
    Ok(())
}

/// Restart the Marvex shell process.
#[tauri::command]
fn marvex_restart(app: AppHandle, state: tauri::State<Mutex<ShellState>>) -> Result<(), String> {
    SHUTTING_DOWN.store(true, Ordering::SeqCst);
    if let Ok(state) = state.lock() {
        state.supervisor.shutdown();
    }
    app.restart();
}

#[tauri::command]
fn set_overlay_click_through(app: AppHandle, ignore: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("overlay") {
        window
            .set_ignore_cursor_events(ignore)
            .map_err(|err| err.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn set_overlay_size(app: AppHandle, width: f64, height: f64) -> Result<(), String> {
    if !width.is_finite() || !height.is_finite() {
        return Err("overlay size must be finite".to_string());
    }
    if let Some(window) = app.get_webview_window("overlay") {
        let scale = window.scale_factor().unwrap_or(1.0);
        let requested_width = ((width.max(1.0)) * scale).round() as u32;
        let requested_height = ((height.max(1.0)) * scale).round() as u32;
        let (width, height, x, y) = if let Ok(Some(monitor)) = window.current_monitor() {
            let monitor_size = monitor.size();
            let monitor_position = monitor.position();
            let margin = 16_i32;
            let width = requested_width
                .min(monitor_size.width.saturating_sub((margin * 2) as u32))
                .max(1);
            let height = requested_height
                .min(monitor_size.height.saturating_sub((margin * 2) as u32))
                .max(1);
            let x = monitor_position.x + (monitor_size.width as i32) - (width as i32) - margin;
            let y = monitor_position.y + margin;
            (width, height, x.max(monitor_position.x), y)
        } else {
            (requested_width, requested_height, 0, 16)
        };
        window
            .set_size(tauri::Size::Physical(tauri::PhysicalSize::new(
                width, height,
            )))
            .map_err(|err| err.to_string())?;
        apply_overlay_window_region(&window, width, height);
        let _ = window.set_position(tauri::PhysicalPosition::new(x, y));
    }
    Ok(())
}

#[tauri::command]
async fn resume_approval_turn(
    text: String,
    trace_id: String,
    turn_id: String,
    approval_id: String,
    decision: String,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<Value, String> {
    let decision = decision.trim().to_ascii_lowercase();
    if !matches!(decision.as_str(), "approve" | "deny" | "cancel") {
        return Err("approval decision must be approve, deny, or cancel".to_string());
    }
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("approval resume text must be non-empty".to_string());
    }
    let approval_id = approval_id.trim().to_string();
    let trace_id = trace_id.trim().to_string();
    let turn_id = turn_id.trim().to_string();
    if approval_id.is_empty() || trace_id.is_empty() || turn_id.is_empty() {
        return Err("approval resume ids must be non-empty".to_string());
    }
    let token = {
        let guard = state
            .lock()
            .map_err(|_| "shell state unavailable".to_string())?;
        guard.token.clone()
    };
    let body = json!({
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_lmstudio_responses",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": format!("{turn_id}:approval-resume-input"),
            "session_ref": {"ref_type": "session", "ref_id": "shell-session"},
            "identity_ref": null,
            "user_visible_input": text,
            "assistant_mode": "default",
            "policy_context": {"requested_capabilities": [], "sensitivity": "normal"},
            "metadata": {"source": "marvex_shell", "approval_resume": true}
        },
        "model": default_chat_model(),
        "instructions": null,
        "previous_response_id": null,
        "resume_approval_id": approval_id,
        "approval_decision": decision,
        "provider_options": {}
    });
    let response = http::http_post_json_with_timeout(
        "127.0.0.1",
        8765,
        "/v1/turns",
        Some(&token),
        &body,
        http::TURN_HTTP_TIMEOUT,
    )
    .await?;
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Core response: {err}"))
}

#[cfg(windows)]
fn apply_overlay_window_region(window: &tauri::WebviewWindow, width: u32, height: u32) {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::Graphics::Gdi::{CreateRoundRectRgn, SetWindowRgn};

    let Ok(hwnd) = window.hwnd() else {
        return;
    };
    let hwnd = HWND(hwnd.0);
    let diameter = width.min(height).max(1) as i32;
    let region = unsafe {
        CreateRoundRectRgn(
            0,
            0,
            width.saturating_add(1) as i32,
            height.saturating_add(1) as i32,
            diameter,
            diameter,
        )
    };
    if region.is_invalid() {
        return;
    }
    // On success Windows owns the region handle after SetWindowRgn.
    let _ = unsafe { SetWindowRgn(hwnd, Some(region), true) };
}

#[cfg(not(windows))]
fn apply_overlay_window_region(_window: &tauri::WebviewWindow, _width: u32, _height: u32) {}

#[tauri::command]
fn show_chat(app: AppHandle) -> Result<(), String> {
    apply_ui_mode(&app, UiMode::Chat)?;
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window unavailable".to_string())?;
    window.set_focus().map_err(|err| err.to_string())
}

/// Enter the overlay/presence mode: hide the chat window and show the dynamic
/// island.
#[tauri::command]
fn show_overlay(app: AppHandle) -> Result<(), String> {
    apply_ui_mode(&app, UiMode::Overlay)
}

/// Open (or focus) the full original Control Plane in its own window.
#[tauri::command]
async fn open_control_plane(
    app: AppHandle,
    state: tauri::State<'_, Mutex<ShellState>>,
) -> Result<(), String> {
    let token = state
        .lock()
        .map_err(|_| "shell state unavailable".to_string())?
        .token
        .clone();
    if let Some(window) = app.get_webview_window("control") {
        window.show().map_err(|err| err.to_string())?;
        return window.set_focus().map_err(|err| err.to_string());
    }
    let entry_url = fetch_control_plane_entry_url(&token).await?;
    tauri::WebviewWindowBuilder::new(
        &app,
        "control",
        tauri::WebviewUrl::External(
            entry_url
                .parse()
                .map_err(|err| format!("invalid Control Plane entry URL: {err}"))?,
        ),
    )
    .title("Marvex Control Plane")
    .inner_size(1280.0, 860.0)
    .build()
    .map_err(|err| err.to_string())?;
    Ok(())
}

#[derive(Copy, Clone)]
enum UiMode {
    Chat,
    Overlay,
}

/// Apply one of the two top-level modes. Chat shows the main window and hides
/// the island; Overlay shows the island (presence) and hides the chat window.
fn apply_ui_mode(app: &AppHandle, mode: UiMode) -> Result<(), String> {
    let main = app.get_webview_window("main");
    let overlay = app.get_webview_window("overlay");

    match mode {
        UiMode::Chat => {
            if let Some(window) = overlay {
                window.hide().map_err(|err| err.to_string())?;
            }
            if let Some(window) = main {
                window.show().map_err(|err| err.to_string())?;
            }
        }
        UiMode::Overlay => {
            if let Some(window) = main {
                window.hide().map_err(|err| err.to_string())?;
            }
            if let Some(window) = overlay {
                window.show().map_err(|err| err.to_string())?;
            }
        }
    }

    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_positioner::init())
        .invoke_handler(tauri::generate_handler![
            shell_runtime_config,
            supervisor_status,
            get_setup_status,
            start_setup,
            start_backend,
            backend_health,
            gui_health,
            submit_chat_turn,
            submit_chat_turn_stream,
            resume_approval_turn,
            create_chat_session,
            list_chat_sessions,
            control_request,
            control_plane_entry_url,
            set_overlay_click_through,
            set_overlay_size,
            show_chat,
            show_overlay,
            open_control_plane,
            marvex_shutdown,
            marvex_restart
        ])
        .setup(|app| {
            let data_dir = app
                .path()
                .app_local_data_dir()
                .unwrap_or_else(|_| PathBuf::from("data"));
            let log_dir = data_dir.join("logs");
            let resource_dir = app.path().resource_dir().ok();
            // Thin-client mode: if the always-on backend Windows service has
            // published its token, attach to the running service instead of
            // spawning our own backend. Otherwise (dev / no service) supervise
            // the backend locally as before.
            let (token, supervisor) =
                match token_handoff::request_token_lease(std::time::Duration::from_secs(2)) {
                    Some(lease) => (
                        lease.token.clone(),
                        Supervisor::attach(lease.token, data_dir.clone()),
                    ),
                    None => {
                        let token =
                            token::generate_local_bearer_token().map_err(std::io::Error::other)?;
                        let supervisor =
                            Supervisor::start(token.clone(), log_dir, data_dir, resource_dir)
                                .map_err(std::io::Error::other)?;
                        (token, supervisor)
                    }
                };
            state_stream::start_state_stream(
                app.handle().clone(),
                token.clone(),
                supervisor.shutdown_flag(),
            );
            app.manage(Mutex::new(ShellState { token, supervisor }));
            build_tray(app.handle())?;
            #[cfg(target_os = "windows")]
            {
                // Ensure installed app is registered for login startup.
                let autostart = app.autolaunch();
                if let Ok(false) = autostart.is_enabled() {
                    let _ = autostart.enable();
                }
            }
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
                window.on_window_event(|event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        // Closing the chat window hides to tray — unless an
                        // explicit shutdown is underway, in which case let it close.
                        if !SHUTTING_DOWN.load(Ordering::SeqCst) {
                            api.prevent_close();
                        }
                    }
                });
            }
            if let Some(window) = app.get_webview_window("overlay") {
                if let (Ok(Some(monitor)), Ok(size)) =
                    (window.current_monitor(), window.outer_size())
                {
                    let m = monitor.size();
                    let x = (m.width as i32) - (size.width as i32) - 16;
                    let _ = window.set_position(tauri::PhysicalPosition::new(x.max(0), 16));
                }
                // The island window stays interactive (small, top-right) so the
                // webview receives hover/click events. Ignoring cursor events
                // would silently swallow hover and the click-to-open-chat.
            }
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open_chat" => {
                let _ = show_chat(app.clone());
            }
            "pause_voice" => {
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = control_request(
                        "/voice/worker/pause".into(),
                        "POST".into(),
                        Some(json!({})),
                        app.state::<Mutex<ShellState>>(),
                    )
                    .await;
                });
            }
            "resume_voice" => {
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = control_request(
                        "/voice/worker/resume".into(),
                        "POST".into(),
                        Some(json!({})),
                        app.state::<Mutex<ShellState>>(),
                    )
                    .await;
                });
            }
            "restart" => {
                let _ = marvex_restart(app.clone(), app.state::<Mutex<ShellState>>());
            }
            "shutdown" => {
                let _ = marvex_shutdown(app.clone(), app.state::<Mutex<ShellState>>());
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running Marvex Shell");
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let menu = MenuBuilder::new(app)
        .text("open_chat", "Open Marvex")
        .separator()
        .text("pause_voice", "Pause voice")
        .text("resume_voice", "Resume voice")
        .separator()
        .text("restart", "Restart Marvex")
        .text("shutdown", "Shutdown Marvex")
        .build()?;
    let mut builder = TrayIconBuilder::with_id("marvex-shell")
        .tooltip("Marvex")
        .menu(&menu)
        .show_menu_on_left_click(true);
    let icon = if let Some(icon) = app.default_window_icon().cloned() {
        icon
    } else {
        Image::from_bytes(TRAY_ICON_BYTES)?
    };
    builder = builder.icon(icon);
    builder.build(app)?;
    Ok(())
}

fn monotonic_id() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    #[test]
    fn default_capability_allows_control_window_commands() {
        let capability: serde_json::Value =
            serde_json::from_str(include_str!("../capabilities/default.json")).unwrap();
        let windows = capability
            .get("windows")
            .and_then(|value| value.as_array())
            .unwrap();

        assert!(windows.iter().any(|value| value.as_str() == Some("main")));
        assert!(windows
            .iter()
            .any(|value| value.as_str() == Some("overlay")));
        assert!(windows
            .iter()
            .any(|value| value.as_str() == Some("control")));
    }

    #[test]
    fn control_plane_window_does_not_inject_bearer_token_into_browser_storage() {
        let source = include_str!("lib.rs");
        let storage_call = concat!("window.", "sessionStorage", ".setItem");
        let storage_key = concat!("marvex_control", "_plane_token");

        assert!(!source.contains(storage_call));
        assert!(!source.contains(storage_key));
        assert!(source.contains("control_plane_entry_url"));
    }
}
