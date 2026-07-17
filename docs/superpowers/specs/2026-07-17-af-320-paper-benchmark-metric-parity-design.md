# AF-320 Paper Benchmark and Metric Parity Design

> Status: approved; corrected for functional-level reproduction. This design
> implements the AF-320 slice
> approved by the paper-aligned DCI milestone. It does not authorize full
> datasets or published-score reproduction.

## Purpose

AF-310 closed exact L0–L4 live context management. AF-320 closes the next
paper-implementation gap: all thirteen benchmark profiles, the paper's
trajectory coverage/localization analysis, retained-evidence measurement, and
bounded deterministic ablation surfaces.

The primary source is arXiv:2605.05242v1, especially §3.3, §4.1, RQ4–RQ6, and
Appendix A.3. The existing Asterion batch runner, recorder, evaluator, analysis,
export, profile, and launcher implementations remain authoritative. AF-320
extends them; it does not create a second benchmark engine.

## Scope and Evidence Boundary

AF-320 owns layers 1–3 only:

1. production implementation;
2. deterministic model-free verification;
3. one bounded QA and one bounded IR provider verification, including one BEIR
   case, only when separately invoked through the cost-visible verifier.

Full thirteen-dataset execution, the paper's 100-example ablations, 100K/200K/
400K corpus-scale runs, and published-score comparisons remain AF-340 work.

## Dataset Inventory

The complete closed inventory is exactly thirteen datasets:

- agentic search: BrowseComp-Plus;
- knowledge-intensive QA: NQ, TriviaQA, Bamboogle, HotpotQA,
  2WikiMultiHopQA, and MuSiQue;
- IR ranking: BRIGHT Biology, Earth Science, Economics, and Robotics; BEIR
  ArguAna and SciFact.

Each dataset has one canonical identifier, family, mode, source split and row
count, versioned exclusion policy, dataset path, corpus path, gold-field
contract, metric/Judge identity, bounded fixture, and execution class. A
separate experiment-scope registry binds each paper result/analysis to dataset
ID, selection mode/count, seed provenance, selection algorithm, and selected-ID
manifest digest. The
two registries are schema-closed, sorted, packaged in the Asterion wheel, and
validated against the batch profile and launcher registries. Aliases are not
accepted as distinct datasets or scopes.

The paper selection scopes are explicit and cannot be collapsed into one
per-dataset default:

- main BrowseComp-Plus results use all 830 questions;
- BrowseComp-Plus trajectory, tool, and corpus analyses use a separately named
  `n=100` scope;
- the BrowseComp-Plus context ablation uses its separately named random `n=100`
  scope;
- the Appendix A.1 random-50 protocol remains a distinct scope rather than
  overriding any of the preceding BrowseComp scopes;
- the four BRIGHT subsets and Bamboogle use their complete test sets; other
  applicable main-result datasets use a deterministic random sample of 50 after
  the versioned ambiguous/time-sensitive-QA exclusion policy. ArguAna selects
  50 from 1,406 source queries and SciFact selects 50 from 300.

Every sampled scope records whether the paper reported a seed. A reported seed
is stored with a fully specified sampling algorithm. When the paper/published
DCI-Bench selection does not report a seed, AF-320 records no fabricated numeric
seed: it packages the exact selected-ID manifest, marks the seed
`paper-unreported`, hashes the sorted IDs, and verifies membership plus exact
source-split count before use. The paper does not publish seeds or selected IDs
for the three sampled BrowseComp analysis scopes. AF-320 therefore does not
label locally selected IDs as paper-published: those scopes use explicit
Asterion-defined reproducible seeds, algorithms, and selected-ID digests. The
all-830 scope records its sorted-ID manifest SHA-256. QA and BrowseComp
correctness records the effective Judge model/API/prompt identity in both result
and Judge cache identity. The paper's GPT-4.1 setting remains experiment
provenance, not a functional implementation prerequisite.

## Functional Reproduction Boundary

AF-320 reproduces DCI capabilities and observable behavior, not literal paper
configuration values. The bounded QA path executes the same agent → Judge
contract with a configured, authenticated Judge and binds its effective provider,
model, API, endpoint, request shaping, and prompt fingerprint. DeepSeek, GPT-4.1,
or another supported Judge may satisfy functional acceptance when reported
truthfully and validated through the production evaluator.

AF-340 owns score reproduction and comparison. A claim that a run reproduces or
compares a paper number must match the paper-declared Judge model and all other
material experiment identities. AF-320 never relabels a configured Judge as the
paper Judge and never infers score comparability from functional acceptance.

The paper uses all 125 Bamboogle test questions, while the existing migrated
profile/launcher names and local file contain a 50-row sample. The paper-full
inventory row is intentionally unbound from that sample profile and launcher;
AF-320 may package and validate its identity but cannot execute it.

ArguAna and SciFact use the existing IR path after repairing its NDCG@10
implementation to standard binary DCG/IDCG semantics: keep only the first
occurrence of a retrieved document, compute ideal DCG from the unique relevant
set, and guarantee a finite result in `[0,1]`. A RED regression first proves the
current duplicate-retrieval behavior can exceed one. Their adapters normalize
source rows into the existing `BenchmarkRow` IR contract; they do not add
BEIR-specific behavior to the generic batch engine. Dataset and corpus
preflight completes before any provider process starts.

Execution classes are closed. `bounded-fixture` rows may execute under the
bounded verifier. `paper-full` rows may only be listed, validated, rendered, or
packaged during AF-320; the executor rejects them unconditionally before any
provider or Judge construction. There is no generic flag or environment bypass.
Only AF-340 may introduce a separately reviewed AF-340-specific authorization.

## Trajectory Evidence Contract

A new `dci.trajectory-resolution/v1` private artifact derives only from an
immutable completed native attempt plus a gold-document manifest. It contains:

- run, attempt, dataset, query, corpus, and analysis-configuration digests;
- exact gold-document identities and full character lengths;
- body-bearing observation alignments kept private;
- content-free counts and metric values for public/aggregate projection;
- an explicit unavailable reason when the metric denominator is empty or
  required evidence is missing.

The analyzer reads the recorder's native tool events and externalized tool
results. It never reconstructs observations from public projections or final
answers. Identity includes SHA-256 for the exact protocol event stream, every
consumed externalized tool-result blob, the final model-visible context
artifact, the gold manifest, and every opened corpus/gold file. All inputs are
rehashed immediately before reuse and export. A changed attempt, corpus, gold
manifest, alignment rule, segment width, or any consumed evidence byte changes
analysis identity and invalidates cached results.

## Paper Coverage Metrics

For question `q` and trajectory `τ`, let `D*(q)` be the non-empty unique gold
document set and `M(q,τ)` the subset surfaced by an observation. A document is
surfaced only when an observation is safely aligned through an explicit corpus
path or matching local text.

- `coverage_any = 1` when at least one gold document is surfaced, else `0`;
- `coverage_mean = |M| / |D*|`;
- `coverage_all = 1` when all gold documents are surfaced, else `0`.

Coverage batch aggregates are arithmetic means over valid per-query values.
Missing or duplicate gold identity, empty gold sets, partial/malformed native
evidence, or an incompatible corpus snapshot fails closed rather than
fabricating zero.

## Paper Localization Metric

Localization uses fixed-width character segments, not lines. The analysis
configuration contains a required positive integer `segment_characters`; the
paper defines the formula using `cseg` but does not state one universal numeric
value in the cited text. Therefore the value is explicit, versioned, and bound
into every artifact/cache key. AF-320 may prove the parameterized formula but
must not claim an unrecorded paper reproduction value.

For character length `x`:

- `ν(x) = max(1, ceil(x / segment_characters))`;
- `ψ(a,b) = max(1 - log(a) / log(b), 0)` for `1 ≤ a ≤ b` and `b > 1`;
- `ψ(a,1) = 1`.

Each aligned candidate snippet receives `ψ(ν(snippet_length),
ν(full_document_length))`. Each surfaced gold document keeps its maximum
candidate score. Query localization is the arithmetic mean of those per-gold
maxima over surfaced gold documents only. When no gold document is surfaced,
localization is explicitly unavailable, not zero. Dataset localization follows
the paper table's matched-document aggregation: flatten all surfaced-gold best
scores across valid queries and divide by that total surfaced-gold count.
Queries with no surfaced gold contribute neither numerator nor denominator; a
zero dataset denominator is explicitly unavailable.

Alignment is closed and conservative:

- grep/rg-style observations produce one candidate per aligned matched line;
- read-style observations use only the returned span when it sufficiently
  overlaps annotated gold evidence;
- path/listing/metadata-only surfacing contributes to coverage but uses full
  document length for localization;
- unmatched or ambiguous local text also falls back to full document length;
- shell pipelines are decomposed only when their recorded output can be safely
  assigned to one of these rules; otherwise they use the conservative fallback.

No fuzzy match may silently narrow a span. Alignment rules and overlap
thresholds are closed configuration with golden fixtures.

## Retained Evidence

`retained_coverage` is the fraction of gold documents whose aligned evidence
remains in the final model-visible conversation state. It is computed from the
private final context artifact and the same gold/corpus identities, separately
from trajectory coverage. If the final model context is unavailable or cannot
be aligned, the value is unavailable. Saved processed views do not substitute
for the final model-visible state.

## Deterministic Ablation Matrices

AF-320 records the paper-declared matrix separately from executable bounded
analogues. Paper rows use the named BrowseComp `n=100` query scope appropriate
to trajectory/tool/corpus analysis or context ablation, context levels 0–4 and
tool profiles `read,grep` and `read,bash`, plus the declared 100K, 200K, and 400K
BrowseComp/FineWeb corpus targets. Each paper row records both the query-scope
seed/algorithm/selected-ID digest and the FineWeb source identity and target
document count. The paper says that FineWeb distractors were randomly sampled
but does not publish their seed, algorithm, selected IDs, or manifest digest.
Those fields therefore carry an explicit `paper-unreported` provenance status
and null values; AF-320 must not fabricate an executable selection identity.
All are `paper-full` and non-executable in AF-320.

The executable analogues use three deliberately tiny, non-paper fixtures:

- context policy: level0 through level4;
- tool profile: literal Pi tool sets `read,grep` and `read,bash` (the restricted
  row uses Pi's dedicated grep tool and never exposes bash);
- corpus scale: explicit immutable corpus manifests representing a tiny base,
  base-plus-one bounded distractor shard, and base-plus-two bounded shards.

Matrix rows contain exact dataset/query fixture IDs, runtime/profile/tool
identity, corpus manifest digest, max turns, provider/model placeholders,
analysis configuration, expected artifact schemas, and declared cost class.
Generation is deterministic and duplicate-free. Local acceptance executes
model-free fixtures only. The bounded provider verifier may run one QA agent
row, one configured Judge operation, and one IR/BEIR agent row; it never
expands a matrix or selects a full dataset implicitly.

## Product Surface

`asterion-dci benchmark` remains the execution surface and gains exact dataset
and matrix/profile selectors. `asterion-dci export` and analysis outputs expose
coverage/localization/retained fields and references without observation or
document bodies. The generic installed application remains AF-330 scope; AF-320
must not duplicate DCI-specific analysis in framework core.

Batch reuse rehashes and validates the complete dataset/profile/corpus/analysis
identity plus the exact protocol stream, every consumed external tool blob,
final context artifact, gold manifest, and each opened corpus/gold file before
reusing metrics. Existing Judge cache identity remains independent but includes
the effective model/API/endpoint/prompt identity and every result field that
affects evaluation request shaping. The bounded evidence binder validates those
effective values against the private evaluation artifact without imposing a
specific provider or model.

## Security and Failure Semantics

- Dataset, corpus, gold, and native evidence files are regular no-follow inputs.
- Corpus-relative paths cannot escape the selected corpus root.
- Duplicate aliases, Unicode/path ambiguities, symlinks, stale digests, missing
  documents, and malformed observations fail before provider execution.
- Public artifacts contain no prompt, answer, document, snippet, tool-output,
  credential, endpoint body, or private path.
- Partial runs remain partial; unavailable metrics carry a closed reason.
- No downloader, provider, Judge, or full-dataset command runs by default.

## Verification and Acceptance

Model-free acceptance must prove:

- the exact thirteen-dataset inventory and wheel/resource parity;
- ArguAna/SciFact normalization, profile, preflight, launcher, first-occurrence
  retrieval deduplication, bounded NDCG@10, and duplicate-rank regression;
- exact coverage formulas, localization formulas, per-query coverage means,
  flattened matched-gold localization aggregation, maxima, retained
  coverage, and every conservative fallback;
- body-free projections, descriptor-safe private evidence, cache invalidation,
  partial/unavailable behavior, and deterministic matrix generation;
- source, installed CLI, batch, analysis, export, and isolated-wheel parity;
- zero provider/Judge operations and no full dataset in the default verifier.

Bounded acceptance requires exactly three declared external operations: one tiny
QA agent fixture, one configured Judge operation for that fixture, and one tiny
BEIR agent fixture. It records effective external runtime/model/Judge and
artifact identities without bodies and does not claim score reproduction or
paper-score comparability.

AF-320 closes only after scope preflight, all local gates, bounded evidence,
independent review, documentation truth, and unchanged external `pi/` pass.

## Non-Goals

- Full dataset downloads or runs.
- Reproducing any paper table value.
- Retrieval baseline/index implementations.
- Generic experiment scheduling.
- AF-330 application composition or Claude semantic acceptance.
- AF-340 budget, calibration, variance, or published-score interpretation.

## Primary References

- [DCI paper, arXiv:2605.05242v1](https://arxiv.org/pdf/2605.05242)
- Repository milestone design:
  `docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md`
