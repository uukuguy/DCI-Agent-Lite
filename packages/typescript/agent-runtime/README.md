# `@dci/agent-runtime`

Public TypeScript host contract for DCI Agent Runtime Protocol v1.

The package exports portable runtime-manifest, run-request, event, and asynchronous
client types. Runtime validators use the canonical schemas copied from the
repository's `schemas/agent-runtime/v1/` directory during the build. It has no Pi,
Claude Code, provider, or transport dependency.

```ts
import {
  validateRuntimeManifest,
  type AgentRuntimeClient,
  type RunRequest,
} from "@dci/agent-runtime";
```

From the repository root, run its complete build and shared-fixture suite with:

```bash
make test-typescript-host
```
