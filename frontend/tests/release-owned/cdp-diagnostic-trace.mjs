import {appendFileSync, mkdirSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import path from 'node:path';

let aggregateBytes = 0;

export function createCDPTrace({directory, targetId, emit}) {
  const pending = new Map(), pauses = new Map(), requests = new Map();
  const connectionId = randomUUID();
  const key = (sessionId, id) => JSON.stringify([sessionId ?? null, id]);
  let generation = 0, ordinal = 0, protocolError = false;
  if (!emit) {
    mkdirSync(directory, {recursive: true, mode: 0o700});
    emit = row => {
      const line = JSON.stringify(row) + '\n';
      aggregateBytes += Buffer.byteLength(line);
      if (aggregateBytes > 64 * 1024 * 1024) throw Error('CDP observational trace exceeds 64MiB');
      appendFileSync(path.join(directory, 'cdp.jsonl'), line, {mode: 0o600});
    };
  }
  const log = row => emit({utc: new Date().toISOString(), monotonic: process.hrtime.bigint().toString(),
    pid: process.pid, targetId, connectionId, transport: 'page-websocket', sessionId: null, generation, ...row});
  const safeURL = value => {if (value === '') return ''; const u = new URL(value); return u.origin + u.pathname;};
  return {
    sent(id, method, params, sessionId = null) {
      if (['Page.reload', 'Page.navigate'].includes(method)) generation++;
      const pause = pauses.get(key(sessionId, params.requestId));
      const consumptive = /^Fetch\.(continueRequest|continueResponse|failRequest|fulfillRequest)$/.test(method);
      const row = {kind: 'send', sessionId, id, method, requestId: params.requestId,
        errorReason: params.errorReason, pauseOrdinal: pause?.ordinal, pauseStage: pause?.stage,
        pauseGeneration: pause?.generation, consumptive};
      if (consumptive && pause) {
        row.priorConsumeCommands = [...pause.commands];
        pause.commands.push(id);
      }
      pending.set(id, row); log(row);
    },
    received(message) {
      const sessionId = message.sessionId ?? null;
      if (message.id !== undefined) {
        const command = pending.get(message.id); pending.delete(message.id);
        if (message.error) protocolError = true;
        log({kind: 'response', sessionId, id: message.id, command, acknowledged: !message.error,
          error: message.error && {code: message.error.code, message: message.error.message}});
        if (command?.method === 'Page.getFrameTree' && message.result?.frameTree) {
          const visit = tree => {
            const f = tree.frame;
            log({kind: 'frameTree', sessionId, frameId: f.id, loaderId: f.loaderId,
              parentId: f.parentId, url: safeURL(f.url)});
            for (const child of tree.childFrames ?? []) visit(child);
          };
          visit(message.result.frameTree);
        }
      } else if (message.method === 'Fetch.requestPaused') {
        const p = message.params;
        const stage = p.responseStatusCode !== undefined || p.responseErrorReason !== undefined ? 'Response' : 'Request';
        const pause = {ordinal: ++ordinal, stage, generation, commands: []}; pauses.set(key(sessionId, p.requestId), pause);
        log({kind: 'paused', sessionId, requestId: p.requestId, networkId: p.networkId, frameId: p.frameId,
          requestMetadata: requests.get(key(sessionId, p.networkId)) ?? null,
          stage, ordinal, url: safeURL(p.request.url), method: p.request.method,
          resourceType: p.resourceType, responseStatusCode: p.responseStatusCode,
          responseErrorReason: p.responseErrorReason});
      } else if (message.method === 'Network.requestWillBeSent') {
        const p = message.params;
        const request = {networkId: p.requestId, frameId: p.frameId, loaderId: p.loaderId,
          url: safeURL(p.request.url), method: p.request.method, type: p.type,
          initiatorType: p.initiator?.type, timestamp: p.timestamp, observedGeneration: generation};
        requests.set(key(sessionId, p.requestId), request);
        log({kind: 'requestWillBeSent', sessionId, ...request});
      } else if (message.method === 'Network.loadingFailed') {
        const p = message.params;
        log({kind: 'loadingFailed', sessionId, networkId: p.requestId, canceled: p.canceled,
          realCancel: p.canceled === true, errorText: p.errorText, blockedReason: p.blockedReason,
          type: p.type, timestamp: p.timestamp, requestMetadata: requests.get(key(sessionId, p.requestId)) ?? null});
      } else if (message.method === 'Network.loadingFinished') {
        const p = message.params;
        log({kind: 'loadingFinished', sessionId, networkId: p.requestId, timestamp: p.timestamp,
          encodedDataLength: p.encodedDataLength, requestMetadata: requests.get(key(sessionId, p.requestId)) ?? null});
      } else if (message.method === 'Page.frameNavigated') {
        const f = message.params.frame;
        log({kind: 'frameNavigated', sessionId, frameId: f.id, loaderId: f.loaderId,
          parentId: f.parentId, url: safeURL(f.url)});
      } else if (['Page.frameStartedLoading', 'Page.frameStoppedLoading', 'Page.frameDetached',
        'Page.lifecycleEvent', 'Page.frameRequestedNavigation', 'Page.frameScheduledNavigation',
        'Page.frameClearedScheduledNavigation', 'Page.domContentEventFired', 'Page.loadEventFired'].includes(message.method)) {
        const p = message.params;
        log({kind: 'pageLifecycle', event: message.method, sessionId, frameId: p.frameId,
          loaderId: p.loaderId, name: p.name, reason: p.reason, timestamp: p.timestamp,
          url: p.url && safeURL(p.url)});
      } else if (message.method === 'Target.attachedToTarget') {
        const p = message.params;
        log({kind: 'sessionAttached', sessionId, childSessionId: p.sessionId,
          childTargetId: p.targetInfo.targetId, targetType: p.targetInfo.type,
          waitingForDebugger: p.waitingForDebugger, url: safeURL(p.targetInfo.url)});
      } else if (['Target.detachedFromTarget', 'Inspector.detached'].includes(message.method)) {
        log({kind: 'sessionDetached', sessionId, event: message.method,
          detachedSessionId: message.params.sessionId, reason: message.params.reason});
      }
    },
    checkpoint(name) {log({kind: 'checkpoint', name, pending: [...pending.values()]});},
    hasProtocolError() {return protocolError;},
    timeout(id) {log({kind: 'timeout', id, command: pending.get(id)});},
    closed() {log({kind: 'close-requested', pending: [...pending.values()]});},
  };
}
