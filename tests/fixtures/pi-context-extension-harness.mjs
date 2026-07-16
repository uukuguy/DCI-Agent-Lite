import process from "node:process";
import { pathToFileURL } from "node:url";

const [loaderPath, extensionPath, cwd] = process.argv.slice(2);
if (!loaderPath || !extensionPath || !cwd) {
  throw new Error("usage: harness LOADER EXTENSION CWD");
}

const { loadExtensions } = await import(pathToFileURL(loaderPath));
const results = {};
for (const profile of ["level0", "level1", "level2", "level3", "level4"]) {
  const loaded = await loadExtensions([extensionPath], cwd);
  if (loaded.errors.length !== 0 || loaded.extensions.length !== 1) {
    throw new Error("Pi did not load the DCI context extension");
  }
  const entries = [];
  loaded.runtime.appendEntry = (customType, data) => {
    entries.push({ customType, data });
  };
  loaded.runtime.flagValues.set("dci-context-profile", profile);
  loaded.runtime.flagValues.set("dci-context-contract", "dci.context-profile/v1");
  const extension = loaded.extensions[0];
  const context = {
    sessionManager: { getEntries: () => [] },
    compact: () => undefined,
  };
  for (const handler of extension.handlers.get("session_start") ?? []) {
    await handler({ type: "session_start", reason: "startup" }, context);
  }
  let toolResult = { content: [{ type: "text", text: "SENTINEL-" + "x".repeat(240_001) }] };
  for (const handler of extension.handlers.get("tool_result") ?? []) {
    const transformed = await handler(
      { type: "tool_result", ...toolResult },
      context,
    );
    if (transformed) toolResult = { ...toolResult, ...transformed };
  }
  const messages = [{ role: "system", content: [{ type: "text", text: "system" }] }];
  for (let turn = 1; turn <= 13; turn += 1) {
    messages.push({ role: "user", content: [{ type: "text", text: `u-${turn}` }] });
    messages.push({ role: "assistant", content: [{ type: "text", text: `a-${turn}` }] });
  }
  let visible = messages;
  for (const handler of extension.handlers.get("context") ?? []) {
    const transformed = await handler({ type: "context", messages: visible }, context);
    if (transformed?.messages) visible = transformed.messages;
  }
  results[profile] = {
    toolCharacters: toolResult.content[0].text.length,
    retainedUsers: visible.filter((message) => message.role === "user").length,
    customTypes: [...new Set(entries.map((entry) => entry.customType))].sort(),
  };
}
process.stdout.write(JSON.stringify(results));
