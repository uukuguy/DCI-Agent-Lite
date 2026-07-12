use std::path::PathBuf;

use serde::Deserialize;

pub const PROTOCOL: &str = "dci.executor/v1";

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
pub enum ExecutorRequest {
    #[serde(rename = "execute")]
    Execute(ExecuteRequest),
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecuteRequest {
    pub protocol: String,
    pub request_id: String,
    pub program_id: String,
    pub arguments: Vec<String>,
    pub cwd: PathBuf,
    pub deadline_ms: u64,
    pub max_output_bytes: usize,
}
