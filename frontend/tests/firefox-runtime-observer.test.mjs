// Supplied wire replies/events only: this suite does not qualify a native browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createEnrollment,createFirefoxTransport} from './firefox-transport.mjs';
import {safeWireRow} from './firefox-wire-trace.mjs';
import {traceStartRecoveryResponses} from './browser-start-recovery-diagnostics.mjs';

const frontend='http://127.0.0.1:15173',backend='http://127.0.0.1:19000';
const realmEvents=['script.realmCreated','script.realmDestroyed'];
const secret='PRIVATE_REALM_ORIGIN_SANDBOX_BODY';
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve();};
function fixture(t){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'runtime-observer-'));fs.chmodSync(directory,0o700);
 const controller=createEnrollment({directory,runNonce:'0'.repeat(32),sourceBinding:'a'.repeat(64),apiOrigin:backend,frontendOrigin:frontend});
 const sent=[],held=[],hold=new Set(),errors=new Map(),replies=new Map(),waiting=new Map(),events=new Map(),live=new Set(),retired=[];
 let wire,serial=0,sequence=0;
 function reply(m,override){
  const result=override??replies.get(m.method)??(
   m.method==='session.new'?{capabilities:{browserName:'firefox',browserVersion:'158.0'}}:
   m.method==='session.subscribe'?{subscription:'subscription-'+(++serial)}:
   m.method==='browsingContext.create'?{context:'top-'+(++serial)}:
   m.method==='browsingContext.navigate'?{navigation:'navigation',url:m.params.url}:{});
  let error=errors.get(m.method);
  if(!error&&m.method==='session.subscribe'&&typeof result.subscription==='string'&&result.subscription)live.add(result.subscription);
  if(!error&&m.method==='session.unsubscribe'){
   for(const id of m.params.subscriptions)if(!live.has(id))error='invalid argument';
   if(!error)for(const id of m.params.subscriptions){live.delete(id);retired.push(id);}
  }
  wire.onmessage({data:JSON.stringify(error?{type:'error',id:m.id,error}:{type:'success',id:m.id,result})});
 }
 const transport=createFirefoxTransport({controller,directory,endpoint:'ws://127.0.0.1:19384/session',producer:()=>{throw Error('Body cache not enrolled');},socketFactory:()=>wire={readyState:1,send(text){const m=JSON.parse(text);sent.push(m);if(hold.has(m.method))held.push(m);else queueMicrotask(()=>reply(m));},close(){this.readyState=3;}}});
 const f={sent,held,hold,errors,replies,events,live,retired,transport,reply,expectFatal:false,
  calls:method=>sent.filter(m=>m.method===method),
  async open(){const p=await transport.open('about:blank');events.set(p.id,[]);f.listen(p);return p;},
  listen(p,observer){p.socket.onmessage=({data})=>{const m=JSON.parse(data);if(!m.id){events.get(p.id).push(m);observer?.(m);return;}const w=waiting.get(m.id);assert.ok(w,'Actual caller command ID must be retained');waiting.delete(m.id);m.error?w.reject(Error(m.error.message)):w.resolve(m.result);};},
  command(p,method='Runtime.enable',params={}){const operation=new Promise((resolve,reject)=>{const id=++sequence;waiting.set(id,{resolve,reject});p.socket.send(JSON.stringify({id,method,params}));});operation.catch(()=>{});return operation;},
  emit(method,params){wire.onmessage({data:JSON.stringify({type:'event',method,params})});},
  created(p,realm='realm',extra={}){f.emit('script.realmCreated',{realm,type:'window',context:p.id,origin:frontend,...extra});},
  release(method,override){const i=held.findIndex(m=>m.method===method);assert.notEqual(i,-1,'Expected held '+method);const m=held.splice(i,1)[0];hold.delete(method);reply(m,override);return m;},
  raw(message){wire.onmessage({data:JSON.stringify(message)});}
 };
 t.after(async()=>{
  hold.clear();errors.clear();for(const m of held.splice(0))reply(m);await flush();
  try{if(f.expectFatal)await assert.rejects(transport.close(),AggregateError);else await transport.close();}
  finally{controller.close();fs.rmSync(directory,{recursive:true,force:true});}
 });
 return f;
}
function diagnostics(){
 const reports=[];
 const trace=traceStartRecoveryResponses(async()=>{},async()=>{},frontend,r=>reports.push(r),{backend});
 return {trace,reports,report(){trace.reportFailure();return reports[0];}};
}
function projected(method,realm='private-realm',context='private-context',top=context){
 return {protocol:'webdriver-bidi',type:'event',method,params:{realm,...(method==='script.realmCreated'?{type:'window',context}:{})},correlation:{context,top,realmType:'window'}};
}

test('Runtime enable waits for matching native ACK and returns the actual subscription result',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');let done=false;
 const enabled=f.command(p).then(result=>{done=true;return result;});enabled.catch(()=>{});await flush();
 assert.equal(f.held.length,1);assert.equal(done,false);
 assert.deepEqual(f.held[0].params,{events:realmEvents,contexts:[p.id]});
 f.release('session.subscribe',{subscription:'runtime-ack'});assert.deepEqual(await enabled,{subscription:'runtime-ack'});
});

test('unknown Runtime options reject before any subscription is sent',async t=>{
 const f=fixture(t),p=await f.open(),before=f.calls('session.subscribe').length;
 for(const params of [{extra:true},{maxCallStackSizeToCapture:5},null,[]])await assert.rejects(f.command(p,'Runtime.enable',params));
 assert.equal(f.calls('session.subscribe').length,before);
});

test('native subscription rejection reaches the caller without an invented cleanup identifier',async t=>{
 const f=fixture(t),p=await f.open();f.errors.set('session.subscribe','unsupported operation');
 await assert.rejects(f.command(p),/^Error: unsupported operation$/);f.errors.clear();await p.close();
 assert.equal(f.calls('session.unsubscribe').length,0);assert.equal(f.calls('browsingContext.close').length,1);
});

test('malformed subscription ACKs cannot establish Runtime readiness or owned cleanup',async t=>{
 const f=fixture(t);
 for(const result of [{},{subscription:''},{subscription:1},{subscription:'x'.repeat(257)}]){
  const p=await f.open();f.replies.set('session.subscribe',result);await assert.rejects(f.command(p));
  f.replies.delete('session.subscribe');await p.close();
 }
 assert.equal(f.calls('session.unsubscribe').length,0);
});

test('an unrelated native reply cannot complete Runtime enable',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');let done=false;
 const enabled=f.command(p).then(result=>{done=true;return result;});enabled.catch(()=>{});await flush();assert.equal(f.held.length,1);
 f.raw({type:'success',id:f.held[0].id+1000,result:{subscription:'wrong-id'}});await flush();assert.equal(done,false);
 f.release('session.subscribe',{subscription:'matching-id'});assert.deepEqual(await enabled,{subscription:'matching-id'});
});

test('a timed-out subscription cannot be revived by its late ACK',async t=>{
 const f=fixture(t),p=await f.open();t.mock.timers.enable({apis:['setTimeout']});f.hold.add('session.subscribe');
 const enabled=f.command(p);await flush();assert.equal(f.held.length,1);t.mock.timers.tick(15001);
 await assert.rejects(enabled,/Firefox command timed out: session.subscribe/);
 f.release('session.subscribe',{subscription:'too-late'});f.created(p);await flush();assert.deepEqual(f.events.get(p.id),[]);
 await assert.rejects(f.command(p),/Firefox command timed out: session.subscribe/);await p.close();assert.equal(f.calls('session.unsubscribe').length,0);
});

test('concurrent and repeated enable share the one acknowledged native subscription',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');
 const one=f.command(p),two=f.command(p);await flush();assert.equal(f.held.length,1);
 f.release('session.subscribe',{subscription:'shared'});assert.deepEqual(await one,await two);assert.deepEqual(await f.command(p),{subscription:'shared'});
 assert.equal(f.calls('session.subscribe').filter(m=>m.params.events.includes('script.realmCreated')).length,1);
});

test('native realm replay before ACK is registered but not published as ready',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');const enabled=f.command(p);await flush();assert.equal(f.held.length,1);
 f.created(p,'early',{origin:secret,sandbox:secret});await flush();assert.deepEqual(f.events.get(p.id),[]);
 f.release('session.subscribe');queueMicrotask(()=>f.created(p,'after-ack'));await enabled;await flush();
 assert.deepEqual(f.events.get(p.id),[projected('script.realmCreated','early',p.id),projected('script.realmCreated','after-ack',p.id)]);
 assert.equal(JSON.stringify(f.events.get(p.id)).includes(secret),false);
});

test('pre-ACK create and destroy retain genuine event order and the original context association',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');const enabled=f.command(p);await flush();assert.equal(f.held.length,1);
 f.created(p,'short-lived');f.emit('script.realmDestroyed',{realm:'short-lived'});await flush();f.release('session.subscribe');await enabled;
 assert.deepEqual(f.events.get(p.id),[projected('script.realmCreated','short-lived',p.id),projected('script.realmDestroyed','short-lived',p.id)]);
});

test('realm events and native subscription cleanup remain isolated between two owned pages',async t=>{
 const f=fixture(t),one=await f.open(),two=await f.open();const a=await f.command(one),b=await f.command(two);
 f.created(one,'one');f.created(two,'two');f.emit('script.realmDestroyed',{realm:'two'});await flush();
 assert.deepEqual(f.events.get(one.id).map(e=>e.params.realm),['one']);assert.deepEqual(f.events.get(two.id).map(e=>e.params.realm),['two','two']);
 await one.close();assert.deepEqual(f.retired,[a.subscription]);assert.equal(f.live.has(b.subscription),true);
});

test('only genuinely owned child contexts receive window realm correlation',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.emit('browsingContext.contextCreated',{context:'child',parent:p.id});
 f.created(p,'child-realm',{context:'child'});f.created(p,'foreign-realm',{context:'foreign'});await flush();
 assert.deepEqual(f.events.get(p.id),[projected('script.realmCreated','child-realm','child',p.id)]);
});

test('context destruction before realm destruction does not lose its actual saved identity',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.emit('browsingContext.contextCreated',{context:'child',parent:p.id});f.created(p,'child-realm',{context:'child'});await flush();
 f.emit('browsingContext.contextDestroyed',{context:'child'});f.emit('script.realmDestroyed',{realm:'child-realm'});await flush();
 assert.deepEqual(f.events.get(p.id).at(-1),projected('script.realmDestroyed','child-realm','child',p.id));
});

test('unknown realms and worker realms never become invented page or CDP context events',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.created(p,'window');await flush();const before=f.events.get(p.id).length;
 f.emit('script.realmCreated',{realm:'worker',type:'dedicated-worker',owners:['window'],origin:secret});
 f.emit('script.realmCreated',{realm:'future',type:secret,context:p.id,origin:secret});
 f.emit('script.realmDestroyed',{realm:'worker'});f.emit('script.realmDestroyed',{realm:'unknown'});await flush();
 assert.equal(f.events.get(p.id).length,before);assert.equal(f.events.get(p.id).some(e=>e.method.startsWith('Runtime.')),false);
});

test('a late diagnostic hook sees real later destruction with saved correlation, not fabricated replay',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.created(p,'before-hook');await flush();
 const d=diagnostics();f.listen(p,message=>d.trace.observeBrowserEvent(message));assert.deepEqual(d.report().browserMetadata.events,[]);
 const later=diagnostics();f.listen(p,message=>later.trace.observeBrowserEvent(message));f.emit('script.realmDestroyed',{realm:'before-hook'});await flush();
 const rows=later.report().browserMetadata.events;assert.equal(rows.length,1);assert.equal(rows[0].event,'bidi-realm-destroyed');assert.equal(rows[0].topLevel,true);
});

test('live realm registry is bounded and does not silently evict routing identity',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.expectFatal=true;
 for(let i=0;i<65;i++)f.created(p,'realm-'+i);await flush();assert.throws(()=>p.socket.assertHealthy(),/realm observer limit/);
 assert.equal(f.events.get(p.id).length,64);
});

test('pre-ACK replay buffering is bounded even when create and destroy leave no live realms',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');const enabled=f.command(p);await flush();assert.equal(f.held.length,1);f.expectFatal=true;
 for(let i=0;i<33;i++){f.created(p,'realm-'+i);f.emit('script.realmDestroyed',{realm:'realm-'+i});}
 await assert.rejects(enabled,/realm observer limit/);assert.deepEqual(f.events.get(p.id),[]);
});

test('contradictory owned realm identity fails closed instead of reassigning a realm',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p);f.created(p,'same');await flush();f.emit('browsingContext.contextCreated',{context:'child',parent:p.id});f.expectFatal=true;
 f.created(p,'same',{context:'child'});await flush();assert.throws(()=>p.socket.assertHealthy(),/Invalid owned Firefox realm event/);
});

test('page close cannot outrun pending Runtime subscription registration',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('session.subscribe');const enabled=f.command(p);await flush();assert.equal(f.held.length,1);
 await assert.rejects(p.close(),/configuration pending/);assert.equal(f.calls('browsingContext.close').length,0);
 f.release('session.subscribe');const result=await enabled;await p.close();assert.deepEqual(f.retired,[result.subscription]);
});

test('successful Runtime unsubscribe stays retired after later context-close failure',async t=>{
 const f=fixture(t),p=await f.open(),result=await f.command(p);f.errors.set('browsingContext.close','unsupported operation');
 await assert.rejects(p.close(),/^Error: unsupported operation$/);assert.deepEqual(f.retired,[result.subscription]);assert.equal(f.calls('session.unsubscribe').length,1);
 f.errors.clear();await p.close();assert.equal(f.calls('session.unsubscribe').length,1);assert.equal(f.calls('browsingContext.close').length,2);
});

test('negative Runtime unsubscribe retains ownership for explicit caller cleanup',async t=>{
 const f=fixture(t),p=await f.open(),result=await f.command(p);f.errors.set('session.unsubscribe','invalid argument');
 await assert.rejects(p.close(),/^Error: invalid argument$/);assert.equal(f.live.has(result.subscription),true);assert.equal(f.calls('browsingContext.close').length,0);
 f.errors.clear();await p.close();assert.deepEqual(f.retired,[result.subscription]);assert.equal(f.calls('session.unsubscribe').length,2);
});

test('Runtime subscription is not retired while its genuine unsubscribe ACK is held',async t=>{
 const f=fixture(t),p=await f.open(),result=await f.command(p);f.hold.add('session.unsubscribe');let done=false;
 const closing=p.close().then(()=>{done=true;});closing.catch(()=>{});await flush();assert.equal(f.held.length,1);assert.equal(done,false);assert.equal(f.live.has(result.subscription),true);
 f.release('session.unsubscribe');await closing;assert.deepEqual(f.retired,[result.subscription]);
});

test('wire trace names genuine realm events but never includes their native payload',()=>{
 for(const method of realmEvents){const row=safeWireRow({kind:'native-event',method,params:{realm:secret,origin:secret},realm:secret});assert.deepEqual(row,{kind:'native-event',method});}
});

test('branded native lifecycle diagnostics use separate context and realm ordinals',()=>{
 const d=diagnostics();d.trace.observeBrowserEvent(projected('script.realmCreated','first','child','top'));
 d.trace.observeBrowserEvent(projected('script.realmDestroyed','first','child','top'));d.trace.observeBrowserEvent(projected('script.realmCreated','second','child','top'));
 const rows=d.report().browserMetadata.events;assert.equal(rows.length,3);assert.equal(rows[0].event,'bidi-realm-created');assert.equal(rows[0].protocol,'webdriver-bidi');
 assert.equal(rows[0].realmOrdinal,rows[1].realmOrdinal);assert.notEqual(rows[0].realmOrdinal,rows[2].realmOrdinal);assert.equal(rows[0].contextOrdinal,rows[2].contextOrdinal);assert.equal(rows[0].topLevel,false);
 assert.equal(rows.some(e=>e.event==='contexts-cleared'),false);
});

test('unbranded, unknown and worker diagnostics cannot masquerade as owned window realms',()=>{
 const d=diagnostics(),unbranded=projected('script.realmCreated');delete unbranded.protocol;d.trace.observeBrowserEvent(unbranded);
 d.trace.observeBrowserEvent({protocol:'webdriver-bidi',type:'event',method:'script.realmCreated',params:{realm:secret,type:'dedicated-worker',owners:[secret]}});
 d.trace.observeBrowserEvent({protocol:'webdriver-bidi',type:'event',method:'script.realmDestroyed',params:{realm:secret}});
 const report=d.report();assert.deepEqual(report.browserMetadata.events,[]);assert.ok(report.browserMetadata.invalidEvents>0);
});

test('native diagnostic metadata excludes IDs, origins, sandbox names and arbitrary extra fields',()=>{
 const d=diagnostics(),event=projected('script.realmCreated',secret,secret,secret);event.params.origin=secret;event.params.sandbox=secret;event.params.extra={body:secret};
 d.trace.observeBrowserEvent(event);const report=d.report();assert.equal(report.browserMetadata.events.length,1);assert.equal(JSON.stringify(report).includes(secret),false);
});

test('native metadata shares existing event bounds and preserves immutable once-only failure snapshots',()=>{
 const d=diagnostics();for(let i=0;i<1000;i++)d.trace.observeBrowserEvent(projected('script.realmCreated','realm-'+i,'context-'+i,'top'));
 const report=d.report(),before=JSON.stringify(report);assert.equal(report.browserMetadata.events.length,64);assert.ok(report.browserMetadata.omittedEvents>0);assert.ok(report.browserMetadata.correlationOverflow>0);
 d.trace.observeBrowserEvent(projected('script.realmDestroyed'));d.trace.reportFailure();assert.equal(d.reports.length,1);assert.equal(JSON.stringify(report),before);assert.ok(before.length<24000);
});

test('a throwing observation hook cannot replace native enable result or a later native rejection',async t=>{
 const f=fixture(t),p=await f.open();f.listen(p,()=>{throw Error(secret);});f.hold.add('session.subscribe');const enabled=f.command(p);await flush();assert.equal(f.held.length,1);
 f.created(p);f.release('session.subscribe',{subscription:'real'});assert.deepEqual(await enabled,{subscription:'real'});assert.equal(f.transport.observerFailed,true);
 f.errors.set('session.unsubscribe','invalid argument');await assert.rejects(p.close(),/^Error: invalid argument$/);
});

test('adding native observations preserves command arguments, results and primary exception identity',async()=>{
 const original={original:true},primary=new Error('primary'),calls=[],reports=[];
 const trace=traceStartRecoveryResponses(async(...args)=>{calls.push(args);return original;},async(e,command)=>{assert.equal(await command('Fetch.continueResponse',{requestId:e.requestId}),original);throw primary;},frontend,value=>reports.push(value),{backend});
 trace.observeBrowserEvent(projected('script.realmCreated'));
 await assert.rejects(trace({requestId:'owned',request:{method:'POST'}}),error=>error===primary);
 assert.deepEqual(calls,[['Fetch.continueResponse',{requestId:'owned'}]]);assert.equal(reports.length,1);assert.equal(reports[0].browserMetadata.events[0].event,'bidi-realm-created');
});

test('actual unchanged driver receiver passes branded native observations without consuming command replies',()=>{
 const source=fs.readFileSync(new URL('./browser-driver.mjs',import.meta.url),'utf8'),begin=source.indexOf('  socket.onmessage ='),end=source.indexOf('\n  function rawCommand',begin);
 assert.ok(begin>=0&&end>begin);const d=diagnostics();let original;
 const context={socket:{},passive:null,intercept:d.trace,pending:new Map([[9,{resolve:result=>{original=result;}}]]),JSON,Error};vm.runInNewContext(source.slice(begin,end),context);
 context.socket.onmessage({data:JSON.stringify(projected('script.realmCreated'))});context.socket.onmessage({data:JSON.stringify({id:9,result:{original:true}})});
 assert.deepEqual(original,{original:true});assert.equal(d.report().browserMetadata.events[0].event,'bidi-realm-created');
});
