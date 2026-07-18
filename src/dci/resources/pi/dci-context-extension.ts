type ProfileName = "level0" | "level1" | "level2" | "level3" | "level4";
type Content = { type: string; text?: string };
type Message = { role: string; content?: Content[] };
type Entry = { type: string; id?: string; customType?: string; data?: unknown; message?: Message };
type State = {
  accumulatedOriginalToolCharacters: number;
  compactionCount: number;
  compactionPending: boolean;
  summaryAttempts: number;
  summarySuccesses: number;
  consecutiveSummaryFailures: number;
  summarySuppressed: boolean;
};
const CONTRACT = "dci.context-profile/v1";
const VERSION = "1.0.0";
const profiles = {
  level0: { cap: null, trigger: null, retained: null, summary: false },
  level1: { cap: 50000, trigger: null, retained: null, summary: false },
  level2: { cap: 20000, trigger: null, retained: null, summary: false },
  level3: { cap: 20000, trigger: 240000, retained: 12, summary: false },
  level4: { cap: 20000, trigger: 240000, retained: 12, summary: true },
} as const;

export default function originalDciContext(pi: any): void {
  pi.registerFlag("dci-context-profile", { type: "string", description: "Original DCI context profile" });
  pi.registerFlag("dci-context-contract", { type: "string", description: "Original DCI context contract" });
  let profileName: ProfileName;
  let profile: (typeof profiles)[ProfileName];
  let state: State = { accumulatedOriginalToolCharacters: 0, compactionCount: 0, compactionPending: false, summaryAttempts: 0, summarySuccesses: 0, consecutiveSummaryFailures: 0, summarySuppressed: false };
  const persist = (event: string) => {
    pi.appendEntry("dci-context-telemetry", { schema: "dci.context-telemetry/v1", event, profile: profileName, contractVersion: CONTRACT, extensionVersion: VERSION, ...state });
    pi.appendEntry("dci-context-state", { schema: "dci.context-state/v1", profile: profileName, contractVersion: CONTRACT, state: { ...state } });
  };
  pi.on("session_start", (event: any, context: any) => {
    const selected = pi.getFlag("dci-context-profile");
    if (!(selected in profiles) || pi.getFlag("dci-context-contract") !== CONTRACT) throw new Error("Original DCI context profile is invalid");
    profileName = selected as ProfileName;
    profile = profiles[profileName];
    const prior = context.sessionManager.getEntries().filter((entry: Entry) => entry.customType === "dci-context-state").at(-1);
    if (prior) state = { ...(prior.data as any).state };
    else if (event.reason === "resume") throw new Error("Original DCI context resume state is missing");
    persist(event.reason === "resume" ? "resume" : "startup");
  });
  pi.on("tool_result", (event: any) => {
    const text = (event.content as Content[]).filter((item) => item.type === "text").map((item) => item.text ?? "").join("");
    state.accumulatedOriginalToolCharacters += text.length;
    if (profile.trigger !== null && state.accumulatedOriginalToolCharacters > profile.trigger) state.compactionPending = true;
    persist("tool_result");
    if (profile.cap === null || text.length <= profile.cap) return undefined;
    return { content: [{ type: "text", text: text.slice(0, profile.cap) }] };
  });
  pi.on("context", (event: any) => {
    if (profile.retained === null || !state.compactionPending) return { messages: [...event.messages] };
    const messages = event.messages as Message[];
    const users = messages.map((message, index) => message.role === "user" ? index : -1).filter((index) => index >= 0);
    const first = users.length > profile.retained ? users[users.length - profile.retained] : 0;
    return { messages: messages.slice(first) };
  });
  pi.on("turn_end", (_event: any, context: any) => {
    if (!state.compactionPending) return;
    const suppressed = state.summarySuppressed;
    context.compact({
      onComplete: () => {
        if (profile.summary && !suppressed) { state.summaryAttempts += 1; state.summarySuccesses += 1; state.consecutiveSummaryFailures = 0; }
        state.compactionPending = false;
        persist("compaction_complete");
      },
      onError: () => {
        if (profile.summary && !suppressed) { state.summaryAttempts += 1; state.consecutiveSummaryFailures += 1; state.summarySuppressed = state.consecutiveSummaryFailures >= 3; }
        state.compactionPending = false;
        persist("compaction_failed");
      },
    });
  });
  pi.on("session_before_compact", (event: any) => {
    if (profileName === "level4" && !state.summarySuppressed) return undefined;
    if (profile.retained === null) return undefined;
    const users = (event.branchEntries as Entry[]).filter((entry) => entry.type === "message" && entry.message?.role === "user");
    const firstKeptEntryId = users.length > profile.retained ? users[users.length - profile.retained]?.id : event.preparation.firstKeptEntryId;
    return { compaction: { summary: "", firstKeptEntryId, tokensBefore: event.preparation.tokensBefore } };
  });
  pi.on("session_compact", () => {
    state.accumulatedOriginalToolCharacters = 0;
    state.compactionPending = false;
    state.compactionCount += 1;
    persist("session_compact");
  });
}
