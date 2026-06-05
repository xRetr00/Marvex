use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use process_wrap::std::{ChildWrapper, CommandWrap};
use serde_json::json;

#[cfg(windows)]
use process_wrap::std::{CreationFlags, JobObject};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
#[cfg(windows)]
use windows::Win32::System::Threading::PROCESS_CREATION_FLAGS;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
const DETACHED_PROCESS: u32 = 0x0000_0008;
const MANIFEST_SCHEMA_VERSION: &str = "1";
const MARVEX_VERSION: &str = "0.2.1";
const CORE_PORT: u16 = 8765;
const CONTROL_PORT: u16 = 8766;
const RUNTIME_WHEEL_MARKER_FILE: &str = "wheel.marker";
const MARVEX_PACKAGE_NAME: &str = "marvex";
const PYTHON_RUNTIME_VERSION: &str = "3.12";
const DEFAULT_PRODUCT_PROVIDER: &str = "litellm";
// ``openrouter/auto`` is not a real chat-completions model id - it routes
// requests through OpenRouter's auto-selector which previously returned
// 404/PROVIDER_UNAVAILABLE from this adapter. Use a concrete OpenRouter
// slug as the safe out-of-the-box default; can be overridden by setting
// MARVEX_MODEL or MARVEX_DEFAULT_MODEL in the launcher environment.
const DEFAULT_PRODUCT_MODEL: &str = "openrouter/anthropic/claude-3.5-sonnet";

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
    pub env: Vec<(String, String)>,
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

    pub fn wait_for_services_stopped(&self, timeout: Duration) -> bool {
        if !self.launched.load(Ordering::SeqCst) {
            return true;
        }
        let deadline = Instant::now() + timeout;
        loop {
            let snapshot = self.status.snapshot();
            let all_stopped = service_specs(&self.config.token)
                .iter()
                .all(|spec| matches!(snapshot.get(spec.name).map(String::as_str), Some("stopped")));
            if all_stopped {
                return true;
            }
            if Instant::now() >= deadline {
                return false;
            }
            thread::sleep(Duration::from_millis(100));
        }
    }

    pub fn shutdown_flag(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.shutdown)
    }
}

fn service_specs(token: &str) -> Vec<ServiceSpec> {
    let provider = default_product_provider();
    let model = default_product_model();
    vec![
        ServiceSpec {
            name: "core",
            module: "services.core.main",
            sidecar: "marvex-core",
            args: vec![
                "--serve".into(),
                "--host".into(),
                "127.0.0.1".into(),
                "--port".into(),
                CORE_PORT.to_string(),
                "--provider".into(),
                "provider_worker".into(),
                "--worker-provider".into(),
                provider,
                "--model".into(),
                model,
                "--web-search".into(),
                "multi".into(),
            ],
            env: vec![("MARVEX_LOCAL_AUTH_TOKEN".into(), token.into())],
            kind: ServiceKind::Core,
        },
        ServiceSpec {
            name: "voice_worker",
            module: "services.voice_worker.main",
            sidecar: "marvex-voice-worker",
            args: vec!["--jsonl".into()],
            env: Vec::new(),
            kind: ServiceKind::JsonlWorker {
                start_command: r#"{"command":"start","command_id":"shell-voice-start","trace_id":"trace-shell-voice-worker"}"#.to_string(),
                stop_command: r#"{"command":"stop","command_id":"shell-voice-stop","trace_id":"trace-shell-voice-worker"}"#.to_string(),
            },
        },
    ]
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

fn runtime_uv_cache_dir(data_dir: &Path) -> PathBuf {
    data_dir.join("runtime").join("uv-cache")
}

/// Path to an executable/script inside the venv (console scripts + python).
fn venv_script(venv: &Path, name: &str) -> PathBuf {
    if cfg!(windows) {
        venv.join("Scripts").join(format!("{name}.exe"))
    } else {
        venv.join("bin").join(name)
    }
}

fn venv_create_args(venv: &Path, clear_existing: bool) -> Vec<String> {
    let mut args = vec![
        "venv".to_string(),
        venv.to_string_lossy().to_string(),
        "--python".to_string(),
        PYTHON_RUNTIME_VERSION.to_string(),
    ];
    if clear_existing {
        args.push("--clear".to_string());
    }
    args
}

/// Resolve an installed sidecar console-script path inside a venv.
#[cfg(test)]
fn sidecar_path(venv: Option<&Path>, name: &str) -> Option<PathBuf> {
    venv.map(|root| venv_script(root, name))
        .filter(|path| path.is_file())
}

fn venv_python_path(venv: Option<&Path>) -> Option<PathBuf> {
    venv.map(|root| venv_script(root, "python"))
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
    let mut wheels = entries
        .flatten()
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("marvex-") && name.ends_with(".whl"))
        })
        .collect::<Vec<_>>();
    wheels.sort();

    let version_prefix = format!("marvex-{}-", env!("CARGO_PKG_VERSION"));
    if let Some(current) = wheels.iter().find(|path| {
        path.file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.starts_with(&version_prefix))
    }) {
        return Some(current.clone());
    }

    (wheels.len() == 1).then(|| wheels.remove(0))
}

fn runtime_wheel_marker_path(data_dir: &Path) -> PathBuf {
    data_dir.join("runtime").join(RUNTIME_WHEEL_MARKER_FILE)
}

fn runtime_wheel_marker(wheel: &Path) -> Option<String> {
    let metadata = wheel.metadata().ok()?;
    let name = wheel.file_name()?.to_string_lossy();
    let mut file = File::open(wheel).ok()?;
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut buffer = [0_u8; 8192];
    loop {
        let read = file.read(&mut buffer).ok()?;
        if read == 0 {
            break;
        }
        for byte in &buffer[..read] {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    Some(format!("{name}:{}:{hash:016x}", metadata.len()))
}

fn record_installed_runtime_wheel(data_dir: &Path, wheel: &Path) -> Result<(), String> {
    let marker =
        runtime_wheel_marker(wheel).ok_or_else(|| "runtime wheel unavailable".to_string())?;
    let marker_path = runtime_wheel_marker_path(data_dir);
    fs::create_dir_all(marker_path.parent().unwrap_or(data_dir))
        .map_err(|err| format!("runtime marker directory unavailable: {err}"))?;
    fs::write(marker_path, marker).map_err(|err| format!("runtime marker write failed: {err}"))
}

fn runtime_venv_is_current(data_dir: &Path, venv: &Path, resource_dir: Option<&Path>) -> bool {
    if !venv_script(venv, "marvex-core").is_file() {
        return false;
    }
    let Some(wheel) = resource_dir.and_then(first_marvex_wheel) else {
        return true;
    };
    let Some(expected) = runtime_wheel_marker(&wheel) else {
        return false;
    };
    fs::read_to_string(runtime_wheel_marker_path(data_dir))
        .map(|installed| installed == expected)
        .unwrap_or(false)
}

fn console_script_can_be_updated(path: &Path) -> bool {
    if !path.is_file() {
        return true;
    }
    OpenOptions::new().append(true).open(path).is_ok()
}

fn resource_env_paths(
    resource_dir: Option<&Path>,
    repo_root: &Path,
    data_dir: &Path,
) -> Vec<(String, String)> {
    let mut env = Vec::new();
    if let Some(uv) = find_uv(resource_dir) {
        if uv.is_absolute() && uv.is_file() {
            env.push((
                "MARVEX_UV_PATH".to_string(),
                uv.to_string_lossy().to_string(),
            ));
        }
    }
    let node = resource_dir
        .map(|dir| dir.join(if cfg!(windows) { "node.exe" } else { "node" }))
        .filter(|path| path.is_file());
    let playwright_mcp_cli = resource_dir
        .map(|dir| {
            dir.join("playwright-mcp")
                .join("node_modules")
                .join("@playwright")
                .join("mcp")
                .join("cli.js")
        })
        .filter(|path| path.is_file());
    if let (Some(node), Some(cli)) = (node, playwright_mcp_cli) {
        env.push((
            "MARVEX_NODE_PATH".to_string(),
            node.to_string_lossy().to_string(),
        ));
        env.push((
            "MARVEX_PLAYWRIGHT_MCP_CLI".to_string(),
            cli.to_string_lossy().to_string(),
        ));
    }
    let web_dist = resource_dir
        .map(|dir| dir.join("control_plane_web"))
        .filter(|path| path.is_dir())
        .or_else(|| {
            let path = repo_root
                .join("apps")
                .join("control_plane_web")
                .join("dist");
            path.is_dir().then_some(path)
        });
    if let Some(path) = web_dist {
        env.push((
            "MARVEX_CONTROL_WEB_DIST".to_string(),
            path.to_string_lossy().to_string(),
        ));
    }
    // The voice asset root must be WRITABLE: the bundled STT + wakeword models
    // ship read-only in the resource dir and are seeded into this root, while the
    // remaining models (Kokoro TTS, etc.) are downloaded into it at runtime via
    // the manifest. So always resolve to a writable location, then seed the
    // bundled assets into it without clobbering anything already downloaded.
    let bundled_voice_assets = resource_dir
        .map(|dir| dir.join("voice-assets"))
        .filter(|path| path.is_dir());
    let voice_root = if resource_dir.is_some() {
        data_dir.join("voice-assets")
    } else {
        let repo_assets = repo_root.join("apps").join("shell").join("voice-assets");
        if repo_assets.is_dir() {
            repo_assets
        } else {
            data_dir.join("voice-assets")
        }
    };
    if let Err(err) = fs::create_dir_all(&voice_root) {
        eprintln!(
            "[marvex] failed to create voice asset root {voice_root:?}: {err}"
        );
    }
    if let Some(bundled) = bundled_voice_assets.as_ref() {
        if let Err(err) = seed_dir_missing(bundled, &voice_root) {
            eprintln!("[marvex] failed to seed bundled voice assets: {err}");
        }
    }
    env.push((
        "MARVEX_VOICE_ASSET_ROOT".to_string(),
        voice_root.to_string_lossy().to_string(),
    ));
    let voice_manifest = resource_dir
        .map(|dir| dir.join("voice_models.manifest.json"))
        .filter(|path| path.is_file())
        .or_else(|| {
            let path = repo_root.join("voice_models.manifest.json");
            path.is_file().then_some(path)
        });
    if let Some(path) = voice_manifest {
        env.push((
            "MARVEX_VOICE_MODEL_MANIFEST".to_string(),
            path.to_string_lossy().to_string(),
        ));
    }
    env
}

/// Recursively copy files from `src` into `dst`, creating directories as needed
/// and skipping any destination file that already exists. Used to seed the
/// bundled (read-only) voice assets into the writable asset root on startup
/// without clobbering models the user has already downloaded there.
fn seed_dir_missing(src: &Path, dst: &Path) -> std::io::Result<()> {
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if file_type.is_dir() {
            fs::create_dir_all(&to)?;
            seed_dir_missing(&from, &to)?;
        } else if file_type.is_file() {
            if to.exists() {
                continue;
            }
            if let Some(parent) = to.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(&from, &to)?;
        }
    }
    Ok(())
}

fn default_product_provider() -> String {
    std::env::var("MARVEX_WORKER_PROVIDER")
        .or_else(|_| std::env::var("MARVEX_PROVIDER"))
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| matches!(value.as_str(), "lmstudio_responses" | "litellm"))
        .unwrap_or_else(|| DEFAULT_PRODUCT_PROVIDER.to_string())
}

fn default_product_model() -> String {
    std::env::var("MARVEX_MODEL")
        .or_else(|_| std::env::var("MARVEX_DEFAULT_MODEL"))
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| DEFAULT_PRODUCT_MODEL.to_string())
}

/// Ensure a runnable Python environment exists, creating it on first launch.
fn ensure_runtime(
    resource_dir: Option<&Path>,
    data_dir: &Path,
    log_dir: &Path,
    status: &SupervisorStatus,
) -> RuntimeOutcome {
    let venv = venv_root(data_dir);
    if runtime_venv_is_current(data_dir, &venv, resource_dir) {
        status.set("runtime", "ready");
        return RuntimeOutcome::Ready(venv);
    }
    let existing_console_script = venv_script(&venv, "marvex-core").is_file();

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

    if !existing_console_script {
        status.set("runtime", "creating environment");
        let venv_args = venv_create_args(&venv, venv.exists());
        if !run_tool(&uv, &venv_args, data_dir, &bootstrap_log) {
            status.set("runtime", "venv_failed");
            return RuntimeOutcome::Failed;
        }
    }

    let core_script = venv_script(&venv, "marvex-core");
    if existing_console_script && !console_script_can_be_updated(&core_script) {
        status.set("runtime", "install_blocked_running_process");
        return RuntimeOutcome::Failed;
    }

    status.set(
        "runtime",
        if existing_console_script {
            "updating packages"
        } else {
            "installing packages"
        },
    );
    let python = venv_script(&venv, "python");
    let mut args: Vec<String> = vec![
        "pip".to_string(),
        "install".to_string(),
        "--no-build".to_string(),
        "--only-binary".to_string(),
        ":all:".to_string(),
    ];
    if existing_console_script {
        args.push("--reinstall-package".to_string());
        args.push(MARVEX_PACKAGE_NAME.to_string());
    }
    args.push("--python".to_string());
    args.push(python.to_string_lossy().to_string());
    // Packaged runtime must be fully offline and wheel-only. Falling back to
    // PyPI or building sdists on a customer machine leaks noisy build output
    // and can fail without a compiler/toolchain.
    if let Some(dir) = resource_dir {
        let wheels = dir.join("wheels");
        if !wheels.is_dir() {
            status.set("runtime", "wheelhouse_missing");
            write_bootstrap_status(
                &bootstrap_log,
                "runtime install failed: packaged wheelhouse is missing",
            );
            return RuntimeOutcome::Failed;
        }
        args.push("--no-index".to_string());
        args.push("--find-links".to_string());
        args.push(wheels.to_string_lossy().to_string());
    }
    args.push(wheel.to_string_lossy().to_string());
    if !run_tool(&uv, &args, data_dir, &bootstrap_log) {
        status.set("runtime", "install_failed");
        return RuntimeOutcome::Failed;
    }

    if core_script.is_file() {
        let _ = record_installed_runtime_wheel(data_dir, &wheel);
        status.set("runtime", "ready");
        RuntimeOutcome::Ready(venv)
    } else {
        status.set("runtime", "install_incomplete");
        RuntimeOutcome::Failed
    }
}

/// Run a one-shot tool (uv) windowless. Raw tool output is suppressed by
/// default because third-party package build logs include local user paths and
/// huge noisy traces. Set MARVEX_VERBOSE_BOOTSTRAP_LOG=1 for local debugging.
fn run_tool(tool: &Path, args: &[String], cwd: &Path, log_path: &Path) -> bool {
    let mut command = Command::new(tool);
    command.args(args);
    command.current_dir(cwd);
    command.env("UV_CACHE_DIR", runtime_uv_cache_dir(cwd));
    command.env("UV_NO_PROGRESS", "1");
    command.env("PIP_DISABLE_PIP_VERSION_CHECK", "1");
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let output = match command.output() {
        Ok(output) => output,
        Err(_) => return false,
    };
    let success = output.status.success();
    if verbose_bootstrap_log_enabled() {
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
            let _ = file.write_all(sanitize_bootstrap_bytes(&output.stdout).as_bytes());
            let _ = file.write_all(sanitize_bootstrap_bytes(&output.stderr).as_bytes());
        }
    } else if !success {
        write_bootstrap_status(
            log_path,
            &format!(
                "runtime bootstrap command failed: {} {} (exit={})",
                tool.file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or("tool"),
                sanitized_bootstrap_args(args),
                output
                    .status
                    .code()
                    .map(|code| code.to_string())
                    .unwrap_or_else(|| "terminated".to_string())
            ),
        );
    }
    success
}

fn verbose_bootstrap_log_enabled() -> bool {
    std::env::var("MARVEX_VERBOSE_BOOTSTRAP_LOG")
        .map(|value| matches!(value.trim(), "1" | "true" | "TRUE" | "yes" | "YES"))
        .unwrap_or(false)
}

fn write_bootstrap_status(log_path: &Path, message: &str) {
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(file, "{message}");
    }
}

fn sanitized_bootstrap_args(args: &[String]) -> String {
    args.iter()
        .map(|arg| {
            if arg.contains('\\') || arg.contains('/') {
                "<path>".to_string()
            } else {
                arg.clone()
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn sanitize_bootstrap_bytes(bytes: &[u8]) -> String {
    let text = String::from_utf8_lossy(bytes);
    let mut sanitized = text.to_string();
    for var in ["USERPROFILE", "LOCALAPPDATA", "APPDATA", "HOME"] {
        if let Some(value) = std::env::var_os(var).and_then(|value| {
            let text = value.to_string_lossy().to_string();
            (!text.is_empty()).then_some(text)
        }) {
            sanitized = sanitized.replace(&value, &format!("<{var}>"));
        }
    }
    sanitized
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
                .map(|root| {
                    format!(
                        "{} -m {}",
                        venv_script(root, "python").to_string_lossy(),
                        spec.module
                    )
                })
                .unwrap_or_else(|| format!("uv run python -m {}", spec.module));
            json!({
                "name": spec.name,
                "module": spec.module,
                "console_script": spec.sidecar,
                "exe": exe,
                "runtime_tier": if venv.is_some() { "tier1_venv_python_module" } else { "tier3_uv_run" },
                "kind": service_kind_label(&spec.kind),
                "port": if matches!(spec.kind, ServiceKind::Core) { Some(CORE_PORT) } else { None::<u16> },
            })
        })
        .collect();
    let manifest = json!({
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "marvex_version": MARVEX_VERSION,
        "runtime_phase": phase,
        "runtime_architecture": "tier1_setuptools_venv_python_modules",
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
) -> Result<Box<dyn ChildWrapper>, String> {
    // Tier 1: venv Python module execution (preferred, production). We keep
    // setuptools console scripts as install markers, but do not execute their
    // launcher EXEs because they are console-subsystem binaries on Windows.
    // Tier 3: Dev fallback `uv run python -m <module>` (source checkout)
    let mut command = if let Some(python) = venv_python_path(venv) {
        let mut command = Command::new(python);
        command.args(["-m", spec.module]);
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

    let repo_root = project_root();
    for (name, value) in resource_env_paths(resource_dir, &repo_root, data_dir) {
        command.env(name, value);
    }
    for (name, value) in &spec.env {
        command.env(name, value);
    }
    command.env("MARVEX_LOG_DIR", log_dir);
    if matches!(spec.kind, ServiceKind::Core) {
        command.env(
            "MARVEX_FILE_CAPABILITY_ROOT",
            default_file_capability_root(data_dir),
        );
    }
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = spawn_wrapped_child(command)
        .map_err(|err| format!("failed to spawn {}: {err}", spec.name))?;
    attach_log_pipe(spec.name, "stdout", child.stdout().take(), log_dir);
    attach_log_pipe(spec.name, "stderr", child.stderr().take(), log_dir);
    Ok(child)
}

fn default_file_capability_root(data_dir: &Path) -> PathBuf {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .filter(|path| !path.as_os_str().is_empty())
        .unwrap_or_else(|| data_dir.to_path_buf())
}

fn spawn_wrapped_child(mut command: Command) -> std::io::Result<Box<dyn ChildWrapper>> {
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP);
    let mut command = CommandWrap::from(command);
    #[cfg(windows)]
    {
        command.wrap(CreationFlags(PROCESS_CREATION_FLAGS(
            CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )));
        command.wrap(JobObject);
    }
    command.spawn()
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn write_child_line(child: &mut Box<dyn ChildWrapper>, line: &str) {
    if let Some(stdin) = child.stdin().as_mut() {
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
            let _ = writeln!(file, "{}", sanitize_log_line(&line));
        }
    });
}

fn sanitize_log_line(line: &str) -> String {
    let lowered = line.to_ascii_lowercase();
    if let Some(index) = lowered.find("bearer ") {
        let token_start = index + "bearer ".len();
        let token_end = line[token_start..]
            .find(|character: char| {
                character.is_whitespace() || character == ',' || character == ';'
            })
            .map(|offset| token_start + offset)
            .unwrap_or(line.len());
        let mut redacted = String::with_capacity(line.len());
        redacted.push_str(&line[..token_start]);
        redacted.push_str("[redacted]");
        redacted.push_str(&line[token_end..]);
        return redacted;
    }
    line.to_string()
}

#[cfg(test)]
mod tests {
    use super::{
        console_script_can_be_updated, default_file_capability_root, default_product_model,
        default_product_provider, find_uv, first_marvex_wheel, record_installed_runtime_wheel,
        resource_env_paths, runtime_uv_cache_dir, runtime_venv_is_current, sanitize_log_line,
        sanitize_bootstrap_bytes, sanitized_bootstrap_args, service_kind_label, service_specs,
        sidecar_path, venv_create_args, venv_root, venv_script, write_runtime_manifest,
        RuntimeConfig, RuntimeOutcome, ServiceKind, Supervisor, SupervisorStatus,
        PYTHON_RUNTIME_VERSION,
    };
    use serde_json::Value;
    use std::{
        fs,
        path::{Path, PathBuf},
        sync::{atomic::AtomicBool, Arc},
        time::{Duration, SystemTime, UNIX_EPOCH},
    };

    #[test]
    fn core_command_receives_token_without_logging_it_in_status() {
        let specs = service_specs("secret-token");
        let core = specs.iter().find(|spec| spec.name == "core").expect("core");
        assert!(!core.args.iter().any(|arg| arg == "secret-token"));
        assert!(core
            .env
            .iter()
            .any(|(name, value)| name == "MARVEX_LOCAL_AUTH_TOKEN" && value == "secret-token"));
        assert_eq!(core.module, "services.core.main");
    }

    #[test]
    fn core_service_uses_worker_backed_real_provider_path() {
        let specs = service_specs("secret-token");
        let core = specs.iter().find(|spec| spec.name == "core").expect("core");

        assert!(core
            .args
            .windows(2)
            .any(|pair| pair == ["--provider", "provider_worker"]));
        assert!(core
            .args
            .windows(2)
            .any(|pair| pair[0] == "--worker-provider" && pair[1] == default_product_provider()));
        assert!(core
            .args
            .windows(2)
            .any(|pair| pair[0] == "--model" && pair[1] == default_product_model()));
        assert!(!core
            .args
            .windows(2)
            .any(|pair| pair == ["--model", "fake-model"]));
    }

    #[test]
    fn product_core_uses_real_web_search_adapter() {
        let specs = service_specs("secret-token");
        let core = specs.iter().find(|spec| spec.name == "core").expect("core");

        assert!(core
            .args
            .windows(2)
            .any(|pair| pair == ["--web-search", "multi"]));
    }

    #[test]
    fn worker_commands_do_not_receive_core_token() {
        let specs = service_specs("secret-token");
        for spec in specs.iter().filter(|spec| spec.name != "core") {
            assert!(!spec.args.iter().any(|arg| arg == "secret-token"));
            assert!(!spec
                .env
                .iter()
                .any(|(_name, value)| value == "secret-token"));
        }
    }

    #[test]
    fn missing_sidecar_falls_back_to_dev_command() {
        assert!(sidecar_path(Some(Path::new("missing")), "marvex-core").is_none());
    }

    #[test]
    fn shutdown_wait_returns_after_supervised_services_are_stopped() {
        let status = Arc::new(SupervisorStatus::default());
        status.set("core", "stopped");
        status.set("voice_worker", "stopped");
        let supervisor = Supervisor {
            shutdown: Arc::new(AtomicBool::new(true)),
            status,
            config: Arc::new(RuntimeConfig {
                token: "secret-token".into(),
                log_dir: Path::new("/logs").to_path_buf(),
                data_dir: Path::new("/data").to_path_buf(),
                resource_dir: None,
            }),
            launched: Arc::new(AtomicBool::new(true)),
            bootstrapping: Arc::new(AtomicBool::new(false)),
        };

        assert!(supervisor.wait_for_services_stopped(Duration::from_millis(1)));
    }

    #[test]
    fn venv_layout_is_per_user_data_dir() {
        let venv = venv_root(Path::new("/data"));
        assert!(venv.ends_with("runtime/venv") || venv.ends_with("runtime\\venv"));
        let core = venv_script(&venv, "marvex-core");
        assert!(core.to_string_lossy().contains("marvex-core"));
    }

    #[test]
    fn uv_cache_lives_under_runtime_data_dir() {
        let cache = runtime_uv_cache_dir(Path::new("/data"));
        assert!(cache.ends_with("runtime/uv-cache") || cache.ends_with("runtime\\uv-cache"));
    }

    #[test]
    fn default_file_capability_root_is_local_user_scoped_when_available() {
        let root = default_file_capability_root(Path::new("/data"));

        assert!(!root.as_os_str().is_empty());
        if let Some(profile) = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME"))
        {
            assert_eq!(root, PathBuf::from(profile));
        }
    }

    #[test]
    fn packaged_runtime_uses_python_312_for_voice_wheels() {
        assert_eq!(PYTHON_RUNTIME_VERSION, "3.12");
    }

    #[test]
    fn incomplete_existing_venv_is_cleared_before_recreate() {
        let root = unique_temp_dir("partial-venv-clear");
        let venv = venv_root(&root);
        fs::create_dir_all(&venv).expect("partial venv");

        let args = venv_create_args(&venv, venv.exists());

        assert!(args.iter().any(|arg| arg == "--clear"));
        assert!(args.iter().any(|arg| arg == "3.12"));
    }

    #[test]
    fn existing_venv_is_not_current_until_bundled_wheel_marker_matches() {
        let root = unique_temp_dir("runtime-wheel-freshness");
        let data_dir = root.join("data");
        let resource_dir = root.join("resources");
        let venv = venv_root(&data_dir);
        fs::create_dir_all(
            venv_script(&venv, "marvex-core")
                .parent()
                .expect("script dir"),
        )
        .expect("venv script dir");
        fs::create_dir_all(&resource_dir).expect("resource dir");
        fs::write(venv_script(&venv, "marvex-core"), b"old core").expect("core script");
        let wheel = resource_dir.join("marvex-runtime.whl");
        fs::write(&wheel, b"new runtime wheel").expect("wheel");

        assert!(!runtime_venv_is_current(
            &data_dir,
            &venv,
            Some(&resource_dir)
        ));

        record_installed_runtime_wheel(&data_dir, &wheel).expect("record marker");
        assert!(runtime_venv_is_current(
            &data_dir,
            &venv,
            Some(&resource_dir)
        ));

        fs::write(&wheel, b"newer runtime wheel").expect("wheel update");
        assert!(!runtime_venv_is_current(
            &data_dir,
            &venv,
            Some(&resource_dir)
        ));
    }

    #[test]
    fn bundled_wheel_selection_prefers_shell_version_over_stale_wheel() {
        let root = unique_temp_dir("runtime-wheel-version-selection");
        let stale = root.join("marvex-0.2.0-py3-none-any.whl");
        let current = root.join(format!(
            "marvex-{}-py3-none-any.whl",
            env!("CARGO_PKG_VERSION")
        ));
        fs::write(&stale, b"stale runtime wheel").expect("stale wheel");
        fs::write(&current, b"current runtime wheel").expect("current wheel");

        assert_eq!(first_marvex_wheel(&root), Some(current));
    }

    #[test]
    fn console_script_update_probe_accepts_missing_and_writable_files() {
        let root = unique_temp_dir("runtime-script-update-probe");
        let script = root.join("marvex-core");

        assert!(console_script_can_be_updated(&script));
        fs::write(&script, b"console script").expect("script");
        assert!(console_script_can_be_updated(&script));
    }

    #[test]
    fn log_pipe_redacts_bearer_value_without_dropping_context() {
        assert_eq!(
            sanitize_log_line("request failed Authorization: Bearer secret-token trace=trace-1"),
            "request failed Authorization: Bearer [redacted] trace=trace-1"
        );
    }

    #[test]
    fn bootstrap_log_helpers_hide_local_paths() {
        let args = vec![
            "pip".to_string(),
            "install".to_string(),
            "C:\\Users\\Example\\AppData\\Local\\com.marvex.shell\\runtime\\marvex.whl"
                .to_string(),
        ];

        assert_eq!(sanitized_bootstrap_args(&args), "pip install <path>");

        let user_profile = std::env::var("USERPROFILE").ok();
        if let Some(profile) = user_profile {
            let raw = format!("failed inside {profile}\\runtime\\uv-cache");
            let sanitized = sanitize_bootstrap_bytes(raw.as_bytes());
            assert!(!sanitized.contains(&profile));
            assert!(sanitized.contains("<USERPROFILE>"));
        }
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
        let voice = specs
            .iter()
            .find(|s| s.name == "voice_worker")
            .expect("voice worker");
        assert_eq!(service_kind_label(&voice.kind), "jsonl");
        assert!(matches!(core.kind, ServiceKind::Core));
    }

    #[test]
    fn shell_supervisor_does_not_spawn_core_owned_workers() {
        let specs = service_specs("token");
        let names: Vec<_> = specs.iter().map(|spec| spec.name).collect();

        assert_eq!(names, vec!["core", "voice_worker"]);
        assert!(!names.contains(&"provider_worker"));
        assert!(!names.contains(&"intent_worker"));
        assert!(!names.contains(&"tool_worker"));
    }

    #[test]
    fn runtime_manifest_lists_only_shell_supervised_services_without_token() {
        let root = unique_temp_dir("manifest-contract");
        let data_dir = root.join("data");
        let log_dir = root.join("logs");
        fs::create_dir_all(&data_dir).expect("data dir");
        fs::create_dir_all(&log_dir).expect("log dir");
        let status = SupervisorStatus::default();
        status.set("runtime", "ready");
        let config = RuntimeConfig {
            token: "secret-token".to_string(),
            log_dir,
            data_dir: data_dir.clone(),
            resource_dir: None,
        };

        write_runtime_manifest(&config, &RuntimeOutcome::Dev, &status);

        let manifest_text =
            fs::read_to_string(data_dir.join("runtime").join("manifest.json")).expect("manifest");
        let manifest: Value = serde_json::from_str(&manifest_text).expect("manifest json");
        let services = manifest["services"].as_array().expect("services");
        let names: Vec<_> = services
            .iter()
            .filter_map(|service| service["name"].as_str())
            .collect();

        assert_eq!(names, vec!["core", "voice_worker"]);
        assert!(!manifest_text.contains("secret-token"));
    }

    #[test]
    fn resource_env_paths_are_present_only_when_resources_exist() {
        let root = unique_temp_dir("resource-env-contract");
        let resource_dir = root.join("resources");
        fs::create_dir_all(resource_dir.join("control_plane_web")).expect("control web");
        fs::create_dir_all(resource_dir.join("voice-assets")).expect("voice assets");
        fs::write(
            resource_dir.join("voice_models.manifest.json"),
            b"{\"assets\":[]}",
        )
        .expect("voice manifest");
        fs::write(resource_dir.join("uv.exe"), b"uv").expect("uv");
        fs::write(resource_dir.join("node.exe"), b"node").expect("node");
        let mcp_cli = resource_dir
            .join("playwright-mcp")
            .join("node_modules")
            .join("@playwright")
            .join("mcp")
            .join("cli.js");
        fs::create_dir_all(mcp_cli.parent().expect("mcp cli parent")).expect("mcp cli dir");
        fs::write(&mcp_cli, b"mcp").expect("mcp cli");

        let data_dir = root.join("data");
        let env = resource_env_paths(Some(&resource_dir), &root, &data_dir);

        assert!(env
            .iter()
            .any(|(name, value)| { name == "MARVEX_UV_PATH" && value.ends_with("uv.exe") }));
        assert!(env
            .iter()
            .any(|(name, value)| { name == "MARVEX_NODE_PATH" && value.ends_with("node.exe") }));
        assert!(env.iter().any(|(name, value)| {
            name == "MARVEX_PLAYWRIGHT_MCP_CLI" && value.ends_with("cli.js")
        }));
        assert!(env.iter().any(|(name, value)| {
            name == "MARVEX_CONTROL_WEB_DIST" && value.ends_with("control_plane_web")
        }));
        assert!(env.iter().any(|(name, value)| {
            name == "MARVEX_VOICE_ASSET_ROOT" && value.ends_with("voice-assets")
        }));
        assert!(env.iter().any(|(name, value)| {
            name == "MARVEX_VOICE_MODEL_MANIFEST" && value.ends_with("voice_models.manifest.json")
        }));

        let missing = resource_env_paths(Some(&root.join("missing")), &root, &data_dir);
        assert_eq!(
            missing,
            vec![(
                "MARVEX_VOICE_ASSET_ROOT".to_string(),
                data_dir.join("voice-assets").to_string_lossy().to_string()
            )]
        );
    }

    fn unique_temp_dir(label: &str) -> std::path::PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("marvex-{label}-{suffix}"));
        fs::create_dir_all(&path).expect("temp dir");
        path
    }
}
