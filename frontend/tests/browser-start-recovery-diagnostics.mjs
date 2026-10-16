const methods = new Set(['OPTIONS', 'POST']);
const resources = new Set(['Preflight', 'Fetch', 'XHR', 'Other']);
const errors = new Set(['Failed', 'Aborted', 'TimedOut', 'AccessDenied', 'ConnectionClosed',
  'ConnectionReset', 'ConnectionRefused', 'ConnectionAborted', 'ConnectionFailed',
  'NameNotResolved', 'InternetDisconnected', 'AddressUnreachable', 'BlockedByClient', 'BlockedByResponse']);
const commands = new Set(['Network.getRequestPostData', 'Fetch.continueRequest', 'Fetch.continueResponse', 'Fetch.failRequest']);
const blockedReasons = new Set(('other csp mixed-content origin inspector integrity subresource-filter content-type '
  + 'coep-frame-resource-needs-coep-header coop-sandboxed-iframe-cannot-navigate-to-coop-page corp-not-same-origin '
  + 'corp-not-same-origin-after-defaulted-to-same-origin-by-coep corp-not-same-origin-after-defaulted-to-same-origin-by-dip '
  + 'corp-not-same-origin-after-defaulted-to-same-origin-by-coep-and-dip corp-not-same-site sri-message-signature-mismatch').split(' '));
const corsErrors = new Set(('DisallowedByMode InvalidResponse WildcardOriginNotAllowed MissingAllowOriginHeader '
  + 'MultipleAllowOriginValues InvalidAllowOriginValue AllowOriginMismatch InvalidAllowCredentials CorsDisabledScheme '
  + 'PreflightInvalidStatus PreflightDisallowedRedirect PreflightWildcardOriginNotAllowed PreflightMissingAllowOriginHeader '
  + 'PreflightMultipleAllowOriginValues PreflightInvalidAllowOriginValue PreflightAllowOriginMismatch PreflightInvalidAllowCredentials '
  + 'PreflightMissingAllowExternal PreflightInvalidAllowExternal InvalidAllowMethodsPreflightResponse InvalidAllowHeadersPreflightResponse '
  + 'MethodDisallowedByPreflightResponse HeaderDisallowedByPreflightResponse RedirectContainsCredentials InsecureLocalNetwork '
  + 'InvalidLocalNetworkAccess NoCorsRedirectModeNotFollow LocalNetworkAccessPermissionDenied').split(' '));
const networkErrors = new Set(('net::ERR_FAILED net::ERR_ABORTED net::ERR_TIMED_OUT net::ERR_CONNECTION_REFUSED '
  + 'net::ERR_CONNECTION_RESET net::ERR_CONNECTION_CLOSED net::ERR_NAME_NOT_RESOLVED net::ERR_INTERNET_DISCONNECTED '
  + 'net::ERR_NETWORK_CHANGED net::ERR_ADDRESS_UNREACHABLE net::ERR_BLOCKED_BY_CLIENT net::ERR_BLOCKED_BY_RESPONSE '
  + 'net::ERR_EMPTY_RESPONSE').split(' '));

function browserMetadata(frontend, backend, networkOrdinal, knownNetworkOrdinal) {
  const front = new URL(frontend).origin, back = new URL(backend).origin;
  const events = [], requests = new Map(), frames = new Map(), loaders = new Map();
  let omittedEvents = 0, unmatchedEvents = 0, invalidEvents = 0;
  let requestOverflow = 0, correlationOverflow = 0, unmatchedInitiators = 0, unknownCategories = 0;
  const numeric = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const category = (value, known) => {
    if (value === undefined) return null;
    if (known.has(value)) return value;
    unknownCategories++; return 'other';
  };
  function record(row) { if (events.length < 64) events.push(row); else omittedEvents++; }
  function ordinal(map, value) {
    if (typeof value !== 'string' || !value || value.length > 256) return null;
    if (!map.has(value)) {
      if (map.size >= 16) { correlationOverflow++; return null; }
      map.set(value, map.size + 1);
    }
    return map.get(value);
  }
  function route(value) {
    if (typeof value !== 'string' || value.length > 4096) return null;
    try {
      const url = new URL(value);
      if (url.username || url.password) return null;
      const prefix = url.origin === back ? '' : url.origin === front ? '/api' : null;
      if (prefix === null || !url.pathname.startsWith(prefix + '/matches')) return null;
      const path = url.pathname.slice(prefix.length);
      if (path === '/matches/start') return 'start';
      if (path === '/matches') return 'summary';
      const found = path.match(/^\/matches\/[a-zA-Z0-9_-]{1,128}(?:\/(action|legal-moves))?$/);
      return found ? found[1] ?? 'match' : null;
    } catch { return null; }
  }
  function observe(message) {
    const { method, params = {} } = message;
    if (method === 'Runtime.executionContextsCleared') { record({ event: 'contexts-cleared' }); return; }
    if (method === 'Page.frameNavigated') {
      if (!params.frame || typeof params.frame.id !== 'string' || !params.frame.id || params.frame.id.length > 256) { invalidEvents++; return; }
      const parent = params.frame.parentId;
      record({ event: 'frame-navigated', frameOrdinal: ordinal(frames, params.frame.id),
        loaderOrdinal: ordinal(loaders, params.frame.loaderId),
        mainFrame: parent === undefined ? true : typeof parent === 'string' && parent ? false : null });
      return;
    }
    if (method === 'Page.navigatedWithinDocument') {
      record({ event: 'same-document-navigation', frameOrdinal: ordinal(frames, params.frameId), mainFrame: null }); return;
    }
    if (!['Network.requestWillBeSent', 'Network.responseReceived', 'Network.loadingFinished', 'Network.loadingFailed'].includes(method)) return;
    const id = params.requestId;
    if (typeof id !== 'string' || !id || id.length > 256) { invalidEvents++; return; }
    if (method === 'Network.requestWillBeSent') {
      const selected = route(params.request?.url);
      if (!selected || !['GET', 'POST', 'OPTIONS'].includes(params.request?.method)) {
        if (requests.has(id)) {
          record({ event: 'scope-exit', networkOrdinal: requests.get(id).info.networkOrdinal }); requests.delete(id);
        }
        return;
      }
      const index = networkOrdinal(id);
      if (index === null || (!requests.has(id) && requests.size >= 16)) { requestOverflow++; return; }
      const info = { networkOrdinal: index, route: selected, method: params.request.method,
        frameOrdinal: ordinal(frames, params.frameId), loaderOrdinal: ordinal(loaders, params.loaderId) };
      const initiator = params.initiator?.requestId;
      const linked = typeof initiator === 'string' ? networkOrdinal(initiator) : null;
      if (typeof initiator === 'string' && !requests.has(initiator)) unmatchedInitiators++;
      requests.set(id, { info, active: true });
      record({ event: 'request', ...info, timestamp: numeric(params.timestamp), initiatorNetworkOrdinal: linked });
      return;
    }
    const request = requests.get(id);
    if (!request) {
      if (method !== 'Network.loadingFailed') return;
      unmatchedEvents++;
    }
    const info = request?.info ?? { networkOrdinal: knownNetworkOrdinal(id), route: 'unmatched', method: null };
    if (method === 'Network.responseReceived') {
      const status = params.response?.status;
      record({ event: 'response', ...info, timestamp: numeric(params.timestamp),
        status: Number.isInteger(status) && status >= 100 && status <= 599 ? status : null });
    } else {
      if (request) request.active = false;
      record({ event: method === 'Network.loadingFailed' ? 'failed' : 'finished', ...info,
        timestamp: numeric(params.timestamp), ...(method === 'Network.loadingFailed' ? {
          canceled: typeof params.canceled === 'boolean' ? params.canceled : null,
          errorClass: category(params.errorText, networkErrors), blockedReason: category(params.blockedReason, blockedReasons),
          corsError: category(params.corsErrorStatus?.corsError, corsErrors),
        } : {}) });
    }
  }
  return {
    observe(message) { try { observe(message); } catch { invalidEvents++; } },
    snapshot() { return { events: structuredClone(events), omittedEvents, unmatchedEvents, invalidEvents,
      requestOverflow, correlationOverflow, unmatchedInitiators, unknownCategories,
      outstandingRequests: [...requests.values()].filter(request => request.active).length }; },
  };
}

export async function continueRequestForPostResponse(command, event) {
  if (event.responseStatusCode !== undefined || event.responseErrorReason !== undefined) return false;
  if (!methods.has(event.request.method)) throw new Error('Only POST or OPTIONS requests may enter POST-response capture');
  // Leave genuine preflight untouched; only POST opts into the later response pause.
  await command('Fetch.continueRequest', {requestId: event.requestId, interceptResponse: event.request.method === 'POST'});
  return true;
}

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
  report = value => console.error('START_RECOVERY_RESPONSE_TRACE', JSON.stringify(value)), metadataOptions) {
  const responses = [], requests = new Map(), networks = new Map();
  const metadata = metadataOptions ? browserMetadata(frontend, metadataOptions.backend,
    value => ordinal(networks, value), value => networks.get(value) ?? null) : null;
  let omittedResponses = 0, reported = false, pendingCommands = 0;
  function reportFailure() {
    if (reported) return;
    reported = true;
    try { report({responses: structuredClone(responses), omittedResponses, pendingCommands,
      ...(metadata ? { browserMetadata: metadata.snapshot() } : {})}); } catch { /* Preserve the original failure. */ }
  }
  function ordinal(map, value) {
    if (typeof value !== 'string' || !value || value.length > 256) return null;
    if (!map.has(value)) {
      if (map.size >= 16) return null;
      map.set(value, map.size + 1);
    }
    return map.get(value);
  }
  const traced = async event => {
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
      pendingCommands++;
      try {
        const result = await command(method, ...args);
        pendingCommands--;
        observation.acknowledgment = 'accepted';
        return result;
      } catch (error) {
        pendingCommands--;
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
  traced.reportFailure = reportFailure;
  if (metadata) traced.observeBrowserEvent = message => metadata.observe(message);
  return traced;
}
