mod http;
mod service_token;
mod state_stream;
mod supervisor;
mod token;

#[cfg(windows)]
pub mod service;

use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    time::{SystemTime, UNIX_EPOCH},
};

/// Set while an explicit Marvex shutdown is in progress so the main window's
/// CloseRequested handler stops swallowing the close (otherwise quit hangs and
/// the process must be killed from Task Manager).
static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);

use serde::Serialize;
use serde_json::{json, Value};
use supervisor::Supervisor;
use tauri::{
    image::Image, menu::MenuBuilder, tray::TrayIconBuilder, AppHandle, Manager, WindowEvent,
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
        .unwrap_or(false);
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
    let body = json!({
        "schema_version": "0.1.1-draft",
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
        "model": null,
        "instructions": null,
        "previous_response_id": null,
        "provider_options": {}
    });
    let response =
        http::http_post_json("127.0.0.1", 8765, "/v1/turns", Some(&token), &body).await?;
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Core response: {err}"))
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
        http::http_post_json(
            "127.0.0.1",
            8766,
            &full_path,
            Some(&token),
            &body.unwrap_or_else(|| json!({})),
        )
        .await?
    } else {
        http::http_get("127.0.0.1", 8766, &full_path, Some(&token)).await?
    };
    serde_json::from_str(&response.body)
        .map_err(|err| format!("invalid Control Plane response: {err}"))
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
        let _ = window.set_position(tauri::PhysicalPosition::new(x, y));
    }
    Ok(())
}

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

/// Open (or focus) the full original Control Plane in its own window. The window
/// loads the Control Plane server same-origin (so the SPA's relative `/control`
/// calls work) and an init script injects the local bearer token into
/// sessionStorage, matching the Control Plane web app's auth expectation.
#[tauri::command]
fn open_control_plane(
    app: AppHandle,
    state: tauri::State<Mutex<ShellState>>,
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
    // Load a shell-owned loader page that shows backend bring-up/errors and then
    // navigates to the control plane server when it is ready. The init script
    // injects the bearer token on whatever origin loads (including 127.0.0.1:8766
    // after navigation), so the SPA authenticates without a blank/race window.
    let escaped = token.replace('\\', "\\\\").replace('\'', "\\'");
    let init = format!("window.sessionStorage.setItem('marvex_control_plane_token', '{escaped}');");
    tauri::WebviewWindowBuilder::new(
        &app,
        "control",
        tauri::WebviewUrl::App("control-loader".into()),
    )
    .title("Marvex Control Plane")
    .inner_size(1280.0, 860.0)
    .initialization_script(&init)
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
            control_request,
            set_overlay_click_through,
            set_overlay_size,
            show_chat,
            show_overlay,
            open_control_plane,
            marvex_shutdown,
            marvex_restart
        ])
        .setup(|app| {
            let log_dir = app
                .path()
                .app_log_dir()
                .unwrap_or_else(|_| PathBuf::from("logs"));
            let data_dir = app
                .path()
                .app_local_data_dir()
                .unwrap_or_else(|_| PathBuf::from("data"));
            let resource_dir = app.path().resource_dir().ok();
            // Thin-client mode: if the always-on backend Windows service has
            // published its token, attach to the running service instead of
            // spawning our own backend. Otherwise (dev / no service) supervise
            // the backend locally as before.
            let (token, supervisor) = match service_token::read_shared_token() {
                Some(shared) => (shared.clone(), Supervisor::attach(shared, data_dir.clone())),
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
