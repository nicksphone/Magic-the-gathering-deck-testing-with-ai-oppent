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

export function uiV2DropFailureMetadata(diagnostic) {
  try {
    const {dropped, postResponseObserved, responses, omittedResponses, canonical} = diagnostic ?? {};
    const retained = Array.isArray(responses) ? responses.length : -1;
    const {status, revision} = canonical ?? {};
    if (typeof dropped !== 'boolean' || typeof postResponseObserved !== 'boolean'
        || !Number.isInteger(retained) || retained < 0 || retained > 16
        || !Number.isSafeInteger(omittedResponses) || omittedResponses < 0
        || !['available', 'pending', 'unavailable', 'timed-out'].includes(status)
        || (status === 'available' ? !Number.isSafeInteger(revision) || revision < 0 : revision !== null)) return null;
    const counts = {retained, omitted: omittedResponses, options_200: 0, current_post_200: 0,
      continue_ack: 0, drop_ack: 0, error: 0, pending: 0};
    for (let index = 0; index < retained; index++) {
      const {method, status: code, current, command, continuation} = responses[index] ?? {};
      if (!['OPTIONS', 'POST', 'GET', 'HEAD', 'PUT', 'PATCH', 'DELETE', 'OTHER'].includes(method)
          || (code !== null && (!Number.isInteger(code) || code < 100 || code > 599))
          || typeof current !== 'boolean' || !['continue', 'drop'].includes(command)
          || !['ack', 'error', 'pending'].includes(continuation)) return null;
      if (method === 'OPTIONS' && code === 200) counts.options_200++;
      if (method === 'POST' && code === 200 && current) counts.current_post_200++;
      if (continuation === 'ack') {
        if (command === 'continue') counts.continue_ack++; else counts.drop_ack++;
      } else counts[continuation]++;
    }
    return {schema: 1, program: 'browser-ui-v2.mjs', stage: 'response-drop', dropped,
      post_response_observed: postResponseObserved, responses: counts, canonical: {status, revision}};
  } catch { return null; }
}

export function reportUiV2DropFailure(diagnostic) {
  try {
    const record = uiV2DropFailureMetadata(diagnostic);
    if (!record) return;
    const body = JSON.stringify(record);
    // Every projected string is fixed ASCII, so length also bounds UTF-8 bytes.
    if (body.length > 512) return;
    writeSync(2, `\n::error title=Browser response drop failure::${body}\n`);
  } catch { /* Annotation failure must not replace the original failure. */ }
}
