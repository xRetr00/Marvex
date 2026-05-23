//! Marvex backend Windows service.
//!
//! Runs the full backend stack (Core + control plane + intent/tool/provider/
//! voice workers) 24/7 via the existing [`crate::supervisor::Supervisor`], so the
//! always-on "Hey Marvex" wake word reaches a warm Core instantly. The per-user
//! shell attaches to this service as a thin client using the shared token file.
//!
//! Usage:
//!   marvex-service --install     register + start the service (run elevated)
//!   marvex-service --uninstall   stop + remove the service (run elevated)
//!   marvex-service --console     run the backend in the foreground (debugging)
//!   marvex-service               (no args) entry point invoked by the SCM

use std::{ffi::OsString, path::PathBuf, sync::mpsc, time::Duration};

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
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("--install") => {
            if let Err(err) = install() {
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
        Some("--console") => run_console(),
        _ => {
            if let Err(err) = service_dispatcher::start(SERVICE_NAME, ffi_service_main) {
                eprintln!("marvex-service dispatcher failed: {err}");
                std::process::exit(1);
            }
        }
    }
}

define_windows_service!(ffi_service_main, service_main);

fn service_main(_arguments: Vec<OsString>) {
    let _ = run_service();
}

fn run_service() -> windows_service::Result<()> {
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

    let supervisor = start_backend();

    loop {
        match shutdown_rx.recv_timeout(Duration::from_secs(1)) {
            Ok(()) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
            Err(mpsc::RecvTimeoutError::Timeout) => {}
        }
    }

    if let Some(supervisor) = supervisor {
        supervisor.shutdown();
    }
    status_handle.set_service_status(status(ServiceState::Stopped, ServiceControlAccept::empty()))?;
    Ok(())
}

fn run_console() {
    let _supervisor = start_backend();
    println!("Marvex backend running in console mode. Press Ctrl+C to stop.");
    loop {
        std::thread::sleep(Duration::from_secs(3600));
    }
}

fn program_data_root() -> PathBuf {
    let base = std::env::var("ProgramData").unwrap_or_else(|_| "C:\\ProgramData".to_string());
    PathBuf::from(base).join("Marvex")
}

fn exe_dir() -> Option<PathBuf> {
    std::env::current_exe().ok().and_then(|path| path.parent().map(PathBuf::from))
}

/// Mint a fresh loopback token, publish it to the shared file (so the shell can
/// attach), and launch the supervised backend stack.
fn start_backend() -> Option<crate::supervisor::Supervisor> {
    let token = crate::token::generate_local_bearer_token().ok()?;
    let _ = crate::service_token::write_shared_token(&token);
    let root = program_data_root();
    let log_dir = root.join("logs");
    let data_dir = root.join("data");
    crate::supervisor::Supervisor::start(token, log_dir, data_dir, exe_dir()).ok()
}

fn install() -> windows_service::Result<()> {
    let manager = ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CREATE_SERVICE)?;
    let executable_path = std::env::current_exe().map_err(windows_service::Error::Winapi)?;
    let info = ServiceInfo {
        name: OsString::from(SERVICE_NAME),
        display_name: OsString::from(SERVICE_DISPLAY_NAME),
        service_type: SERVICE_TYPE,
        start_type: ServiceStartType::AutoStart,
        error_control: ServiceErrorControl::Normal,
        executable_path,
        launch_arguments: vec![],
        dependencies: vec![],
        account_name: None,
        account_password: None,
    };
    let service = manager.create_service(&info, ServiceAccess::CHANGE_CONFIG | ServiceAccess::START)?;
    let _ = service.set_description("Marvex always-on assistant backend (Core, workers, Hey Marvex wake word).");
    service.start::<OsString>(&[])?;
    Ok(())
}

fn uninstall() -> windows_service::Result<()> {
    let manager = ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CONNECT)?;
    let service = manager.open_service(SERVICE_NAME, ServiceAccess::STOP | ServiceAccess::DELETE)?;
    let _ = service.stop();
    service.delete()?;
    Ok(())
}
