//! Marvex backend Windows service.
//!
//! Runs the shell-supervised backend boundary (Core + voice worker) 24/7 via
//! the existing [`crate::supervisor::Supervisor`]. Core owns provider, intent,
//! and tool worker IPC internally through persistent JSONL clients. The per-user
//! shell attaches to this service as a thin client using the local token handoff
//! named pipe.
//!
//! Usage:
//!   marvex-service --install     register + start the service (run elevated)
//!   marvex-service --uninstall   stop + remove the service (run elevated)
//!   marvex-service --console     run the backend in the foreground (debugging)
//!   marvex-service               (no args) entry point invoked by the SCM

use std::{
    ffi::OsString,
    fs::{self, OpenOptions},
    io::Write,
    path::PathBuf,
    sync::mpsc,
    time::Duration,
};

use windows_service::{
    define_windows_service,
    service::{
        ServiceAccess, ServiceControl, ServiceControlAccept, ServiceErrorControl, ServiceExitCode,
        ServiceInfo, ServiceStartType, ServiceState, ServiceStatus, ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
    service_dispatcher,
    service_manager::{ServiceManager, ServiceManagerAccess},
};

const SERVICE_NAME: &str = "MarvexBackend";
const SERVICE_DISPLAY_NAME: &str = "Marvex Backend";
const SERVICE_TYPE: ServiceType = ServiceType::OWN_PROCESS;

pub fn main() {
    let args: Vec<OsString> = std::env::args_os().collect();
    match args.get(1).and_then(|arg| arg.to_str()) {
        Some("--install") => {
            if let Err(err) = install(parse_service_options(&args[2..])) {
                eprintln!("marvex-service install failed: {err}");
                std::process::exit(1);
            }
            println!("Marvex backend service installed and started.");
        }
        Some("--uninstall") => {
            if let Err(err) = uninstall() {
                eprintln!("marvex-service uninstall failed: {err}");
                std::process::exit(1);
            }
            println!("Marvex backend service removed.");
        }
        Some("--console") => run_console(parse_service_options(&args[2..])),
        _ => {
            if let Err(err) = service_dispatcher::start(SERVICE_NAME, ffi_service_main) {
                eprintln!("marvex-service dispatcher failed: {err}");
                std::process::exit(1);
            }
        }
    }
}

define_windows_service!(ffi_service_main, service_main);

#[derive(Clone, Debug, Default, PartialEq, Eq)]
struct ServiceOptions {
    app_data_dir: Option<PathBuf>,
}

fn service_main(arguments: Vec<OsString>) {
    let _ = run_service(parse_service_options(&arguments));
}

fn run_service(options: ServiceOptions) -> windows_service::Result<()> {
    let (shutdown_tx, shutdown_rx) = mpsc::channel::<()>();
    let event_handler = move |control| -> ServiceControlHandlerResult {
        match control {
            ServiceControl::Stop | ServiceControl::Shutdown => {
                let _ = shutdown_tx.send(());
                ServiceControlHandlerResult::NoError
            }
            ServiceControl::Interrogate => ServiceControlHandlerResult::NoError,
            _ => ServiceControlHandlerResult::NotImplemented,
        }
    };

    let status_handle = service_control_handler::register(SERVICE_NAME, event_handler)?;
    let status = |state: ServiceState, accept: ServiceControlAccept| ServiceStatus {
        service_type: SERVICE_TYPE,
        current_state: state,
        controls_accepted: accept,
        exit_code: ServiceExitCode::Win32(0),
        checkpoint: 0,
        wait_hint: Duration::default(),
        process_id: None,
    };

    status_handle.set_service_status(status(
        ServiceState::Running,
        ServiceControlAccept::STOP | ServiceControlAccept::SHUTDOWN,
    ))?;

    let supervisor = start_backend(&options);

    loop {
        match shutdown_rx.recv_timeout(Duration::from_secs(1)) {
            Ok(()) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
            Err(mpsc::RecvTimeoutError::Timeout) => {}
        }
    }

    if let Some(supervisor) = supervisor {
        supervisor.shutdown();
        let _ = supervisor.wait_for_services_stopped(Duration::from_secs(20));
    }
    status_handle
        .set_service_status(status(ServiceState::Stopped, ServiceControlAccept::empty()))?;
    Ok(())
}

fn run_console(options: ServiceOptions) {
    let supervisor = start_backend(&options);
    let stop_file = console_stop_file_path();
    println!("Marvex backend running in console mode. Press Ctrl+C to stop.");
    loop {
        if console_stop_requested(stop_file.as_ref()) {
            break;
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    if let Some(supervisor) = supervisor {
        supervisor.shutdown();
        let _ = supervisor.wait_for_services_stopped(Duration::from_secs(20));
    }
}

fn console_stop_file_path() -> Option<PathBuf> {
    std::env::var_os("MARVEX_SERVICE_CONSOLE_STOP_FILE").map(PathBuf::from)
}

fn console_stop_requested(stop_file: Option<&PathBuf>) -> bool {
    stop_file.is_some_and(|path| path.is_file())
}

fn parse_service_options(args: &[OsString]) -> ServiceOptions {
    let mut options = ServiceOptions::default();
    let mut index = 0;
    while index < args.len() {
        if args[index].to_str() == Some("--app-data-dir") {
            if let Some(value) = args.get(index + 1).filter(|value| !value.is_empty()) {
                options.app_data_dir = Some(PathBuf::from(value));
                index += 2;
                continue;
            }
        }
        index += 1;
    }
    options
}

fn service_launch_arguments(options: &ServiceOptions) -> Vec<OsString> {
    let mut arguments = Vec::new();
    if let Some(root) = &options.app_data_dir {
        arguments.push(OsString::from("--app-data-dir"));
        arguments.push(root.as_os_str().to_os_string());
    }
    arguments
}

fn installed_service_options(options: ServiceOptions) -> ServiceOptions {
    if options.app_data_dir.is_some() {
        return options;
    }
    ServiceOptions {
        app_data_dir: std::env::var_os("LOCALAPPDATA")
            .filter(|value| !value.is_empty())
            .map(PathBuf::from)
            .map(|root| root.join("com.marvex.shell")),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        app_data_root_from_env, console_stop_requested, installed_service_options,
        parse_service_options, service_launch_arguments, ServiceOptions,
    };
    use std::ffi::OsString;
    use std::path::PathBuf;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    #[test]
    fn console_stop_requested_uses_explicit_stop_file_only() {
        let path = std::env::temp_dir().join(format!(
            "marvex-console-stop-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("time")
                .as_nanos()
        ));

        assert!(!console_stop_requested(None));
        assert!(!console_stop_requested(Some(&path)));
        fs::write(&path, b"stop").expect("stop file");
        assert!(console_stop_requested(Some(&path)));
        let _ = fs::remove_file(path);
    }

    #[test]
    fn service_app_data_root_prefers_explicit_override() {
        let explicit_root = PathBuf::from("explicit-marvex-data-root");
        let root = app_data_root_from_env(
            Some(explicit_root.clone()),
            Some(PathBuf::from("local-app-data-root")),
            Some(PathBuf::from("program-data-root")),
        );

        assert_eq!(root, explicit_root);
    }

    #[test]
    fn service_app_data_root_matches_tauri_local_app_data_identifier() {
        let local_app_data = PathBuf::from("local-app-data-root");
        let root = app_data_root_from_env(
            None,
            Some(local_app_data.clone()),
            Some(PathBuf::from("program-data-root")),
        );

        assert_eq!(root, local_app_data.join("com.marvex.shell"));
        assert!(!root.to_string_lossy().contains("ProgramData"));
    }

    #[test]
    fn service_options_parse_and_round_trip_app_data_dir() {
        let root = PathBuf::from(r"C:\Users\MarvexUser\AppData\Local\com.marvex.shell");
        let options = parse_service_options(&[
            OsString::from("--app-data-dir"),
            root.as_os_str().to_os_string(),
        ]);

        assert_eq!(
            options,
            ServiceOptions {
                app_data_dir: Some(root.clone())
            }
        );
        assert_eq!(
            service_launch_arguments(&options),
            vec![
                OsString::from("--app-data-dir"),
                root.as_os_str().to_os_string()
            ]
        );
    }

    #[test]
    fn installed_service_options_preserves_explicit_user_data_root() {
        let root = PathBuf::from("explicit-user-data-root");
        let options = installed_service_options(ServiceOptions {
            app_data_dir: Some(root.clone()),
        });

        assert_eq!(options.app_data_dir, Some(root));
    }
}

fn app_data_root(explicit_root: Option<PathBuf>) -> PathBuf {
    app_data_root_from_env(
        explicit_root.or_else(|| std::env::var_os("MARVEX_APP_DATA_DIR").map(PathBuf::from)),
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from),
        std::env::var_os("ProgramData").map(PathBuf::from),
    )
}

fn app_data_root_from_env(
    explicit_root: Option<PathBuf>,
    local_app_data: Option<PathBuf>,
    program_data: Option<PathBuf>,
) -> PathBuf {
    if let Some(root) = explicit_root.filter(|path| !path.as_os_str().is_empty()) {
        return root;
    }
    if let Some(root) = local_app_data.filter(|path| !path.as_os_str().is_empty()) {
        return root.join("com.marvex.shell");
    }
    program_data
        .unwrap_or_else(|| PathBuf::from("data"))
        .join("com.marvex.shell")
}

fn exe_dir() -> Option<PathBuf> {
    std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(PathBuf::from))
}

/// Mint a fresh loopback token, publish an in-memory lease broker so the shell
/// can attach, and launch the supervised backend stack.
fn start_backend(options: &ServiceOptions) -> Option<crate::supervisor::Supervisor> {
    let root = app_data_root(options.app_data_dir.clone());
    append_service_log(&root, "starting Marvex backend service");
    let token = match crate::token::generate_local_bearer_token() {
        Ok(token) => token,
        Err(err) => {
            append_service_log(&root, &format!("token generation failed: {err}"));
            return None;
        }
    };
    crate::token_handoff::delete_legacy_shared_token();
    let log_dir = root.join("logs");
    let data_dir = root;
    let supervisor = match crate::supervisor::Supervisor::start(
        token.clone(),
        log_dir,
        data_dir.clone(),
        exe_dir(),
    ) {
        Ok(supervisor) => supervisor,
        Err(err) => {
            append_service_log(&data_dir, &format!("supervisor start failed: {err}"));
            return None;
        }
    };
    let _broker = crate::token_handoff::start_token_broker(token, supervisor.shutdown_flag());
    append_service_log(&data_dir, "backend supervisor started");
    Some(supervisor)
}

fn append_service_log(root: &PathBuf, message: &str) {
    let log_dir = root.join("logs");
    if fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("service.log"))
    else {
        return;
    };
    let _ = writeln!(file, "{message}");
}

fn install(options: ServiceOptions) -> windows_service::Result<()> {
    let manager =
        ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CREATE_SERVICE)?;
    let executable_path = std::env::current_exe().map_err(windows_service::Error::Winapi)?;
    let options = installed_service_options(options);
    let info = ServiceInfo {
        name: OsString::from(SERVICE_NAME),
        display_name: OsString::from(SERVICE_DISPLAY_NAME),
        service_type: SERVICE_TYPE,
        start_type: ServiceStartType::AutoStart,
        error_control: ServiceErrorControl::Normal,
        executable_path,
        launch_arguments: service_launch_arguments(&options),
        dependencies: vec![],
        account_name: None,
        account_password: None,
    };
    let service =
        manager.create_service(&info, ServiceAccess::CHANGE_CONFIG | ServiceAccess::START)?;
    let _ = service.set_description(
        "Marvex always-on assistant backend (Core, workers, Hey Marvex wake word).",
    );
    service.start::<OsString>(&[])?;
    Ok(())
}

fn uninstall() -> windows_service::Result<()> {
    let manager = ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CONNECT)?;
    let service =
        manager.open_service(SERVICE_NAME, ServiceAccess::STOP | ServiceAccess::DELETE)?;
    let _ = service.stop();
    service.delete()?;
    crate::token_handoff::delete_legacy_shared_token();
    Ok(())
}
