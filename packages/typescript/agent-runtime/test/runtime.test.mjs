import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  ProtocolValidationError,
  validateEventStream,
  validateRunRequest,
  validateRuntimeManifest,
} from "../dist/src/index.js";

const fixtures = new URL("../../../../tests/fixtures/agent_runtime/v1/", import.meta.url);

async function readJson(name) {
  return JSON.parse(await readFile(new URL(name, fixtures), "utf8"));
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
