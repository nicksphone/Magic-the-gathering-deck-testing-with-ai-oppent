import {randomBytes} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {openBrowser} from './browser-driver.mjs';
import {continueRequestForPostResponse} from './browser-start-recovery-diagnostics.mjs';

export const modes = ['baseline', 'current-request', 'response-only', 'dual-static'];
const errorNames = new Set(['Error', 'TypeError', 'SyntaxError', 'AbortError', 'TimeoutError', 'HTTPError']);
const networkErrors = new Set(['net::ERR_ABORTED', 'net::ERR_FAILED', 'net::ERR_TIMED_OUT',
  'net::ERR_CONNECTION_CLOSED', 'net::ERR_CONNECTION_RESET', 'net::ERR_CONNECTION_REFUSED',
  'net::ERR_BLOCKED_BY_CLIENT', 'net::ERR_BLOCKED_BY_RESPONSE']);
const errorClass = error => errorNames.has(error?.name) ? error.name : 'other';
const unavailable = () => ({read: 'unavailable', revision: null});

export function patternsFor(mode, url) {
  if (!modes.includes(mode)) throw new Error('Unknown diagnostic mode');
  const stages = mode === 'baseline' ? [] : mode === 'current-request' ? ['Request']
    : mode === 'response-only' ? ['Response'] : ['Request', 'Response'];
  return stages.map(requestStage => ({urlPattern: url, requestStage}));
}

export async function continueRequest(mode, command, event) {
  if (event.responseStatusCode !== undefined || event.responseErrorReason !== undefined) return false;
  if (mode === 'current-request') return continueRequestForPostResponse(command, event);
  if (mode !== 'dual-static' || !['OPTIONS', 'POST'].includes(event.request.method)) {
    throw new Error('Unexpected diagnostic request pause');
  }
  await command('Fetch.continueRequest', {requestId: event.requestId});
  return true;
}

export function interception(mode, url, command, row) {
  const callbacks = new Set();
  let held = null, releaseAttempted = false, networkId = null;
  async function observed(method, params, stage = 'control') {
    if (row.acks.length >= 16) { row.overflow = true; throw new Error('Diagnostic command cap'); }
    const ack = {method, stage, accepted: false, errorClass: null};
    row.acks.push(ack);
    try { const value = await command(method, params); ack.accepted = true; return value; }
    catch (error) { ack.errorClass = errorClass(error); throw error; }
  }
  function handle(event) {
    const task = (async () => {
      if (event?.request?.url !== url || !['POST', 'OPTIONS'].includes(event.request.method)
        || typeof event.requestId !== 'string' || !event.requestId || event.requestId.length > 256) {
        throw new Error('Unexpected diagnostic event');
      }
      if (++row.pauseCount > 16) { row.overflow = true; throw new Error('Diagnostic event cap'); }
      const stage = event.responseErrorReason !== undefined ? 'response-error'
        : event.responseStatusCode !== undefined ? 'response' : 'request';
      row.pauses.push({method: event.request.method, stage,
        status: Number.isInteger(event.responseStatusCode) && event.responseStatusCode >= 100 && event.responseStatusCode <= 599 ? event.responseStatusCode : null,
        responseError: event.responseErrorReason !== undefined});
      if (await continueRequest(mode, (method, params) => observed(method, params, stage), event)) return;
      if (event.request.method === 'POST' && event.responseStatusCode === 200) {
        if (held) throw new Error('Duplicate diagnostic response');
        held = event.requestId; row.heldPOST200 = true; return;
      }
      if (event.responseErrorReason === undefined) await observed('Fetch.continueResponse', {requestId: event.requestId}, stage);
    })().catch(error => { row.infrastructureError = true; row.errorClass ??= errorClass(error); });
    callbacks.add(task);
    void task.finally(() => callbacks.delete(task));
    return task;
  }
  handle.observeBrowserEvent = message => {
    const p = message?.params;
    if (message?.method === 'Network.requestWillBeSent' && p?.request?.url === url && p.request.method === 'POST') {
      row.nativePOSTs = (row.nativePOSTs ?? 0) + 1;
      if (row.nativePOSTs > 16 || typeof p.requestId !== 'string' || !p.requestId || p.requestId.length > 256) {
        row.overflow = true; row.infrastructureError = true; return;
      }
      if (networkId !== null && networkId !== p.requestId) row.nativeAmbiguous = true;
      networkId = p.requestId;
    } else if (networkId !== null && p?.requestId === networkId) {
      if (message.method === 'Network.loadingFailed') {
        row.nativeErrorClass = networkErrors.has(p.errorText) ? p.errorText : 'other';
        row.nativeCanceled = typeof p.canceled === 'boolean' ? p.canceled : null;
      } else if (message.method === 'Network.responseReceived') {
        row.nativeStatus = Number.isInteger(p.response?.status) && p.response.status >= 100 && p.response.status <= 599 ? p.response.status : null;
      }
    }
  };
  return {handle, observed, held: () => held !== null,
    async release() {
      if (!held || releaseAttempted) throw new Error('Invalid diagnostic release');
      releaseAttempted = true; row.releaseAttempted = true;
      await observed('Fetch.continueResponse', {requestId: held}, 'release'); row.releaseAccepted = true;
    },
    async drain() { await Promise.all([...callbacks]); return callbacks.size === 0; },
    pending: () => callbacks.size};
}

function newRow(mode) {
  return {mode, actionPOSTs: 0, pauseCount: 0, pauses: [], acks: [], heldPOST200: false,
    nativePOSTs: 0, nativeStatus: null, nativeErrorClass: null, nativeCanceled: null, nativeAmbiguous: false,
    before: unavailable(), beforeHold: unavailable(), afterRelease: unavailable(), afterAttempt: unavailable(),
    browserBeforeRelease: null, browserAfterRelease: null, browserFinal: null,
    releaseAttempted: false, releaseAccepted: false, infrastructureError: false, errorClass: null,
    overflow: false, fetchDisabled: false, callbacksDrained: false, pageClosed: false,
    callbackPending: null, baselineValid: null, laterMutationNotRuledOut: true};
}

export async function runCase(mode, {backend, frontend, usedIds,
  open = openBrowser, request = fetch, now = () => performance.now(),
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)), key = () => randomBytes(16).toString('hex')} = {}) {
  const row = newRow(mode);
  let browser, capture, deadline, id, targetId;
  const browserOrigin = process.env.MTG_BROWSER_ORIGIN || 'http://127.0.0.1:19222';
  const remaining = () => deadline - now();
  async function readState() {
    if (remaining() <= 0) return unavailable();
    const signal = AbortSignal.timeout(Math.max(1, Math.ceil(remaining())));
    try {
      const response = await request(`${backend}/matches/${id}`, {signal});
      if (!response.ok) throw new Error('Diagnostic state response');
      const state = await response.json();
      if (remaining() <= 0) return unavailable();
      if (state?.id !== id || !Number.isSafeInteger(state.revision) || state.revision < 0
        || !Array.isArray(state.players?.['2']?.hand) || !Array.isArray(state.players?.['2']?.battlefield)) {
        throw new Error('Diagnostic state shape');
      }
      return {read: 'available', revision: state.revision,
        forestInHand: state.players['2'].hand.some(card => card.id === 'forest'),
        forestOnBattlefield: state.players['2'].battlefield.filter(card => card.id === 'forest').length};
    } catch (error) { if (signal.aborted && remaining() <= 0) return unavailable(); throw error; }
  }
  async function pageState() {
    if (remaining() <= 0) return null;
    const value = await browser.evaluate('globalThis.__MTG_CORS_PROBE__');
    if (remaining() <= 0) return null;
    if (!['pending', 'fulfilled', 'rejected'].includes(value?.state)
      || !(value.status === null || Number.isInteger(value.status) && value.status >= 100 && value.status <= 599)
      || !(value.errorClass === null || errorNames.has(value.errorClass) || value.errorClass === 'other')) {
      throw new Error('Diagnostic page shape');
    }
    return {state: value.state, status: value.status, errorClass: value.errorClass};
  }
  try {
    if (backend !== 'http://127.0.0.1:10199' || frontend !== 'http://127.0.0.1:15173'
      || browserOrigin !== 'http://127.0.0.1:19222') throw new Error('Diagnostic origin role mismatch');
    patternsFor(mode, '');
    const response = await request(`${backend}/fixture`, {method: 'POST', signal: AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error('Diagnostic fixture response');
    const fixture = await response.json();
    id = fixture?.id;
    if (typeof id !== 'string' || !id || id.length > 256 || usedIds.has(id)
      || fixture.active_player !== 2 || fixture.priority_player !== 2 || fixture.step !== 'precombat_main'
      || !fixture.players?.['2']?.hand?.some(card => card.id === 'forest')) throw new Error('Diagnostic fixture shape');
    usedIds.add(id);
    browser = await open(`${frontend}/tests/fixtures/ci-development-runtime/probe.html`);
    const url = `${backend}/matches/${id}/action`;
    capture = interception(mode, url, (...args) => browser.command(...args), row);
    browser.onIntercept(capture.handle);
    const {targetInfo} = await capture.observed('Target.getTargetInfo', {});
    if (targetInfo?.type !== 'page' || typeof targetInfo.targetId !== 'string'
      || !targetInfo.targetId || targetInfo.targetId.length > 256
      || targetInfo.url !== `${frontend}/tests/fixtures/ci-development-runtime/probe.html`) {
      throw new Error('Diagnostic page identity unavailable');
    }
    targetId = targetInfo.targetId;
    await capture.observed('Network.enable', {});
    const patterns = patternsFor(mode, url);
    if (patterns.length) await capture.observed('Fetch.enable', {patterns});
    deadline = now() + 2000;
    row.before = await readState();
    if (row.before.read !== 'available' || !row.before.forestInHand || row.before.forestOnBattlefield !== 0) throw new Error('Diagnostic initial state unavailable');
    const init = {method: 'POST', headers: {'Content-Type': 'application/json',
      'X-Match-Revision': String(row.before.revision), 'Idempotency-Key': key()},
    body: JSON.stringify({player_id: 2, action: {type: 'play_land', card_id: 'forest'}})};
    row.actionPOSTs++;
    await browser.evaluate(`(() => {
      const record = globalThis.__MTG_CORS_PROBE__ = {state:'pending',status:null,errorClass:null};
      void fetch(${JSON.stringify(url)}, {...${JSON.stringify(init)}, signal:AbortSignal.timeout(30000)})
        .then(async response => {
          record.status = response.status;
          if (!response.ok) { record.errorClass = 'HTTPError'; record.state = 'rejected'; return; }
          await response.json(); record.state = 'fulfilled';
        }).catch(error => {
          record.errorClass = ${JSON.stringify([...errorNames])}.includes(error?.name) ? error.name : 'other';
          record.state = 'rejected';
        });
      return true;
    })()`);
    let polls = 0;
    while (remaining() > 0 && polls++ < 100) {
      if (row.infrastructureError) break;
      const state = await pageState();
      if (capture.held() && !row.releaseAttempted) {
        row.browserBeforeRelease = state;
        if (state !== null && state.state !== 'pending') row.infrastructureError = true;
        row.beforeHold = await readState();
        await capture.release();
      }
      if (state?.state !== 'pending' && state !== null) { row.browserFinal = state; break; }
      if (remaining() > 0) await sleep(Math.min(20, remaining()));
    }
    if (capture.held() && !row.releaseAttempted) await capture.release();
    if (row.releaseAccepted) {
      row.browserAfterRelease = row.browserFinal ?? await pageState();
      row.afterRelease = await readState();
    } else row.afterAttempt = await readState();
    if (!row.browserFinal) row.browserFinal = await pageState();
    const final = row.releaseAccepted ? row.afterRelease : row.afterAttempt;
    row.laterMutationNotRuledOut = row.browserFinal?.state !== 'fulfilled' || final.read !== 'available';
    if (mode === 'baseline') {
      row.baselineValid = row.browserFinal?.state === 'fulfilled' && row.browserFinal.status === 200
        && final.read === 'available' && final.revision === row.before.revision + 1
        && final.forestOnBattlefield === 1 && !final.forestInHand;
      if (!row.baselineValid) row.infrastructureError = true;
    }
  } catch (error) { row.infrastructureError = true; row.errorClass ??= errorClass(error); }
  finally {
    if (browser) {
      try { await capture.observed('Fetch.disable', {}); row.fetchDisabled = true; }
      catch (error) { row.infrastructureError = true; row.errorClass ??= errorClass(error); }
      try { row.callbacksDrained = await capture.drain(); }
      catch (error) { row.infrastructureError = true; row.errorClass ??= errorClass(error); }
      try {
        await browser.close();
        if (!targetId) throw new Error('Diagnostic page identity unavailable');
        const response = await request(`${browserOrigin}/json/list`, {signal: AbortSignal.timeout(15000)});
        if (!response.ok) throw new Error('Diagnostic target closure read');
        const targets = await response.json();
        if (!Array.isArray(targets) || targets.length > 16
          || targets.some(target => typeof target?.id !== 'string' || target.id === targetId)) {
          throw new Error('Diagnostic target closure unavailable');
        }
        row.pageClosed = true;
      }
      catch (error) { row.infrastructureError = true; row.errorClass ??= errorClass(error); }
      if (capture) {
        row.callbacksDrained = await capture.drain(); row.callbackPending = capture.pending();
        if (!row.callbacksDrained || row.callbackPending) row.infrastructureError = true;
      }
    }
  }
  return row;
}

export async function diagnostic(options) {
  const rows = [], usedIds = new Set();
  for (const mode of modes) {
    const row = await runCase(mode, {...options, usedIds}); rows.push(row);
    if (row.infrastructureError) break;
  }
  return rows;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let rows = [];
  try { rows = await diagnostic({backend: process.env.MTG_BACKEND_ORIGIN, frontend: process.env.MTG_FRONTEND_ORIGIN}); }
  catch { rows.push({infrastructureError: true, errorClass: 'other', pageClosed: false, callbacksDrained: false}); }
  console.error('CORS_TRANSPORT_DIAGNOSTIC', JSON.stringify(rows));
  if (rows.length !== modes.length || rows.some(row => row.infrastructureError || !row.pageClosed || !row.callbacksDrained)) {
    throw new Error('CORS transport diagnostic failed; see typed record');
  }
}
