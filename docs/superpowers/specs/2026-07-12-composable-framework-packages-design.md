# Composable Framework Packages Design

> Status: approved for autonomous AF-060 package-first delivery under the existing framework roadmap.

## Goal

Define a portable package contract and deterministic composition boundary so capabilities, policies, workflows, observability, memory, and evaluation can declare what they provide and require without importing runtime-adapter internals.

## Chosen approach

Use a versioned `dci.package/v1` manifest plus a pure composition resolver. This is preferred over building a workflow engine first or an enterprise control plane first because it establishes the smallest shared contract those systems can later consume.

## Package manifest

Each closed JSON manifest declares a stable package ID/version/kind, provided and required capability IDs, required policy IDs, emitted/consumed event types, and produced/consumed artifact media types. Package kinds are `capability`, `workflow`, `policy`, `memory`, `observability`, and `evaluation`.

The manifest contains no prompts, provider credentials, runtime commands, executable paths, mutable state, or adapter-private types. JSON Schema and positive/negative shared fixtures are canonical.

## Composition

The Python reference composer accepts manifests plus host-provided capabilities/policies. It rejects duplicate package IDs, unsatisfied capabilities, missing policies, incompatible event/artifact edges, and dependency cycles. Successful output is deterministic topological order plus a normalized composition summary suitable for artifacts and audit.

Composition is static validation, not workflow execution. A future workflow engine consumes the resolved graph without changing package identities or policy semantics.

## Reference vertical slice

Checked-in manifests model DCI local-corpus research, its runtime capability requirements, a restrictive local-corpus policy, protocol event observability, and evaluation. The same package graph must compose against both Pi and Claude Code runtime manifests through portable capabilities; no provider-backed call is required.

## Language boundary

Python owns the reference resolver because orchestration/evaluation remain Python-heavy. TypeScript validates the same schemas and fixtures through the existing host package so language hosts share discovery truth without duplicating the resolver in AF-060.

## Non-goals

- No general-purpose workflow scheduler or prompt DSL.
- No persistent memory/vector database implementation.
- No multi-tenant policy administration or remote control plane.
- No adapter-specific package variants or claims of identical native runtime behavior.

## Acceptance

- Shared schemas/fixtures prove closed portable package manifests.
- Python tests prove deterministic composition and every rejection boundary.
- TypeScript validates the shared package fixtures.
- The DCI reference graph composes for Pi and Claude Code portable runtime capabilities.
- Documentation explains extension points and the static-composition boundary.
- Full Python, TypeScript, Rust, scope, format, lint, and diff gates pass.
