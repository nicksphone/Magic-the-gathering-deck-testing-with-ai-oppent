// Pure library tests: owned files and a synthetic socket, never a native receipt.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {createEnrollment,createGetter,createFirefoxTransport} from './firefox-transport.mjs';
import {safeWireRow,createWireTrace} from './firefox-wire-trace.mjs';

const api='http://127.0.0.1:19000',frontend='http://127.0.0.1:15173';
const patterns=[{urlPattern:'*/matches/*',requestStage:'Response'}];
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
const start=()=>fs.readFileSync('/proc/self/stat','utf8').split(')').at(-1).trim().split(/\s+/)[19];
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');

function fixture(t,{observe}={}){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'firefox-transport-test-'));
 fs.chmodSync(directory,0o700);
 const controller=createEnrollment({directory,runNonce:'0'.repeat(32),sourceBinding:'a'.repeat(64),apiOrigin:api,frontendOrigin:frontend});
 const sent=[],events=[],waiting=new Map(),held=[],replies=new Map(),errors=new Map(),hold=new Set();
 let socket,tab=0,serial=0,id=0,transportClosed=false;
 function respond(m){
  const result=replies.has(m.method)?structuredClone(replies.get(m.method)):
   m.method==='session.new'?{capabilities:{browserName:'firefox',browserVersion:'158.0'}}:
   m.method==='session.subscribe'?{subscription:'subscription-'+(++serial)}:
   m.method==='browsingContext.create'?{context:'top-'+(++tab)}:
   m.method==='browsingContext.navigate'?{navigation:'navigation-id',url:m.params.url}:
   m.method==='browsingContext.getTree'?{contexts:[{context:m.params.root,url:'about:blank',children:[]}]}:
   m.method==='network.addIntercept'?{intercept:'intercept-'+(++serial)}:
   m.method==='network.addDataCollector'?{collector:'collector-'+(++serial)}:
   m.method==='script.addPreloadScript'?{script:'preload-'+(++serial)}:
   m.method==='script.evaluate'?{type:'success',result:{type:'boolean',value:true}}:{};
  socket.onmessage({data:JSON.stringify(errors.has(m.method)?{type:'error',id:m.id,error:errors.get(m.method),message:'PRIVATE_NATIVE_TEXT'}:{type:'success',id:m.id,result})});
 }
 const transport=createFirefoxTransport({controller,directory,endpoint:'ws://127.0.0.1:19384/session',producer:()=>({pid:process.pid,start:start()}),observe,
  socketFactory:()=>socket={readyState:1,closed:false,send(text){const m=JSON.parse(text);sent.push(m);if(hold.has(m.method))held.push(m);else queueMicrotask(()=>respond(m));},close(){this.closed=true;this.readyState=3;}}});
 const channels=[];
 const f={directory,controller,transport,sent,events,replies,errors,hold,held,respond,
  async open(url='about:blank'){
   const c=await transport.open(url);channels.push(c);
   c.socket.onmessage=({data})=>{const m=JSON.parse(data);if(!m.id){events.push(m);return;}const w=waiting.get(m.id);assert.ok(w,'unexpected compatibility reply');waiting.delete(m.id);if(m.error)w.reject(Error(m.error.message));else w.resolve(m.result);};
   return c;
  },
  command(c,method,params={},sessionId){return new Promise((resolve,reject)=>{const next=++id;waiting.set(next,{resolve,reject});c.socket.send(JSON.stringify({id:next,method,params,...(sessionId?{sessionId}:{})}));});},
  emit(method,params){socket.onmessage({data:JSON.stringify({type:'event',method,params})});},
  async close(c){await c.close();channels.splice(channels.indexOf(c),1);},
  async expectBrokenClose(){await assert.rejects(transport.close(),/closure unavailable/);assert.equal(socket.closed,true);channels.length=0;transportClosed=true;},
  get socket(){return socket;}
 };
 t.after(async()=>{
  hold.clear();errors.clear();for(const m of held.splice(0))respond(m);
  try{for(const c of [...channels])await f.close(c);if(!transportClosed)await transport.close();}
  finally{try{controller.close();}finally{fs.rmSync(directory,{recursive:true,force:true});}}
 });
 return f;
}
function networkEvent(c,request='request',url=api+'/matches/test',response=false){
 return {context:c.id,isBlocked:true,request:{request,url,method:'GET',headers:[],bodySize:0,destination:'document'},...(response?{response:{status:200,headers:[]}}:{})};
}
function capture(f,c,overrides={}){
 const id=crypto.randomBytes(16).toString('hex'),body=Buffer.from('{"ok":true}'),now=process.hrtime.bigint(),current=f.controller.current();
 const metadata={schema_version:1,capture_id:id,...f.controller.bindings,episode:current.episode,enrollment_generation:current.generation,native_top_context:c.id,method:'GET',status:200,raw_path_length:13,raw_path_sha256:digest('/matches/test'),raw_query_length:0,raw_query_sha256:digest(''),body_length:body.length,body_sha256:digest(body),producer_pid:process.pid,producer_start:start(),published_ns:now.toString(),expires_ns:(now+15_000_000_000n).toString(),...overrides};
 const write=(suffix,bytes)=>fs.writeFileSync(path.join(f.directory,id+suffix),bytes,{mode:0o600,flag:'wx'});
 write('.body',body);write('.json',JSON.stringify(Object.fromEntries(Object.keys(metadata).sort().map(k=>[k,metadata[k]]))));
 const event=networkEvent(c,'request-'+id,api+'/matches/test',true);
 event.response.headers=[{name:'x-release-test-capture-id',value:{type:'string',value:id}}];
 return {id,body,event,file:suffix=>path.join(f.directory,id+suffix)};
}

test('navigate sends actual scoped BiDi navigation and returns CDP frame/loader identifiers',async t=>{
 const f=fixture(t),c=await f.open();
 assert.deepEqual(await f.command(c,'Page.navigate',{url:frontend+'/?fixture=original'}),{frameId:c.id,loaderId:'navigation-id'});
 assert.deepEqual(f.sent.at(-1).params,{context:c.id,url:frontend+'/?fixture=original',wait:'none'});
 f.replies.set('browsingContext.navigate',{navigation:null,url:'about:blank'});
 assert.deepEqual(await f.command(c,'Page.navigate',{url:'about:blank'}),{frameId:c.id});
});
test('navigate rejects foreign/special origins, credentials, unsupported options and unknown contexts without sending',async t=>{
 const f=fixture(t),c=await f.open(),count=f.sent.length;
 for(const url of ['https://example.com',api+'/',frontend.replace('http://','http://user@')+'/', 'data:text/html,private','chrome://sandbox/','about:config'])await assert.rejects(f.command(c,'Page.navigate',{url}));
 for(const extra of [{referrer:frontend},{transitionType:'reload'},{frameId:c.id},{wait:'complete'}])await assert.rejects(f.command(c,'Page.navigate',{url:frontend,...extra}));
 await assert.rejects(f.command(c,'Page.navigate',{url:frontend},'foreign'));
 assert.equal(f.sent.length,count);
});
test('preload registers source as actual scoped function and removes owned scripts on close',async t=>{
 const f=fixture(t),c=await f.open(),source="window.testErrors = []; localStorage.setItem('mtg.activeMatch', 'fixture');";
 const {identifier}=await f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source});
 assert.match(identifier,/^preload-/);
 assert.equal(f.sent.at(-1).method,'script.addPreloadScript');
 assert.deepEqual(f.sent.at(-1).params,{functionDeclaration:`() => {\n${source}\n}`,contexts:[c.id]});
 await f.close(c);
 assert.deepEqual(f.sent.find(m=>m.method==='script.removePreloadScript').params,{script:identifier});
 assert.ok(f.sent.findIndex(m=>m.method==='script.removePreloadScript')<f.sent.findIndex(m=>m.method==='browsingContext.close'));
});
test('preload and activate reject unsupported options; child preload cannot silently widen its scope',async t=>{
 const f=fixture(t),c=await f.open();f.emit('browsingContext.contextCreated',{context:'child',parent:c.id});await flush();
 const count=f.sent.length;
 for(const extra of [{worldName:'sandbox'},{includeCommandLineAPI:true},{runImmediately:true}])await assert.rejects(f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source:'true',...extra}));
 await assert.rejects(f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source:42}));
 await assert.rejects(f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source:'true'},'child'));
 await assert.rejects(f.command(c,'Page.bringToFront',{anything:true}));
 assert.equal(f.sent.length,count);
});
test('bringToFront actually activates owned top and rejects child activation',async t=>{
 const f=fixture(t),c=await f.open();assert.deepEqual(await f.command(c,'Page.bringToFront'),{});
 assert.deepEqual(f.sent.at(-1),{id:f.sent.at(-1).id,method:'browsingContext.activate',params:{context:c.id}});
 f.emit('browsingContext.contextCreated',{context:'child',parent:c.id});await flush();
 await assert.rejects(f.command(c,'Page.bringToFront',{},'child'));
});
for(const [cdp,native,params] of [
 ['Page.navigate','browsingContext.navigate',{url:frontend}],
 ['Page.bringToFront','browsingContext.activate',{}],
 ['Page.addScriptToEvaluateOnNewDocument','script.addPreloadScript',{source:'true'}],
 ['Network.setBlockedURLs','network.addIntercept',{urls:['https://*']}]
])test(cdp+' preserves true native error, never successful no-op',async t=>{
 const f=fixture(t),c=await f.open();f.errors.set(native,'unsupported operation');
 await assert.rejects(f.command(c,cdp,params),/^Error: unsupported operation$/);
 assert.equal(f.sent.at(-1).method,native);
});
test('blocked URLs install acknowledged native beforeRequestSent intercept and actually fail matching requests',async t=>{
 const f=fixture(t),c=await f.open();f.hold.add('network.addIntercept');let done=false;
 const pending=f.command(c,'Network.setBlockedURLs',{urls:['https://*']}).then(r=>{done=true;return r;});pending.catch(()=>{});await flush();
 assert.equal(done,false);assert.equal(f.held.length,1);
 assert.deepEqual(f.held[0].params,{contexts:[c.id],phases:['beforeRequestSent']});
 f.hold.clear();f.respond(f.held.shift());await pending;
 f.emit('network.beforeRequestSent',networkEvent(c,'blocked','https://example.com/private'));await flush();
 assert.deepEqual(f.sent.at(-1).params,{request:'blocked'});assert.equal(f.sent.at(-1).method,'network.failRequest');assert.equal(f.events.length,0);
 f.emit('network.beforeRequestSent',networkEvent(c,'allowed',frontend+'/'));await flush();
 assert.equal(f.sent.at(-1).method,'network.continueRequest');assert.deepEqual(f.sent.at(-1).params,{request:'allowed'});
});
test('block rule replacement/clear preserves Fetch interception, validates wildcard literals',async t=>{
 const f=fixture(t),c=await f.open();const {intercept:fetchID}=await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
 await f.command(c,'Network.setBlockedURLs',{urls:['https://*/asset[1].png']});
 f.emit('network.beforeRequestSent',networkEvent(c,'literal','https://example.com/asset[1].png'));await flush();assert.equal(f.sent.at(-1).method,'network.failRequest');
 f.emit('network.beforeRequestSent',networkEvent(c,'not-regex','https://example.com/asset1.png'));await flush();assert.equal(f.events.at(-1).params.requestId,'not-regex');
 await f.command(c,'Fetch.continueRequest',{requestId:'not-regex'});
 await f.command(c,'Network.setBlockedURLs',{urls:[]});
 assert.equal(f.sent.filter(m=>m.method==='network.removeIntercept').length,1);
 assert.ok(!f.sent.some(m=>m.method==='network.removeIntercept'&&m.params.intercept===fetchID));
 f.emit('network.beforeRequestSent',networkEvent(c,'still-fetch'));await flush();assert.equal(f.events.at(-1).params.requestId,'still-fetch');
});
test('Fetch.disable removes only owned Fetch intercepts and drains both blocked phases',async t=>{
 const f=fixture(t),c=await f.open(),other=await f.open();
 await f.command(other,'Fetch.enable',{patterns});
 await f.command(c,'Network.setBlockedURLs',{urls:['https://*']});
 const {intercept:fetchIntercept}=await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'},{urlPattern:'*',requestStage:'Response'}]});
 const count=f.events.length;
 f.emit('network.beforeRequestSent',networkEvent(c,'paused-request'));f.emit('network.responseStarted',networkEvent(c,'paused-response',undefined,true));await flush();
 assert.equal(f.events.length,count+2);
 await f.command(c,'Fetch.disable');
 assert.deepEqual(f.sent.filter(m=>m.method==='network.removeIntercept').map(m=>m.params),[{intercept:fetchIntercept}]);
 assert.equal(f.sent.filter(m=>m.method==='network.removeIntercept').length,1);
 for(const [method,request] of [['network.continueRequest','paused-request'],['network.continueResponse','paused-response']])assert.ok(f.sent.some(m=>m.method===method&&m.params.request===request));
 f.emit('network.beforeRequestSent',networkEvent(c,'still-blocked','https://example.com'));await flush();assert.equal(f.sent.at(-1).method,'network.failRequest');
 f.emit('network.responseStarted',networkEvent(other,'other-scope',undefined,true));await flush();assert.equal(f.events.at(-1).params.requestId,'other-scope');
 const removals=f.sent.filter(m=>m.method==='network.removeIntercept').length;await f.command(c,'Fetch.disable');assert.equal(f.sent.filter(m=>m.method==='network.removeIntercept').length,removals);
});
test('Fetch defaults match actual omitted-stage caller patterns, with no URL regexp interpretation',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Fetch.enable',{patterns:[{urlPattern:frontend+'/api/*'}]});
 f.emit('network.beforeRequestSent',networkEvent(c,'default-stage',frontend+'/api/test'));await flush();assert.equal(f.events.at(-1).params.requestId,'default-stage');
});
test('Fetch.disable waits for in-flight response ACK without duplicate continue or premature release',async t=>{
 const f=fixture(t);await f.controller.withEnrolledBodyEpisode('human_vs_human',async()=>{
  const c=await f.open();await f.command(c,'Fetch.enable',{patterns});const cap=capture(f,c);
  f.emit('network.responseStarted',cap.event);await flush();await f.command(c,'Fetch.getResponseBody',{requestId:cap.event.request.request});
  f.hold.add('network.continueResponse');const ack=f.command(c,'Fetch.continueResponse',{requestId:cap.event.request.request});await flush();
  let disabled=false;const disable=f.command(c,'Fetch.disable').then(()=>{disabled=true;});await flush();
  assert.equal(disabled,false);assert.equal(fs.existsSync(cap.file('.release')),false);assert.equal(f.held.length,1);
  f.hold.clear();f.respond(f.held.shift());await ack;await disable;
  assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,1);
  assert.equal(JSON.parse(fs.readFileSync(cap.file('.release'),'utf8')).ack_command_id,f.sent.find(m=>m.method==='network.continueResponse').id);
  await f.close(c);
 });
});
for(const negative of [false,true])test('Fetch.disable body-cache '+(negative?'negative native ACK never releases':'positive ACK releases only after native reply'),async t=>{
 const f=fixture(t);await f.controller.withEnrolledBodyEpisode('human_vs_human',async()=>{
  const c=await f.open();await f.command(c,'Fetch.enable',{patterns});const cap=capture(f,c);
  f.emit('network.responseStarted',cap.event);await flush();assert.deepEqual(await f.command(c,'Fetch.getResponseBody',{requestId:cap.event.request.request}),{body:cap.body.toString('base64'),base64Encoded:true});
  if(negative)f.errors.set('network.continueResponse','no such request');
  if(negative)await assert.rejects(f.command(c,'Fetch.disable'),/no such request/);else await f.command(c,'Fetch.disable');
  assert.equal(fs.existsSync(cap.file('.release')),!negative);
  f.errors.clear();await f.close(c);
 });
});
test('new mappings reject unsupported options and child-wide mutations without sending',async t=>{
 const f=fixture(t),c=await f.open();f.emit('browsingContext.contextCreated',{context:'child',parent:c.id});await flush();const count=f.sent.length;
 for(const [method,params] of [['Fetch.disable',{unknown:true}],['Network.setBlockedURLs',{urls:['https://*'],urlPatterns:[]}],['Network.setBlockedURLs',{urls:'https://*'}],['Network.setBlockedURLs',{urls:[null]}],['Network.setBlockedURLs',{urls:['']}],['Network.setBlockedURLs',{urls:['x'.repeat(4097)]}]])await assert.rejects(f.command(c,method,params));
 for(const [method,params] of [['Fetch.disable',{}],['Network.setBlockedURLs',{urls:['https://*']}]])await assert.rejects(f.command(c,method,params,'child'));
 assert.equal(f.sent.length,count);
});
test('failed native intercept removal is returned and stays owned for close retry',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Fetch.enable',{patterns});f.errors.set('network.removeIntercept','no such intercept');
 await assert.rejects(f.command(c,'Fetch.disable'),/no such intercept/);const failed=f.sent.at(-1);
 f.errors.clear();await f.close(c);assert.ok(f.sent.filter(m=>m.method==='network.removeIntercept').some(m=>m.id!==failed.id&&m.params.intercept===failed.params.intercept));
});
test('old evaluation, request collector and response interception retain genuine native arguments',async t=>{
 const f=fixture(t),c=await f.open();assert.deepEqual(await f.command(c,'Runtime.evaluate',{expression:'true',awaitPromise:true,returnByValue:true}),{result:{value:true}});
 assert.deepEqual(f.sent.at(-1).params,{expression:'true',target:{context:c.id},awaitPromise:true,resultOwnership:'none',serializationOptions:{maxObjectDepth:null}});
 await assert.rejects(f.command(c,'Runtime.evaluate',{expression:'true'}));
 await f.command(c,'Network.enable');await f.command(c,'Fetch.enable',{patterns});
 f.replies.set('network.getData',{bytes:{type:'string',value:'{"id":1}'}});const e=networkEvent(c,'post',undefined,true);e.request.method='POST';delete e.request.bodySize;
 f.emit('network.responseStarted',e);await flush();assert.equal(f.events.at(-1).params.request.postData,'{"id":1}');
 assert.deepEqual(await f.command(c,'Network.getRequestPostData',{requestId:'post'}),{postData:Buffer.from('{"id":1}').toString('base64'),base64Encoded:true});
 await f.command(c,'Fetch.failRequest',{requestId:'post',errorReason:'Failed'});assert.deepEqual(f.sent.at(-1).params,{request:'post'});
});
test('armFutureChildren receipts precede future creation; never fake CDP autoattach or debugger pauses',async t=>{
 const f=fixture(t),c=await f.open(),ready=[];c.onChildInitialized(e=>ready.push(e));const receipt=await c.armFutureChildren(patterns);
 for(const [kind,method] of [['network','session.subscribe'],['lifecycle','session.subscribe'],['contexts','session.subscribe'],['collector','network.addDataCollector'],['intercept','network.addIntercept']]){
  const ack=receipt.registrations[kind];assert.equal(ack.method,method);assert.deepEqual(f.sent.find(m=>m.id===ack.id).params,ack.params);assert.ok(Object.isFrozen(ack.params.contexts));
 }
 f.emit('browsingContext.contextCreated',{context:'future',parent:c.id});await flush();assert.equal(c.validateChildInitialized(ready[0]),ready[0]);
 const count=f.sent.length;await assert.rejects(f.command(c,'Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:true,flatten:true}),/FIREFOX_CAPABILITY_HOLD/);assert.equal(f.sent.length,count);
 assert.equal(f.events.some(e=>e.method==='Target.attachedToTarget'),false);assert.equal(f.sent.some(m=>m.method==='Runtime.runIfWaitingForDebugger'),false);
 f.emit('browsingContext.contextDestroyed',{context:'future'});await flush();assert.throws(()=>c.validateChildInitialized(ready[0]));
});
for(const mode of ['existing','during','negative'])test('armFutureChildren rejects '+mode+' child/registration races',async t=>{
 const f=fixture(t),c=await f.open(),ready=[];c.onChildInitialized(e=>ready.push(e));
 if(mode==='existing')f.replies.set('browsingContext.getTree',{contexts:[{context:c.id,children:[{context:'existing'}]}]});
 if(mode==='negative')f.errors.set('network.addIntercept','invalid argument');
 if(mode==='during'){const send=f.socket.send;f.socket.send=text=>{if(JSON.parse(text).method==='network.addIntercept')f.emit('browsingContext.contextCreated',{context:'early',parent:c.id});send(text);};}
 await assert.rejects(c.armFutureChildren(patterns));assert.equal(ready.length,0);
 f.errors.clear();
});
test('sanitized observations whitelist only real new BiDi methods and redact all private text',async t=>{
 const rows=[],f=fixture(t,{observe:row=>rows.push(row)}),c=await f.open();
 await f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source:'PRIVATE_SOURCE'});await f.command(c,'Page.bringToFront');await f.close(c);
 for(const method of ['script.addPreloadScript','script.removePreloadScript','browsingContext.activate'])assert.ok(rows.some(r=>r.method===method));
 const privateRow=safeWireRow({kind:'native-reply',id:1,errorCode:'PRIVATE_ERROR',message:'PRIVATE_MESSAGE',params:{source:'PRIVATE_SOURCE'}});
 assert.equal(privateRow.errorCategory,'OTHER_REDACTED');assert.equal(JSON.stringify([...rows,privateRow]).includes('PRIVATE_'),false);
 const trace=createWireTrace(f.directory);trace.record({kind:'wire-close',reason:'PRIVATE_CLOSE',pending:[{id:1,method:'PRIVATE_METHOD'}]});assert.equal(trace.failed,false);assert.equal(fs.readFileSync(path.join(f.directory,'cdp.jsonl'),'utf8').includes('PRIVATE_'),false);
});
for(const fault of ['nonce','expiry','producer','mode','symlink','hardlink','duplicate'])test('preserved getter rejects '+fault+' violation using only owned files',async t=>{
 const f=fixture(t);await f.controller.withEnrolledBodyEpisode('human_vs_human',async()=>{
  const c=await f.open();await f.command(c,'Fetch.enable',{patterns});
  const cap=capture(f,c,fault==='nonce'?{run_nonce:'f'.repeat(32)}:fault==='expiry'?{published_ns:'1',expires_ns:'15000000001'}:fault==='producer'?{producer_start:'1'}:{});
  if(fault==='mode')fs.chmodSync(cap.file('.body'),0o644);
  if(['symlink','hardlink'].includes(fault)){fs.renameSync(cap.file('.body'),cap.file('.owned'));if(fault==='symlink')fs.symlinkSync(cap.file('.owned'),cap.file('.body'));else fs.linkSync(cap.file('.owned'),cap.file('.body'));}
  if(fault==='duplicate'){const original=fs.readFileSync(cap.file('.json'),'utf8');fs.writeFileSync(cap.file('.json'),'{"status":500,'+original.slice(1));}
  f.emit('network.responseStarted',cap.event);await flush();await assert.rejects(f.command(c,'Fetch.getResponseBody',{requestId:cap.event.request.request}));assert.equal(fs.existsSync(cap.file('.release')),false);await f.close(c);
 });
});
test('enrollment/getter APIs deny unauthenticated controller and incompatible browser versions',async t=>{
 const f=fixture(t);assert.throws(()=>createGetter({directory:f.directory,enrollment:f.controller.bindings,producer:{pid:process.pid,start:start()},contexts:new Set(['owned']),controller:{}}));
 f.replies.set('session.new',{capabilities:{browserName:'firefox',browserVersion:'159.0'}});await assert.rejects(f.open());
 assert.equal(f.sent.some(m=>m.method==='browsingContext.create'),false);
});
test('Fetch.disable revokes old and future child initialization readiness after removing intercept',async t=>{
 const f=fixture(t),c=await f.open(),ready=[];c.onChildInitialized(e=>ready.push(e));await c.armFutureChildren(patterns);
 f.emit('browsingContext.contextCreated',{context:'before-disable',parent:c.id});await flush();assert.equal(c.validateChildInitialized(ready[0]),ready[0]);
 await f.command(c,'Fetch.disable');assert.throws(()=>c.validateChildInitialized(ready[0]));
 f.emit('browsingContext.contextCreated',{context:'after-disable',parent:c.id});await flush();assert.equal(ready.length,1);
});
test('pending POST data retrieval cannot emit a stale Fetch pause after disable',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Network.enable');await f.command(c,'Fetch.enable',{patterns});
 f.hold.add('network.getData');const e=networkEvent(c,'late-post',undefined,true);e.request.method='POST';e.request.bodySize=7;
 f.emit('network.responseStarted',e);await flush();assert.equal(f.held.length,1);
 await f.command(c,'Fetch.disable');f.hold.clear();f.replies.set('network.getData',{bytes:{type:'string',value:'private'}});f.respond(f.held.shift());await flush();
 assert.equal(f.events.length,0);assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,1);
});
test('foreign native intercept pauses never become Fetch events or commands',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Fetch.enable',{patterns});await f.command(c,'Network.setBlockedURLs',{urls:['https://*']});const count=f.sent.length;
 for(const response of [false,true]){const e=networkEvent(c,'foreign-'+response,'https://example.com',response);e.intercepts=['not-owned'];f.emit(response?'network.responseStarted':'network.beforeRequestSent',e);}
 f.emit('network.beforeRequestSent',{...networkEvent(c,'foreign-context'),context:'foreign'});await flush();assert.equal(f.sent.length,count);assert.equal(f.events.length,0);
});
test('failed Fetch enable leaves prior acknowledged matching configuration intact',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Fetch.enable',{patterns});f.errors.set('network.addIntercept','invalid argument');
 await assert.rejects(f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]}),/invalid argument/);
 f.emit('network.responseStarted',networkEvent(c,'still-response',undefined,true));await flush();assert.equal(f.events.at(-1).params.requestId,'still-response');
 f.errors.clear();await f.command(c,'Fetch.disable');assert.equal(f.sent.filter(m=>m.method==='network.removeIntercept').length,1);
});
test('clearing blocked URLs returns native removal errors and keeps old blocking rules',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Network.setBlockedURLs',{urls:['https://*']});f.errors.set('network.removeIntercept','no such intercept');
 await assert.rejects(f.command(c,'Network.setBlockedURLs',{urls:[]}),/no such intercept/);
 f.emit('network.beforeRequestSent',networkEvent(c,'still-policy','https://example.com'));await flush();assert.equal(f.sent.at(-1).method,'network.failRequest');
 f.errors.clear();await f.command(c,'Network.setBlockedURLs',{urls:[]});
});
test('preload close failures keep owned script for retry and never remove other channel scripts',async t=>{
 const f=fixture(t),c=await f.open(),other=await f.open();const {identifier}=await f.command(c,'Page.addScriptToEvaluateOnNewDocument',{source:'true'});
 const {identifier:otherScript}=await f.command(other,'Page.addScriptToEvaluateOnNewDocument',{source:'false'});
 f.errors.set('script.removePreloadScript','no such script');await assert.rejects(c.close(),/no such script/);
 assert.equal(f.sent.at(-1).params.script,identifier);assert.equal(f.sent.some(m=>m.method==='browsingContext.close'),false);
 f.errors.clear();await f.close(c);assert.equal(f.sent.filter(m=>m.method==='script.removePreloadScript'&&m.params.script===identifier).length,2);
 assert.equal(f.sent.some(m=>m.method==='script.removePreloadScript'&&m.params.script===otherScript),false);
 await assert.rejects(f.command(c,'Page.bringToFront'));
});
test('malformed new native success replies fail closed, never fabricate identifiers',async t=>{
 const f=fixture(t),c=await f.open();
 for(const [method,native,params,result] of [
  ['Page.navigate','browsingContext.navigate',{url:frontend},{url:frontend}],
  ['Page.addScriptToEvaluateOnNewDocument','script.addPreloadScript',{source:'true'},{script:7}],
  ['Network.setBlockedURLs','network.addIntercept',{urls:['https://*']},{intercept:''}]
 ]){f.replies.set(native,result);await assert.rejects(f.command(c,method,params));f.replies.delete(native);}
});
test('observer errors cannot authorize or suppress native command execution',async t=>{
 const f=fixture(t,{observe(){throw Error('private observer fault');}}),c=await f.open();
 await f.command(c,'Page.bringToFront');assert.equal(f.transport.observerFailed,true);assert.equal(f.sent.at(-1).method,'browsingContext.activate');
});
test('disable joins blocked events arriving during native intercept removal',async t=>{
 const f=fixture(t),c=await f.open();const {intercept}=await f.command(c,'Fetch.enable',{patterns});
 f.hold.add('network.removeIntercept');let disabled=false;
 const disable=f.command(c,'Fetch.disable').then(()=>{disabled=true;});disable.catch(()=>{});await flush();
 f.hold.add('network.continueResponse');const e=networkEvent(c,'during-removal',undefined,true);e.intercepts=[intercept];f.emit('network.responseStarted',e);await flush();
 const removal=f.held.find(m=>m.method==='network.removeIntercept'),continuation=f.held.find(m=>m.method==='network.continueResponse');assert.ok(continuation);
 f.respond(removal);await flush();assert.equal(disabled,false);
 f.hold.clear();f.respond(continuation);f.held.length=0;await disable;
 assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,1);
});
test('request continuation can opt into response interception using native ACKs',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
 f.emit('network.beforeRequestSent',networkEvent(c,'opt-in'));await flush();
 await f.command(c,'Fetch.continueRequest',{requestId:'opt-in',interceptResponse:true});
 assert.deepEqual(f.sent.at(-1).params,{request:'opt-in'});
 f.emit('network.responseStarted',networkEvent(c,'opt-in',undefined,true));await flush();
 assert.equal(f.events.at(-1).params.responseStatusCode,200);
 await f.command(c,'Fetch.fulfillRequest',{requestId:'opt-in',responseCode:200,body:'e30=',responseHeaders:[{name:'content-type',value:'application/json'}]});
 assert.deepEqual(f.sent.at(-1).params,{request:'opt-in',statusCode:200,body:{type:'base64',value:'e30='},headers:[{name:'content-type',value:{type:'string',value:'application/json'}}]});
});
test('failed actual URL blocking terminates transport health instead of inventing success',async t=>{
 const rows=[],f=fixture(t,{observe:r=>rows.push(r)}),c=await f.open();await f.command(c,'Network.setBlockedURLs',{urls:['https://*']});
 f.errors.set('network.failRequest','PRIVATE_NATIVE_ERROR');f.emit('network.beforeRequestSent',networkEvent(c,'blocked-error','https://example.com/private'));await flush();
 await assert.rejects(f.command(c,'Page.bringToFront'),/^Error: PRIVATE_NATIVE_ERROR$/);
 assert.equal(rows.at(-1).errorCategory,'OTHER_REDACTED');assert.equal(JSON.stringify(rows).includes('PRIVATE_'),false);
 // Native failure is intentionally sticky; assert failed closure, not success.
 await f.expectBrokenClose();
});
test('integration gap: async-readiness data document remains outside the admitted page scope',async t=>{
 const f=fixture(t);
 await assert.rejects(f.transport.open('data:text/html,<body>Async readiness regression</body>'),/Outside owned Firefox page origin/);
 assert.equal(f.sent.length,0);assert.equal(f.socket,undefined);
});

async function finishOrdering(f,c){
 f.hold.clear();for(const m of f.held.splice(0))f.respond(m);await flush();
 let broken=false;try{c.socket.assertHealthy();}catch{broken=true;}
 if(broken)await f.expectBrokenClose();
}
for(const disabling of [false,true])test('review P1: response before request ACK serializes automatic continuation'+(disabling?' during disable':''),async t=>{
 const f=fixture(t),c=await f.open();
 try{
  await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  f.emit('network.beforeRequestSent',networkEvent(c,'early-response'));await flush();
  f.hold.add('network.continueRequest');f.hold.add('network.continueResponse');
  const request=f.command(c,'Fetch.continueRequest',{requestId:'early-response'});request.catch(()=>{});await flush();
  f.emit('network.responseStarted',networkEvent(c,'early-response',undefined,true));await flush();
  let disabled=false;const disable=disabling?f.command(c,'Fetch.disable').then(()=>{disabled=true;}):Promise.resolve();disable.catch(()=>{});await flush();
  assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,0);
  assert.doesNotThrow(()=>c.socket.assertHealthy());
  const prior=f.held.splice(f.held.findIndex(m=>m.method==='network.continueRequest'),1)[0];assert.ok(prior);f.respond(prior);
  await request;await flush();
  const response=f.held.splice(f.held.findIndex(m=>m.method==='network.continueResponse'),1)[0];assert.ok(response);
  assert.deepEqual(response.params,{request:'early-response'});assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,1);
  if(disabling)assert.equal(disabled,false);
  f.respond(response);await disable;await flush();
  assert.equal(f.events.length,1);assert.doesNotThrow(()=>c.socket.assertHealthy());
  await f.command(c,'Page.bringToFront');
 }finally{await finishOrdering(f,c);}
});
for(const disablingBeforeACK of [false,true])test('review P1: explicit response handler cannot race automatic continuation '+(disablingBeforeACK?'when disable precedes request ACK':'when disable joins response ACK'),async t=>{
 const f=fixture(t),c=await f.open();let responsePauses=0,handled;
 const receive=c.socket.onmessage;c.socket.onmessage=message=>{
  receive(message);const m=JSON.parse(message.data);
  if(m.method==='Fetch.requestPaused'&&m.params.responseStatusCode){responsePauses++;handled=f.command(c,'Fetch.continueResponse',{requestId:m.params.requestId});handled.catch(()=>{});}
 };
 try{
  await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  f.emit('network.beforeRequestSent',networkEvent(c,'explicit-early'));await flush();
  f.hold.add('network.continueRequest');f.hold.add('network.continueResponse');
  const request=f.command(c,'Fetch.continueRequest',{requestId:'explicit-early',interceptResponse:true});request.catch(()=>{});await flush();
  f.emit('network.responseStarted',networkEvent(c,'explicit-early',undefined,true));await flush();
  assert.equal(responsePauses,0,'a selected response cannot be exposed before the actual request ACK');
  let disabled=false,disable;
  if(disablingBeforeACK){disable=f.command(c,'Fetch.disable').then(()=>{disabled=true;});disable.catch(()=>{});await flush();}
  f.respond(f.held.splice(f.held.findIndex(m=>m.method==='network.continueRequest'),1)[0]);await request;await flush();
  assert.equal(responsePauses,disablingBeforeACK?0:1);
  if(!disablingBeforeACK){disable=f.command(c,'Fetch.disable').then(()=>{disabled=true;});disable.catch(()=>{});await flush();assert.ok(handled);}
  assert.equal(disabled,false);assert.equal(f.sent.filter(m=>m.method==='network.continueResponse').length,1);
  f.respond(f.held.splice(f.held.findIndex(m=>m.method==='network.continueResponse'),1)[0]);if(handled)await handled;await disable;
  assert.doesNotThrow(()=>c.socket.assertHealthy());
 }finally{await finishOrdering(f,c);}
});
test('review P2: disable and re-enable cannot resurrect a drained POST pause when getData replies',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Network.enable');await f.command(c,'Fetch.enable',{patterns});
 f.hold.add('network.getData');const e=networkEvent(c,'previous-generation',undefined,true);e.request.method='POST';e.request.bodySize=7;
 f.emit('network.responseStarted',e);await flush();assert.equal(f.held.length,1);
 await f.command(c,'Fetch.disable');await f.command(c,'Fetch.enable',{patterns});
 f.replies.set('network.getData',{bytes:{type:'string',value:'private'}});f.hold.clear();f.respond(f.held.shift());await flush();
 assert.equal(f.events.length,0,'the old, already-drained event belongs to the previous Fetch configuration');
 assert.equal(f.sent.filter(m=>m.method==='network.continueResponse'&&m.params.request==='previous-generation').length,1);
 f.emit('network.responseStarted',networkEvent(c,'fresh-generation',undefined,true));await flush();assert.equal(f.events.length,1);assert.equal(f.events[0].params.requestId,'fresh-generation');
 await f.command(c,'Fetch.continueResponse',{requestId:'fresh-generation'});assert.doesNotThrow(()=>c.socket.assertHealthy());
});
test('review P2: a reused request ID cannot give a drained POST event new ownership',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Network.enable');await f.command(c,'Fetch.enable',{patterns});
 f.hold.add('network.getData');const e=networkEvent(c,'reused-request',undefined,true);e.request.method='POST';e.request.bodySize=7;
 f.emit('network.responseStarted',e);await flush();await f.command(c,'Fetch.disable');await f.command(c,'Fetch.enable',{patterns});
 f.emit('network.responseStarted',networkEvent(c,'reused-request',undefined,true));await flush();assert.equal(f.events.length,1);
 f.replies.set('network.getData',{bytes:{type:'string',value:'private'}});f.hold.clear();f.respond(f.held.shift());await flush();
 assert.equal(f.events.length,1);assert.equal(f.events[0].params.request.method,'GET');
 await f.command(c,'Fetch.continueResponse',{requestId:'reused-request'});
});
test('review P2: replacing Fetch configuration invalidates and safely continues an unexposed POST event',async t=>{
 const f=fixture(t),c=await f.open();await f.command(c,'Network.enable');await f.command(c,'Fetch.enable',{patterns});
 f.hold.add('network.getData');const e=networkEvent(c,'reconfigured-post',undefined,true);e.request.method='POST';e.request.bodySize=7;
 f.emit('network.responseStarted',e);await flush();await f.command(c,'Fetch.enable',{patterns});
 f.replies.set('network.getData',{bytes:{type:'string',value:'private'}});f.hold.clear();f.respond(f.held.shift());await flush();
 assert.equal(f.events.length,0,'even identical pattern contents are a different acknowledged configuration');
 assert.equal(f.sent.filter(m=>m.method==='network.continueResponse'&&m.params.request==='reconfigured-post').length,1);
 assert.doesNotThrow(()=>c.socket.assertHealthy());
});

// Opaque mocked native result data, not a generated PNG or native acceptance receipt.
const screenshotResult={data:'OPAQUE_NATIVE_SCREENSHOT_TEST_DATA'};
for(const [label,flag,origin] of [['omitted',undefined,'viewport'],['false',false,'viewport'],['true',true,'document']]){
 test('screenshot '+label+' forwards exact native scope and result data',async t=>{
  const f=fixture(t),c=await f.open();f.replies.set('browsingContext.captureScreenshot',screenshotResult);
  const params={format:'png',...(flag===undefined?{}:{captureBeyondViewport:flag})};
  const before=f.sent.length;
  assert.deepEqual(await f.command(c,'Page.captureScreenshot',params),screenshotResult);
  assert.equal(f.sent.length,before+1);
  assert.deepEqual(f.sent.at(-1).params,{context:c.id,origin,format:{type:'image/png'}});
  assert.equal(f.sent.at(-1).method,'browsingContext.captureScreenshot');
 });
}
for(const flag of [null,0,1,'false',[],{}]){
 test('screenshot rejects non-boolean scope '+JSON.stringify(flag)+' without native traffic',async t=>{
  const f=fixture(t),c=await f.open(),before=f.sent.length;
  await assert.rejects(f.command(c,'Page.captureScreenshot',{format:'png',captureBeyondViewport:flag}));
  assert.equal(f.sent.length,before);
 });
}
test('screenshot keeps explicit PNG and rejects every other option rather than silently dropping it',async t=>{
 const f=fixture(t),c=await f.open(),before=f.sent.length;
 for(const params of [{},{format:'jpeg'},{format:'png',quality:80},{format:'png',clip:{}},
  {format:'png',fromSurface:true},{format:'png',optimizeForSpeed:true},
  {format:'png',captureBeyondViewport:true,unknown:true}])await assert.rejects(f.command(c,'Page.captureScreenshot',params));
 assert.equal(f.sent.length,before);
});
for(const flag of [false,true]){
 test('screenshot '+flag+' cannot settle before its actual mocked native ACK',async t=>{
  const f=fixture(t),c=await f.open();f.replies.set('browsingContext.captureScreenshot',screenshotResult);
  f.hold.add('browsingContext.captureScreenshot');let settled=false;
  const result=f.command(c,'Page.captureScreenshot',{format:'png',captureBeyondViewport:flag}).finally(()=>{settled=true;});result.catch(()=>{});
  await flush();assert.equal(settled,false);
  const command=f.held.shift();assert.ok(command);assert.equal(command.method,'browsingContext.captureScreenshot');
  f.respond(command);assert.deepEqual(await result,screenshotResult);
  assert.equal(settled,true);
 });
 test('screenshot '+flag+' preserves the native failure without viewport fallback',async t=>{
  const f=fixture(t),c=await f.open();f.errors.set('browsingContext.captureScreenshot','unsupported operation');
  const before=f.sent.length;
  await assert.rejects(f.command(c,'Page.captureScreenshot',{format:'png',captureBeyondViewport:flag}),/^Error: unsupported operation$/);
  assert.equal(f.sent.length,before+1);assert.equal(f.sent.at(-1).method,'browsingContext.captureScreenshot');
 });
}
test('screenshot scope cannot admit an unowned context or revive a closed page',async t=>{
 const f=fixture(t),c=await f.open();let before=f.sent.length;
 await assert.rejects(f.command(c,'Page.captureScreenshot',{format:'png',captureBeyondViewport:true},'unowned-context'));
 assert.equal(f.sent.length,before);
 await f.close(c);before=f.sent.length;
 await assert.rejects(f.command(c,'Page.captureScreenshot',{format:'png',captureBeyondViewport:false}));
 assert.equal(f.sent.length,before);
});

const fulfillmentHeaders=[{name:'Access-Control-Allow-Origin',value:frontend},
 {name:'Access-Control-Allow-Methods',value:'GET, POST, OPTIONS'}];
async function optionsPause(f,c,request){
 await f.command(c,'Fetch.enable',{patterns:[{urlPattern:'*/matches/*',requestStage:'Request'}]});
 const event=networkEvent(c,request);event.request.method='OPTIONS';
 f.emit('network.beforeRequestSent',event);await flush();
 assert.equal(f.events.at(-1).params.requestId,request);
 assert.equal(f.events.at(-1).params.request.method,'OPTIONS');
}
const nativeFulfillmentHeaders=()=>fulfillmentHeaders.map(h=>({name:h.name,value:{type:'string',value:h.value}}));
test('bodyless 204 omits native body instead of manufacturing empty base64 bytes',async t=>{
 const f=fixture(t),c=await f.open();await optionsPause(f,c,'bodyless-204');
 const before=f.sent.length;
 await f.command(c,'Fetch.fulfillRequest',{requestId:'bodyless-204',responseCode:204,responseHeaders:fulfillmentHeaders});
 assert.equal(f.sent.length,before+1);assert.equal(f.sent.at(-1).method,'network.provideResponse');
 assert.deepEqual(f.sent.at(-1).params,{request:'bodyless-204',statusCode:204,headers:nativeFulfillmentHeaders()});
 assert.equal(Object.hasOwn(f.sent.at(-1).params,'body'),false);
 await f.command(c,'Fetch.disable');
 assert.equal(f.sent.filter(m=>m.method==='network.continueRequest'&&m.params.request==='bodyless-204').length,0);
});
for(const [responseCode,body] of [[200,'e30='],[204,''],[204,'e30=']]){
 test('supplied string body is forwarded unchanged for '+responseCode+' '+JSON.stringify(body),async t=>{
  const f=fixture(t),c=await f.open();await optionsPause(f,c,'supplied-body');
  await f.command(c,'Fetch.fulfillRequest',{requestId:'supplied-body',responseCode,body,responseHeaders:fulfillmentHeaders});
  assert.deepEqual(f.sent.at(-1).params,{request:'supplied-body',statusCode:responseCode,
   body:{type:'base64',value:body},headers:nativeFulfillmentHeaders()});
 });
}
test('bodyless exception cannot weaken old body, status or header type guards',async t=>{
 const f=fixture(t),c=await f.open();await optionsPause(f,c,'invalid-fulfillment');const before=f.sent.length;
 const base={requestId:'invalid-fulfillment',responseCode:200,responseHeaders:fulfillmentHeaders};
 for(const responseCode of [200,201,400]){
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{...base,responseCode}));
  // JSON compatibility transport omits undefined; for non-204 it must still reject.
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{...base,responseCode,body:undefined}));
 }
 for(const responseCode of [200,204])for(const body of [null,0,false,[],{}])
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{...base,responseCode,body}));
 for(const responseCode of [null,204.5,'204'])
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{...base,responseCode}));
 for(const responseHeaders of [undefined,null,'headers',{}])
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{...base,responseCode:204,responseHeaders}));
 assert.equal(f.sent.length,before);
});
for(const negative of [false,true]){
 test('bodyless 204 '+(negative?'negative':'positive')+' ACK remains pending for disable without duplicate commands',async t=>{
  const f=fixture(t),c=await f.open();await optionsPause(f,c,'pending-204');
  f.hold.add('network.provideResponse');let settled=false,disabled=false;
  const result=f.command(c,'Fetch.fulfillRequest',{requestId:'pending-204',responseCode:204,responseHeaders:fulfillmentHeaders}).finally(()=>{settled=true;});result.catch(()=>{});
  await flush();assert.equal(settled,false);
  const native=f.held.shift();assert.ok(native);assert.equal(native.method,'network.provideResponse');
  assert.equal(Object.hasOwn(native.params,'body'),false);
  const disable=f.command(c,'Fetch.disable').then(()=>{disabled=true;});disable.catch(()=>{});
  await flush();assert.equal(disabled,false);
  assert.equal(f.sent.filter(m=>m.method==='network.provideResponse').length,1);
  assert.equal(f.sent.filter(m=>m.method==='network.continueRequest'&&m.params.request==='pending-204').length,0);
  if(negative)f.errors.set('network.provideResponse','unsupported operation');
  f.respond(native);
  if(negative){
   await assert.rejects(result,/^Error: unsupported operation$/);await assert.rejects(disable,/^Error: unsupported operation$/);
   assert.equal(disabled,false);
  }else{await result;await disable;assert.equal(disabled,true);}
  assert.equal(settled,true);
  assert.equal(f.sent.filter(m=>m.method==='network.provideResponse').length,1);
 });
}
test('bodyless 204 cannot fulfill another page request, an unknown request or an already-resolved pause',async t=>{
 const f=fixture(t),c=await f.open(),other=await f.open();await optionsPause(f,other,'foreign-204');
 let before=f.sent.length;
 for(const requestId of ['foreign-204','missing-204'])
  await assert.rejects(f.command(c,'Fetch.fulfillRequest',{requestId,responseCode:204,responseHeaders:fulfillmentHeaders}));
 await assert.rejects(f.command(other,'Fetch.fulfillRequest',{requestId:'foreign-204',responseCode:204,responseHeaders:fulfillmentHeaders},'unowned-context'));
 assert.equal(f.sent.length,before);
 await optionsPause(f,c,'resolved-204');await f.command(c,'Fetch.continueRequest',{requestId:'resolved-204',interceptResponse:false});
 before=f.sent.length;
 await assert.rejects(f.command(c,'Fetch.fulfillRequest',{requestId:'resolved-204',responseCode:204,responseHeaders:fulfillmentHeaders}));
 assert.equal(f.sent.length,before);
});
