# Climb Adjudicator Log

Append-only decision-gate record.

## 2026-07-12 H-001

- Decision: pursue a single tracked revision lock with exact-commit override support.
- Evidence: moving `main` is non-reproducible; duplicate pins can drift; submodule/vendor conflicts with the external-checkout boundary.
- Vote: autonomous climb adjudication — PUSH to deterministic local acceptance.
