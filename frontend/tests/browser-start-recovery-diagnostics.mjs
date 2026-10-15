const methods = new Set(['OPTIONS', 'POST']);
const resources = new Set(['Preflight', 'Fetch', 'XHR', 'Other']);
const errors = new Set(['Failed', 'Aborted', 'TimedOut', 'AccessDenied', 'ConnectionClosed',
  'ConnectionReset', 'ConnectionRefused', 'ConnectionAborted', 'ConnectionFailed',
  'NameNotResolved', 'InternetDisconnected', 'AddressUnreachable', 'BlockedByClient', 'BlockedByResponse']);
const commands = new Set(['Network.getRequestPostData', 'Fetch.continueResponse', 'Fetch.failRequest']);

function cors(headers, frontend) {
  if (!Array.isArray(headers) || headers.length > 128) return {allowOrigin: 'unavailable', contentTypeAllowed: null, idempotencyKeyAllowed: null};
  const values = name => headers.filter(header => typeof header?.name === 'string' && header.name.toLowerCase() === name)
    .map(header => typeof header.value === 'string' && header.value.length <= 4096 ? header.value : null);
  const origins = values('access-control-allow-origin');
  const allowed = values('access-control-allow-headers').filter(value => value !== null)
    .flatMap(value => value.toLowerCase().split(',').map(name => name.trim()));
  return {allowOrigin: !origins.length ? 'absent' : origins.length !== 1 ? 'multiple'
    : origins[0] === frontend ? 'expected' : origins[0] === '*' ? 'wildcard' : 'other',
  contentTypeAllowed: allowed.includes('content-type'), idempotencyKeyAllowed: allowed.includes('idempotency-key')};
}

export function traceStartRecoveryResponses(command, handler, frontend,
  report = value => console.error('START_RECOVERY_RESPONSE_TRACE', JSON.stringify(value))) {
  const responses = [], requests = new Map(), networks = new Map();
  let omittedResponses = 0, reported = false;
  function reportFailure() {
    if (reported) return;
    reported = true;
    try { report({responses: structuredClone(responses), omittedResponses}); } catch { /* Preserve the original failure. */ }
  }
  function ordinal(map, value) {
    if (typeof value !== 'string' || !value || value.length > 256) return null;
    if (!map.has(value)) {
      if (map.size >= 16) return null;
      map.set(value, map.size + 1);
    }
    return map.get(value);
  }
  return async event => {
    const row = {method: methods.has(event?.request?.method) ? event.request.method : 'other',
      requestOrdinal: ordinal(requests, event?.requestId), networkOrdinal: ordinal(networks, event?.networkId),
      resourceType: resources.has(event?.resourceType) ? event.resourceType : 'other',
      status: Number.isInteger(event?.responseStatusCode) && event.responseStatusCode >= 100 && event.responseStatusCode <= 599 ? event.responseStatusCode : null,
      responseError: event?.responseErrorReason === undefined ? null : errors.has(event.responseErrorReason) ? event.responseErrorReason : 'other',
      cors: cors(event?.responseHeaders, frontend), commands: [], omittedCommands: 0};
    if (responses.length < 16) responses.push(row); else omittedResponses++;
    async function observedCommand(method, ...args) {
      const observation = {method: commands.has(method) ? method : 'other', acknowledgment: 'pending', errorCode: null};
      if (row.commands.length < 8) row.commands.push(observation); else row.omittedCommands++;
      try {
        const result = await command(method, ...args);
        observation.acknowledgment = 'accepted';
        return result;
      } catch (error) {
        observation.acknowledgment = 'error';
        try {
          if (typeof error.message === 'string' && error.message.length <= 4096) {
            const code = JSON.parse(error.message)?.code;
            if (Number.isSafeInteger(code)) observation.errorCode = code;
          }
        } catch { /* Diagnostic parsing cannot replace the native failure. */ }
        reportFailure();
        throw error;
      }
    }
    try { return await handler(event, observedCommand); }
    catch (error) {
      reportFailure();
      throw error;
    }
  };
}
