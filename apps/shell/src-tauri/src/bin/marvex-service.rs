fn main() {
    #[cfg(windows)]
    {
        marvex_shell_lib::service::main();
    }
    #[cfg(not(windows))]
    {
        eprintln!("marvex-service is only supported on Windows.");
        std::process::exit(1);
    }
}
