# Python and TypeScript Host Boundaries Design

> Status: approved for autonomous AF-040 delivery.

## Goal

Expose Agent Runtime Protocol v1 as stable public Python and TypeScript host APIs. Application code must be able to describe a runtime, submit a run request, and consume a validated asynchronous event stream without importing Pi, Claude Code, or any other adapter-private type.

## Boundary decision

The JSON Schemas under `schemas/agent-runtime/v1/` remain the canonical wire contract. AF-040 adds a runtime-manifest schema and matching fixtures, then exposes deliberately small host-native types and client interfaces:

- Python: `dci.framework.host` provides public typed records, validation entry points, and an `AgentRuntimeClient` protocol.
- TypeScript: `packages/typescript/agent-runtime` provides equivalent public types, runtime validation, and an `AgentRuntimeClient` interface.
- Both clients expose one immutable runtime manifest and one asynchronous `run` operation.
- Both consume the same checked-in conformance fixtures. A schema change is incomplete until both suites accept and reject the same fixture classes.

The host API is a contract, not a transport. AF-040 does not add HTTP, WebSocket, process management, workflow scheduling, or adapter selection. Existing Pi and Claude Code code remains behind adapter/runtime boundaries and may implement the client contract in later packages.

## Runtime manifest

The manifest contains only portable discovery data:

- protocol version;
- stable runtime identifier;
- unique capability identifiers.

Provider credentials, model configuration, account metadata, adapter classes, and executable paths are not manifest fields. Capability identifiers are opaque names at the host boundary; semantic package definitions belong to later capability packages.

## Client lifecycle

`run(request)` returns an asynchronous stream of protocol events. Host helpers validate the request before dispatch and validate stream invariants as events arrive or when a fixture stream is materialized. Terminal behavior remains defined by Agent Runtime Protocol v1: exactly one completed/failed event and no post-terminal events.

Cancellation uses host-native control without changing the v1 wire request: TypeScript implementations may observe `AbortSignal`, while Python implementations receive cancellation through their concrete async task/runtime integration. Cross-process cancellation transport is deferred until a runtime transport is selected.

## Type and validation strategy

Public types are hand-authored, readable representations of the versioned schema, not generated adapter models. Runtime validation remains mandatory at untrusted JSON boundaries. TypeScript uses a standards-based JSON Schema validator so it does not silently accept data that Python rejects; schema files are packaged as runtime assets rather than duplicated as private constants.

## Error boundary

Host validation errors identify the protocol object and violated public field but do not include credentials, provider payloads, or adapter stderr. Adapter/provider failures must already be normalized as `run.failed` before they reach host consumers.

## Acceptance

- A runtime-manifest schema and positive/negative fixtures are language neutral.
- Python and TypeScript public APIs model the same manifest, request, event, and asynchronous client boundary.
- Both validation suites consume shared fixtures and agree on valid/invalid cases.
- Public host modules do not import Pi or Claude Code adapter/runtime modules.
- Python tests, TypeScript build/tests, scope audit, and repository checks pass without provider credentials.
