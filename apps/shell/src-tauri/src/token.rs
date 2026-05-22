pub fn generate_local_bearer_token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::getrandom(&mut bytes).map_err(|err| format!("token entropy unavailable: {err}"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

#[cfg(test)]
mod tests {
    use super::generate_local_bearer_token;

    #[test]
    fn generated_token_is_not_empty() {
        let token = generate_local_bearer_token().expect("token");
        assert_eq!(token.len(), 64);
        assert!(token.chars().all(|ch| ch.is_ascii_hexdigit()));
    }
}
