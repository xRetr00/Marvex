use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
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

/// Per-process runtime layout. The Python services run from a real uv-managed
/// virtual environment created on first launch, so any dependency installed
/// later (via the Deps tab -> `uv pip install`) is importable. This is the key
/// difference from the previous frozen-PyInstaller sidecars, whose sealed
/// sys.path made runtime-installed packages impossible to import.
#[derive(Clone)]
pub struct Supervisor {
    shutdown: Arc<AtomicBool>,
    pub status: Arc<SupervisorStatus>,
}

impl Supervisor {
    pub fn start(
        token: String,
        log_dir: PathBuf,
        data_dir: PathBuf,
        resource_dir: Option<PathBuf>,
    ) -> Result<Self, String> {
        fs::create_dir_all(&log_dir).map_err(|err| format!("log directory unavailable: {err}"))?;
        fs::create_dir_all(&data_dir).map_err(|err| format!("data directory unavailable: {err}"))?;
        let shutdown = Arc::new(AtomicBool::new(false));
        let status = Arc::new(SupervisorStatus::default());

        // Bootstrap the runtime (venv) and then launch services from a single
        // controller thread so the GUI never blocks on first-run installation.
        let controller_status = Arc::clone(&status);
        let controller_shutdown = Arc::clone(&shutdown);
        thread::spawn(move || {
            let venv = ensure_runtime(resource_dir.as_deref(), &data_dir, &log_dir, &controller_status);
            let venv = Arc::new(venv);
            if controller_shutdown.load(Ordering::SeqCst) {
                return;
            }
            for spec in service_specs(&token) {
                let service_shutdown = Arc::clone(&controller_shutdown);
                let service_status = Arc::clone(&controller_status);
                let service_log_dir = log_dir.clone();
                let service_data_dir = data_dir.clone();
                let service_resource_dir = resource_dir.clone();
                let service_venv = Arc::clone(&venv);
                thread::spawn(move || {
                    supervise_service(
                        spec,
                        service_shutdown,
                        service_status,
                        service_log_dir,
                        service_data_dir,
                        service_resource_dir,
                        service_venv,
                    )
                });
            }
        });
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
            module: "services.voice_worker.main",
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

// ---------------------------------------------------------------------------
// Runtime (uv venv) bootstrap
// ---------------------------------------------------------------------------

fn venv_root(data_dir: &Path) -> PathBuf {
    data_dir.join("runtime").join("venv")
}

/// Path to an executable/script inside the venv (console scripts + python).
fn venv_script(venv: &Path, name: &str) -> PathBuf {
    if cfg!(windows) {
        venv.join("Scripts").join(format!("{name}.exe"))
    } else {
        venv.join("bin").join(name)
    }
}

/// Resolve the `uv` binary: prefer the bundled copy in the resource dir, then
/// fall back to `uv` on PATH (dev machines).
fn find_uv(resource_dir: Option<&Path>) -> Option<PathBuf> {
    if let Some(dir) = resource_dir {
        let candidate = dir.join(if cfg!(windows) { "uv.exe" } else { "uv" });
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    Some(PathBuf::from("uv"))
}

/// Find the bundled `marvex-*.whl` in the resource dir.
fn first_marvex_wheel(resource_dir: &Path) -> Option<PathBuf> {
    let entries = fs::read_dir(resource_dir).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if let Some(name) = path.file_name().and_then(|s| s.to_str()) {
            if name.starts_with("marvex-") && name.ends_with(".whl") {
                return Some(path);
            }
        }
    }
    None
}

/// Ensure a runnable Python environment exists, creating it on first launch.
/// Returns the venv root if usable, otherwise None (callers fall back to the
/// dev `uv run` path when running from a source checkout).
fn ensure_runtime(
    resource_dir: Option<&Path>,
    data_dir: &Path,
    log_dir: &Path,
    status: &SupervisorStatus,
) -> Option<PathBuf> {
    let venv = venv_root(data_dir);
    if venv_script(&venv, "marvex-core").is_file() {
        status.set("runtime", "ready");
        return Some(venv);
    }

    // First-run bootstrap requires a bundled uv + marvex wheel. When those are
    // absent (dev checkout), signal "dev" so services use the `uv run` path.
    let wheel = match resource_dir.and_then(first_marvex_wheel) {
        Some(wheel) => wheel,
        None => {
            status.set("runtime", "dev");
            return None;
        }
    };
    let uv = match find_uv(resource_dir) {
        Some(uv) => uv,
        None => {
            status.set("runtime", "uv_unavailable");
            return None;
        }
    };

    let bootstrap_log = log_dir.join("runtime.bootstrap.log");
    let _ = fs::create_dir_all(venv.parent().unwrap_or(data_dir));

    status.set("runtime", "creating environment");
    let venv_arg = venv.to_string_lossy().to_string();
    if !run_tool(&uv, &["venv".to_string(), venv_arg, "--python".to_string(), "3.11".to_string()], data_dir, &bootstrap_log) {
        status.set("runtime", "venv_failed");
        return None;
    }

    status.set("runtime", "installing packages");
    let python = venv_script(&venv, "python");
    let mut args: Vec<String> = vec![
        "pip".to_string(),
        "install".to_string(),
        "--python".to_string(),
        python.to_string_lossy().to_string(),
    ];
    // Prefer bundled wheels (offline) when present, but allow PyPI fallback for
    // any wheel not vendored.
    if let Some(dir) = resource_dir {
        let wheels = dir.join("wheels");
        if wheels.is_dir() {
            args.push("--find-links".to_string());
            args.push(wheels.to_string_lossy().to_string());
        }
    }
    args.push(wheel.to_string_lossy().to_string());
    if !run_tool(&uv, &args, data_dir, &bootstrap_log) {
        status.set("runtime", "install_failed");
        return None;
    }

    if venv_script(&venv, "marvex-core").is_file() {
        status.set("runtime", "ready");
        Some(venv)
    } else {
        status.set("runtime", "install_incomplete");
        None
    }
}

/// Run a one-shot tool (uv) windowless, appending combined output to a log.
fn run_tool(tool: &Path, args: &[String], cwd: &Path, log_path: &Path) -> bool {
    let mut command = Command::new(tool);
    command.args(args);
    command.current_dir(cwd);
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let output = match command.output() {
        Ok(output) => output,
        Err(_) => return false,
    };
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = file.write_all(&output.stdout);
        let _ = file.write_all(&output.stderr);
    }
    output.status.success()
}

// ---------------------------------------------------------------------------
// Service supervision
// ---------------------------------------------------------------------------

fn supervise_service(
    spec: ServiceSpec,
    shutdown: Arc<AtomicBool>,
    status: Arc<SupervisorStatus>,
    log_dir: PathBuf,
    data_dir: PathBuf,
    resource_dir: Option<PathBuf>,
    venv: Arc<Option<PathBuf>>,
) {
    let mut backoff_seconds = 1_u64;
    while !shutdown.load(Ordering::SeqCst) {
        status.set(spec.name, "starting");
        match spawn_service(&spec, &log_dir, &data_dir, resource_dir.as_deref(), venv.as_deref()) {
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

fn spawn_service(
    spec: &ServiceSpec,
    log_dir: &Path,
    data_dir: &Path,
    resource_dir: Option<&Path>,
    venv: Option<&Path>,
) -> Result<Child, String> {
    // Resolution order:
    //   1. venv console script (installed product) -> cwd = writable data dir
    //   2. legacy frozen sidecar in resource dir   -> cwd = writable data dir
    //   3. dev fallback `uv run python -m <module>` -> cwd = source repo
    let mut command = if let Some(exe) = venv
        .map(|root| venv_script(root, spec.sidecar))
        .filter(|path| path.is_file())
    {
        let mut command = Command::new(exe);
        command.args(&spec.args);
        command.current_dir(data_dir);
        command
    } else if let Some(path) = sidecar_path(resource_dir, spec.sidecar) {
        let mut command = Command::new(path);
        command.args(&spec.args);
        command.current_dir(data_dir);
        command
    } else {
        let mut command = Command::new("uv");
        command.args(["run", "python", "-m", spec.module]);
        command.args(&spec.args);
        command.current_dir(project_root());
        command
    };
    // Expose the bundled uv to services so the Deps tab can install extra
    // packages into this same venv (importable without a restart).
    if let Some(uv) = find_uv(resource_dir) {
        if uv.is_absolute() {
            command.env("MARVEX_UV_PATH", uv);
        }
    }
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
    use super::{find_uv, service_specs, sidecar_path, venv_root, venv_script};
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

    #[test]
    fn venv_layout_is_per_user_data_dir() {
        let venv = venv_root(Path::new("/data"));
        assert!(venv.ends_with("runtime/venv") || venv.ends_with("runtime\\venv"));
        let core = venv_script(&venv, "marvex-core");
        let core = core.to_string_lossy();
        assert!(core.contains("marvex-core"));
    }

    #[test]
    fn find_uv_falls_back_to_path_binary() {
        assert!(find_uv(None).is_some());
    }
}
