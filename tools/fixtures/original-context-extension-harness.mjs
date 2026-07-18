import process from "node:process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [loaderPath, extensionPath, cwd] = process.argv.slice(2);
if (!loaderPath || !extensionPath || !cwd) throw new Error("invalid harness arguments");
const { loadExtensions } = await import(pathToFileURL(loaderPath));
const extensionSha256 = createHash("sha256").update(readFileSync(extensionPath)).digest("hex");

async function runtime(profile, prior = [], reason = "startup", contract = "dci.context-profile/v1", digest = extensionSha256) {
  const loaded = await loadExtensions([extensionPath], cwd);
  if (loaded.errors.length || loaded.extensions.length !== 1) throw new Error("extension load failed");
  const entries = [];
  loaded.runtime.appendEntry = (customType, data) => entries.push({ type: "custom", customType, data });
  loaded.runtime.flagValues.set("dci-context-profile", profile);
  loaded.runtime.flagValues.set("dci-context-contract", contract);
  loaded.runtime.flagValues.set("dci-context-extension-sha256", digest);
  const handlers = loaded.extensions[0].handlers;
  let compactOptions;
  const context = {
    sessionManager: { getEntries: () => prior },
    compact: (options) => { compactOptions = options; },
  };
  for (const handler of handlers.get("session_start") ?? []) await handler({ reason }, context);
  return { entries, handlers, context, compactOptions: () => compactOptions };
}

async function pressure(instance, succeeded) {
  let result = { content: [{ type: "text", text: "x".repeat(240001) }] };
  for (const handler of instance.handlers.get("tool_result") ?? []) {
    const changed = await handler(result, instance.context);
    if (changed) result = { ...result, ...changed };
  }
  let messages = [{ role: "system", content: [] }];
  for (let index = 1; index <= 13; index += 1) messages.push({ role: "user", content: [] }, { role: "assistant", content: [] });
  for (const handler of instance.handlers.get("context") ?? []) {
    const changed = await handler({ messages }, instance.context);
    if (changed?.messages) messages = changed.messages;
  }
  for (const handler of instance.handlers.get("turn_end") ?? []) await handler({}, instance.context);
  const callbacks = instance.compactOptions();
  if (callbacks) {
    for (const handler of instance.handlers.get("session_before_compact") ?? []) {
      await handler({ preparation: { settings: { keepRecentTokens: 20000 }, firstKeptEntryId: undefined, tokensBefore: 30000 }, branchEntries: [] }, instance.context);
    }
    if (succeeded) callbacks.onComplete(); else callbacks.onError();
    if (succeeded) for (const handler of instance.handlers.get("session_compact") ?? []) await handler({}, instance.context);
  }
  return { toolCharacters: result.content[0].text.length, retainedUsers: messages.filter((message) => message.role === "user").length };
}

const profiles = {};
for (const profile of ["level0", "level1", "level2", "level3", "level4"]) {
  const instance = await runtime(profile);
  const pressureResult = await pressure(instance, true);
  const latest = instance.entries.filter((entry) => entry.customType === "dci-context-telemetry").at(-1).data;
  profiles[profile] = { ...pressureResult, compactions: latest.compactionCount, summarySuccesses: latest.summarySuccesses, summaryRecentTokenTarget: latest.summaryRecentTokenTarget, customTypes: [...new Set(instance.entries.map((entry) => entry.customType))].sort() };
}

const failures = await runtime("level4");
for (let index = 0; index < 3; index += 1) await pressure(failures, false);
const failedState = failures.entries.filter((entry) => entry.customType === "dci-context-state").at(-1);
const failedTelemetry = failures.entries.filter((entry) => entry.customType === "dci-context-telemetry").at(-1).data;
const resumed = await runtime("level4", [failedState], "resume");
const resumeTelemetry = resumed.entries.filter((entry) => entry.customType === "dci-context-telemetry").at(-1).data;

async function rejected(profile, contract, digest) {
  try { await runtime(profile, [failedState], "resume", contract, digest); return false; }
  catch { return true; }
}
const resumeGuards = {
  profile: await rejected("level3", "dci.context-profile/v1", extensionSha256),
  contract: await rejected("level4", "dci.context-profile/v0", extensionSha256),
  digest: await rejected("level4", "dci.context-profile/v1", "0".repeat(64)),
};
const target = await runtime("level4");
await pressure(target, true);
let retainedTargetGuard = false;
try {
  for (const handler of target.handlers.get("session_before_compact") ?? []) await handler({ preparation: { settings: { keepRecentTokens: 19000 } }, branchEntries: [] }, target.context);
} catch { retainedTargetGuard = true; }

process.stdout.write(JSON.stringify({ profiles, failureSuppression: { attempts: failedTelemetry.summaryAttempts, suppressed: failedTelemetry.summarySuppressed }, resumeEvent: resumeTelemetry.event, resumeGuards, retainedTargetGuard }));
