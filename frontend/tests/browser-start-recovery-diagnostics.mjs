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

function browserMetadata(frontend, backend, networkOrdinal, knownNetworkOrdinal, requestSignals) {
  const front = new URL(frontend).origin, back = new URL(backend).origin;
  const events = [], requests = new Map(), frames = new Map(), loaders = new Map();
  const bidiContexts = new Map(), bidiRealms = new Map();
  const sockets = new Map();
  const signalContexts = new Map(), signalRecords = [];
  let signalContextsSeen = 0, signalContextOverflow = 0, signalInvalid = 0,
    signalUnknownContext = 0, signalOmitted = 0, signalSeen = false;
  const signalClasses = new Set(['TimeoutError', 'AbortError', 'TypeError', 'Error', 'other']);
  const reasons = new Set(['formSubmissionGet', 'formSubmissionPost', 'httpHeaderRefresh', 'scriptInitiated',
    'metaTagRefresh', 'pageBlockInterstitial', 'reload', 'anchorClick']);
  const navigationTypes = new Set(['reload', 'reloadBypassingCache', 'restore', 'restoreWithPost',
    'sameDocument', 'differentDocument', 'historySameDocument', 'historyDifferentDocument']);
  const initiators = new Set(['parser', 'script', 'preload', 'SignedExchange', 'preflight', 'other']);
  const messageTypes = new Set(['connected', 'update', 'full-reload', 'custom', 'prune', 'error', 'ping']);
  let omittedEvents = 0, unmatchedEvents = 0, invalidEvents = 0;
  let requestOverflow = 0, correlationOverflow = 0, unmatchedInitiators = 0, unknownCategories = 0;
  let webSocketOverflow = 0, ignoredWebSockets = 0;
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
  function observe(message, source) {
    const { method, params = {} } = message;
    if (['Page.frameDetached', 'Page.frameSubtreeWillBeDetached', 'Inspector.detached',
      'Inspector.targetCrashed', 'Target.targetDestroyed', 'Target.targetCrashed', 'Target.detachedFromTarget'].includes(method)) {
      // These are direct owned-page CDP notifications, not child-session or BiDi events.
      if (message.protocol !== undefined || message.sessionId !== undefined) return;
      if (method.startsWith('Page.')) {
        const id = params.frameId;
        if (typeof id !== 'string' || !id || id.length > 256) { invalidEvents++; return; }
        const frameOrdinal = frames.get(id) ?? null;
        record({event: method === 'Page.frameDetached' ? 'frame-detached' : 'frame-subtree-will-detach',
          frameOrdinal, correlation: frameOrdinal === null ? 'unjoined' : 'joined',
          ...(method === 'Page.frameDetached' ? {reason: category(params.reason, new Set(['remove', 'swap']))} : {})});
        if (method === 'Page.frameDetached') {
          for (const [key, context] of signalContexts) if (context.frame === id) signalContexts.delete(key);
        }
      } else if (method.startsWith('Inspector.')) {
        record({event: method === 'Inspector.detached' ? 'inspector-detached' : 'inspector-target-crashed',
          ownership: 'owned-page-session'});
        signalContexts.clear();
      } else {
        const id = params.targetId;
        const owned = typeof id === 'string' && id.length > 0 && id.length <= 256
          && source?.protocol === 'cdp' && source.targetId === id;
        record({event: method === 'Target.targetDestroyed' ? 'target-destroyed'
          : method === 'Target.targetCrashed' ? 'target-crashed' : 'target-detached',
        ownership: owned ? 'owned' : 'unjoined', ...(method === 'Target.targetCrashed'
          ? {errorCode: Number.isSafeInteger(params.errorCode) ? params.errorCode : null} : {})});
        if (owned) signalContexts.clear();
      }
      return;
    }
    if (method === 'Runtime.executionContextCreated') {
      const c = params.context;
      if (Number.isSafeInteger(c?.id) && signalContexts.has(c.id)) {
        signalContexts.delete(c.id); signalInvalid = Math.min(65535, signalInvalid + 1); return;
      }
      if (!Number.isSafeInteger(c?.id) || c.id <= 0 || c.origin !== front || c.auxData?.isDefault !== true
        || typeof c.auxData.frameId !== 'string' || !c.auxData.frameId || c.auxData.frameId.length > 256) return;
      if (signalContextsSeen >= 16) { signalContextOverflow = Math.min(65535, signalContextOverflow + 1); return; }
      signalContexts.set(c.id, {ordinal: ++signalContextsSeen, frame: c.auxData.frameId, lastRecord: 0});
      return;
    }
    if (method === 'Runtime.executionContextDestroyed') { signalContexts.delete(params.executionContextId); return; }
    if (method === 'Runtime.consoleAPICalled') {
      const args = params.args;
      if (!Array.isArray(args) || args[0]?.type !== 'string' || args[0].value !== 'MTG_REQUEST_SIGNAL_DIAGNOSTIC') return;
      signalSeen = true;
      const context = signalContexts.get(params.executionContextId);
      if (!context || !frames.has(context.frame)) { signalUnknownContext = Math.min(65535, signalUnknownContext + 1); return; }
      if (signalRecords.length >= 16) { signalOmitted = Math.min(65535, signalOmitted + 1); return; }
      let data;
      try {
        if (params.type !== 'debug' || args.length !== 2 || args[1]?.type !== 'string'
          || typeof args[1].value !== 'string' || new TextEncoder().encode(args[1].value).byteLength > 1024) throw Error();
        data = JSON.parse(args[1].value);
        const keys = ['phase', 'ordinal', 'route', 'method', 'elapsedMs', 'signalAvailable', 'initialAborted',
          'signalAborted', 'signalReasonClass', 'errorClass', 'atRecordCap'];
        if (!data || typeof data !== 'object' || Array.isArray(data) || Object.keys(data).length !== keys.length
          || Object.keys(data).some(key => !keys.includes(key)) || data.phase !== 'fetch-rejected'
          || !Number.isInteger(data.ordinal) || data.ordinal < 1 || data.ordinal > 16 || data.ordinal <= context.lastRecord
          || !['start', 'legal-moves', 'action', 'other'].includes(data.route) || !['GET', 'POST', 'other'].includes(data.method)
          || !(data.elapsedMs === null || Number.isInteger(data.elapsedMs) && data.elapsedMs >= 0 && data.elapsedMs <= 30000)
          || typeof data.signalAvailable !== 'boolean' || ![true, false, null].includes(data.initialAborted)
          || !(data.signalAvailable ? typeof data.signalAborted === 'boolean' : data.signalAborted === null)
          || data.initialAborted === true && data.signalAborted === false
          || !(data.signalAborted === true ? signalClasses.has(data.signalReasonClass) : data.signalReasonClass === null)
          || !signalClasses.has(data.errorClass) || data.atRecordCap !== (data.ordinal === 16)) throw Error();
      } catch { signalInvalid = Math.min(65535, signalInvalid + 1); return; }
      context.lastRecord = data.ordinal;
      const {ordinal: diagnosticOrdinal, ...details} = data;
      signalRecords.push({...details, diagnosticOrdinal, frameOrdinal: frames.get(context.frame), contextOrdinal: context.ordinal});
      return;
    }
    if (message.protocol === 'webdriver-bidi' && message.type === 'event' &&
        ['script.realmCreated', 'script.realmDestroyed'].includes(method)) {
      if (method === 'script.realmCreated' && typeof params.type === 'string' && params.type !== 'window') return;
      const correlation = message.correlation;
      const identity = value => typeof value === 'string' && value.length > 0 && value.length <= 256;
      if (!identity(params.realm) || correlation?.realmType !== 'window' ||
          !identity(correlation.context) || !identity(correlation.top) ||
          method === 'script.realmCreated' && (params.type !== 'window' || params.context !== correlation.context)) {
        invalidEvents++; return;
      }
      record({ event: method === 'script.realmCreated' ? 'bidi-realm-created' : 'bidi-realm-destroyed',
        protocol: 'webdriver-bidi', realmOrdinal: ordinal(bidiRealms, params.realm),
        contextOrdinal: ordinal(bidiContexts, correlation.context), topContextOrdinal: ordinal(bidiContexts, correlation.top),
        topLevel: correlation.context === correlation.top });
      return;
    }
    if (method === 'Page.frameRequestedNavigation' || method === 'Page.frameStartedNavigating') {
      if (typeof params.frameId !== 'string' || !params.frameId || params.frameId.length > 256) { invalidEvents++; return; }
      const frameOrdinal = ordinal(frames, params.frameId);
      if (method === 'Page.frameRequestedNavigation') {
        record({event: 'navigation-requested', frameOrdinal, reason: category(params.reason, reasons)});
      } else {
        record({event: 'navigation-started', frameOrdinal, loaderOrdinal: ordinal(loaders, params.loaderId),
          navigationType: category(params.navigationType, navigationTypes)});
      }
      return;
    }
    if (['Network.webSocketCreated', 'Network.webSocketHandshakeResponseReceived',
      'Network.webSocketFrameReceived', 'Network.webSocketClosed'].includes(method)) {
      const id = params.requestId;
      if (typeof id !== 'string' || !id || id.length > 256) { invalidEvents++; return; }
      const socket = sockets.get(id);
      if (method === 'Network.webSocketCreated') {
        if (socket) { socket.state = 'invalid'; invalidEvents++; return; }
        let url;
        try { if (typeof params.url === 'string' && params.url.length <= 4096) url = new URL(params.url); } catch { /* Unowned URL. */ }
        if (!url || url.origin !== front.replace(/^http/, 'ws') || url.pathname !== '/'
          || url.username || url.password || url.hash || url.href !== params.url) { ignoredWebSockets++; return; }
        if (sockets.size >= 16) { webSocketOverflow++; return; }
        const socketOrdinal = sockets.size + 1;
        sockets.set(id, {socketOrdinal, state: 'created'});
        record({event: 'frontend-websocket-created', socketOrdinal, timestamp: numeric(params.timestamp)});
        return;
      }
      if (!socket) { ignoredWebSockets++; return; }
      if (method === 'Network.webSocketHandshakeResponseReceived') {
        const headers = params.response?.headers;
        const entries = headers && typeof headers === 'object' && !Array.isArray(headers) ? Object.entries(headers) : [];
        const protocol = entries.length <= 128 ? entries.filter(([key]) => key.toLowerCase() === 'sec-websocket-protocol') : [];
        if (socket.state !== 'created' || params.response?.status !== 101 || protocol.length !== 1
          || protocol[0][1] !== 'vite-hmr') { socket.state = 'invalid'; invalidEvents++; return; }
        socket.state = 'open';
        record({event: 'vite-handshake', socketOrdinal: socket.socketOrdinal, timestamp: numeric(params.timestamp)});
        return;
      }
      if (socket.state !== 'open') { ignoredWebSockets++; return; }
      if (method === 'Network.webSocketClosed') {
        socket.state = 'closed';
        record({event: 'vite-closed', socketOrdinal: socket.socketOrdinal, timestamp: numeric(params.timestamp)});
        return;
      }
      const response = params.response, text = response?.payloadData;
      if (response?.opcode !== 1 || typeof text !== 'string' || text.length > 4096
        || new TextEncoder().encode(text).byteLength > 4096) { invalidEvents++; return; }
      let payload;
      try { payload = JSON.parse(text); } catch { invalidEvents++; return; }
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) { invalidEvents++; return; }
      if (!messageTypes.has(payload.type)) { unknownCategories++; return; }
      record({event: 'vite-message', socketOrdinal: socket.socketOrdinal, timestamp: numeric(params.timestamp), messageType: payload.type});
      return;
    }
    if (method === 'Runtime.executionContextsCleared') { signalContexts.clear(); record({ event: 'contexts-cleared' }); return; }
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
      if (params.type === 'Document') {
        let url;
        try { if (typeof params.request?.url === 'string' && params.request.url.length <= 4096) url = new URL(params.request.url); } catch { /* Unowned URL. */ }
        if (url && url.origin === front && url.pathname === '/' && !url.username && !url.password) {
          record({event: 'document-request', networkOrdinal: networkOrdinal(id),
            frameOrdinal: ordinal(frames, params.frameId), loaderOrdinal: ordinal(loaders, params.loaderId),
            timestamp: numeric(params.timestamp), initiator: category(params.initiator?.type, initiators)});
        }
      }
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
        networkType: category(params.type, resources), initiatorType: category(params.initiator?.type, initiators),
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
        status: Number.isInteger(status) && status >= 100 && status <= 599 ? status : null,
        ...(info.method === 'OPTIONS' || info.route === 'legal-moves' ? {cors: networkCors(params.response?.headers, front)} : {}) });
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
    observe(message, source) { try { requestSignals?.observe(message, source); observe(message, source); } catch { invalidEvents++; } },
    snapshot() { return { events: structuredClone(events), omittedEvents, unmatchedEvents, invalidEvents,
      requestOverflow, correlationOverflow, unmatchedInitiators, unknownCategories,
      webSocketOverflow, ignoredWebSockets,
      outstandingRequests: [...requests.values()].filter(request => request.active).length,
      ...(requestSignals ? {requestSignalAttribution: requestSignals.snapshot()} : signalSeen ? {requestSignalAttribution: {status: signalRecords.length ? 'observed-partial' : 'unavailable',
        correlation: 'not-joined-to-native-network-id', records: structuredClone(signalRecords),
        atRecordCap: signalRecords.length >= 16 || signalRecords.some(row => row.atRecordCap),
        contextOverflow: signalContextOverflow, invalidRecords: signalInvalid,
        unknownContext: signalUnknownContext, omittedRecords: signalOmitted}} : {}) }; },
  };
}

export function createRequestSignalObserver(frontend, backend) {
  const metadata = browserMetadata(frontend, backend, () => null, () => null);
  const methods = new Set(['Runtime.executionContextCreated', 'Runtime.executionContextDestroyed',
    'Runtime.executionContextsCleared', 'Runtime.consoleAPICalled', 'Page.frameNavigated',
    'Page.frameDetached', 'Inspector.detached', 'Inspector.targetCrashed',
    'Target.targetDestroyed', 'Target.targetCrashed', 'Target.detachedFromTarget']);
  return {
    observe(message, source) { if (methods.has(message?.method)) metadata.observe(message, source); },
    // Frame/context ordinals belong to this observer, not the later native trace.
    snapshot() { return metadata.snapshot().requestSignalAttribution; },
  };
}

export async function continueRequestForPostResponse(command, event) {
  if (event.responseStatusCode !== undefined || event.responseErrorReason !== undefined) return false;
  if (!methods.has(event.request.method)) throw new Error('Only POST or OPTIONS requests may enter POST-response capture');
  // Do not opt OPTIONS into a response pause; only POST requests one.
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

function networkCors(headers, frontend) {
  const unavailable = {allowOrigin: 'unavailable', contentTypeAllowed: null, idempotencyKeyAllowed: null,
    getAllowed: null, postAllowed: null, methodsWildcard: null, headersWildcard: null, privateNetwork: 'unavailable'};
  if (!headers || typeof headers !== 'object' || Array.isArray(headers)) return unavailable;
  const selected = new Map(['access-control-allow-origin', 'access-control-allow-methods',
    'access-control-allow-headers', 'access-control-allow-private-network'].map(name => [name, []]));
  let count = 0, selectedCount = 0;
  for (const key in headers) {
    if (!Object.hasOwn(headers, key)) continue;
    const descriptor = Object.getOwnPropertyDescriptor(headers, key), value = descriptor?.value;
    if (++count > 128 || key.length > 256 || typeof value !== 'string' || value.length > 4096) return unavailable;
    const values = selected.get(key.toLowerCase());
    if (values) for (const part of value.split('\n')) {
      if (++selectedCount > 128) return unavailable;
      values.push(part.trim());
    }
  }
  const entries = [...selected].flatMap(([name, values]) => values.map(value => ({name, value})));
  const tokens = (name, lower = false) => {
    const values = selected.get(name).flatMap(value => value.split(',').map(part => part.trim()));
    if (values.some(value => !/^[!#$%&'*+.^_`|~0-9a-zA-Z-]+$/.test(value))) return null;
    return lower ? values.map(value => value.toLowerCase()) : values;
  };
  const allowedMethods = tokens('access-control-allow-methods'), allowedHeaders = tokens('access-control-allow-headers', true);
  const privateNetwork = selected.get('access-control-allow-private-network');
  return {...cors(entries, frontend),
    contentTypeAllowed: allowedHeaders?.includes('content-type') ?? null,
    idempotencyKeyAllowed: allowedHeaders?.includes('idempotency-key') ?? null,
    getAllowed: allowedMethods?.includes('GET') ?? null, postAllowed: allowedMethods?.includes('POST') ?? null,
    methodsWildcard: allowedMethods?.includes('*') ?? null, headersWildcard: allowedHeaders?.includes('*') ?? null,
    privateNetwork: !privateNetwork.length ? 'absent' : privateNetwork.length !== 1 ? 'multiple'
      : ['true', 'false'].includes(privateNetwork[0]) ? privateNetwork[0] : 'other'};
}

export function traceStartRecoveryResponses(command, handler, frontend,
  report = value => console.error('START_RECOVERY_RESPONSE_TRACE', JSON.stringify(value)), metadataOptions) {
  const responses = [], requests = new Map(), networks = new Map();
  const metadata = metadataOptions ? browserMetadata(frontend, metadataOptions.backend,
    value => ordinal(networks, value), value => networks.get(value) ?? null, metadataOptions.requestSignals) : null;
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
  if (metadata) traced.observeBrowserEvent = (message, source) => metadata.observe(message, source);
  return traced;
}
