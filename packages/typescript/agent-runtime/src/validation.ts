import { readFileSync } from "node:fs";

import {
  Ajv2020,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";

import type { RunEvent, RunRequest, RuntimeManifest } from "./types.js";

function readSchema(name: string): object {
  return JSON.parse(
    readFileSync(new URL(`../schemas/${name}`, import.meta.url), "utf8"),
  ) as object;
}

const ajv = new Ajv2020({ allErrors: true });
const manifestValidator = ajv.compile(readSchema("runtime-manifest.schema.json"));
const requestValidator = ajv.compile(readSchema("run-request.schema.json"));
const eventValidator = ajv.compile(readSchema("event.schema.json"));

export class ProtocolValidationError extends Error {
  constructor(label: string, errors: readonly ErrorObject[] | null | undefined) {
    const first = errors?.[0];
    const location = first?.instancePath || "/";
    const reason = first?.message || "violates Agent Runtime Protocol v1";
    super(`${label} ${location} ${reason}`);
    this.name = "ProtocolValidationError";
  }
}

function requireValid<T>(
  label: string,
  validator: ValidateFunction,
  value: unknown,
): T {
  if (!validator(value)) {
    throw new ProtocolValidationError(label, validator.errors);
  }
  return value as T;
}

export function validateRuntimeManifest(value: unknown): RuntimeManifest {
  return requireValid("runtime manifest", manifestValidator, value);
}

export function validateRunRequest(value: unknown): RunRequest {
  return requireValid("run request", requestValidator, value);
}

export function validateEventStream(value: unknown): readonly RunEvent[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new ProtocolValidationError("event stream", null);
  }
  const events = value.map((event) =>
    requireValid<RunEvent>("event", eventValidator, event),
  );
  const runId = events[0]?.run_id;
  const calls = new Set<string>();
  const results = new Set<string>();
  let terminalSeen = false;

  for (const [index, event] of events.entries()) {
    const expectedSequence = index + 1;
    if (event.sequence !== expectedSequence) {
      throw new ProtocolValidationError("event stream sequence", null);
    }
    if (event.run_id !== runId) {
      throw new ProtocolValidationError("event stream run_id", null);
    }
    if (terminalSeen) {
      throw new ProtocolValidationError("event stream terminal", null);
    }
    if (index === 0 && event.type !== "run.started") {
      throw new ProtocolValidationError("event stream start", null);
    }
    if (index > 0 && event.type === "run.started") {
      throw new ProtocolValidationError("event stream start", null);
    }
    if (event.type === "tool.call") {
      if (calls.has(event.payload.call_id)) {
        throw new ProtocolValidationError("tool.call call_id", null);
      }
      calls.add(event.payload.call_id);
    } else if (event.type === "tool.result") {
      if (
        !calls.has(event.payload.call_id) ||
        results.has(event.payload.call_id)
      ) {
        throw new ProtocolValidationError("tool.result call_id", null);
      }
      results.add(event.payload.call_id);
    }
    terminalSeen = event.type === "run.completed" || event.type === "run.failed";
  }
  if (!terminalSeen) {
    throw new ProtocolValidationError("event stream terminal", null);
  }
  return events;
}
