# Responses Strict Judge Schema Design

## Context

The shared parser retries invalid free-form JSON, and H-006 detects a bad backend before a batch. OpenAI's Responses API supports strict JSON Schema output, which can prevent malformed verdicts at generation time; generic compatible backends cannot be assumed to implement it.

## Decision

Add an opt-in `DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA=false` setting. When enabled for `api=responses`, request the fixed judge verdict schema through `text.format: {type: json_schema, strict: true}`. Chat Completions and all default configurations keep their existing request shapes.

## Design

- `JudgeConfig` resolves, validates, and safely persists the boolean flag.
- Responses requests add the strict object schema for `is_correct`, `normalized_prediction`, and `reason` only when enabled.
- Public configuration and evaluator cache identity include the flag so results produced under different request shapes are never reused.
- Unit tests cover opt-in Responses shape, default compatibility, and cache invalidation; live H-009 runs only when the configured backend supports Responses strict schema.

## Non-goals

- Do not make strict schema the global default or send it to Chat Completions compatible backends.
