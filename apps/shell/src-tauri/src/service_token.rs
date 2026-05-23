use std::{fs, io::Write, path::PathBuf};

/// Shared local file where the backend Windows service writes the loopback
/// bearer token so the per-user shell (thin client) can authenticate against the
/// already-running service. Lives under ProgramData so a perMachine service and
/// a per-user shell can both reach it.
pub fn shared_token_path() -> PathBuf {
    let base = std::env::var("ProgramData").unwrap_or_else(|_| "C:\\ProgramData".to_string());
    PathBuf::from(base).join("Marvex").join("service.token")
}

pub fn read_shared_token() -> Option<String> {
    let token = fs::read_to_string(shared_token_path()).ok()?;
    let trimmed = token.trim().to_string();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

pub fn write_shared_token(token: &str) -> std::io::Result<()> {
    let path = shared_token_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::File::create(&path)?;
    file.write_all(token.as_bytes())?;
    Ok(())
}
