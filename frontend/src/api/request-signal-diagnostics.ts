let recorded = 0;
const classes = new Set(["TimeoutError", "AbortError", "TypeError", "Error", "other"]);

function className(value: unknown): string {
  try {
    const name = (value as {name?: unknown} | null)?.name;
    return typeof name === "string" && classes.has(name) ? name : "other";
  } catch { return "other"; }
}

export function requestSignalStart(): number | null {
  try { const value = performance.now(); return Number.isFinite(value) ? value : null; }
  catch { return null; }
}

export function requestSignalAborted(signal: unknown): boolean | null {
  try {
    const value = Object.getOwnPropertyDescriptor(AbortSignal.prototype, "aborted")?.get?.call(signal);
    return typeof value === "boolean" ? value : null;
  } catch { return null; }
}

export function recordRequestSignal(path: unknown, options: RequestInit | undefined, error: unknown,
  started: number | null, initialAborted: boolean | null): void {
  try {
    if (recorded >= 16) return;
    const signal = options?.signal;
    const aborted = requestSignalAborted(signal);
    let reason: string | null = null;
    if (aborted === true) {
      try { reason = className(Object.getOwnPropertyDescriptor(AbortSignal.prototype, "reason")?.get?.call(signal)); }
      catch { reason = "other"; }
    }
    const method = options ? Object.getOwnPropertyDescriptor(options, "method")?.value : undefined;
    const elapsed = started === null ? null : requestSignalStart();
    const route = path === "/matches/start" ? "start"
      : typeof path === "string" && /^\/matches\/[a-zA-Z0-9_-]{1,128}\/legal-moves(?:\?player_id=[12])?$/.test(path) ? "legal-moves"
      : typeof path === "string" && /^\/matches\/[a-zA-Z0-9_-]{1,128}\/action$/.test(path) ? "action" : "other";
    const value = {phase: "fetch-rejected", ordinal: ++recorded, route,
      method: method === undefined ? "GET" : method === "GET" || method === "POST" ? method : "other",
      elapsedMs: elapsed === null || started === null ? null : Math.max(0, Math.min(30000, Math.round(elapsed - started))),
      signalAvailable: aborted !== null, initialAborted, signalAborted: aborted, signalReasonClass: reason,
      errorClass: className(error), atRecordCap: recorded === 16};
    const text = JSON.stringify(value);
    if (new TextEncoder().encode(text).byteLength <= 1024) console.debug("MTG_REQUEST_SIGNAL_DIAGNOSTIC", text);
  } catch { /* Missing diagnostics cannot replace the original request rejection. */ }
}
