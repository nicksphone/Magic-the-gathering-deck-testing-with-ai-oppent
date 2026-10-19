import {writeSync} from 'node:fs';

const source = new URL('./browser-ui-v2.mjs', import.meta.url).href;
const escapedSource = source.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const frame = new RegExp(`^\\s+at (?:async )?(?:[^()\\n]* \\()?${escapedSource}:(\\d{1,6}):(\\d{1,6})\\)?$`);
const classes = new Set(['Error', 'AssertionError', 'TypeError', 'RangeError',
  'ReferenceError', 'SyntaxError', 'URIError', 'EvalError']);

export function uiV2FailureMetadata(error) {
  const result = {schema: 1, program: 'browser-ui-v2.mjs', reported_line: null,
    error_class: 'other', location_verified: false};
  try {
    if (!(error instanceof Error)) return result;
    const name = error.name;
    if (classes.has(name)) result.error_class = name;
    const stack = error.stack;
    if (typeof stack !== 'string' || stack.length > 131072) return result;
    if (typeof error.message !== 'string' || error.message.length > 131072) return result;
    // Cached stack text can be stale; this is only a hint, never execution proof.
    const header = String(error);
    if (!stack.startsWith(`${header}\n`)) return result;
    for (const line of stack.slice(header.length + 1).split('\n').slice(0, 32)) {
      const location = frame.exec(line);
      if (location && Number(location[1]) > 0 && Number(location[2]) > 0) {
        result.reported_line = Number(location[1]);
        break;
      }
    }
  } catch { /* Diagnostic getters must never replace the original exception. */ }
  return result;
}

export function observeUiV2Failures() {
  process.on('uncaughtExceptionMonitor', error => {
    try {
      writeSync(2, `\n::error title=Browser source failure::${JSON.stringify(uiV2FailureMetadata(error))}\n`);
    } catch { /* Best effort only; default uncaught-exception handling remains intact. */ }
  });
}
