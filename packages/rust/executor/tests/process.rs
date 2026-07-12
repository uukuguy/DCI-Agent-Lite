use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use dci_controlled_executor::policy::{AuthorizedExecution, PolicyConfig, TrustedPolicy};
use dci_controlled_executor::process::execute_direct;
use dci_controlled_executor::protocol::ExecuteRequest;

static NEXT_WORKSPACE: AtomicU64 = AtomicU64::new(0);

fn workspace() -> PathBuf {
    let nonce = NEXT_WORKSPACE.fetch_add(1, Ordering::Relaxed);
    let path = std::env::temp_dir().join(format!(
        "dci-executor-process-{}-{nonce}",
        std::process::id()
    ));
    fs::create_dir_all(path.join("nested")).expect("workspace");
    path
}

fn authorize(
    workspace_root: &Path,
    executable: &str,
    arguments: Vec<String>,
) -> AuthorizedExecution {
    let trusted = TrustedPolicy::try_from(PolicyConfig {
        workspace_root: workspace_root.to_owned(),
        programs: BTreeMap::from([("fixture".to_owned(), PathBuf::from(executable))]),
        max_deadline_ms: 30_000,
        max_output_bytes: 65_536,
        max_concurrency: 2,
    })
    .expect("policy");
    trusted
        .authorize(ExecuteRequest {
            protocol: "dci.executor/v1".to_owned(),
            request_id: "request-1".to_owned(),
            program_id: "fixture".to_owned(),
            arguments,
            cwd: PathBuf::from("nested"),
            deadline_ms: 1_000,
            max_output_bytes: 4_096,
        })
        .expect("authorized")
}

#[tokio::test]
async fn executes_literal_arguments_without_shell_expansion() {
    let workspace_root = workspace();
    let sentinel = workspace_root.join("shell-was-used");
    let authorized = authorize(
        &workspace_root,
        "/bin/echo",
        vec![
            "$HOME".to_owned(),
            ";".to_owned(),
            "touch".to_owned(),
            sentinel.display().to_string(),
        ],
    );

    let output = execute_direct(authorized).await.expect("execute");

    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).expect("stdout"),
        format!("$HOME ; touch {}\n", sentinel.display())
    );
    assert!(!sentinel.exists());
    fs::remove_dir_all(workspace_root).expect("cleanup");
}

#[tokio::test]
async fn clears_the_child_environment() {
    let workspace_root = workspace();
    let authorized = authorize(&workspace_root, "/usr/bin/env", vec![]);

    let output = execute_direct(authorized).await.expect("execute");

    assert!(output.status.success());
    assert!(output.stdout.is_empty(), "child inherited environment");
    fs::remove_dir_all(workspace_root).expect("cleanup");
}

#[tokio::test]
async fn closes_child_stdin() {
    let workspace_root = workspace();
    let authorized = authorize(&workspace_root, "/bin/cat", vec![]);

    let output = execute_direct(authorized).await.expect("execute");

    assert!(output.status.success());
    assert!(output.stdout.is_empty());
    fs::remove_dir_all(workspace_root).expect("cleanup");
}

#[tokio::test]
async fn executes_in_the_authorized_canonical_working_directory() {
    let workspace_root = workspace();
    let authorized = authorize(&workspace_root, "/bin/pwd", vec![]);
    let expected = workspace_root.join("nested").canonicalize().expect("cwd");

    let output = execute_direct(authorized).await.expect("execute");

    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).expect("stdout").trim(),
        expected.display().to_string()
    );
    fs::remove_dir_all(workspace_root).expect("cleanup");
}
