use std::io;
use std::process::{ExitStatus, Output, Stdio};
use std::time::Duration;

use tokio::io::{AsyncRead, AsyncReadExt};
use tokio::process::Command;
use tokio::task::JoinHandle;
use tokio::time::timeout;

use crate::policy::AuthorizedExecution;

#[derive(Debug, Eq, PartialEq)]
pub struct CapturedOutput {
    pub bytes: Vec<u8>,
    pub truncated: bool,
}

#[derive(Debug)]
pub struct BoundedProcessOutput {
    pub exit_status: Option<ExitStatus>,
    pub stdout: CapturedOutput,
    pub stderr: CapturedOutput,
    pub timed_out: bool,
}

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

pub async fn execute_bounded(execution: AuthorizedExecution) -> io::Result<BoundedProcessOutput> {
    let output_limit = execution.max_output_bytes();
    let deadline = Duration::from_millis(execution.deadline_ms());
    let mut command = Command::new(execution.executable());
    command
        .args(execution.arguments())
        .current_dir(execution.cwd())
        .env_clear()
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    let mut child = command.spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| io::Error::other("child stdout is unavailable"))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| io::Error::other("child stderr is unavailable"))?;
    let stdout_task = tokio::spawn(read_capped(stdout, output_limit));
    let stderr_task = tokio::spawn(read_capped(stderr, output_limit));

    let (exit_status, timed_out) = match timeout(deadline, child.wait()).await {
        Ok(status) => (status?, false),
        Err(_) => {
            child.start_kill()?;
            (child.wait().await?, true)
        }
    };
    let stdout = join_capture(stdout_task).await?;
    let stderr = join_capture(stderr_task).await?;

    Ok(BoundedProcessOutput {
        exit_status: Some(exit_status),
        stdout,
        stderr,
        timed_out,
    })
}

async fn read_capped<R>(mut reader: R, limit: usize) -> io::Result<CapturedOutput>
where
    R: AsyncRead + Unpin,
{
    let mut bytes = Vec::with_capacity(limit);
    let mut buffer = [0_u8; 8_192];
    let mut truncated = false;
    loop {
        let read = reader.read(&mut buffer).await?;
        if read == 0 {
            break;
        }
        let retained = limit.saturating_sub(bytes.len()).min(read);
        bytes.extend_from_slice(&buffer[..retained]);
        truncated |= retained < read;
    }
    Ok(CapturedOutput { bytes, truncated })
}

async fn join_capture(task: JoinHandle<io::Result<CapturedOutput>>) -> io::Result<CapturedOutput> {
    task.await.map_err(io::Error::other)?
}
