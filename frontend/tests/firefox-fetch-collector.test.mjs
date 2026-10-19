// Mocked native protocol only; sent commands and supplied replies are not native evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createEnrollment,createFirefoxTransport} from './firefox-transport.mjs';

const api='http://127.0.0.1:19000',frontend='http://127.0.0.1:15173';
const patterns=[{urlPattern:'*/matches/*',requestStage:'Request'}];
const body='{"action":"PUBLIC","unicode":"\u00e9"}';
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve();};
function fixture(t,{strictCollectors=false}={}){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fetch-collector-'));
 fs.chmodSync(directory,0o700);
 const controller=createEnrollment({directory,runNonce:'0'.repeat(32),sourceBinding:'a'.repeat(64),apiOrigin:api,frontendOrigin:frontend});
 const sent=[],events=[],held=[],hold=new Set(),errors=new Map(),replies=new Map(),waiting=new Map(),pages=[];
 const liveCollectors=new Set(),retiredCollectors=new Set();
 let socket,serial=0,sequence=0;
 function respond(message){
  const result=replies.get(message.method)??(
   message.method==='session.new'?{capabilities:{browserName:'firefox',browserVersion:'158.0'}}:
   message.method==='session.subscribe'?{subscription:'subscription-'+(++serial)}:
   message.method==='browsingContext.create'?{context:'top-'+(++serial)}:
   message.method==='browsingContext.navigate'?{navigation:'navigation',url:message.params.url}:
   message.method==='browsingContext.getTree'?{contexts:[{context:message.params.root,url:'about:blank',children:[]}]}:
   message.method==='network.addDataCollector'?{collector:'collector-'+(++serial)}:
   message.method==='network.addIntercept'?{intercept:'intercept-'+(++serial)}:
   message.method==='network.getData'?{bytes:{type:'base64',value:Buffer.from(body).toString('base64')}}:{});
  let duplicate=false;
  if(strictCollectors&&!errors.has(message.method)){
   if(message.method==='network.addDataCollector')liveCollectors.add(result.collector);
   if(message.method==='network.removeDataCollector'){
    duplicate=!liveCollectors.delete(message.params.collector);
    if(!duplicate)retiredCollectors.add(message.params.collector);
   }
  }
  socket.onmessage({data:JSON.stringify(errors.has(message.method)||duplicate?{type:'error',id:message.id,error:errors.get(message.method)??'no such network data'}:{type:'success',id:message.id,result})});
 }
 const transport=createFirefoxTransport({controller,directory,endpoint:'ws://127.0.0.1:19384/session',producer:()=>{throw Error('Response body cache not enrolled');},socketFactory:()=>socket={readyState:1,send(text){const m=JSON.parse(text);sent.push(m);if(hold.has(m.method))held.push(m);else queueMicrotask(()=>respond(m));},close(){this.readyState=3;}}});
 const f={sent,events,held,hold,errors,replies,transport,respond,liveCollectors,retiredCollectors,
  calls:method=>sent.filter(m=>m.method===method),
  async open(){const p=await transport.open('about:blank');pages.push(p);p.socket.onmessage=({data})=>{const m=JSON.parse(data);if(!m.id){events.push(m);return;}const w=waiting.get(m.id);assert.ok(w);waiting.delete(m.id);m.error?w.reject(Error(m.error.message)):w.resolve(m.result);};return p;},
  command(p,method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;waiting.set(id,{resolve,reject});p.socket.send(JSON.stringify({id,method,params}));});},
  emit(p,response=false){socket.onmessage({data:JSON.stringify({type:'event',method:response?'network.responseStarted':'network.beforeRequestSent',params:{context:p.id,isBlocked:true,request:{request:'post-request',url:api+'/matches/public/action',method:'POST',headers:[],bodySize:Buffer.byteLength(body),destination:'empty'},...(response?{response:{status:200,headers:[]}}:{})}})});},
  release(method){const i=held.findIndex(m=>m.method===method);assert.notEqual(i,-1,'Expected held '+method);hold.delete(method);respond(held.splice(i,1)[0]);},
  async close(p){await p.close();pages.splice(pages.indexOf(p),1);}
 };
 t.after(async()=>{
  strictCollectors=false; // Release only mock teardown after a failed regression assertion.
  hold.clear();errors.clear();for(const m of held.splice(0))respond(m);
  await flush();
  try{for(const p of [...pages])await f.close(p);await transport.close();}
  finally{controller.close();fs.rmSync(directory,{recursive:true,force:true});}
 });
 return f;
}

test('Fetch collector ACK must precede intercept registration and enable completion',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');f.hold.add('network.addIntercept');let done=false;
 const enabled=f.command(p,'Fetch.enable',{patterns}).then(value=>{done=true;return value;});enabled.catch(()=>{});await flush();
 assert.equal(f.calls('network.addDataCollector').length,1);
 assert.equal(f.calls('network.addIntercept').length,0);assert.equal(done,false);
 assert.deepEqual(f.calls('network.addDataCollector')[0].params,{dataTypes:['request'],maxEncodedDataSize:8*1024*1024,collectorType:'blob',contexts:[p.id]});
 f.release('network.addDataCollector');await flush();assert.equal(f.calls('network.addIntercept').length,1);assert.equal(done,false);
 f.release('network.addIntercept');assert.ok((await enabled).intercept);assert.equal(done,true);
});

test('Fetch-only POST waits for actual supplied request-data ACK and preserves exact bytes',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p,'Fetch.enable',{patterns});
 assert.equal(f.calls('network.addDataCollector').length,1);assert.equal(f.calls('session.subscribe').length,1,'Fetch must not add a Network.enable subscription');
 f.hold.add('network.getData');f.emit(p);await flush();assert.equal(f.events.length,0);assert.equal(f.calls('network.getData').length,1);
 const get=f.calls('network.getData')[0];assert.equal(get.params.request,'post-request');assert.equal(get.params.dataType,'request');assert.equal(get.params.disown,true);assert.match(get.params.collector,/^collector-/);
 f.release('network.getData');await flush();assert.equal(f.events[0].params.request.postData,body);
 const captured=await f.command(p,'Network.getRequestPostData',{requestId:'post-request'});assert.equal(Buffer.from(captured.postData,'base64').toString(),body);
 await f.command(p,'Fetch.continueRequest',{requestId:'post-request',interceptResponse:true});f.emit(p,true);await flush();assert.equal(f.events[1].params.responseStatusCode,200);
 await f.command(p,'Fetch.continueResponse',{requestId:'post-request'});assert.equal(f.calls('network.getData').length,1);p.socket.assertHealthy();
});

test('Fetch disable/rearm reuses the collector and page close removes it once',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p,'Fetch.enable',{patterns});await f.command(p,'Fetch.disable');await f.command(p,'Fetch.enable',{patterns});
 assert.equal(f.calls('network.addDataCollector').length,1);assert.equal(f.calls('network.removeDataCollector').length,0);
 await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,1);
 assert.ok(f.sent.findIndex(m=>m.method==='network.removeDataCollector')<f.sent.findIndex(m=>m.method==='browsingContext.close'));
});

test('original Network.enable collector and repeat subscription behavior remain intact',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p,'Network.enable');await f.command(p,'Fetch.enable',{patterns});await f.command(p,'Network.enable');
 assert.equal(f.calls('network.addDataCollector').length,1);assert.equal(f.calls('session.subscribe').length,3);
 for(const m of f.calls('session.subscribe').slice(1))assert.deepEqual(m.params,{events:['network.beforeRequestSent','network.responseStarted','network.responseCompleted','network.fetchError'],contexts:[p.id]});
});

for(const first of ['Network.enable','Fetch.enable'])test(first+' pending collector is shared with the other enable, never duplicated',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');
 const one=f.command(p,first,first==='Fetch.enable'?{patterns}:{});one.catch(()=>{});await flush();
 const other=first==='Fetch.enable'?'Network.enable':'Fetch.enable';const two=f.command(p,other,other==='Fetch.enable'?{patterns}:{});two.catch(()=>{});await flush();
 assert.equal(f.calls('network.addDataCollector').length,1);assert.equal(f.calls('network.addIntercept').length,0);
 f.release('network.addDataCollector');await Promise.all([one,two]);assert.equal(f.calls('network.addDataCollector').length,1);assert.equal(f.calls('network.addIntercept').length,1);
});

test('two concurrent Network.enable calls share collector but retain both native subscriptions',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');const one=f.command(p,'Network.enable');const two=f.command(p,'Network.enable');one.catch(()=>{});two.catch(()=>{});await flush();
 assert.equal(f.calls('network.addDataCollector').length,1);f.release('network.addDataCollector');await Promise.all([one,two]);assert.equal(f.calls('session.subscribe').length,3);
});

test('collector registration error reaches caller without interception or invented cleanup identifier',async t=>{
 const f=fixture(t),p=await f.open();f.errors.set('network.addDataCollector','unsupported operation');
 await assert.rejects(f.command(p,'Fetch.enable',{patterns}),/^Error: unsupported operation$/);
 assert.equal(f.calls('network.addIntercept').length,0);await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,0);assert.equal(f.calls('browsingContext.close').length,1);
});

test('intercept failure retains only the acknowledged collector for owned page cleanup',async t=>{
 const f=fixture(t),p=await f.open();f.errors.set('network.addIntercept','invalid argument');
 await assert.rejects(f.command(p,'Fetch.enable',{patterns}),/^Error: invalid argument$/);assert.equal(f.calls('network.addDataCollector').length,1);
 await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,1);assert.equal(f.calls('network.removeIntercept').length,0);assert.equal(f.calls('browsingContext.close').length,1);
});

test('malformed collector success cannot admit interception or fabricate an owned collector',async t=>{
 const f=fixture(t),p=await f.open();f.replies.set('network.addDataCollector',{collector:''});
 await assert.rejects(f.command(p,'Fetch.enable',{patterns}),/BODY_CACHE_UNAVAILABLE/);assert.equal(f.calls('network.addIntercept').length,0);
 await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,0);
});

test('collector cleanup negative ACK remains a failure before genuine context closure',async t=>{
 const f=fixture(t),p=await f.open();await f.command(p,'Fetch.enable',{patterns});assert.equal(f.calls('network.addDataCollector').length,1);
 f.errors.set('network.removeDataCollector','no such network data');await assert.rejects(p.close(),/no such network data/);assert.equal(f.calls('browsingContext.close').length,0);
 f.errors.clear();await f.close(p);assert.equal(f.calls('browsingContext.close').length,1);
});

test('invalid Fetch options reject before creating any collector or intercept',async t=>{
 const f=fixture(t),p=await f.open();for(const params of [{patterns:[]},{patterns,extra:true},{patterns:[{urlPattern:'*',requestStage:'Unknown'}]}])await assert.rejects(f.command(p,'Fetch.enable',params));
 assert.equal(f.calls('network.addDataCollector').length,0);assert.equal(f.calls('network.addIntercept').length,0);
});

test('collectors remain page-owned, not shared across two actual mocked context IDs',async t=>{
 const f=fixture(t),one=await f.open(),two=await f.open();await f.command(one,'Fetch.enable',{patterns});await f.command(two,'Fetch.enable',{patterns});
 assert.equal(f.calls('network.addDataCollector').length,2);assert.deepEqual(f.calls('network.addDataCollector').map(m=>m.params.contexts),[[one.id],[two.id]]);
 await f.close(one);assert.equal(f.calls('network.removeDataCollector').length,1);assert.equal(f.calls('browsingContext.close')[0].params.context,one.id);
});

test('close cannot pass pending Network collector registration, then cleans its genuine ACK',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');const enabled=f.command(p,'Network.enable');enabled.catch(()=>{});await flush();
 await assert.rejects(p.close(),/configuration pending/);assert.equal(f.calls('browsingContext.close').length,0);
 f.release('network.addDataCollector');await enabled;await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,1);
});

test('future-child arming refuses a pending collector instead of creating a second one',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');const enabled=f.command(p,'Network.enable');enabled.catch(()=>{});await flush();
 const armed=p.armFutureChildren(patterns);armed.catch(()=>{});await flush();
 assert.equal(f.calls('network.addDataCollector').length,1);await assert.rejects(armed,/BODY_CACHE_UNAVAILABLE/);
 f.release('network.addDataCollector');await enabled;
});

test('Network enable cannot race an active future-child collector registration',async t=>{
 const f=fixture(t),p=await f.open();f.hold.add('network.addDataCollector');const armed=p.armFutureChildren(patterns);armed.catch(()=>{});await flush();
 const enabled=f.command(p,'Network.enable');enabled.catch(()=>{});await flush();
 assert.equal(f.calls('network.addDataCollector').length,1);await assert.rejects(enabled,/BODY_CACHE_UNAVAILABLE/);
 f.release('network.addDataCollector');await armed;
});

for(const later of ['session.unsubscribe','browsingContext.close'])test('successful collector removal survives later '+later+' failure without duplicate removal',async t=>{
 const f=fixture(t,{strictCollectors:true}),p=await f.open();
 if(later==='session.unsubscribe')await p.armFutureChildren(patterns);else await f.command(p,'Fetch.enable',{patterns});
 assert.equal(f.liveCollectors.size,1);const collector=[...f.liveCollectors][0];
 f.errors.set(later,'unsupported operation');
 await assert.rejects(p.close(),/^Error: unsupported operation$/);
 assert.equal(f.liveCollectors.size,0);assert.deepEqual([...f.retiredCollectors],[collector]);
 assert.equal(f.calls('network.removeDataCollector').length,1);assert.equal(f.calls(later).length,1,'the later failure must actually be reached');
 f.errors.delete(later);
 await f.close(p); // Explicit caller cleanup, never an automatic production retry.
 assert.deepEqual(f.calls('network.removeDataCollector').map(m=>m.params.collector),[collector]);
 assert.equal(f.calls('browsingContext.close').length,later==='browsingContext.close'?2:1);
});

test('collector removal ACK precedes stalled context close and stays retired after that close fails',async t=>{
 const f=fixture(t,{strictCollectors:true}),p=await f.open();await f.command(p,'Fetch.enable',{patterns});
 const collector=[...f.liveCollectors][0];f.hold.add('browsingContext.close');let settled=false;
 const closing=p.close().finally(()=>{settled=true;});closing.catch(()=>{});await flush();
 assert.equal(settled,false);assert.equal(f.calls('browsingContext.close').length,1);
 assert.equal(f.liveCollectors.size,0);assert.deepEqual([...f.retiredCollectors],[collector]);assert.equal(f.calls('network.removeDataCollector').length,1);
 f.errors.set('browsingContext.close','unsupported operation');f.release('browsingContext.close');
 await assert.rejects(closing,/unsupported operation/);assert.equal(settled,true);
 f.errors.clear();await f.close(p);assert.equal(f.calls('network.removeDataCollector').length,1);assert.equal(f.calls('browsingContext.close').length,2);
});

test('negative removal ACK retains the exact collector until explicit acknowledged cleanup',async t=>{
 const f=fixture(t,{strictCollectors:true}),p=await f.open();await f.command(p,'Fetch.enable',{patterns});
 const collector=[...f.liveCollectors][0];f.hold.add('network.removeDataCollector');
 const closing=p.close();closing.catch(()=>{});await flush();
 assert.deepEqual([...f.liveCollectors],[collector]);assert.equal(f.retiredCollectors.size,0);assert.equal(f.calls('browsingContext.close').length,0);
 f.errors.set('network.removeDataCollector','unsupported operation');f.release('network.removeDataCollector');
 await assert.rejects(closing,/unsupported operation/);assert.deepEqual([...f.liveCollectors],[collector]);assert.equal(f.retiredCollectors.size,0);
 f.errors.clear();await f.close(p);
 assert.deepEqual(f.calls('network.removeDataCollector').map(m=>m.params.collector),[collector,collector]);assert.equal(f.liveCollectors.size,0);assert.deepEqual([...f.retiredCollectors],[collector]);assert.equal(f.calls('browsingContext.close').length,1);
});
