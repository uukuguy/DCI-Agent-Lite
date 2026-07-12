# Research Tree — DCI climb

> Deterministic summary generated from tracked state (6 runs).
> Do not edit directly; run `python3 tools/climb/regen-tree.py`.

## In-flight / session state

- Phase: knowledge-layer
- Last cycle: 6
- Next hypothesis: H-007
- In flight: none
- Next action: Implement H-007 safe judge credential provenance preflight.

## Active hypotheses

- **H-007** (pending, rank 0.70): Report safe judge credential provenance and warn when process environment shadows rotated .env values.

## Run ladder

| run | hypothesis | local | verdict |
|---|---|---:|---|
| 20260712-084042-dci-climb-h001 | H-001 | 4 | confirmed 4/4 |
| 20260712-085134-dci-climb-h002 | H-002 | 4 | confirmed 4/4 |
| 20260712-092803-dci-climb-h003 | H-003 | 4 | confirmed 4/4 |
| 20260712-160332-dci-climb-h004 | H-004 | 4 | confirmed 4/4 |
| 20260712-161133-dci-climb-h005 | H-005 | 4 | confirmed 4/4 |
| 20260712-171944-dci-climb-h006 | H-006 | 4 | confirmed 4/4 |

## Negative cache

- duplicate the authoritative Pi commit across setup.sh and .env.template
- convert the independent Pi checkout to vendored or submodule ownership
