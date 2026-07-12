# Research Tree — DCI climb

> Deterministic summary generated from tracked state (2 runs).
> Do not edit directly; run `python3 tools/climb/regen-tree.py`.

## In-flight / session state

- Phase: implementation
- Last cycle: 2
- Next hypothesis: H-003
- In flight: none
- Next action: Start H-003.

## Active hypotheses

- **H-003** (pending, rank 0.50): Detect Pi RPC protocol incompatibility before benchmark execution.

## Run ladder

| run | hypothesis | local | verdict |
|---|---|---:|---|
| 20260712-084042-dci-climb-h001 | H-001 | 4 | confirmed 4/4 |
| 20260712-085134-dci-climb-h002 | H-002 | 4 | confirmed 4/4 |

## Negative cache

- duplicate the authoritative Pi commit across setup.sh and .env.template
- convert the independent Pi checkout to vendored or submodule ownership
