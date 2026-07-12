import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

import {
  ProtocolValidationError,
  validateEventStream,
  validatePackageManifest,
  validateRunRequest,
  validateRuntimeManifest,
} from "../dist/src/index.js";

const fixtures = new URL("../../../../tests/fixtures/agent_runtime/v1/", import.meta.url);
const packageFixtures = new URL(
  "../../../../tests/fixtures/packages/v1/",
  import.meta.url,
);
const referenceManifests = new URL(
  "../../../manifests/",
  import.meta.url,
);
const sourceDirectory = new URL("../src/", import.meta.url);

async function readJson(name) {
  return JSON.parse(await readFile(new URL(name, fixtures), "utf8"));
}

async function readPackageJson(name) {
  return JSON.parse(await readFile(new URL(name, packageFixtures), "utf8"));
}

async function readJsonl(name) {
  return (await readFile(new URL(name, fixtures), "utf8"))
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

test("validates the shared runtime manifest fixtures", async () => {
  const valid = await readJson("valid-runtime-manifest.json");
  const invalid = await readJson("invalid-runtime-manifest.json");

  assert.deepEqual(validateRuntimeManifest(valid), valid);
  assert.throws(() => validateRuntimeManifest(invalid), ProtocolValidationError);
});

test("validates shared requests and complete event streams", async () => {
  const request = {
    protocol: "dci.agent-runtime/v1",
    run_id: "typescript-host",
    input: { text: "Investigate the fixture corpus" },
    requested_capabilities: ["filesystem.read"],
  };
  assert.deepEqual(validateRunRequest(request), request);
  assert.throws(
    () => validateRunRequest({ ...request, requested_capabilities: ["shell", "shell"] }),
    ProtocolValidationError,
  );

  for (const name of [
    "valid-research.jsonl",
    "valid-cancelled.jsonl",
    "valid-artifact.jsonl",
  ]) {
    const events = await readJsonl(name);
    assert.deepEqual(validateEventStream(events), events);
  }
  for (const name of [
    "invalid-sequence-gap.jsonl",
    "invalid-unmatched-tool-result.jsonl",
    "invalid-post-terminal.jsonl",
  ]) {
    const events = await readJsonl(name);
    assert.throws(() => validateEventStream(events), ProtocolValidationError);
  }
});

test("validates the shared package manifest fixture", async () => {
  const valid = await readPackageJson("valid-capability.json");

  assert.deepEqual(validatePackageManifest(valid), valid);
});

test("rejects every shared invalid package manifest fixture", async () => {
  for (const name of [
    "invalid-unknown-field.json",
    "invalid-duplicate-edge.json",
    "invalid-package-id.json",
    "invalid-forbidden-command.json",
  ]) {
    const invalid = await readPackageJson(name);
    assert.throws(() => validatePackageManifest(invalid), ProtocolValidationError);
  }
});

test("rejects package edge arrays that are not sorted", async () => {
  const valid = await readPackageJson("valid-capability.json");
  const unsorted = {
    ...valid,
    provides_capabilities: ["z.last", "a.first"],
  };

  assert.throws(() => validatePackageManifest(unsorted), ProtocolValidationError);
});

test("validates every checked-in reference package manifest", async () => {
  const names = (await readdir(referenceManifests))
    .filter((name) => name.endsWith(".json"))
    .sort();
  assert.deepEqual(names, [
    "code-quality-evaluation.json",
    "code-quality-workflow.json",
    "controlled-code-policy.json",
    "dci-evaluation.json",
    "dci-research.json",
    "execution-audit-observability.json",
    "local-corpus-policy.json",
    "protocol-observability.json",
  ]);
  for (const name of names) {
    const manifest = JSON.parse(
      await readFile(new URL(name, referenceManifests), "utf8"),
    );
    assert.deepEqual(validatePackageManifest(manifest), manifest);
  }
});

test("keeps package composition outside the TypeScript host", async () => {
  const sources = await Promise.all(
    (await readdir(sourceDirectory))
      .filter((name) => name.endsWith(".ts"))
      .map((name) => readFile(new URL(name, sourceDirectory), "utf8")),
  );
  const publicSource = sources.join("\n");

  assert.doesNotMatch(publicSource, /composePackages|PackageComposition/);
});
