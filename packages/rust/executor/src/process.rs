use std::io;
use std::process::{Output, Stdio};

use tokio::process::Command;

use crate::policy::AuthorizedExecution;

pub async fn execute_direct(execution: AuthorizedExecution) -> io::Result<Output> {
    let mut command = Command::new(execution.executable());
    command
        .args(execution.arguments())
        .current_dir(execution.cwd())
        .env_clear()
        .stdin(Stdio::null())
        .kill_on_drop(true);
    command.output().await
}
