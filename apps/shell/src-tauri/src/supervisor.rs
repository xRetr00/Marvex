use std::{
    collections::BTreeMap,
    fs::{self, File},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{atomic::{AtomicBool, Ordering}, Arc, Mutex},
    thread,
    time::Duration,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;

#[derive(Clone, Debug)]
pub enum ServiceKind {
    Core,
    JsonlWorker { start_command: String, stop_command: String },
}

#[derive(Clone, Debug)]
pub struct ServiceSpec {
    pub name: &'static str,
    pub module: &'static str,
    pub sidecar: &'static str,
    pub args: Vec<String>,
    pub kind: ServiceKind,
}

#[derive(Default)]
pub struct SupervisorStatus {
    inner: Mutex<BTreeMap<String, String>>,
}

impl SupervisorStatus {
    pub fn set(&self, name: &str, status: impl Into<String>) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.insert(name.to_string(), status.into());
        }
    }

    pub fn snapshot(&self) -> BTreeMap<String, String> {
        self.inner.lock().map(|inner| inner.clone()).unwrap_or_default()
    }
}

#[derive(Clone)]
pub struct Supervisor {
    shutdown: Arc<AtomicBool>,
    pub status: Arc<SupervisorStatus>,
}

impl Supervisor {
    pub fn start(token: String, log_dir: PathBuf, resource_dir: Option<PathBuf>) -> Result<Self, String> {
        fs::create_dir_all(&log_dir).map_err(|err| format!("log directory unavailable: {err}"))?;
        let shutdown = Arc::new(AtomicBool::new(false));
        let status = Arc::new(SupervisorStatus::default());
        for spec in service_specs(&token) {
            let service_shutdown = Arc::clone(&shutdown);
            let service_status = Arc::clone(&status);
            let service_log_dir = log_dir.clone();
            let service_resource_dir = resource_dir.clone();
            thread::spawn(move || supervise_service(spec, service_shutdown, service_status, service_log_dir, service_resource_dir));
        }
        Ok(Self { shutdown, status })
    }

    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::SeqCst);
    }

    pub fn shutdown_flag(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.shutdown)
    }
}

fn service_specs(token: &str) -> Vec<ServiceSpec> {
    vec![
        ServiceSpec {
            name: "core",
            module: "services.core.main",
            sidecar: "marvex-core",
            args: vec!["--serve".into(), "--host".into(), "127.0.0.1".into(), "--port".into(), "8765".into(), "--local-auth-token".into(), token.into()],
            kind: ServiceKind::Core,
        },
        jsonl("provider_worker", "services.provider_worker.main", "marvex-provider-worker"),
        jsonl("intent_worker", "services.intent_worker.main", "marvex-intent-worker"),
        jsonl("tool_worker", "services.tool_worker.main", "marvex-tool-worker"),
        ServiceSpec {
            name: "voice_worker",
            module: "packages.voice_worker_runtime.worker_main",
            sidecar: "marvex-voice-worker",
            args: vec!["--jsonl".into()],
            kind: ServiceKind::JsonlWorker {
                start_command: r#"{"command":"start","command_id":"shell-voice-start","trace_id":"trace-shell-voice-worker"}"#.to_string(),
                stop_command: r#"{"command":"stop","command_id":"shell-voice-stop","trace_id":"trace-shell-voice-worker"}"#.to_string(),
            },
        },
    ]
}

fn jsonl(name: &'static str, module: &'static str, sidecar: &'static str) -> ServiceSpec {
    ServiceSpec {
        name,
        module,
        sidecar,
        args: vec!["--jsonl".into()],
        kind: ServiceKind::JsonlWorker {
            start_command: format!(r#"{{"command":"start","trace_id":"trace-shell-{name}"}}"#),
            stop_command: format!(r#"{{"command":"stop","trace_id":"trace-shell-{name}"}}"#),
        },
    }
}

fn supervise_service(spec: ServiceSpec, shutdown: Arc<AtomicBool>, status: Arc<SupervisorStatus>, log_dir: PathBuf, resource_dir: Option<PathBuf>) {
    let mut backoff_seconds = 1_u64;
    while !shutdown.load(Ordering::SeqCst) {
        status.set(spec.name, "starting");
        match spawn_service(&spec, &log_dir, resource_dir.as_deref()) {
            Ok(mut child) => {
                status.set(spec.name, format!("running pid {}", child.id()));
                if let ServiceKind::JsonlWorker { start_command, .. } = &spec.kind {
                    write_child_line(&mut child, start_command);
                }
                loop {
                    if shutdown.load(Ordering::SeqCst) {
                        if let ServiceKind::JsonlWorker { stop_command, .. } = &spec.kind {
                            write_child_line(&mut child, stop_command);
                        }
                        thread::sleep(Duration::from_millis(300));
                        let _ = child.kill();
                        let _ = child.wait();
                        status.set(spec.name, "stopped");
                        return;
                    }
                    match child.try_wait() {
                        Ok(Some(exit)) => {
                            status.set(spec.name, format!("exited {exit}"));
                            break;
                        }
                        Ok(None) => thread::sleep(Duration::from_millis(500)),
                        Err(err) => {
                            status.set(spec.name, format!("monitor_error {err}"));
                            break;
                        }
                    }
                }
            }
            Err(err) => status.set(spec.name, format!("spawn_error {err}")),
        }
        thread::sleep(Duration::from_secs(backoff_seconds));
        backoff_seconds = (backoff_seconds * 2).min(30);
    }
}

fn spawn_service(spec: &ServiceSpec, log_dir: &Path, resource_dir: Option<&Path>) -> Result<Child, String> {
    let mut command = if let Some(path) = sidecar_path(resource_dir, spec.sidecar) {
        let mut command = Command::new(path);
        command.args(&spec.args);
        command
    } else {
        let mut command = Command::new("uv");
        command.args(["run", "python", "-m", spec.module]);
        command.args(&spec.args);
        command
    };
    command.current_dir(project_root());
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
    let mut child = command.spawn().map_err(|err| format!("failed to spawn {}: {err}", spec.name))?;
    attach_log_pipe(spec.name, "stdout", child.stdout.take(), log_dir);
    attach_log_pipe(spec.name, "stderr", child.stderr.take(), log_dir);
    Ok(child)
}

fn sidecar_path(resource_dir: Option<&Path>, sidecar: &str) -> Option<PathBuf> {
    let dir = resource_dir?;
    let exe = if cfg!(windows) { format!("{sidecar}.exe") } else { sidecar.to_string() };
    let candidate = dir.join(exe);
    candidate.is_file().then_some(candidate)
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..").canonicalize().unwrap_or_else(|_| PathBuf::from("."))
}

fn write_child_line(child: &mut Child, line: &str) {
    if let Some(stdin) = child.stdin.as_mut() {
        let _ = stdin.write_all(line.as_bytes());
        let _ = stdin.write_all(b"\n");
        let _ = stdin.flush();
    }
}

fn attach_log_pipe(name: &'static str, stream_name: &'static str, stream: Option<impl std::io::Read + Send + 'static>, log_dir: &Path) {
    let Some(stream) = stream else { return };
    let path = log_dir.join(format!("{name}.{stream_name}.log"));
    thread::spawn(move || {
        let mut file = match File::create(path) {
            Ok(file) => file,
            Err(_) => return,
        };
        for line in BufReader::new(stream).lines().map_while(Result::ok) {
            if !line.to_ascii_lowercase().contains("bearer ") {
                let _ = writeln!(file, "{line}");
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::{service_specs, sidecar_path};
    use std::path::Path;

    #[test]
    fn core_command_receives_token_without_logging_it_in_status() {
        let specs = service_specs("secret-token");
        let core = specs.iter().find(|spec| spec.name == "core").expect("core");
        assert!(core.args.iter().any(|arg| arg == "secret-token"));
        assert_eq!(core.module, "services.core.main");
    }

    #[test]
    fn missing_sidecar_falls_back_to_dev_command() {
        assert!(sidecar_path(Some(Path::new("missing")), "marvex-core").is_none());
    }
}
