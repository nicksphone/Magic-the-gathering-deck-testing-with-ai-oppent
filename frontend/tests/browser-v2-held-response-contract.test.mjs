import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';
import {traceStartRecoveryResponses} from './browser-start-recovery-diagnostics.mjs';
import * as diagnostics from './browser-start-recovery-diagnostics.mjs';

const source = readFileSync(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8');
const begin = source.indexOf(' b.onIntercept(');
const end = source.indexOf("\n s=await setup('/fixture');", begin);
assert.ok(begin >= 0 && end > begin, 'Actual held-response callback must be present');
const frontend = 'http://127.0.0.1:15173';
const event = changes => ({requestId: 'PRIVATE_FETCH', networkId: 'PRIVATE_NETWORK', resourceType: 'Preflight',
  responseStatusCode: 200, request: {method: 'OPTIONS', postData: 'PRIVATE_BODY', headers: {Authorization: 'PRIVATE_KEY'}},
  responseHeaders: [{name: 'Access-Control-Allow-Origin', value: frontend}], ...changes});

function fixture(command = async () => ({})) {
  const reports = [], calls = [];
  let callback;
  const context = {ui: frontend, api:'http://api.invalid', s:{id:'PRIVATE_MATCH'}, traceStartRecoveryResponses, continueRequestForPostResponse: diagnostics.continueRequestForPostResponse,
    b: {async command(...args) { calls.push(args); return command(...args); }, onIntercept(fn) { callback = fn; }},
    console: {error(label, value) { reports.push({label, value: JSON.parse(value)}); }}};
  vm.runInNewContext(`let held, continueHeld, heldTrace, currentUrlSeen=false, otherUrlSeen=false;\n${source.slice(begin, end)}\nglobalThis.heldResponse = () => held; globalThis.resumeHeld = () => continueHeld();`, context);
  return {calls, reports, invoke: value => callback(value), held: () => context.heldResponse(), resume: () => context.resumeHeld()};
}

test('actual cost callback still holds the real POST response without auto-continuing', async () => {
  const f = fixture(), post = event({request: {method: 'POST'}});
  await f.invoke(post);
  assert.equal(f.held(), post);
  assert.deepEqual(f.calls, []);
  assert.deepEqual(f.reports, []);
});

test('actual cost callback continues successful CORS preflight exactly once', async () => {
  const f = fixture(), options = event();
  await f.invoke(options);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][0], 'Fetch.continueResponse');
  assert.deepEqual(Object.keys(f.calls[0][1]), ['requestId']);
  assert.equal(f.calls[0][1].requestId, options.requestId);
  assert.equal(f.held(), undefined);
  assert.deepEqual(f.reports, []);
});

test('actual cost callback reports failed continuation without changing its failure', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await assert.rejects(f.invoke(event()), actual => actual === error);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].label, 'V2_HELD_RESPONSE_TRACE');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
  assert.equal(JSON.stringify(f.reports).includes('PRIVATE_'), false);
});

test('actual cost callback correlates response/error pauses and retains genuine ACK order', async () => {
  let call = 0;
  const f = fixture(async () => { if (++call === 2) throw Error('{"code":-32602}'); });
  await f.invoke(event());
  await assert.rejects(f.invoke(event({responseStatusCode: undefined, responseErrorReason: 'Failed'})));
  assert.equal(f.reports.length, 1);
  const [first, second] = f.reports[0].value.responses;
  assert.equal(first.requestOrdinal, second.requestOrdinal);
  assert.equal(first.networkOrdinal, second.networkOrdinal);
  assert.equal(first.commands[0].acknowledgment, 'accepted');
  assert.equal(second.commands[0].acknowledgment, 'error');
  assert.equal(second.responseError, 'Failed');
});

test('actual held POST is continued exactly once by the later explicit release', async () => {
  const f = fixture(), post = event({resourceType: 'Fetch', request: {method: 'POST'}});
  await f.invoke(post);
  assert.deepEqual(f.calls, []);
  await f.resume();
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][0], 'Fetch.continueResponse');
  assert.equal(f.calls[0][1].requestId, post.requestId);
  assert.deepEqual(f.reports, []);
  assert.ok(source.includes("await continueHeld();await b.command('Fetch.disable');"), 'Actual program must use the observed explicit release');
});

test('actual deferred POST release failure is observed without changing its error', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await f.invoke(event({resourceType: 'Fetch', request: {method: 'POST'}}));
  await assert.rejects(f.resume(), actual => actual === error);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].label, 'V2_HELD_RESPONSE_TRACE');
  assert.equal(f.reports[0].value.responses[0].method, 'POST');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
  assert.equal(JSON.stringify(f.reports).includes('PRIVATE_'), false);
});

function requestPause(method) {
  const input = event({resourceType: 'XHR', request: {method}});
  delete input.responseStatusCode;
  return input;
}

test('actual OPTIONS XHR request bypasses response interception and never becomes a held POST', async () => {
  const f = fixture();
  await f.invoke(requestPause('OPTIONS'));
  assert.deepEqual(JSON.parse(JSON.stringify(f.calls)), [['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: false}]]);
  assert.equal(f.held(), undefined);
  assert.deepEqual(f.reports, []);
});

test('actual POST request only opts in, then its response waits for the same explicit release', async () => {
  const f = fixture(), post = event({resourceType: 'XHR', request: {method: 'POST'}});
  await f.invoke(requestPause('POST'));
  assert.deepEqual(JSON.parse(JSON.stringify(f.calls)), [['Fetch.continueRequest', {requestId: 'PRIVATE_FETCH', interceptResponse: true}]]);
  assert.equal(f.held(), undefined);
  await f.invoke(post);
  assert.equal(f.held(), post);
  assert.equal(f.calls.length, 1);
  await f.resume();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1][0], 'Fetch.continueResponse');
  assert.equal(f.calls[1][1].requestId, post.requestId);
});

test('held-response request continuation rejection is observed and never creates a held response', async () => {
  const error = new Error('{"code":-32602,"message":"PRIVATE_REASON"}');
  const f = fixture(async () => { throw error; });
  await assert.rejects(f.invoke(requestPause('POST')), actual => actual === error);
  assert.equal(f.held(), undefined);
  assert.equal(f.reports.length, 1);
  assert.equal(f.reports[0].value.responses[0].commands[0].method, 'Fetch.continueRequest');
  assert.equal(f.reports[0].value.responses[0].commands[0].errorCode, -32602);
});

test('held-response handler rejects unexpected request methods instead of treating them as preflight', async () => {
  const f = fixture();
  await assert.rejects(f.invoke(requestPause('GET')));
  assert.deepEqual(f.calls, []);
  assert.equal(f.held(), undefined);
  assert.equal(f.reports.length, 1);
});

test('actual held-response enable selects Request stage for POST response opt-in at the unchanged endpoint', async () => {
  const calls = [];
  const start = source.indexOf(" await b.command('Fetch.enable'", begin);
  const stop = source.indexOf('\n', start + 1);
  await vm.runInNewContext(`(async()=>{${source.slice(start, stop)}})()`, {b: {command: async (...args) => calls.push(args)}});
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [['Fetch.enable', {patterns: [{urlPattern: '*/matches/*/action', requestStage: 'Request'}]}]]);
});

const deferred=()=>{
  let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  return {promise,resolve,reject};
};
async function flushSequence(){for(let i=0;i<1000;i++)await Promise.resolve();}
const privateMarker='PRIVATE_HELD_DATA';
function sequence({phase='none',holdRequest=false,requestError,clickError,logError,
  holdUi=false,holdCanonical=false,holdRuntime=false,uiError,canonicalError,runtimeError,
  holdCanonicalBody=false,canonicalRevision=0,renderedRevision='0',foreignUrl=false}={}) {
  const start=source.indexOf(' let s,held,continueHeld;');
  const stop=source.lastIndexOf('\n} finally {await b.close();}');
  assert.ok(start>=0&&stop>start);
  const logs=[],calls=[],loopDelays=[],canonicalReads=[],runtimeReads=[],uiReads=[],callbacks=[],logAttempts=[];
  const requestAck=deferred(),uiRead=deferred(),canonicalRead=deferred(),runtimeRead=deferred();
  const timers=new Map();let timerSequence=0,intercept,primary,completed=false;
  const state={id:privateMarker,revision:0};
  const capturedAssert=Object.create(assert);
  capturedAssert.ok=(...args)=>{try{return assert.ok(...args);}catch(error){primary=error;throw error;}};
  const browser={
    onIntercept(fn){intercept=fn;},
    async command(method,params){
      calls.push([method,params]);
      if(method==='Fetch.continueRequest'&&holdRequest)await requestAck.promise;
      if(method==='Fetch.continueRequest'&&requestError)throw requestError;
    },
    async click(prefix){
      assert.equal(prefix,'Play Land Forest');calls.push(['click']);
      if(clickError)throw clickError;
      if(phase!=='none'){
        const method=phase==='OPTIONS'?'OPTIONS':'POST';
        const url=foreignUrl?`http://private.invalid/${privateMarker}/action`:`http://api.invalid/matches/${privateMarker}/action`;
        const request=event({request:{method,url,postData:privateMarker,headers:{Authorization:privateMarker}},resourceType:'XHR',responseStatusCode:undefined});
        const paused=intercept(request);paused.catch(()=>{});callbacks.push(paused);
        if(phase==='response'){
          await paused;
          const response=intercept({...request,responseStatusCode:200});response.catch(()=>{});callbacks.push(response);await response;
        }
      }
    },
    async waitFor(predicate){
      assert.ok(predicate==="document.body.innerText.includes('Match operation pending')"||predicate==="!document.body.innerText.includes('Match operation pending')");
      calls.push(['waitFor',predicate]);
    },
    async evaluate(expression){
      if(expression==="[...document.querySelectorAll('#table fieldset,#match-controls fieldset')].every(e=>e.disabled)")return true;
      uiReads.push(expression);
      if(holdUi)await uiRead.promise;if(uiError)throw uiError;
      return vm.runInNewContext(expression,{
        localStorage:{getItem:key=>{assert.equal(key,'mtg.activeMatch');return privateMarker;}},
        document:{body:{innerText:'Match operation pending'},
          querySelector:selector=>{
            if(selector==='.battlefield')return{dataset:{matchId:privateMarker,matchRevision:renderedRevision}};
            assert.equal(selector,'.operation-alert');return{textContent:privateMarker};
          },
          querySelectorAll:selector=>{
            if(selector==='#table fieldset,#match-controls fieldset')return[{disabled:true}];
            assert.equal(selector,'button');return[{textContent:'Play Land Forest',matches:()=>true}];
          }},
      });
    },
    async browserIdentity(signal){
      runtimeReads.push(signal);if(holdRuntime)await runtimeRead.promise;if(runtimeError)throw runtimeError;
      return{product:'Chrome/155.0.8059.79',protocolVersion:'1.3',webSocketDebuggerUrl:privateMarker};
    },
  };
  const context={b:browser,api:'http://api.invalid',ui:frontend,assert:capturedAssert,AbortController,
    setup:async path=>{assert.equal(path,'/fixture');return state;},
    traceStartRecoveryResponses,continueRequestForPostResponse:diagnostics.continueRequestForPostResponse,
    waitForApiState:async(url,predicate)=>{
      assert.equal(url,`http://api.invalid/matches/${privateMarker}`);
      const final={revision:1,players:{'2':{battlefield:[{id:'forest'}]}}};assert.ok(predicate(final));return final;
    },
    fetch:async(url,options)=>{
      assert.equal(url,`http://api.invalid/matches/${privateMarker}`);assert.equal(options.method,'GET');
      canonicalReads.push(options);if(holdCanonical)await canonicalRead.promise;if(canonicalError)throw canonicalError;
      return{ok:true,json:async()=>{
        if(holdCanonicalBody)await canonicalRead.promise;
        return{revision:canonicalRevision,id:privateMarker,body:privateMarker};
      }};
    },
    setTimeout:(fn,ms)=>{
      if(ms===20){loopDelays.push(ms);queueMicrotask(fn);return ++timerSequence;}
      assert.equal(ms,1000,'Only the separate original diagnostic bound may be added');
      const id=++timerSequence;timers.set(id,fn);return id;
    },
    clearTimeout:id=>timers.delete(id),
    console:{log(){},error(label,value){logAttempts.push(label);if(logError)throw logError;logs.push({label,value:JSON.parse(value)});}},
  };
  const promise=vm.runInNewContext(`(async()=>{${source.slice(start,stop)}})()`,context).finally(()=>{completed=true;});
  promise.catch(()=>{});
  return{promise,logs,calls,loopDelays,canonicalReads,runtimeReads,uiReads,callbacks,logAttempts,
    requestAck,uiRead,canonicalRead,runtimeRead,primary:()=>primary,completed:()=>completed,
    diagnosticTimeout:()=>{for(const fn of [...timers.values()])fn();}};
}
function failureContext(p){
  assert.deepEqual(p.logs.map(row=>row.label),['V2_HELD_RESPONSE_TRACE','V2_HELD_FAILURE_CONTEXT']);
  const text=JSON.stringify(p.logs);
  for(const secret of [privateMarker,'PRIVATE_','api.invalid','private.invalid',frontend])assert.equal(text.includes(secret),false);
  return p.logs[1].value;
}

for(const phase of ['none','OPTIONS','POST','pending']) {
  test(`actual outer held assertion publishes ${phase} history and bounded read-only context`,async()=>{
    const p=sequence({phase:phase==='pending'?'POST':phase,holdRequest:phase==='pending',canonicalRevision:phase==='POST'?1:0});
    await flushSequence();await assert.rejects(p.promise,error=>error===p.primary()&&error.code==='ERR_ASSERTION');
    assert.deepEqual(p.loopDelays,Array(100).fill(20));
    const context=failureContext(p),history=p.logs[0].value;
    assert.equal(context.cause,'unknown');assert.equal(context.held,false);
    assert.equal(context.currentUrlSeen,phase!=='none');assert.equal(context.otherUrlSeen,false);
    assert.equal(history.responses.length,phase==='none'?0:1);
    assert.equal(history.pendingCommands,phase==='pending'?1:0);
    if(phase!=='none'){
      assert.equal(history.responses[0].method,phase==='OPTIONS'?'OPTIONS':'POST');
      assert.equal(history.responses[0].status,null);
      assert.equal(history.responses[0].commands[0].method,'Fetch.continueRequest');
      assert.equal(history.responses[0].commands[0].acknowledgment,phase==='pending'?'pending':'accepted');
    }
    assert.equal(context.ui.status,'available');assert.equal(context.ui.pending,true);
    assert.equal(context.ui.controlsDisabled,true);assert.equal(context.ui.renderedRevision,0);
    assert.deepEqual(context.canonical,{status:'available',revision:phase==='POST'?1:0});
    assert.deepEqual(context.runtime,{status:'available',product:'Chrome/155.0.8059.79',protocolVersion:'1.3'});
    assert.equal(p.canonicalReads.length,1);assert.equal(p.runtimeReads.length,1);assert.equal(p.uiReads.length,1);
    assert.equal(p.canonicalReads[0].signal,p.runtimeReads[0]);assert.equal(p.canonicalReads[0].signal.aborted,true);
    assert.equal(p.calls.filter(([method])=>method==='click').length,1);
    assert.ok(!p.calls.some(([method])=>method==='Fetch.continueResponse'||method==='Fetch.disable'));
    if(phase==='pending'){p.requestAck.resolve();await Promise.all(p.callbacks);}
  });
}

test('actual positive held sequence retains explicit release/disable and adds no diagnostics',async()=>{
  const p=sequence({phase:'response'});await p.promise;
  assert.deepEqual(p.logs,[]);assert.deepEqual(p.canonicalReads,[]);assert.deepEqual(p.runtimeReads,[]);assert.deepEqual(p.uiReads,[]);
  assert.deepEqual(p.loopDelays,[]);
  assert.deepEqual(p.calls.filter(([method])=>method.startsWith('Fetch.')).map(([method])=>method),
    ['Fetch.enable','Fetch.continueRequest','Fetch.continueResponse','Fetch.disable']);
});

for(const outcome of ['accepted','rejected']) {
  test(`outer failure pending snapshot remains frozen after late ${outcome} ACK`,async()=>{
    const p=sequence({phase:'POST',holdRequest:true});await flushSequence();
    await assert.rejects(p.promise,error=>error===p.primary());
    failureContext(p);const snapshot=JSON.stringify(p.logs);
    assert.equal(p.logs[0].value.pendingCommands,1);
    if(outcome==='accepted'){p.requestAck.resolve();await Promise.all(p.callbacks);}
    else{
      const error=new Error('{"code":-32602,"message":"PRIVATE_LATE"}');p.requestAck.reject(error);
      await assert.rejects(p.callbacks[0],actual=>actual===error);
    }
    assert.equal(JSON.stringify(p.logs),snapshot);assert.equal(p.logs.length,2);
  });
}

test('all three hung failure reads share one 1000ms budget and never wait for a pending native ACK',async()=>{
  const p=sequence({phase:'POST',holdRequest:true,holdUi:true,holdCanonical:true,holdRuntime:true});
  await flushSequence();
  assert.equal(p.logs.length,1,'History must publish immediately before diagnostic reads settle');
  assert.equal(p.completed(),false);
  assert.equal(p.uiReads.length,1);assert.equal(p.canonicalReads.length,1);assert.equal(p.runtimeReads.length,1);
  const signal=p.canonicalReads[0].signal;assert.equal(signal,p.runtimeReads[0]);assert.equal(signal.aborted,false);
  p.diagnosticTimeout();await assert.rejects(p.promise,error=>error===p.primary());
  const context=failureContext(p);
  assert.equal(context.ui.status,'timed-out');assert.equal(context.canonical.status,'timed-out');assert.equal(context.runtime.status,'timed-out');
  assert.equal(signal.aborted,true);assert.deepEqual(p.loopDelays,Array(100).fill(20));
  const snapshot=JSON.stringify(p.logs);
  p.uiRead.resolve();p.canonicalRead.resolve();p.runtimeRead.resolve();p.requestAck.resolve();
  await Promise.all(p.callbacks);await flushSequence();assert.equal(JSON.stringify(p.logs),snapshot);
});

test('completed canonical/runtime evidence survives a hung UI read within the same diagnostic budget',async()=>{
  const p=sequence({holdUi:true,canonicalRevision:1});await flushSequence();p.diagnosticTimeout();
  await assert.rejects(p.promise,error=>error===p.primary());
  const context=failureContext(p);
  assert.equal(context.ui.status,'timed-out');assert.deepEqual(context.canonical,{status:'available',revision:1});
  assert.equal(context.runtime.status,'available');p.uiRead.resolve();await flushSequence();
});

test('read failures and reporter failures cannot replace the primary native exception or retry',async()=>{
  const primary=new Error('{"code":-32602,"message":"PRIVATE_PRIMARY"}');
  const observer=new Error('PRIVATE_OBSERVER');
  const p=sequence({clickError:primary,logError:observer,uiError:observer,canonicalError:observer,runtimeError:observer});
  await assert.rejects(p.promise,error=>error===primary);
  assert.deepEqual(p.logAttempts,['V2_HELD_RESPONSE_TRACE','V2_HELD_FAILURE_CONTEXT']);
  assert.equal(p.uiReads.length,1);assert.equal(p.canonicalReads.length,1);assert.equal(p.runtimeReads.length,1);
  assert.equal(p.calls.filter(([method])=>method==='click').length,1);
});

test('unavailable failure reads preserve the original assertion and fixed availability statuses',async()=>{
  const error=new Error('PRIVATE_READ');const p=sequence({uiError:error,canonicalError:error,runtimeError:error});
  await flushSequence();await assert.rejects(p.promise,actual=>actual===p.primary());
  const context=failureContext(p);
  assert.equal(context.ui.status,'unavailable');assert.deepEqual(context.canonical,{status:'unavailable',revision:null});
  assert.deepEqual(context.runtime,{status:'unavailable',product:null,protocolVersion:null});
});

test('wildcard capture reports only current/other URL booleans and rejects private revision text',async()=>{
  const p=sequence({phase:'POST',foreignUrl:true,canonicalRevision:privateMarker,renderedRevision:privateMarker});
  await flushSequence();await assert.rejects(p.promise,actual=>actual===p.primary());
  const context=failureContext(p);
  assert.equal(context.currentUrlSeen,false);assert.equal(context.otherUrlSeen,true);
  assert.equal(context.ui.renderedRevision,null);assert.deepEqual(context.canonical,{status:'unavailable',revision:null});
});

test('actual callback rejection followed by the outer assertion publishes history only once',async()=>{
  const native=new Error('{"code":-32602,"message":"PRIVATE_NATIVE"}');
  const p=sequence({phase:'POST',requestError:native});await flushSequence();
  await assert.rejects(p.callbacks[0],error=>error===native);
  await assert.rejects(p.promise,error=>error===p.primary());
  failureContext(p);
  assert.equal(p.logs[0].value.pendingCommands,0);
  assert.equal(p.logs[0].value.responses[0].commands[0].errorCode,-32602);
  assert.equal(p.logs[0].value.responses[0].commands[0].acknowledgment,'error');
});

test('a canonical response body that never settles is bounded without losing completed UI/runtime reads',async()=>{
  const p=sequence({holdCanonicalBody:true});await flushSequence();
  assert.equal(p.completed(),false);assert.equal(p.canonicalReads.length,1);
  p.diagnosticTimeout();await assert.rejects(p.promise,error=>error===p.primary());
  const context=failureContext(p);
  assert.equal(context.ui.status,'available');assert.equal(context.runtime.status,'available');
  assert.deepEqual(context.canonical,{status:'timed-out',revision:null});
  assert.equal(p.canonicalReads[0].signal.aborted,true);
  p.canonicalRead.resolve();await flushSequence();assert.equal(p.logs.length,2);
});
