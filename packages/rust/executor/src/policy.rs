use std::collections::BTreeMap;
use std::fmt;
use std::path::{Path, PathBuf};

use serde::Deserialize;

const MAX_DEADLINE_MS: u64 = 86_400_000;
const MAX_OUTPUT_BYTES: usize = 16_777_216;
const MAX_CONCURRENCY: usize = 256;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PolicyConfig {
    pub workspace_root: PathBuf,
    pub programs: BTreeMap<String, PathBuf>,
    pub max_deadline_ms: u64,
    pub max_output_bytes: usize,
    pub max_concurrency: usize,
}

#[derive(Debug)]
pub struct TrustedPolicy {
    workspace_root: PathBuf,
    programs: BTreeMap<String, PathBuf>,
    pub max_deadline_ms: u64,
    pub max_output_bytes: usize,
    pub max_concurrency: usize,
}

#[derive(Debug, Eq, PartialEq)]
pub struct PolicyError(&'static str);

impl fmt::Display for PolicyError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.0)
    }
}

impl std::error::Error for PolicyError {}

impl TryFrom<PolicyConfig> for TrustedPolicy {
    type Error = PolicyError;

    fn try_from(config: PolicyConfig) -> Result<Self, Self::Error> {
        let workspace_root = config
            .workspace_root
            .canonicalize()
            .map_err(|_| PolicyError("workspace root is unavailable"))?;
        if !workspace_root.is_dir() {
            return Err(PolicyError("workspace root is not a directory"));
        }
        if config.programs.is_empty() {
            return Err(PolicyError("program allowlist is empty"));
        }
        if !(1..=MAX_DEADLINE_MS).contains(&config.max_deadline_ms) {
            return Err(PolicyError("deadline limit is invalid"));
        }
        if !(1..=MAX_OUTPUT_BYTES).contains(&config.max_output_bytes) {
            return Err(PolicyError("output limit is invalid"));
        }
        if !(1..=MAX_CONCURRENCY).contains(&config.max_concurrency) {
            return Err(PolicyError("concurrency limit is invalid"));
        }

        let mut programs = BTreeMap::new();
        for (program_id, path) in config.programs {
            if program_id.is_empty() || !path.is_absolute() {
                return Err(PolicyError("program entry is invalid"));
            }
            let path = path
                .canonicalize()
                .map_err(|_| PolicyError("program is unavailable"))?;
            if !path.is_file() {
                return Err(PolicyError("program is not a file"));
            }
            programs.insert(program_id, path);
        }

        Ok(Self {
            workspace_root,
            programs,
            max_deadline_ms: config.max_deadline_ms,
            max_output_bytes: config.max_output_bytes,
            max_concurrency: config.max_concurrency,
        })
    }
}

impl TrustedPolicy {
    pub fn workspace_root(&self) -> &Path {
        &self.workspace_root
    }

    pub fn program(&self, program_id: &str) -> Option<&Path> {
        self.programs.get(program_id).map(PathBuf::as_path)
    }
}
