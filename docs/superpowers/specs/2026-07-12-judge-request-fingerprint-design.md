# Judge Request Fingerprint Design

## Context

Evaluation-result reuse currently compares a hand-maintained list of judge configuration fields and the three answer inputs. That list must be extended whenever request shaping changes, which makes an omitted field capable of silently reusing a verdict generated under a different judge request.

## Decision

Use a deterministic SHA-256 fingerprint of the safe public judge configuration, effective endpoint, and fully built request payload as the sole reuse identity. Persist only the hexadecimal digest in `eval_result.json`; never persist credentials or a duplicate prompt payload for cache matching.

## Design

- `judge.py` builds a canonical JSON representation of `{configuration, endpoint, request}` with stable key ordering and computes its SHA-256 digest.
- `judge_answer_sync` persists `judge_request_fingerprint` beside the existing safe judge metadata.
- `maybe_reuse_existing_eval` recomputes the fingerprint from the current configuration and answer inputs. A result is reusable only when its stored digest matches exactly and it contains a boolean verdict.
- Existing artifacts without the new field are intentionally non-reusable once, so they are refreshed under the new contract.
- Focused tests prove deterministic matching, invalidation for endpoint and shaped-request changes, and legacy-artifact safety. The H-010 climb adapter records the four acceptance dimensions.

## Non-goals

- Do not change judge endpoint selection, credential precedence, request defaults, or provider request bodies.
- Do not include API keys, key hashes, or raw prompts in cache metadata.
