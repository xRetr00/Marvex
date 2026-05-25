use std::{
    fs,
    path::{Path, PathBuf},
    sync::{atomic::AtomicBool, Arc},
    thread,
    time::Duration,
};

use serde::{Deserialize, Serialize};

const TOKEN_PIPE_NAME: &str = r"\\.\pipe\Marvex.TokenHandoff.v1";
const CORE_BASE_URL: &str = "http://127.0.0.1:8765";
const CONTROL_BASE_URL: &str = "http://127.0.0.1:8766/control";

#[derive(Clone, Deserialize, Serialize)]
pub struct TokenLease {
    pub token: String,
    pub core_base_url: String,
    pub control_base_url: String,
    pub auth_token_present: bool,
    pub token_value_logged: bool,
}

pub fn request_token_lease(timeout: Duration) -> Option<TokenLease> {
    request_token_lease_from_pipe(TOKEN_PIPE_NAME, timeout)
}

pub fn start_token_broker(token: String, shutdown: Arc<AtomicBool>) -> thread::JoinHandle<()> {
    start_token_broker_on_pipe(TOKEN_PIPE_NAME.to_string(), token, shutdown)
}

pub fn delete_legacy_shared_token() {
    delete_legacy_shared_token_under(Path::new(
        &std::env::var("ProgramData").unwrap_or_else(|_| "C:\\ProgramData".to_string()),
    ));
}

fn legacy_shared_token_path_under(base: &Path) -> PathBuf {
    base.join("Marvex").join("service.token")
}

fn delete_legacy_shared_token_under(base: &Path) {
    let _ = fs::remove_file(legacy_shared_token_path_under(base));
}

#[cfg(windows)]
fn request_token_lease_from_pipe(pipe_name: &str, timeout: Duration) -> Option<TokenLease> {
    windows_impl::request_token_lease_from_pipe(pipe_name, timeout)
}

#[cfg(not(windows))]
fn request_token_lease_from_pipe(_pipe_name: &str, _timeout: Duration) -> Option<TokenLease> {
    None
}

#[cfg(windows)]
fn start_token_broker_on_pipe(
    pipe_name: String,
    token: String,
    shutdown: Arc<AtomicBool>,
) -> thread::JoinHandle<()> {
    thread::spawn(move || windows_impl::run_token_broker(&pipe_name, &token, &shutdown))
}

#[cfg(not(windows))]
fn start_token_broker_on_pipe(
    _pipe_name: String,
    _token: String,
    _shutdown: Arc<AtomicBool>,
) -> thread::JoinHandle<()> {
    thread::spawn(|| {})
}

#[cfg(windows)]
mod windows_impl {
    use super::{TokenLease, CONTROL_BASE_URL, CORE_BASE_URL};
    use serde_json::json;
    use std::{
        ffi::OsStr,
        os::windows::ffi::OsStrExt,
        sync::{
            atomic::{AtomicBool, Ordering},
            Arc,
        },
        thread,
        time::{Duration, Instant},
    };
    use windows::{
        core::PCWSTR,
        Win32::{
            Foundation::{
                CloseHandle, GetLastError, LocalFree, ERROR_PIPE_CONNECTED, HANDLE, HLOCAL,
                INVALID_HANDLE_VALUE,
            },
            Security::{
                Authorization::{
                    ConvertStringSecurityDescriptorToSecurityDescriptorW, SDDL_REVISION_1,
                },
                PSECURITY_DESCRIPTOR, SECURITY_ATTRIBUTES,
            },
            Storage::FileSystem::{
                CreateFileW, ReadFile, WriteFile, FILE_ATTRIBUTE_NORMAL, FILE_GENERIC_READ,
                FILE_GENERIC_WRITE, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
                PIPE_ACCESS_DUPLEX,
            },
            System::Pipes::{
                ConnectNamedPipe, CreateNamedPipeW, PIPE_READMODE_BYTE, PIPE_TYPE_BYTE, PIPE_WAIT,
            },
        },
    };

    pub fn request_token_lease_from_pipe(pipe_name: &str, timeout: Duration) -> Option<TokenLease> {
        let deadline = Instant::now() + timeout;
        loop {
            let handle = unsafe {
                CreateFileW(
                    PCWSTR(wide(pipe_name).as_ptr()),
                    FILE_GENERIC_READ.0 | FILE_GENERIC_WRITE.0,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL,
                    None,
                )
            };
            if let Ok(handle) = handle {
                return request_with_handle(handle);
            }
            if Instant::now() >= deadline {
                return None;
            }
            thread::sleep(Duration::from_millis(25));
        }
    }

    pub fn run_token_broker(pipe_name: &str, token: &str, shutdown: &Arc<AtomicBool>) {
        while !shutdown.load(Ordering::SeqCst) {
            let security = pipe_security_attributes();
            let handle = unsafe {
                CreateNamedPipeW(
                    PCWSTR(wide(pipe_name).as_ptr()),
                    PIPE_ACCESS_DUPLEX,
                    PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                    1,
                    4096,
                    4096,
                    1000,
                    security
                        .as_ref()
                        .map(|(attributes, _descriptor)| attributes as *const _),
                )
            };
            if let Some((_attributes, descriptor)) = security {
                unsafe {
                    let _ = LocalFree(Some(HLOCAL(descriptor.0)));
                }
            }
            if handle == INVALID_HANDLE_VALUE {
                thread::sleep(Duration::from_millis(100));
                continue;
            }
            let connected = unsafe { ConnectNamedPipe(handle, None).is_ok() }
                || unsafe { GetLastError() } == ERROR_PIPE_CONNECTED;
            if connected {
                serve_client(handle, token);
            }
            unsafe {
                let _ = CloseHandle(handle);
            }
        }
    }

    fn request_with_handle(handle: HANDLE) -> Option<TokenLease> {
        let request = b"{\"request\":\"token_lease\"}\n";
        let mut written = 0_u32;
        let wrote = unsafe { WriteFile(handle, Some(request), Some(&mut written), None).is_ok() };
        if !wrote {
            unsafe {
                let _ = CloseHandle(handle);
            }
            return None;
        }
        let response = read_to_newline(handle);
        unsafe {
            let _ = CloseHandle(handle);
        }
        serde_json::from_slice::<TokenLease>(&response).ok()
    }

    fn serve_client(handle: HANDLE, token: &str) {
        let request = read_to_newline(handle);
        if !String::from_utf8_lossy(&request).contains("token_lease") {
            return;
        }
        let response = json!({
            "token": token,
            "core_base_url": CORE_BASE_URL,
            "control_base_url": CONTROL_BASE_URL,
            "auth_token_present": true,
            "token_value_logged": false,
        })
        .to_string()
            + "\n";
        let mut written = 0_u32;
        unsafe {
            let _ = WriteFile(handle, Some(response.as_bytes()), Some(&mut written), None);
        }
    }

    fn read_to_newline(handle: HANDLE) -> Vec<u8> {
        let mut output = Vec::new();
        let mut buffer = [0_u8; 512];
        loop {
            let mut read = 0_u32;
            let ok = unsafe { ReadFile(handle, Some(&mut buffer), Some(&mut read), None).is_ok() };
            if !ok || read == 0 {
                break;
            }
            output.extend_from_slice(&buffer[..read as usize]);
            if output.contains(&b'\n') {
                break;
            }
        }
        output
    }

    fn wide(value: &str) -> Vec<u16> {
        OsStr::new(value).encode_wide().chain(Some(0)).collect()
    }

    fn pipe_security_attributes() -> Option<(SECURITY_ATTRIBUTES, PSECURITY_DESCRIPTOR)> {
        let mut descriptor = PSECURITY_DESCRIPTOR::default();
        // LocalSystem and administrators get full control; the interactive user
        // session can request a short token lease without exposing a disk secret.
        let sddl = wide("D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGW;;;IU)");
        let converted = unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                PCWSTR(sddl.as_ptr()),
                SDDL_REVISION_1,
                &mut descriptor,
                None,
            )
        };
        if converted.is_err() {
            return None;
        }
        Some((
            SECURITY_ATTRIBUTES {
                nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
                lpSecurityDescriptor: descriptor.0,
                bInheritHandle: false.into(),
            },
            descriptor,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        delete_legacy_shared_token_under, legacy_shared_token_path_under,
        request_token_lease_from_pipe, start_token_broker_on_pipe,
    };
    use std::{
        fs,
        sync::{
            atomic::{AtomicBool, Ordering},
            Arc,
        },
        time::{Duration, SystemTime, UNIX_EPOCH},
    };

    #[test]
    #[cfg(windows)]
    fn broker_serves_fake_token_lease() {
        let pipe_name = unique_pipe_name("lease");
        let shutdown = Arc::new(AtomicBool::new(false));
        let broker = start_token_broker_on_pipe(
            pipe_name.clone(),
            "fake-token-for-lease".to_string(),
            Arc::clone(&shutdown),
        );

        let lease =
            request_token_lease_from_pipe(&pipe_name, Duration::from_secs(3)).expect("token lease");

        assert_eq!(lease.token, "fake-token-for-lease");
        assert_eq!(lease.core_base_url, "http://127.0.0.1:8765");
        assert_eq!(lease.control_base_url, "http://127.0.0.1:8766/control");
        assert!(lease.auth_token_present);
        assert!(!lease.token_value_logged);

        shutdown.store(true, Ordering::SeqCst);
        let _ = request_token_lease_from_pipe(&pipe_name, Duration::from_secs(1));
        broker.join().expect("broker exits");
    }

    #[test]
    fn missing_broker_returns_none_quickly() {
        let lease =
            request_token_lease_from_pipe(&unique_pipe_name("missing"), Duration::from_millis(25));

        assert!(lease.is_none());
    }

    #[test]
    fn legacy_service_token_path_is_deleted_best_effort() {
        let root = std::env::temp_dir().join(format!("marvex-token-test-{}", unique_suffix()));
        let path = legacy_shared_token_path_under(&root);
        fs::create_dir_all(path.parent().expect("parent")).expect("mkdir");
        fs::write(&path, "raw-token-on-disk").expect("write token");

        delete_legacy_shared_token_under(&root);

        assert!(!path.exists());
        let _ = fs::remove_dir_all(root);
    }

    fn unique_pipe_name(label: &str) -> String {
        format!(r"\\.\pipe\Marvex.TokenHandoff.{label}.{}", unique_suffix())
    }

    fn unique_suffix() -> u128 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time")
            .as_nanos()
    }
}
