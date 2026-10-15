import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
const oldStart = source.indexOf("s=await setup('/fixture');let dropped=false;");
const oldEnd = source.indexOf("\n  await record('Dropped accepted HTTP response", oldStart);
function projection() {
  const start = source.indexOf('async function recoverDroppedResponse(s) {');
  const end = source.indexOf('\ntry {', start);
  if (start >= 0) return `(${source.slice(start, end)})`;
  assert.ok(oldStart >= 0 && oldEnd > oldStart);
  return `(async function recoverDroppedResponse() { let s, state; ${source.slice(oldStart, oldEnd)} return state; })`;
}
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
async function flush() { for (let i=0; i<12; i++) await Promise.resolve(); }
function protocol({ lateEvent = false, failError, wrongEvent = false, lateUi = false, lateReady = false,
  continueError, holdContinue = false, uiReadError, holdUiRead = false, logError,
  storedId = 'new-fixture', renderedId = 'new-fixture', alertText = '', pending = false,
  restoring = false } = {}) {
  const events = [], tasks = [], logs = [], state = { id: 'new-fixture', revision: 0 };
  const fail = deferred(), ui = deferred(), continuation = deferred(), uiRead = deferred();
  let intercept, enabled = false;
  let now = 0, sequence = 0; const timers = new Map();
  const timeout = new Error('Current accepted response was not dropped');
  const browser = {
    onIntercept(fn) { intercept = fn; },
    async command(method, params) {
      events.push(method);
      if (method === 'Fetch.enable') enabled = true;
      if (method === 'Fetch.disable') enabled = false;
      if (method === 'Fetch.continueResponse') {
        if (holdContinue) await continuation.promise;
        if (continueError) throw continueError;
      }
      if (method === 'Fetch.failRequest') {
        assert.equal(params.errorReason, 'Failed');
        await fail.promise;
        if (failError) throw failError;
        events.push('drop-fulfilled');
      }
    },
  };
  function deliver(extra = false) {
    state.revision = 1;
    events.push('server-commit');
    if (enabled) {
      const action = wrongEvent && !extra ? 'other-fixture' : state.id;
      const task = intercept({requestId: 'public-request', request: {method:'POST',
        url:`http://fixture.invalid/matches/${action}/action`}, responseStatusCode:200});
      tasks.push(Promise.resolve(task).catch(error => events.push('callback-error:'+error.message)));
    }
  }
  const context = {
    assert, b: browser, api:'http://fixture.invalid', origin:'http://ui.invalid',
    console:{error(...args) { if (logError) throw logError; logs.push(args); }},
    command: browser.command.bind(browser),
    evaluate: async expression => {
      events.push('diagnostic-ui');
      if (holdUiRead) await uiRead.promise;
      if (uiReadError) throw uiReadError;
      return vm.runInNewContext(expression, {
        localStorage: { getItem: key => { assert.equal(key, 'mtg.activeMatch'); return storedId; } },
        document: {
          body: { innerText: [pending && 'Match operation pending', restoring && 'Restoring saved session'].filter(Boolean).join(' ') },
          querySelector: selector => {
            if (selector === '.battlefield') return { dataset: { matchId: renderedId } };
            assert.equal(selector, '.operation-alert');
            return alertText ? { textContent: alertText } : null;
          },
        },
      });
    },
    setup: async () => state,
    click: async text => { assert.equal(text,'Play Land Forest'); events.push('click'); state.revision=1; if (!lateEvent) deliver(); },
    waitFor: async (predicate, budget) => {
      events.push('ui-wait');
      if (predicate.includes('dataset.matchId')) {
        assert.ok(predicate.includes('new-fixture'));
        assert.ok(predicate.includes('matchRevision'));
        assert.ok(predicate.includes('Match operation pending'));
        assert.ok(predicate.includes('Restoring saved session'));
        if (lateUi) await ui.promise;
        if (now >= 15000) throw timeout;
        assert.ok(budget > 0 && budget <= 15000);
        if (lateReady) now=15100; // Real driver may return a late evaluate result.
      } // OLD generic alert is already present, so its wait completes immediately.
    },
    fetch: async () => ({json:async()=>state}), shot:async()=>{},
    Date:{now:()=>now},
    setTimeout: (fn, ms) => { assert.ok(ms>0 && ms<=15000); const id=++sequence; timers.set(id,{fn,ms}); return id; },
    clearTimeout: id => {timers.delete(id);},
  };
  const fn = vm.runInNewContext(projection(), context);
  let completed=false;
  const promise = fn(state).finally(()=>{completed=true;});
  // Consume rejection during deferred probes without changing its eventual value.
  promise.catch(()=>{});
  return {events, state, promise, fail, ui, continuation, uiRead, deliver, tasks, logs,
    pause: event => intercept(event),
    completed:()=>completed, advance:ms=>{now=ms;},
    timeout:()=>{now=15000;for (const {fn,ms} of [...timers.values()]) if (ms===15000) fn();},
    diagnosticTimeout:()=>{for (const {fn,ms} of [...timers.values()]) if (ms===1000) fn();}};
}

test('old alert cannot disable before current POST200 callback', async () => {
  const p=protocol({lateEvent:true}); await flush();
  assert.ok(!p.events.includes('Fetch.disable'), 'Generic old alert prematurely disabled interception');
  assert.equal(p.completed(),false);
  p.deliver(); p.fail.resolve(); await p.promise;
  assert.ok(p.events.indexOf('Fetch.disable')>p.events.indexOf('drop-fulfilled'));
  assert.equal(p.state.revision,1);
});
test('callback entry is not drop-command fulfillment', async () => {
  const p=protocol(); await flush();
  assert.ok(p.events.includes('Fetch.failRequest'));
  assert.ok(!p.events.includes('Fetch.disable'), 'Callback entry is not accepted drop evidence');
  assert.equal(p.completed(),false); p.fail.resolve(); await p.promise;
  assert.ok(p.events.indexOf('Fetch.disable')>p.events.indexOf('drop-fulfilled'));
});
test('foreign match POST200 cannot prove this response drop', async () => {
  const p=protocol({wrongEvent:true}); await flush();
  assert.ok(p.events.includes('Fetch.continueResponse'));
  assert.ok(!p.events.includes('Fetch.failRequest'));
  p.deliver(true); p.fail.resolve(); await p.promise;
});
test('failed drop command rejects without pretending delivery or retrying', async () => {
  const error=new Error('PUBLIC drop command denied'); const p=protocol({failError:error});
  p.fail.resolve(); await assert.rejects(p.promise,e=>e===error);
  assert.equal(p.events.filter(e=>e==='click').length,1);
  assert.ok(!p.events.includes('drop-fulfilled'));
});
test('missing intercept times out within original deadline and disables finally', async () => {
  const p=protocol({lateEvent:true}); await flush(); p.timeout();
  await assert.rejects(p.promise,/response|drop|intercept/i);
  assert.ok(p.events.includes('Fetch.disable'));
  assert.equal(p.events.filter(e=>e==='click').length,1);
});
test('current reconciled UI is required after actual drop', async () => {
  const p=protocol({lateUi:true}); p.fail.resolve(); await flush();
  assert.equal(p.completed(),false); assert.ok(p.events.includes('ui-wait'));
  p.ui.resolve(); await p.promise;
  assert.ok(p.events.indexOf('ui-wait')>p.events.indexOf('drop-fulfilled'));
});
test('late-ready driver return cannot pass the shared deadline', async () => {
  const p=protocol({lateReady:true}); await flush();
  p.advance(14900); p.fail.resolve();
  await assert.rejects(p.promise,/reconciliation timed out/);
  assert.ok(p.events.includes('drop-fulfilled'));
  assert.ok(p.events.includes('Fetch.disable'));
  assert.equal(p.events.filter(e=>e==='click').length,1);
});

const privateMarker = 'PRIVATE-CONTENT-MUST-NOT-APPEAR';
function pausedResponse({ method = 'OPTIONS', status = 200, current = true, headers = [] } = {}) {
  return { requestId: privateMarker, request: { method,
    url: current ? 'http://fixture.invalid/matches/new-fixture/action' : `http://private.invalid/${privateMarker}`,
    headers: { Authorization: privateMarker }, postData: privateMarker },
    responseStatusCode: status, responseHeaders: headers, body: privateMarker };
}
function trace(p) {
  assert.equal(p.logs.length, 1);
  assert.equal(p.logs[0][0], 'DROP_RESPONSE_TRACE');
  const serialized = p.logs[0][1];
  for (const secret of [privateMarker, 'new-fixture', 'fixture.invalid', 'ui.invalid']) {
    assert.ok(!serialized.includes(secret), 'Failure diagnostics leaked non-allowlisted content');
  }
  return JSON.parse(serialized);
}

test('OPTIONS continuation acknowledgment and UI booleans survive the original missing-POST timeout', async () => {
  const p=protocol({ lateEvent:true, storedId:privateMarker, renderedId:privateMarker,
    alertText:`${privateMarker}: Failed to fetch NetworkError Load failed`, pending:true, restoring:true });
  await flush();
  await p.pause(pausedResponse({ headers:[
    {name:'aCcEsS-CoNtRoL-aLlOw-OrIgIn',value:'http://ui.invalid'},
    {name:'Set-Cookie',value:privateMarker},
  ] }));
  assert.equal(p.completed(),false);
  assert.ok(!p.events.includes('Fetch.failRequest'));
  p.timeout(); await assert.rejects(p.promise,/Current accepted response drop timed out/);
  const report=trace(p);
  assert.deepEqual(report.responses,[{method:'OPTIONS',status:200,current:true,
    allowOriginMatchesExpected:true,command:'continue',continuation:'ack',errorCode:null}]);
  assert.equal(report.postResponseObserved,false);
  assert.equal(report.dropped,false);
  assert.equal(report.uiStatus,'available');
  assert.deepEqual(report.ui,{activeMatch:false,renderedMatch:false,alert:true,pending:true,
    restoring:true,failedToFetch:true,networkError:true,loadFailed:true});
  assert.equal(p.events.filter(e=>e==='click').length,1);
  assert.ok(p.events.includes('Fetch.disable'));
});

for (const headers of [[], [{name:'Access-Control-Allow-Origin',value:privateMarker}]]) {
  test(`OPTIONS ${headers.length ? 'mismatched' : 'missing'} allow-origin is only a false boolean`, async () => {
    const p=protocol({lateEvent:true}); await flush();
    await p.pause(pausedResponse({headers})); p.timeout();
    await assert.rejects(p.promise,/drop timed out/);
    const report=trace(p);
    assert.equal(report.responses[0].allowOriginMatchesExpected,false);
    assert.deepEqual(report.ui,{activeMatch:true,renderedMatch:true,alert:false,pending:false,
      restoring:false,failedToFetch:false,networkError:false,loadFailed:false});
  });
}

test('unacknowledged continuation remains pending, not a claimed success or POST drop', async () => {
  const p=protocol({lateEvent:true,holdContinue:true}); await flush();
  const paused=p.pause(pausedResponse()); await flush(); p.timeout();
  await assert.rejects(p.promise,/drop timed out/);
  assert.equal(trace(p).responses[0].continuation,'pending');
  assert.equal(trace(p).dropped,false);
  p.continuation.resolve(); await paused;
});

test('continuation failure reports only numeric CDP code and preserves the original error', async () => {
  const error=new Error(JSON.stringify({code:-32000,message:privateMarker,data:privateMarker}));
  const p=protocol({lateEvent:true,continueError:error}); await flush();
  await p.pause(pausedResponse()); await assert.rejects(p.promise,e=>e===error);
  const response=trace(p).responses[0];
  assert.equal(response.continuation,'error'); assert.equal(response.errorCode,-32000);
  assert.ok(!p.events.includes('Fetch.failRequest'));
});

test('drop failure cannot leak arbitrary message or a string-valued code', async () => {
  const error=new Error(JSON.stringify({code:privateMarker,message:privateMarker}));
  const p=protocol({failError:error}); p.fail.resolve();
  await assert.rejects(p.promise,e=>e===error);
  const report=trace(p);
  assert.equal(report.postResponseObserved,true); assert.equal(report.dropped,false);
  assert.equal(report.responses[0].command,'drop');
  assert.equal(report.responses[0].continuation,'error');
  assert.equal(report.responses[0].errorCode,null);
});

test('diagnostic response retention is bounded without hiding a later actual POST drop', async () => {
  const p=protocol({lateEvent:true,lateReady:true}); await flush();
  await p.pause(pausedResponse({method:privateMarker,status:privateMarker,current:false}));
  for(let n=0;n<19;n++) await p.pause(pausedResponse());
  p.deliver(); p.fail.resolve();
  await assert.rejects(p.promise,/reconciliation timed out/);
  const report=trace(p);
  assert.equal(report.responses.length,16); assert.equal(report.omittedResponses,5);
  assert.equal(report.responses[0].method,'OTHER'); assert.equal(report.responses[0].status,null);
  assert.equal(report.responses[0].current,false);
  assert.equal(report.postResponseObserved,true); assert.equal(report.dropped,true);
});

test('UI diagnostic read failures cannot replace the original drop error', async () => {
  const original=new Error('original drop rejection');
  const p=protocol({failError:original,uiReadError:new Error(privateMarker)}); p.fail.resolve();
  await assert.rejects(p.promise,e=>e===original);
  assert.equal(trace(p).uiStatus,'unavailable'); assert.equal(trace(p).ui,null);
});

test('hung UI diagnostics are bounded independently of the original timeout', async () => {
  const p=protocol({lateEvent:true,holdUiRead:true}); await flush(); p.timeout(); await flush();
  assert.ok(p.events.includes('diagnostic-ui')); assert.equal(p.completed(),false);
  p.diagnosticTimeout(); await assert.rejects(p.promise,/drop timed out/);
  assert.equal(trace(p).uiStatus,'timed-out'); assert.equal(trace(p).ui,null);
  assert.ok(p.events.includes('Fetch.disable'));
  p.uiRead.resolve(); await flush();
});

test('diagnostic logger failure cannot mask the original error or skip cleanup', async () => {
  const original=new Error('original drop rejection');
  const p=protocol({failError:original,logError:new Error(privateMarker)}); p.fail.resolve();
  await assert.rejects(p.promise,e=>e===original);
  assert.ok(p.events.includes('Fetch.disable'));
});

test('successful response drop does not read diagnostic UI or emit diagnostics', async () => {
  const p=protocol(); p.fail.resolve(); await p.promise;
  assert.ok(!p.events.includes('diagnostic-ui')); assert.equal(p.logs.length,0);
});
