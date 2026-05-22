mod http;
mod state_stream;
mod supervisor;
mod token;

use std::{path::PathBuf, sync::Mutex, time::{SystemTime, UNIX_EPOCH}};

use serde::Serialize;
use serde_json::{json, Value};
use supervisor::Supervisor;
use tauri::{menu::MenuBuilder, tray::TrayIconBuilder, AppHandle, Manager, WindowEvent};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

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
    let state = state.lock().map_err(|_| "shell state unavailable".to_string())?;
    Ok(json!(state.supervisor.status.snapshot()))
}

#[tauri::command]
fn submit_chat_turn(text: String, state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("chat text must be non-empty".to_string());
    }
    let token = state.lock().map_err(|_| "shell state unavailable".to_string())?.token.clone();
    let now = monotonic_id();
    let trace_id = format!("trace-shell-chat-{now}");
    let turn_id = format!("turn-shell-chat-{now}");
    let body = json!({
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": format!("event-shell-chat-{now}"),
            "session_ref": {"ref_type": "session", "ref_id": "shell-session"},
            "identity_ref": null,
            "user_visible_input": text,
            "assistant_mode": "default",
            "policy_context": {"requested_capabilities": [], "sensitivity": "normal"},
            "metadata": {"source": "marvex_shell"}
        },
        "model": "fake-model",
        "instructions": null,
        "previous_response_id": null,
        "provider_options": {}
    });
    let response = http::http_post_json("127.0.0.1", 8765, "/v1/turns", Some(&token), &body)?;
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Core response: {err}"))
}

#[tauri::command]
fn control_request(path: String, method: String, body: Option<Value>, state: tauri::State<Mutex<ShellState>>) -> Result<Value, String> {
    if !path.starts_with('/') || path.contains("://") {
        return Err("control path must be local".to_string());
    }
    let token = state.lock().map_err(|_| "shell state unavailable".to_string())?.token.clone();
    let full_path = format!("/control{path}");
    let response = if method.eq_ignore_ascii_case("POST") {
        http::http_post_json("127.0.0.1", 8766, &full_path, Some(&token), &body.unwrap_or_else(|| json!({})))?
    } else {
        http::http_get("127.0.0.1", 8766, &full_path, Some(&token))?
    };
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Control Plane response: {err}"))
}

#[tauri::command]
fn set_overlay_click_through(app: AppHandle, ignore: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("overlay") {
        window.set_ignore_cursor_events(ignore).map_err(|err| err.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn show_chat(app: AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("main").ok_or_else(|| "main window unavailable".to_string())?;
    window.show().map_err(|err| err.to_string())?;
    window.set_focus().map_err(|err| err.to_string())
}

#[tauri::command]
fn show_spotlight(app: AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("spotlight").ok_or_else(|| "spotlight window unavailable".to_string())?;
    window.show().map_err(|err| err.to_string())?;
    window.set_focus().map_err(|err| err.to_string())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .plugin(tauri_plugin_positioner::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().with_handler(|app, shortcut, event| {
            let spotlight = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);
            if shortcut == &spotlight && event.state() == ShortcutState::Pressed {
                let _ = show_spotlight(app.clone());
            }
        }).build())
        .invoke_handler(tauri::generate_handler![
            shell_runtime_config,
            supervisor_status,
            submit_chat_turn,
            control_request,
            set_overlay_click_through,
            show_chat,
            show_spotlight
        ])
        .setup(|app| {
            let token = token::generate_local_bearer_token().map_err(std::io::Error::other)?;
            let log_dir = app.path().app_log_dir().unwrap_or_else(|_| PathBuf::from("logs"));
            let resource_dir = app.path().resource_dir().ok();
            let supervisor = Supervisor::start(token.clone(), log_dir, resource_dir).map_err(std::io::Error::other)?;
            state_stream::start_state_stream(app.handle().clone(), token.clone(), supervisor.shutdown_flag());
            app.manage(Mutex::new(ShellState { token, supervisor }));
            build_tray(app.handle())?;
            app.global_shortcut().register(Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space))?;
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
                window.on_window_event(|event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                    }
                });
            }
            if let Some(window) = app.get_webview_window("overlay") {
                let _ = window.set_ignore_cursor_events(true);
            }
            Ok(())
        })
        .on_menu_event(|app, event| {
            match event.id().as_ref() {
                "open_chat" => { let _ = show_chat(app.clone()); }
                "open_spotlight" => { let _ = show_spotlight(app.clone()); }
                "pause_voice" => { let _ = control_request("/voice/worker/pause".into(), "POST".into(), Some(json!({})), app.state::<Mutex<ShellState>>()); }
                "resume_voice" => { let _ = control_request("/voice/worker/resume".into(), "POST".into(), Some(json!({})), app.state::<Mutex<ShellState>>()); }
                "quit" => {
                    if let Some(state) = app.try_state::<Mutex<ShellState>>() {
                        if let Ok(state) = state.lock() {
                            state.supervisor.shutdown();
                        }
                    }
                    app.exit(0);
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Marvex Shell");
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let menu = MenuBuilder::new(app)
        .text("open_chat", "Open chat")
        .text("open_spotlight", "Settings / Control Plane")
        .separator()
        .text("pause_voice", "Pause voice")
        .text("resume_voice", "Resume voice")
        .separator()
        .text("quit", "Quit")
        .build()?;
    TrayIconBuilder::with_id("marvex-shell")
        .tooltip("Marvex")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .build(app)?;
    Ok(())
}

fn monotonic_id() -> u128 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|duration| duration.as_millis()).unwrap_or_default()
}
