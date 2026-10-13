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
function protocol({ lateEvent = false, failError, wrongEvent = false, lateUi = false, lateReady = false } = {}) {
  const events = [], tasks = [], state = { id: 'new-fixture', revision: 0 };
  const fail = deferred(), ui = deferred(); let intercept, enabled = false;
  let now = 0, timer; const timeout = new Error('Current accepted response was not dropped');
  const browser = {
    onIntercept(fn) { intercept = fn; },
    async command(method, params) {
      events.push(method);
      if (method === 'Fetch.enable') enabled = true;
      if (method === 'Fetch.disable') enabled = false;
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
    assert, b: browser, api:'http://fixture.invalid', console:{error(){}},
    command: browser.command.bind(browser),
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
    setTimeout: (fn, ms) => { assert.ok(ms>0 && ms<=15000); timer=fn; return 1; },
    clearTimeout: () => {timer=null;},
  };
  const fn = vm.runInNewContext(projection(), context);
  let completed=false;
  const promise = fn(state).finally(()=>{completed=true;});
  // Consume rejection during deferred probes without changing its eventual value.
  promise.catch(()=>{});
  return {events, state, promise, fail, ui, deliver, tasks,
    completed:()=>completed, advance:ms=>{now=ms;}, timeout:()=>{now=15000;timer?.();}};
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
