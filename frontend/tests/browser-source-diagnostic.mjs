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

export function startRecoveryFailureMetadata(snapshot) {
  const fixed = {schema: 1, program: 'browser-start-recovery.mjs', scope: 'latest-existing-trace'};
  if (snapshot === null || snapshot === undefined) return {...fixed, available: false,
    responses: null, commands: null, latest: null, pending_commands: null, active_callbacks: null, control: null};
  try {
    const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
    const count = value => Number.isSafeInteger(value) && value >= 0;
    if (!record(snapshot)) return null;
    const {responses, omittedResponses, pendingCommands, activeCallbacks, causal} = snapshot;
    if (!Array.isArray(responses) || responses.length > 16 || !count(omittedResponses)
        || !count(pendingCommands) || !count(activeCallbacks) || !record(causal)) return null;
    const {generationState, enableGeneration} = causal;
    if (!['unknown', 'enable-pending', 'enabled', 'disable-pending', 'disabled'].includes(generationState)
        || (enableGeneration !== null && (!Number.isInteger(enableGeneration)
          || enableGeneration < 0 || enableGeneration > 16))) return null;
    const responseCounts = {retained: responses.length, omitted: omittedResponses,
      options: 0, post: 0, other: 0, http_200: 0, without_status: 0};
    const commandCounts = {retained: 0, omitted: 0, pending: 0, accepted: 0, error: 0};
    let latest = null;
    for (let index = 0; index < responses.length; index++) {
      const row = responses[index];
      if (!record(row)) return null;
      const {method, status, commands, omittedCommands} = row;
      if (!['OPTIONS', 'POST', 'other'].includes(method)
          || (status !== null && (!Number.isInteger(status) || status < 100 || status > 599))
          || !Array.isArray(commands) || commands.length > 8 || !count(omittedCommands)) return null;
      if (method === 'OPTIONS') responseCounts.options++;
      else if (method === 'POST') responseCounts.post++;
      else responseCounts.other++;
      if (status === 200) responseCounts.http_200++;
      if (status === null) responseCounts.without_status++;
      commandCounts.retained += commands.length;
      commandCounts.omitted += omittedCommands;
      if (!count(commandCounts.omitted)) return null;
      latest = {method, status, command: null, ack: null, error_code: null};
      for (let commandIndex = 0; commandIndex < commands.length; commandIndex++) {
        const observation = commands[commandIndex];
        if (!record(observation)) return null;
        const {method: command, acknowledgment, errorCode} = observation;
        if (!['Network.getRequestPostData', 'Fetch.continueRequest', 'Fetch.continueResponse',
          'Fetch.failRequest', 'other'].includes(command)
            || !['pending', 'accepted', 'error'].includes(acknowledgment)
            || (errorCode !== null && !Number.isSafeInteger(errorCode))) return null;
        commandCounts[acknowledgment]++;
        latest = {method, status, command, ack: acknowledgment, error_code: errorCode};
      }
    }
    return {...fixed, available: true, responses: responseCounts, commands: commandCounts, latest,
      pending_commands: pendingCommands, active_callbacks: activeCallbacks,
      control: {state: generationState, enable_generation: enableGeneration}};
  } catch { return null; }
}

export function reportStartRecoveryFailure(snapshot) {
  try {
    const record = startRecoveryFailureMetadata(snapshot);
    if (!record) return;
    const body = JSON.stringify(record);
    if (body.length > 768) return;
    writeSync(2, `\n::error title=Browser start recovery failure::${body}\n`);
  } catch { /* Annotation failure must not replace the original failure. */ }
}

export function startRecoveryPhaseFailureMetadata(phase, error) {
  if (!['setup', 'lost-prepare', 'lost-recover', 'lost-verify',
    'reload-prepare', 'reload-pending', 'reload-replay', 'reload-verify',
    'click-prepare', 'click-pending', 'click-replay', 'click-verify',
    'legacy-prepare', 'legacy-pending', 'legacy-reload', 'legacy-review',
    'legacy-replay', 'legacy-verify'].includes(phase)) return null;
  let errorClass = 'other';
  try {
    if (error instanceof Error) {
      const name = error.name;
      if (classes.has(name)) errorClass = name;
    }
  } catch { /* Error getters must never replace the original failure. */ }
  return {schema: 1, program: 'browser-start-recovery.mjs', phase, error_class: errorClass};
}

export function reportStartRecoveryPhaseFailure(phase, error) {
  try {
    const record = startRecoveryPhaseFailureMetadata(phase, error);
    if (!record) return;
    const body = JSON.stringify(record);
    if (body.length > 512) return;
    writeSync(2, `\n::error title=Browser start recovery phase failure::${body}\n`);
  } catch { /* Annotation failure must not replace the original failure. */ }
}

export function uiV2DropRequestStateMetadata(diagnostic) {
  try {
    const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
    const count = value => Number.isSafeInteger(value) && value >= 0;
    if (!record(diagnostic)) return null;
    const {requests, uiStatus, actionUi, ui} = diagnostic;
    if (!record(requests)) return null;
    const {POST} = requests;
    if (!record(POST)) return null;
    const {observed, attempted, ack, error, pending} = POST;
    if (![observed, attempted, ack, error, pending].every(count)
        || !['available', 'unavailable', 'timed-out'].includes(uiStatus)) return null;
    let action = {enabled_prefix_count: null, rendered_revision: null};
    let view = {status: uiStatus, pending: null, restoring: null, alert: null};
    if (uiStatus === 'available') {
      if (!record(actionUi) || !record(ui)) return null;
      const {enabledPrefixCount, renderedRevision} = actionUi;
      const {pending: uiPending, restoring, alert} = ui;
      if ((enabledPrefixCount !== null && !count(enabledPrefixCount))
          || (renderedRevision !== null && !count(renderedRevision))
          || typeof uiPending !== 'boolean' || typeof restoring !== 'boolean'
          || typeof alert !== 'boolean') return null;
      action = {enabled_prefix_count: enabledPrefixCount, rendered_revision: renderedRevision};
      view = {status: uiStatus, pending: uiPending, restoring, alert};
    } else if (ui !== null || actionUi !== null) return null;
    return {schema: 1, program: 'browser-ui-v2.mjs', stage: 'response-drop-request-state',
      post: {observed, attempted, ack, error, pending}, action, ui: view};
  } catch { return null; }
}

export function reportUiV2DropRequestStateFailure(diagnostic) {
  try {
    const record = uiV2DropRequestStateMetadata(diagnostic);
    if (!record) return;
    const body = JSON.stringify(record);
    if (body.length > 512) return;
    writeSync(2, `\n::error title=Browser response drop request state failure::${body}\n`);
  } catch { /* Annotation failure must not replace the original failure. */ }
}
