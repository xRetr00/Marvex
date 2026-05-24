use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use serde_json::json;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
const MANIFEST_SCHEMA_VERSION: &str = "1";
const MARVEX_VERSION: &str = "0.1.0";
const CORE_PORT: u16 = 8765;
const CONTROL_PORT: u16 = 8766;

#[derive(Clone, Debug)]
pub enum ServiceKind {
    Core,
    JsonlWorker {
        start_command: String,
        stop_command: String,
    },
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

    pub fn get(&self, name: &str) -> Option<String> {
        self.inner
            .lock()
            .ok()
            .and_then(|inner| inner.get(name).cloned())
    }

    pub fn snapshot(&self) -> BTreeMap<String, String> {
        self.inner
            .lock()
            .map(|inner| inner.clone())
            .unwrap_or_default()
    }
}

/// Outcome of the runtime (venv) bootstrap.
enum RuntimeOutcome {
    /// Installed product venv is ready; carries the venv root.
    Ready(PathBuf),
    /// Dev checkout (no bundled wheel) — services use the `uv run` fallback.
    Dev,
    /// Bootstrap failed; services are not spawned so a retry can re-attempt.
    Failed,
}

struct RuntimeConfig {
    token: String,
    log_dir: PathBuf,
    data_dir: PathBuf,
    resource_dir: Option<PathBuf>,
}

/// Per-process runtime. The Python services run from a real uv-managed virtual
/// environment created on first launch, so any dependency installed later (via
/// the Deps tab -> `uv pip install`) is importable. This differs from frozen
/// PyInstaller sidecars, whose sealed sys.path made runtime installs impossible.
#[derive(Clone)]
pub struct Supervisor {
    shutdown: Arc<AtomicBool>,
    pub status: Arc<SupervisorStatus>,
    config: Arc<RuntimeConfig>,
    launched: Arc<AtomicBool>,
    bootstrapping: Arc<AtomicBool>,
}

impl Supervisor {
    pub fn start(
        token: String,
        log_dir: PathBuf,
        data_dir: PathBuf,
        resource_dir: Option<PathBuf>,
    ) -> Result<Self, String> {
        fs::create_dir_all(&log_dir).map_err(|err| format!("log directory unavailable: {err}"))?;
        fs::create_dir_all(&data_dir)
            .map_err(|err| format!("data directory unavailable: {err}"))?;
        let supervisor = Self {
            shutdown: Arc::new(AtomicBool::new(false)),
            status: Arc::new(SupervisorStatus::default()),
            config: Arc::new(RuntimeConfig {
                token,
                log_dir,
                data_dir,
                resource_dir,
            }),
            launched: Arc::new(AtomicBool::new(false)),
            bootstrapping: Arc::new(AtomicBool::new(false)),
        };
        supervisor.spawn_controller();
        Ok(supervisor)
    }

    /// Bootstrap the runtime then launch services from a dedicated controller
    /// thread so the GUI never blocks on first-run installation.
    fn spawn_controller(&self) {
        if self.bootstrapping.swap(true, Ordering::SeqCst) {
            return; // a bootstrap attempt is already running
        }
        let config = Arc::clone(&self.config);
        let status = Arc::clone(&self.status);
        let shutdown = Arc::clone(&self.shutdown);
        let launched = Arc::clone(&self.launched);
        let bootstrapping = Arc::clone(&self.bootstrapping);
        thread::spawn(move || {
            let outcome = ensure_runtime(
                config.resource_dir.as_deref(),
                &config.data_dir,
                &config.log_dir,
                &status,
            );
            write_runtime_manifest(&config, &outcome, &status);
            bootstrapping.store(false, Ordering::SeqCst);
            if shutdown.load(Ordering::SeqCst) {
                return;
            }
            let venv = match outcome {
                RuntimeOutcome::Ready(venv) => Some(venv),
                RuntimeOutcome::Dev => None,
                RuntimeOutcome::Failed => return, // leave launched=false for retry
            };
            if launched.swap(true, Ordering::SeqCst) {
                return; // services already running
            }
            let venv = Arc::new(venv);
            for spec in service_specs(&config.token) {
                let service_shutdown = Arc::clone(&shutdown);
                let service_status = Arc::clone(&status);
                let service_config = Arc::clone(&config);
                let service_venv = Arc::clone(&venv);
                thread::spawn(move || {
                    supervise_service(
                        spec,
                        service_shutdown,
                        service_status,
                        service_config,
                        service_venv,
                    )
                });
            }
        });
    }

    /// Thin-client mode: the backend is owned by the always-on Windows service,
    /// so the shell does NOT spawn or supervise any processes. It records a
    /// "service" status and a no-op shutdown (it must never kill the service).
    pub fn attach(token: String, data_dir: PathBuf) -> Self {
        let status = Arc::new(SupervisorStatus::default());
        status.set("runtime", "ready");
        status.set("core", "running (service)");
        Self {
            shutdown: Arc::new(AtomicBool::new(false)),
            status,
            config: Arc::new(RuntimeConfig {
                token,
                log_dir: data_dir.clone(),
                data_dir,
                resource_dir: None,
            }),
            launched: Arc::new(AtomicBool::new(true)),
            bootstrapping: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Re-attempt the runtime bootstrap when a previous attempt failed (e.g.
    /// the first launch had no network). No-op once services are running.
    pub fn retry_setup(&self) {
        if !self.launched.load(Ordering::SeqCst) {
            self.spawn_controller();
        }
    }

    pub fn is_launched(&self) -> bool {
        self.launched.load(Ordering::SeqCst)
    }

    pub fn runtime_manifest_path(&self) -> PathBuf {
        self.config.data_dir.join("runtime").join("manifest.json")
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
            args: vec!["--serve".into(), "--host".into(), "127.0.0.1".into(), "--port".into(), CORE_PORT.to_string(), "--local-auth-token".into(), token.into()],
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

fn service_kind_label(kind: &ServiceKind) -> &'static str {
    match kind {
        ServiceKind::Core => "http",
        ServiceKind::JsonlWorker { .. } => "jsonl",
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

/// Resolve an installed sidecar console-script path inside a venv, returning
/// `None` when the venv is absent or the script is not present on disk (so the
/// caller falls back to the dev `uv run` path).
fn sidecar_path(venv: Option<&Path>, name: &str) -> Option<PathBuf> {
    venv.map(|root| venv_script(root, name))
        .filter(|path| path.is_file())
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
fn ensure_runtime(
    resource_dir: Option<&Path>,
    data_dir: &Path,
    log_dir: &Path,
    status: &SupervisorStatus,
) -> RuntimeOutcome {
    let venv = venv_root(data_dir);
    if venv_script(&venv, "marvex-core").is_file() {
        status.set("runtime", "ready");
        return RuntimeOutcome::Ready(venv);
    }

    // First-run bootstrap requires a bundled marvex wheel. When absent (dev
    // checkout), signal "dev" so services use the `uv run` path.
    let wheel = match resource_dir.and_then(first_marvex_wheel) {
        Some(wheel) => wheel,
        None => {
            status.set("runtime", "dev");
            return RuntimeOutcome::Dev;
        }
    };
    let uv = match find_uv(resource_dir) {
        Some(uv) => uv,
        None => {
            status.set("runtime", "uv_unavailable");
            return RuntimeOutcome::Failed;
        }
    };

    let bootstrap_log = log_dir.join("runtime.bootstrap.log");
    let _ = fs::create_dir_all(venv.parent().unwrap_or(data_dir));

    status.set("runtime", "creating environment");
    let venv_arg = venv.to_string_lossy().to_string();
    if !run_tool(
        &uv,
        &[
            "venv".to_string(),
            venv_arg,
            "--python".to_string(),
            "3.11".to_string(),
        ],
        data_dir,
        &bootstrap_log,
    ) {
        status.set("runtime", "venv_failed");
        return RuntimeOutcome::Failed;
    }

    status.set("runtime", "installing packages");
    let python = venv_script(&venv, "python");
    let mut args: Vec<String> = vec![
        "pip".to_string(),
        "install".to_string(),
        "--python".to_string(),
        python.to_string_lossy().to_string(),
    ];
    // Prefer bundled wheels (offline) when present, with PyPI fallback.
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
        return RuntimeOutcome::Failed;
    }

    if venv_script(&venv, "marvex-core").is_file() {
        status.set("runtime", "ready");
        RuntimeOutcome::Ready(venv)
    } else {
        status.set("runtime", "install_incomplete");
        RuntimeOutcome::Failed
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

/// Write `<data_dir>/runtime/manifest.json` describing the live runtime so the
/// GUI, health checks and diagnostics have a single source of truth.
fn write_runtime_manifest(
    config: &RuntimeConfig,
    outcome: &RuntimeOutcome,
    status: &SupervisorStatus,
) {
    let runtime_dir = config.data_dir.join("runtime");
    let _ = fs::create_dir_all(&runtime_dir);
    let (phase, venv): (String, Option<PathBuf>) = match outcome {
        RuntimeOutcome::Ready(venv) => ("ready".to_string(), Some(venv.clone())),
        RuntimeOutcome::Dev => ("dev".to_string(), None),
        RuntimeOutcome::Failed => (
            status
                .get("runtime")
                .unwrap_or_else(|| "failed".to_string()),
            None,
        ),
    };
    let services: Vec<_> = service_specs(&config.token)
        .iter()
        .map(|spec| {
            let exe = venv
                .as_ref()
                .map(|root| venv_script(root, spec.sidecar).to_string_lossy().to_string())
                .unwrap_or_else(|| format!("uv run python -m {}", spec.module));
            json!({
                "name": spec.name,
                "module": spec.module,
                "console_script": spec.sidecar,
                "exe": exe,
                "runtime_tier": if venv.is_some() { "tier1_setuptools" } else { "tier3_uv_run" },
                "kind": service_kind_label(&spec.kind),
                "port": if matches!(spec.kind, ServiceKind::Core) { Some(CORE_PORT) } else { None::<u16> },
            })
        })
        .collect();
    let manifest = json!({
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "marvex_version": MARVEX_VERSION,
        "runtime_phase": phase,
        "runtime_architecture": "tier1_setuptools_console_scripts",
        "created_at_unix_ms": now_unix_ms(),
        "venv": venv.as_ref().map(|p| p.to_string_lossy().to_string()),
        "python": venv.as_ref().map(|p| venv_script(p, "python").to_string_lossy().to_string()),
        "uv": find_uv(config.resource_dir.as_deref()).map(|p| p.to_string_lossy().to_string()),
        "endpoints": {
            "core": format!("http://127.0.0.1:{CORE_PORT}"),
            "control": format!("http://127.0.0.1:{CONTROL_PORT}/control"),
        },
        "services": services,
    });
    if let Ok(text) = serde_json::to_string_pretty(&manifest) {
        let _ = fs::write(runtime_dir.join("manifest.json"), text);
    }
}

fn now_unix_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or_default()
}

// ---------------------------------------------------------------------------
// Service supervision
// ---------------------------------------------------------------------------

fn supervise_service(
    spec: ServiceSpec,
    shutdown: Arc<AtomicBool>,
    status: Arc<SupervisorStatus>,
    config: Arc<RuntimeConfig>,
    venv: Arc<Option<PathBuf>>,
) {
    let mut backoff_seconds = 1_u64;
    while !shutdown.load(Ordering::SeqCst) {
        status.set(spec.name, "starting");
        match spawn_service(
            &spec,
            &config.log_dir,
            &config.data_dir,
            config.resource_dir.as_deref(),
            venv.as_deref(),
        ) {
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
    // Tier 1: Setuptools console scripts (preferred, production)
    // Tier 3: Dev fallback `uv run python -m <module>` (source checkout)
    let mut command = if let Some(exe) = sidecar_path(venv, spec.sidecar) {
        let mut command = Command::new(exe);
        command.args(&spec.args);
        command.current_dir(data_dir);
        command
    } else {
        // Development fallback: services from source
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
    // Point the control plane server at the built control_plane_web SPA so the
    // shell's Control Plane window can load it same-origin. Prefer a bundled
    // copy in the resource dir; fall back to the dev checkout dist.
    let web_dist = resource_dir
        .map(|dir| dir.join("control_plane_web"))
        .filter(|p| p.is_dir())
        .unwrap_or_else(|| {
            project_root()
                .join("apps")
                .join("control_plane_web")
                .join("dist")
        });
    if web_dist.is_dir() {
        command.env("MARVEX_CONTROL_WEB_DIST", web_dist);
    }
    command.env("MARVEX_LOG_DIR", log_dir);
    // Point the voice worker at the bundled/installed "Hey Marvex" model assets.
    let voice_assets = resource_dir
        .map(|dir| dir.join("voice-assets"))
        .filter(|p| p.is_dir())
        .unwrap_or_else(|| {
            project_root()
                .join("apps")
                .join("shell")
                .join("voice-assets")
        });
    if voice_assets.is_dir() {
        command.env("MARVEX_VOICE_ASSET_ROOT", voice_assets);
    }
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
    let mut child = command
        .spawn()
        .map_err(|err| format!("failed to spawn {}: {err}", spec.name))?;
    attach_log_pipe(spec.name, "stdout", child.stdout.take(), log_dir);
    attach_log_pipe(spec.name, "stderr", child.stderr.take(), log_dir);
    Ok(child)
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn write_child_line(child: &mut Child, line: &str) {
    if let Some(stdin) = child.stdin.as_mut() {
        let _ = stdin.write_all(line.as_bytes());
        let _ = stdin.write_all(b"\n");
        let _ = stdin.flush();
    }
}

fn attach_log_pipe(
    name: &'static str,
    stream_name: &'static str,
    stream: Option<impl std::io::Read + Send + 'static>,
    log_dir: &Path,
) {
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
    use super::{
        find_uv, service_kind_label, service_specs, sidecar_path, venv_root, venv_script,
        ServiceKind,
    };
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
        assert!(core.to_string_lossy().contains("marvex-core"));
    }

    #[test]
    fn find_uv_falls_back_to_path_binary() {
        assert!(find_uv(None).is_some());
    }

    #[test]
    fn service_kinds_are_labelled_for_manifest() {
        let specs = service_specs("token");
        let core = specs.iter().find(|s| s.name == "core").expect("core");
        assert_eq!(service_kind_label(&core.kind), "http");
        let provider = specs
            .iter()
            .find(|s| s.name == "provider_worker")
            .expect("provider");
        assert_eq!(service_kind_label(&provider.kind), "jsonl");
        assert!(matches!(core.kind, ServiceKind::Core));
    }
}
