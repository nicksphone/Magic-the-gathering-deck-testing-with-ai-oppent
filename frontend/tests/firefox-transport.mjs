import {safeWireRow} from './firefox-wire-trace.mjs';
// Private file ABI only; caller must supply authentic, owned native events/replies.
// This is not a Firefox/CDP adapter or an App/native execution grant.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const hex=(v,n)=>typeof v==='string'&&new RegExp('^[0-9a-f]{'+n+'}$').test(v);
const decimal=v=>typeof v==='string'&&/^(0|[1-9][0-9]*)$/.test(v)&&v.length<=20;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const unavailable=()=>{throw Error('BODY_CACHE_UNAVAILABLE');};
const META=['schema_version','capture_id','run_nonce','episode','api_origin','frontend_origin','source_binding','enrollment_generation','native_top_context','method','status','raw_path_length','raw_path_sha256','raw_query_length','raw_query_sha256','body_length','body_sha256','producer_pid','producer_start','published_ns','expires_ns'];
const ACK=new Set(['network.continueResponse','network.failRequest','network.provideResponse']);
const publishers=new WeakSet();
function fingerprint(s){return [s.dev,s.ino,s.ctimeNs,s.size].join(':');}
function validFile(s){return s.isFile()&&s.nlink===1n&&s.uid===BigInt(process.getuid())&&(s.mode&0o777n)===0o600n;}

export function createGetter({directory,enrollment,producer,contexts,controller}) {
 if(typeof directory!=='string'||path.resolve(directory)!==directory||fs.realpathSync(directory)!==directory)unavailable();
 const root=fs.lstatSync(directory,{bigint:true});
 if(!root.isDirectory()||root.uid!==BigInt(process.getuid())||(root.mode&0o777n)!==0o700n)unavailable();
 if(!publishers.has(controller)||!enrollment||!hex(enrollment.run_nonce,32)||!hex(enrollment.source_binding,64)||!(contexts instanceof Set)||!contexts.size||!producer||!Number.isSafeInteger(producer.pid)||producer.pid<=0||!decimal(producer.start))unavailable();
 const expected={...enrollment};const ownedContexts=contexts,used=new Map(),active=new Map(),pending=new Map(),captured=new Map();let closed=false,cleanupDeferred=false;
 function checkRoot(){const s=fs.lstatSync(directory,{bigint:true});if(!s.isDirectory()||s.dev!==root.dev||s.ino!==root.ino||s.uid!==root.uid||(s.mode&0o777n)!==0o700n)unavailable();}
 function read(name,limit,identity){
  checkRoot();const file=path.join(directory,name),before=fs.lstatSync(file,{bigint:true});
  if(!validFile(before)||before.size>BigInt(limit)||(identity&&fingerprint(before)!==identity))unavailable();
  const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try{
   const opened=fs.fstatSync(fd,{bigint:true});if(!validFile(opened)||fingerprint(opened)!==fingerprint(before))unavailable();
   const bytes=fs.readFileSync(fd),after=fs.fstatSync(fd,{bigint:true}),leaf=fs.lstatSync(file,{bigint:true});
   if(bytes.length!==Number(opened.size)||fingerprint(after)!==fingerprint(opened)||fingerprint(leaf)!==fingerprint(opened)||!validFile(leaf))unavailable();
   return {bytes,identity:fingerprint(opened)};
  }finally{fs.closeSync(fd);}
 }
 function write(name,value,expiry){
  if(name.endsWith('.release')){
   checkRoot();const bytes=Buffer.from(JSON.stringify(value));if(bytes.length>4096)unavailable();
   const stage=name+'.next',stagePath=path.join(directory,stage),finalPath=path.join(directory,name);
   const fd=fs.openSync(stagePath,fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
   let owned,linked=false,removed=false;
   try{
    owned=fs.fstatSync(fd,{bigint:true});if(!validFile(owned))unavailable();
    fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);
    const final=fs.fstatSync(fd,{bigint:true});if(!validFile(final)||final.size!==BigInt(bytes.length))unavailable();
    const checked=read(stage,4096);if(checked.identity!==fingerprint(final)||!checked.bytes.equals(bytes))unavailable();
    checkRoot();if(process.hrtime.bigint()>=expiry)return false;
    // link is atomic and cannot replace an existing final name.
    fs.linkSync(stagePath,finalPath);linked=true;
    const staged=fs.lstatSync(stagePath,{bigint:true}),published=fs.lstatSync(finalPath,{bigint:true});
    if(!staged.isFile()||staged.nlink!==2n||staged.uid!==owned.uid||(staged.mode&0o777n)!==0o600n||staged.dev!==owned.dev||staged.ino!==owned.ino||staged.size!==BigInt(bytes.length)||fingerprint(staged)!==fingerprint(published))unavailable();
    fs.unlinkSync(stagePath);removed=true;
    // Producer may consume immediately now; no later final-inode assertion.
    return true;
   }finally{
    fs.closeSync(fd);
    if(!removed){
     checkRoot();const staged=fs.lstatSync(stagePath,{bigint:true});
     if(!owned||!staged.isFile()||staged.uid!==owned.uid||(staged.mode&0o777n)!==0o600n||staged.dev!==owned.dev||staged.ino!==owned.ino||staged.nlink!==(linked?2n:1n))unavailable();
     if(linked){const published=fs.lstatSync(finalPath,{bigint:true});if(fingerprint(published)!==fingerprint(staged))unavailable();fs.unlinkSync(finalPath);}
     fs.unlinkSync(stagePath);
    }
   }
  }
  checkRoot();const bytes=Buffer.from(JSON.stringify(value));if(bytes.length>4096)unavailable();
  const fd=fs.openSync(path.join(directory,name),fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  try{fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);const s=fs.fstatSync(fd,{bigint:true});if(!validFile(s)||s.size!==BigInt(bytes.length))unavailable();return fingerprint(s);}
  finally{fs.closeSync(fd);}
 }
 function prune(){const now=process.hrtime.bigint();for(const [id,expiry]of used)if(now>=expiry)used.delete(id);}
 function getResponseBody(event){
  const began=process.hrtime.bigint();prune();if(closed||active.size>=64)unavailable();
  const current=controller.current();if(!current)unavailable();
  if(!event||event.isBlocked!==true||!ownedContexts.has(event.context)||!controller.hasContext(event.context)||typeof event.context!=='string'||event.context.length>128||!event.request||typeof event.request.request!=='string'||!event.request.request||event.request.request.length>128||!event.response)unavailable();
  const headers=event.response.headers;if(!Array.isArray(headers))unavailable();
  const tags=headers.filter(h=>typeof h.name==='string'&&h.name.toLowerCase()==='x-release-test-capture-id');
  if(tags.length!==1||tags[0].value?.type!=='string'||!hex(tags[0].value.value,32))unavailable();
  const id=tags[0].value.value;if(used.has(id)||active.has(event.request.request))unavailable();
  const raw=event.request.url;if(typeof raw!=='string'||!/^[\x21-\x7e]+$/.test(raw))unavailable();
  let url;try{url=new URL(raw);}catch{unavailable();}
  if(url.href!==raw||url.origin!==expected.api_origin||url.username||url.password||url.hash||!raw.startsWith(expected.api_origin+'/'))unavailable();
  const rawSuffix=raw.slice(expected.api_origin.length),question=rawSuffix.indexOf('?');
  const rawPath=Buffer.from(question<0?rawSuffix:rawSuffix.slice(0,question),'ascii'),rawQuery=Buffer.from(question<0?'':rawSuffix.slice(question+1),'ascii');
  const record=read(id+'.json',4096);let m;try{m=JSON.parse(record.bytes.toString('utf8'));}catch{unavailable();}
  if(!m||Object.keys(m).sort().join('|')!==[...META].sort().join('|')||m.schema_version!==1||m.capture_id!==id)unavailable();
  // Producer writes one canonical, scalar-only JSON object; this also rejects
  // duplicate keys and malformed UTF-8 without a second JSON parser.
  if(JSON.stringify(Object.fromEntries(Object.keys(m).sort().map(k=>[k,m[k]])))!==record.bytes.toString('utf8'))unavailable();
  for(const field of ['run_nonce','api_origin','frontend_origin','source_binding'])if(m[field]!==expected[field])unavailable();
  if(m.episode!==current.episode||m.enrollment_generation!==current.generation||m.native_top_context!==current.native_top_context)unavailable();
  if(m.producer_pid!==producer.pid||m.producer_start!==producer.start||!Number.isInteger(m.status)||m.status<100||m.status>599||m.status!==event.response.status||m.method!==event.request.method||!['GET','POST','OPTIONS'].includes(m.method)||!Number.isInteger(m.body_length)||m.body_length<0||m.body_length>8*1024*1024||!hex(m.body_sha256,64)||!decimal(m.published_ns)||!decimal(m.expires_ns))unavailable();
  if(!Number.isInteger(m.raw_path_length)||!Number.isInteger(m.raw_query_length)||m.raw_path_length!==rawPath.length||m.raw_query_length!==rawQuery.length||m.raw_path_sha256!==hash(rawPath)||m.raw_query_sha256!==hash(rawQuery))unavailable();
  const published=BigInt(m.published_ns),expiry=BigInt(m.expires_ns),deadline=began+15_000_000_000n;
  if(expiry-published!==15_000_000_000n||began<published||began>=expiry)unavailable();
  const actualStart=fs.readFileSync('/proc/'+producer.pid+'/stat','utf8').split(')').at(-1).trim().split(/\s+/)[19];if(actualStart!==producer.start)unavailable();
  const claim={schema_version:1,kind:'response_body_claim',capture_id:id,run_nonce:m.run_nonce,episode:m.episode,native_context:event.context,native_request_id:event.request.request,response_status:m.status,body_sha256:m.body_sha256,source_binding:m.source_binding,enrollment_generation:m.enrollment_generation};
  const claimIdentity=write(id+'.claim',claim);used.set(id,expiry);
  const body=read(id+'.body',8*1024*1024);if(body.bytes.length!==m.body_length||hash(body.bytes)!==m.body_sha256||process.hrtime.bigint()>=expiry||process.hrtime.bigint()>=deadline)unavailable();
  // Recheck immutable metadata/claim after the final body hash before returning.
  read(id+'.json',4096,record.identity);read(id+'.claim',4096,claimIdentity);
  if(process.hrtime.bigint()>=expiry||process.hrtime.bigint()>=deadline)unavailable();
  const still=controller.current();if(!still||still.generation!==current.generation||still.native_top_context!==current.native_top_context)unavailable();
  active.set(event.request.request,{id,claim,claimIdentity,metadataIdentity:record.identity,bodyIdentity:body.identity,expiry,cancelled:false});
  // Evidence only: never confer authority from the earlier used/claim state.
  captured.set(id,Object.freeze({captureId:id,metadataIdentity:record.identity,producerPid:producer.pid,producerStart:producer.start,runNonce:expected.run_nonce,sourceBinding:expected.source_binding,rootDev:root.dev,rootIno:root.ino,rootUID:root.uid,releasePublished:false}));
  if(captured.size>64)captured.delete(captured.keys().next().value);
  return {body:body.bytes.toString('base64'),base64Encoded:true};
 }
 function recordCommand(command){
  if(closed||!command||!ACK.has(command.method)||!Number.isSafeInteger(command.id)||command.id<=0||pending.has(command.id)||pending.size>=64)unavailable();
  const request=command.params?.request,e=active.get(request),current=controller.current();if(!e||e.cancelled||!current||current.generation!==e.claim.enrollment_generation)unavailable();
  pending.set(command.id,{id:command.id,method:command.method,request,entry:e});
 }
 function acceptReply(reply){
  if(closed||!reply||!Number.isSafeInteger(reply.id))unavailable();const sent=pending.get(reply.id);if(!sent)unavailable();pending.delete(reply.id);
  if(reply.type!=='success'||reply.result===null||typeof reply.result!=='object'||Array.isArray(reply.result)||sent.entry.cancelled||active.get(sent.request)!==sent.entry)unavailable();
  const e=sent.entry;
  function expiredLeaf(error,suffixes){
   if(error.code!=='ENOENT'||process.hrtime.bigint()<e.expiry||!suffixes.some(suffix=>error.path===path.join(directory,e.id+suffix)))throw error;
   checkRoot();const parent=fs.lstatSync(directory,{bigint:true});
   if(parent.nlink!==root.nlink||fs.realpathSync(directory)!==directory)unavailable();
   cleanupDeferred=true;
  }
  if(process.hrtime.bigint()<e.expiry){
   let missing=false;
   try{read(e.id+'.body',8*1024*1024,e.bodyIdentity);read(e.id+'.json',4096,e.metadataIdentity);read(e.id+'.claim',4096,e.claimIdentity);}
   catch(error){expiredLeaf(error,['.body','.json','.claim']);missing=true;}
   if(!missing){
    if(process.hrtime.bigint()>=e.expiry){cleanupDeferred=true;}
    else{
     // Opening/writing errors are never classified as producer expiry.
     const published=write(e.id+'.release',{...e.claim,kind:'native_ack_release',ack_method:sent.method,ack_command_id:sent.id},e.expiry);
     if(published&&captured.has(e.id))captured.set(e.id,Object.freeze({...captured.get(e.id),releasePublished:true}));
     if(!published||process.hrtime.bigint()>=e.expiry){
      checkRoot();const parent=fs.lstatSync(directory,{bigint:true});
      if(parent.nlink!==root.nlink||fs.realpathSync(directory)!==directory)unavailable();
      cleanupDeferred=true; // Producer alone owns cleanup of a published receipt.
     }
    }
   }
  }else{
   // Retrieval TTL cannot shorten an already-returned body's original command
   // clock. Never recreate expired IPC or claim producer closure from this ACK.
   checkRoot();if(fs.lstatSync(directory,{bigint:true}).nlink!==root.nlink||fs.realpathSync(directory)!==directory)unavailable();
   cleanupDeferred=true;
  }
  active.delete(sent.request);return true;
 }
 function cancel(request){const e=active.get(request);if(e)e.cancelled=true;for(const [id,s]of pending)if(s.request===request)pending.delete(id);active.delete(request);}
 function cacheLeafProof(file){
  if(closed||typeof file!=='string'||path.dirname(file)!==directory)return null;
  const match=/^([0-9a-f]{32})\.(body|json|claim|release(?:\.next)?)$/.exec(path.basename(file));
  const proof=match&&captured.get(match[1]);if(!proof||(match[2].startsWith('release')&&!proof.releasePublished))return null;
  checkRoot();return proof;
 }
 function close(){closed=true;pending.clear();active.clear();captured.clear();} // Producer alone cleans authenticated IPC files.
 return {getResponseBody,recordCommand,acceptReply,cancel,close,cacheLeafProof,get cleanupDeferred(){return cleanupDeferred;}};
}

// Sole control-plane publisher. Native commands/replies are supplied unchanged
// by the pinned transport; no browser command, timer or listener is created here.
export function createEnrollment({directory,runNonce,sourceBinding,apiOrigin,frontendOrigin}) {
 if(runNonce===undefined)runNonce=crypto.randomBytes(16).toString('hex');
 if(!hex(runNonce,32)||!hex(sourceBinding,64)||apiOrigin===frontendOrigin)unavailable();
 for(const origin of [apiOrigin,frontendOrigin]){let u;try{u=new URL(origin);}catch{unavailable();}if(u.origin!==origin||u.protocol!=='http:'||u.hostname!=='127.0.0.1'||!u.port||u.username||u.password)unavailable();}
 if(typeof directory!=='string'||path.resolve(directory)!==directory||fs.realpathSync(directory)!==directory)unavailable();
 const root=fs.lstatSync(directory,{bigint:true});if(!root.isDirectory()||root.uid!==BigInt(process.getuid())||(root.mode&0o777n)!==0o700n)unavailable();
 const start=fs.readFileSync('/proc/self/stat','utf8').split(')').at(-1).trim().split(/\s+/)[19];if(!decimal(start)||!Number.isSafeInteger(Number(start)))unavailable();
 const budgets={'human_vs_human':900000,'player_vs_ai':1200000,'player_vs_ai-seat2':1200000};
 const sequence=Object.keys(budgets),sent=new Map(),children=new Map();let completed=0,generation=0,armed=null,currentRecord=null,publishedIdentity=null,stagingIdentity=null,broken=false,closed=false;
 function checkRoot(){const s=fs.lstatSync(directory,{bigint:true});if(!s.isDirectory()||s.dev!==root.dev||s.ino!==root.ino||s.uid!==root.uid||(s.mode&0o777n)!==0o700n)unavailable();}
 function leaf(name){try{return fs.lstatSync(path.join(directory,name),{bigint:true});}catch(e){if(e.code==='ENOENT')return null;throw e;}}
 function publish(enabled){
  checkRoot();if(generation>=6||broken||!armed)unavailable();
  const old=leaf('enrollment.json');if((old&&!publishedIdentity)||(!old&&publishedIdentity)||(old&&fingerprint(old)!==publishedIdentity)||leaf('enrollment.next'))unavailable();
  const record={schema_version:1,generation:generation+1,enabled,episode:armed.episode,run_nonce:runNonce,source_binding:sourceBinding,api_origin:apiOrigin,frontend_origin:frontendOrigin,publisher_uid:process.getuid(),pid:process.pid,start_ticks:Number(start),native_top_context:enabled?armed.context:null,armed_ns:armed.at.toString(),expires_ns:armed.expiry.toString()};
  const data=Buffer.from(JSON.stringify(record));if(data.length>4096)unavailable();
  const fd=fs.openSync(path.join(directory,'enrollment.next'),fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  try{fs.writeFileSync(fd,data);fs.fsyncSync(fd);const s=fs.fstatSync(fd,{bigint:true});if(!validFile(s)||s.size!==BigInt(data.length))unavailable();stagingIdentity=fingerprint(s);}finally{fs.closeSync(fd);}
  try{
   const staged=leaf('enrollment.next');if(!staged||!validFile(staged)||fingerprint(staged)!==stagingIdentity)unavailable();
   fs.renameSync(path.join(directory,'enrollment.next'),path.join(directory,'enrollment.json'));
   const actual=leaf('enrollment.json');if(!actual||!validFile(actual)||actual.dev!==staged.dev||actual.ino!==staged.ino||actual.size!==staged.size)unavailable();
   publishedIdentity=fingerprint(actual);stagingIdentity=null;
   const dirfd=fs.openSync(directory,fs.constants.O_RDONLY|fs.constants.O_DIRECTORY|fs.constants.O_NOFOLLOW);try{fs.fsyncSync(dirfd);}finally{fs.closeSync(dirfd);}
   generation++;currentRecord=record;
  }catch(e){broken=true;currentRecord=null;throw e;}
 }
 function current(){if(closed||broken||!armed||!currentRecord?.enabled||process.hrtime.bigint()>=armed.expiry)return null;return {...currentRecord};}
 function withEnrolledBodyEpisode(episode,thunk){
  if(closed||broken||armed||episode!==sequence[completed]||typeof thunk!=='function')unavailable();
  const at=process.hrtime.bigint();armed={episode,at,expiry:at+BigInt(budgets[episode])*1_000_000n,context:null,activated:false};currentRecord=null;children.clear();sent.clear();
  return (async()=>{
   let value,primary,cleanup,failed=false;
   try{value=await thunk();if(!armed.activated)unavailable();}catch(e){primary=e;failed=true;}
   finally{
    // Revoke synchronously before atomic disabled publication, even when the
    // original Promise.race returned while its helper promise remains pending.
    currentRecord=null;
    try{publish(false);}catch(e){cleanup=e;broken=true;}
    armed=null;sent.clear();children.clear();completed++;
   }
   if(failed){if(cleanup&&primary&&typeof primary==='object')primary.enrollmentCleanupUnavailable=true;throw primary;}
   if(cleanup)throw cleanup;return value;
  })();
 }
 function recordCommand(command){
  if(!armed||broken||closed||process.hrtime.bigint()>=armed.expiry||!Number.isSafeInteger(command?.id)||command.id<=0||sent.has(command.id)||sent.size>=64)unavailable();
  if(command.method==='browsingContext.create'){
   if(armed.context||command.params?.type!=='tab')unavailable();
  }else if(command.method==='network.addIntercept'){
   const p=command.params;if(!armed.context||currentRecord?.enabled||!p||!Array.isArray(p.contexts)||p.contexts.length!==1||p.contexts[0]!==armed.context||JSON.stringify(p.phases)!==JSON.stringify(['beforeRequestSent','responseStarted']))unavailable();
  }else unavailable();
  sent.set(command.id,{id:command.id,method:command.method,context:armed.context,episode:armed.episode});
 }
 function acceptReply(reply){
  const command=sent.get(reply?.id);if(!command)unavailable();sent.delete(reply.id);
  if(!armed||broken||closed||process.hrtime.bigint()>=armed.expiry||command.episode!==armed.episode||reply.type!=='success'||!reply.result||typeof reply.result!=='object')unavailable();
  if(command.method==='browsingContext.create'){
   const context=reply.result.context;if(typeof context!=='string'||!context||context.length>128||armed.context)unavailable();armed.context=context;
  }else{
   if(command.context!==armed.context||typeof reply.result.intercept!=='string'||!reply.result.intercept)unavailable();publish(true);armed.activated=true;
  }
  return reply.result; // Original caller still receives only the native result.
 }
 function contextCreated(event){
  if(!current()||typeof event?.context!=='string'||!event.context||event.context.length>128||event.context===armed.context||children.has(event.context)||children.size>=16||!(event.parent===armed.context||children.has(event.parent)))unavailable();children.set(event.context,event.parent);
 }
 function hasContext(context){return !!current()&&(context===armed.context||children.has(context));}
 function close(){
  if(armed)unavailable();closed=true;checkRoot();
  for(const [name,identity]of [['enrollment.next',stagingIdentity],['enrollment.json',publishedIdentity]]){
   const s=leaf(name);if(s){if(!identity||!validFile(s)||fingerprint(s)!==identity)unavailable();fs.unlinkSync(path.join(directory,name));}
   else if(identity)unavailable();
  }
  publishedIdentity=null;stagingIdentity=null;
 }
 const publisher={withEnrolledBodyEpisode,recordCommand,acceptReply,contextCreated,hasContext,current,close,get isArmed(){return !!armed&&!closed&&!broken;},bindings:Object.freeze({run_nonce:runNonce,source_binding:sourceBinding,api_origin:apiOrigin,frontend_origin:frontendOrigin})};
 publishers.add(publisher);return publisher;
}

// Private original-driver ABI hookup. Only actual BiDi wire replies are native
// receipts; translated CDP-shaped results are compatibility values, not receipts.
export function createFirefoxTransport({controller,directory,endpoint,producer,observe=()=>{},pageOrigins=[controller?.bindings?.frontend_origin],socketFactory=url=>new WebSocket(url)}) {
 if(!publishers.has(controller)||typeof producer!=='function'||typeof socketFactory!=='function'||typeof observe!=='function')unavailable();
 if(!Array.isArray(pageOrigins)||!pageOrigins.includes(controller.bindings.frontend_origin)||pageOrigins.length>2||new Set(pageOrigins).size!==pageOrigins.length)unavailable();
 const ownedPageOrigins=new Set(pageOrigins);for(const origin of ownedPageOrigins){const u=new URL(origin);if(u.origin!==origin||u.protocol!=='http:'||u.hostname!=='127.0.0.1'||!u.port||u.username||u.password||origin===controller.bindings.api_origin)unavailable();}
 const parsed=new URL(endpoint);if(parsed.protocol!=='ws:'||parsed.hostname!=='127.0.0.1'||!parsed.port||parsed.pathname!=='/session'||parsed.search||parsed.hash||parsed.username||parsed.password||parsed.href!==endpoint)unavailable();
 const channels=new Map(),pending=new Map();let wire,opening,sequence=0,stopped=false,failure,cleanupDeferred=false,observerFailed=false;
 function record(row){try{observe(safeWireRow(row));}catch{observerFailed=true;}}
 function healthy(){if(stopped)unavailable();if(failure)throw failure;}
 function fatal(error){failure??=error;for(const [id,w]of pending){pending.delete(id);clearTimeout(w.timer);w.reject(error);}}
 function native(method,params={},receipt,until,registration){
  healthy();if(!wire||wire.readyState!==1||pending.size>=64)unavailable();
  const remaining=until===undefined?15000:Number((until-process.hrtime.bigint())/1000000n);if(remaining<=0)throw Error('Firefox original command deadline exhausted');
  const command={id:++sequence,method,params};if(receipt)receipt.recordCommand(command);
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{pending.delete(command.id);if(receipt?.cancel&&params.request)receipt.cancel(params.request);reject(Error('Firefox command timed out: '+method));},Math.min(15000,remaining));
   pending.set(command.id,{resolve,reject,timer,receipt,command,registration});
   try{record({kind:'native-command',id:command.id,method});wire.send(JSON.stringify(command));}catch(error){record({kind:'wire-send-error',pending:[{id:command.id,method}]});pending.delete(command.id);clearTimeout(timer);if(receipt?.cancel&&params.request)receipt.cancel(params.request);reject(error);}
  });
 }
 function bytes(value){if(value?.type==='string'&&typeof value.value==='string')return Buffer.from(value.value);if(value?.type==='base64'&&typeof value.value==='string'&&Buffer.from(value.value,'base64').toString('base64')===value.value)return Buffer.from(value.value,'base64');unavailable();}
 function decoded(value){
  if(!value||typeof value.type!=='string')unavailable();
  if(value.type==='undefined')return undefined;if(value.type==='null')return null;
  if(value.type==='string'&&typeof value.value==='string'||value.type==='boolean'&&typeof value.value==='boolean')return value.value;
  if(value.type==='number'){if(typeof value.value==='number')return value.value;if(value.value==='NaN')return NaN;if(value.value==='-0')return -0;if(value.value==='Infinity')return Infinity;if(value.value==='-Infinity')return -Infinity;}
  if(value.type==='array'&&Array.isArray(value.value))return value.value.map(decoded);
  if(value.type==='object'&&Array.isArray(value.value)){const result={};for(const pair of value.value){if(!Array.isArray(pair)||pair.length!==2)unavailable();const key=typeof pair[0]==='string'?pair[0]:decoded(pair[0]);if(typeof key!=='string'||Object.hasOwn(result,key))unavailable();Object.defineProperty(result,key,{value:decoded(pair[1]),enumerable:true,writable:true,configurable:true});}return result;}
  throw Error('Unsupported Firefox by-value result: '+value.type);
 }
 function channelFor(context){for(const channel of channels.values())if(channel.contexts.has(context))return channel;return null;}
 async function ensureWire(){
  healthy();if(opening)return opening;
  opening=(async()=>{
   wire=socketFactory(endpoint);
   if(wire.readyState!==1)await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Firefox WebSocket connection timed out')),15000);wire.onopen=()=>{record({kind:'wire-open'});clearTimeout(timer);resolve();};wire.onerror=()=>{record({kind:'wire-error'});clearTimeout(timer);reject(Error('Firefox WebSocket connection failed'));};});
   wire.onmessage=({data})=>{
    try{
     const message=JSON.parse(data);
     if(message.type==='event'){record({kind:'native-event',method:message.method,blocked:message.params?.isBlocked,status:message.params?.response?.status});}
     else record({kind:'native-reply',id:message.id,type:message.type,resultType:message.result?.type,errorCode:message.error});
     if(message.type==='event'){void event(message).catch(fatal);return;}
     const waiter=pending.get(message.id);if(!waiter)return;pending.delete(message.id);clearTimeout(waiter.timer);
     if(message.type!=='success'||!message.result||typeof message.result!=='object'||Array.isArray(message.result)){
      try{waiter.receipt?.acceptReply(message);}catch{/* Original native error remains the command error. */}
      const error=Error(message.error??'Firefox native protocol error');error.nativeCode=message.error;waiter.reject(error);return;
     }
     try{waiter.receipt?.acceptReply(message);waiter.registration?.(Object.freeze({id:waiter.command.id,method:waiter.command.method,params:Object.freeze(Object.fromEntries(Object.entries(waiter.command.params).map(([key,value])=>[key,Array.isArray(value)?Object.freeze([...value]):value])))}),message.result);cleanupDeferred ||= waiter.receipt?.cleanupDeferred===true;waiter.resolve(message.result);}catch(error){waiter.reject(error);}
    }catch(error){fatal(error);}
   };
   wire.onclose=event=>{record({kind:'wire-close',code:event?.code,wasClean:event?.wasClean,reason:event?.reason,stopped,pending:[...pending.values()].map(w=>({id:w.command.id,method:w.command.method}))});if(!stopped)fatal(Error('Firefox native transport closed'));};wire.onerror=()=>{record({kind:'wire-error',pending:[...pending.values()].map(w=>({id:w.command.id,method:w.command.method}))});fatal(Error('Firefox native transport failed'));};
   const session=await native('session.new',{capabilities:{alwaysMatch:{}}});
   if(session.capabilities?.browserName!=='firefox'||!session.capabilities?.browserVersion?.startsWith('158.'))unavailable();
   const subscription=await native('session.subscribe',{events:['browsingContext.contextCreated','browsingContext.contextDestroyed','network.beforeRequestSent','network.responseStarted','network.responseCompleted','network.fetchError']});
   if(typeof subscription.subscription!=='string'||!subscription.subscription)unavailable();
   return Object.freeze({protocol:'webdriver-bidi',browserName:session.capabilities.browserName,browserVersion:session.capabilities.browserVersion,subscription:subscription.subscription});
  })();
  return opening;
 }
 async function postData(channel,event,until){
  const request=event.request.request;let held=channel.requests.get(request);if(!held)unavailable();
  if(!held.post){if(!channel.collector)unavailable();held.post=(async()=>bytes((await native('network.getData',{request,dataType:'request',collector:channel.collector,disown:true},undefined,until)).bytes))();}
  return held.post;
 }
 function matches(pattern,url,stage){if(pattern.requestStage!==stage)return false;const expression=pattern.urlPattern??'*';if(typeof expression!=='string')unavailable();return new RegExp('^'+expression.split('*').map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$').test(url);}
 function options(params,keys){if(!params||typeof params!=='object'||Array.isArray(params)||Object.keys(params).some(k=>!keys.includes(k)))throw Error('Unsupported Firefox command options');}
 function fetchPatterns(params){
  options(params,['patterns']);
  if(!Array.isArray(params.patterns)||!params.patterns.length||params.patterns.length>64)unavailable();
  return params.patterns.map(p=>{options(p,['urlPattern','requestStage']);const stage=p.requestStage??'Request';if(!['Request','Response'].includes(stage)||typeof p.urlPattern!=='string'||p.urlPattern.length>4096)unavailable();return {urlPattern:p.urlPattern,requestStage:stage};});
 }
 // A request has one native terminal/continuation command in flight. Disable
 // joins that actual ACK, never fabricating a receipt or sending a second one.
 async function resolveRequest(channel,held,method,params,until){
  if(held.pending)throw Error('Firefox request command already pending');
  if(!held.blocked)throw Error('Firefox request is not blocked');
  const event=held.event;
  const command=native(method,params,ACK.has(method)?held.getter:undefined,until).then(result=>{
   if(held.event===event){held.blocked=false;if(method!=='network.continueRequest')channel.requests.delete(params.request);}
   return result;
  });
  held.pending=command;
  try{return await command;}finally{if(held.pending===command)held.pending=null;}
 }
 async function disableFetch(channel,until){
  channel.patterns=[];channel.initialization=null;channel.readyChildren.clear();
  async function drain(){
   for(const [request,held]of channel.requests){
    held.responseWanted=false;
    while(held.pending)await held.pending;
    if(held.blocked&&held.owner==='fetch')await resolveRequest(channel,held,held.event.response?'network.continueResponse':'network.continueRequest',{request},until);
   }
  }
  await drain();
  for(const id of [...channel.intercepts]){await native('network.removeIntercept',{intercept:id},undefined,until);channel.intercepts.splice(channel.intercepts.indexOf(id),1);}
  await drain(); // Events already received while native removal was pending.
 }
 async function event(message){
  const e=message.params;
  if(message.method==='browsingContext.contextCreated'){
   const channel=channelFor(e.parent);if(!channel)return;
   if(channel.contexts.size>=17||channel.contexts.has(e.context)||typeof e.context!=='string'||!e.context)unavailable();
   channel.contexts.add(e.context);if(controller.current()?.native_top_context===channel.id)controller.contextCreated(e);
   if(channel.registering)channel.earlyChild=true;
   if(channel.initialization){const readiness=Object.freeze({context:e.context,parent:e.parent,top:channel.id,generation:channel.initialization.generation,initializationReady:true});channel.readyChildren.set(e.context,readiness);channel.childInitialized?.(readiness);}
   return;
  }
  const channel=channelFor(e?.context);if(!channel)return;
  if(message.method==='browsingContext.contextDestroyed'){channel.contexts.delete(e.context);channel.readyChildren.delete(e.context);channel.childDestroyed?.(e.context);if(e.context===channel.id)channel.initialization=null;return;}
  if(!message.method.startsWith('network.')||!e.request||typeof e.request.request!=='string')return;
  const request=e.request.request;
  if(message.method==='network.fetchError'){channel.requests.get(request)?.getter?.cancel(request);channel.requests.delete(request);return;}
  if(message.method==='network.responseCompleted'){channel.requests.delete(request);return;}
  if(!['network.beforeRequestSent','network.responseStarted'].includes(message.method)||e.isBlocked!==true)return;
  // Never continue/fail a pause owned solely by another native intercept.
  if(Array.isArray(e.intercepts)&&!e.intercepts.some(id=>channel.intercepts.includes(id)||id===channel.blockIntercept))return;
  let held=channel.requests.get(request);if(!held){if(channel.requests.size>=64)unavailable();held={responseWanted:false};channel.requests.set(request,held);}held.event=e;
  held.blocked=true;
  const configuration=channel.patterns; // Array identity is the configuration generation.
  // Native phase events can precede the prior phase's command reply.
  while(held.pending)await held.pending;
  if(channel.requests.get(request)!==held||held.event!==e||!held.blocked)return;
  const response=message.method==='network.responseStarted';
  if(!response&&channel.blockIntercept&&channel.blockedURLs.some(urlPattern=>matches({urlPattern,requestStage:'Request'},e.request.url,'Request'))){
   held.owner='block';await resolveRequest(channel,held,'network.failRequest',{request});return;
  }
  const selected=channel.patterns===configuration&&(channel.patterns.some(p=>matches(p,e.request.url,response?'Response':'Request'))||(response&&held.responseWanted));
  held.owner='fetch';
  if(!selected){await resolveRequest(channel,held,response?'network.continueResponse':'network.continueRequest',{request});return;}
  const headers={};for(const h of e.request.headers){const name=h.name.toLowerCase();if(Object.hasOwn(headers,name))unavailable();headers[name]=bytes(h.value).toString('utf8');}
  const translated={requestId:request,networkId:request,request:{url:e.request.url,method:e.request.method,headers},resourceType:e.request.destination==='image'?'Image':e.request.destination==='document'?'Document':'Other',...(response?{responseStatusCode:e.response.status,responseHeaders:e.response.headers.map(h=>({name:h.name,value:bytes(h.value).toString('utf8')}))}:{})};
  if(e.request.method==='POST'&&e.request.bodySize!==0)translated.request.postData=(await postData(channel,e)).toString('utf8');
  while(held.pending)await held.pending;
  if(channel.requests.get(request)!==held||held.event!==e||!held.blocked)return;
  if(channel.patterns!==configuration){await resolveRequest(channel,held,response?'network.continueResponse':'network.continueRequest',{request});return;}
  if(!channel.patterns.length&&!held.responseWanted)return; // Disable owns the pending drain.
  channel.emit({method:'Fetch.requestPaused',params:translated,...(e.context!==channel.id?{sessionId:e.context}:{})});
 }
 async function open(url){
  healthy();const u=new URL(url);if(!ownedPageOrigins.has(u.origin)&&u.protocol!=='about:')throw Error('Outside owned Firefox page origin');if(u.protocol==='about:'&&url!=='about:blank')unavailable();
  await ensureWire();if(channels.size>=16)unavailable();
  const created=await native('browsingContext.create',{type:'tab'},controller.isArmed?controller:undefined);
  if(typeof created.context!=='string'||!created.context||channels.has(created.context))unavailable();
  const channel={id:created.context,contexts:new Set([created.context]),requests:new Map(),patterns:[],intercepts:[],getters:new Map(),collector:null,initialization:null,registering:false,earlyChild:false,generation:0,readyChildren:new Map(),subscriptions:[],childInitialized:null,childDestroyed:null,onmessage:null,emit(message){channel.onmessage?.({data:JSON.stringify(message)});},assertHealthy:healthy};
  Object.assign(channel,{blockIntercept:null,blockedURLs:[],preloads:[],configuring:false,closing:false});
  channels.set(channel.id,channel);
  function validateChildInitialized(readiness){
   healthy();if(!channel.initialization||channel.readyChildren.get(readiness?.context)!==readiness||readiness.generation!==channel.initialization.generation||!channel.contexts.has(readiness.context))unavailable();return readiness;
  }
  function onChildInitialized(callback,destroyed){if(channel.childInitialized||typeof callback!=='function'||destroyed!==undefined&&typeof destroyed!=='function')unavailable();channel.childInitialized=callback;channel.childDestroyed=destroyed;}
  async function armFutureChildren(patterns){
   healthy();if(channel.initialization||channel.registering||channel.generation||channel.contexts.size!==1||!Array.isArray(patterns)||!patterns.length||patterns.some(p=>!['Request','Response'].includes(p.requestStage)||typeof p.urlPattern!=='string'))unavailable();
   const until=process.hrtime.bigint()+15_000_000_000n,registrations={};channel.registering=true;channel.generation++;
   const noChildren=async()=>{const tree=await native('browsingContext.getTree',{root:channel.id},undefined,until);if(!Array.isArray(tree.contexts)||tree.contexts.length!==1||tree.contexts[0].context!==channel.id||!Array.isArray(tree.contexts[0].children)||tree.contexts[0].children.length||channel.contexts.size!==1||channel.earlyChild)unavailable();};
   async function register(kind,method,params){return native(method,params,undefined,until,(ack,result)=>{
    if(method==='session.subscribe'){if(typeof result.subscription!=='string'||!result.subscription)unavailable();channel.subscriptions.push(result.subscription);}
    if(method==='network.addDataCollector'){if(typeof result.collector!=='string'||!result.collector)unavailable();channel.collector=result.collector;}
    if(method==='network.addIntercept'){if(typeof result.intercept!=='string'||!result.intercept)unavailable();channel.intercepts.push(result.intercept);}
    registrations[kind]=ack;
   });}
   try{
    await noChildren();
    await register('network','session.subscribe',{events:['network.beforeRequestSent','network.responseStarted','network.responseCompleted','network.fetchError'],contexts:[channel.id]});
    await register('lifecycle','session.subscribe',{events:['browsingContext.load','browsingContext.domContentLoaded'],contexts:[channel.id]});
    await register('contexts','session.subscribe',{events:['browsingContext.contextCreated','browsingContext.contextDestroyed'],contexts:[channel.id]});
    if(channel.collector){await native('network.removeDataCollector',{collector:channel.collector},undefined,until);channel.collector=null;}
    await register('collector','network.addDataCollector',{dataTypes:['request'],maxEncodedDataSize:8*1024*1024,collectorType:'blob',contexts:[channel.id]});
    channel.patterns=structuredClone(patterns);
    await register('intercept','network.addIntercept',{contexts:[channel.id],phases:['beforeRequestSent','responseStarted']});
    await noChildren();
    channel.initialization=Object.freeze({top:channel.id,generation:channel.generation,initializationReady:true,registrations:Object.freeze(registrations)});
    return channel.initialization;
   }finally{channel.registering=false;}
  }
  async function mapped(method,params={},context=channel.id,until){
   const sendNative=(method,params,receipt)=>native(method,params,receipt,until);
   healthy();if(channel.closing||!channels.has(channel.id)||!channel.contexts.has(context))unavailable();
   if(['Fetch.enable','Fetch.disable','Network.setBlockedURLs','Page.addScriptToEvaluateOnNewDocument'].includes(method)){
    if(context!==channel.id||channel.configuring||channel.registering)unavailable();
    channel.configuring=true;
    try{
     if(method==='Fetch.disable'){options(params,[]);await disableFetch(channel,until);return {};}
     if(method==='Network.setBlockedURLs'){
      options(params,['urls']);const urls=params.urls;
      if(!Array.isArray(urls)||urls.length>64||urls.some(s=>typeof s!=='string'||!s.length||s.length>4096||!/^[\x21-\x7e]+$/.test(s)))unavailable();
      if(urls.length&&!channel.blockIntercept){
       await native('network.addIntercept',{contexts:[channel.id],phases:['beforeRequestSent']},undefined,until,(_ack,result)=>{if(typeof result.intercept!=='string'||!result.intercept)unavailable();channel.blockIntercept=result.intercept;channel.blockedURLs=[...urls];});
      }else if(!urls.length&&channel.blockIntercept){
       await sendNative('network.removeIntercept',{intercept:channel.blockIntercept});channel.blockIntercept=null;channel.blockedURLs=[];
      }else channel.blockedURLs=[...urls];
      return {};
     }
     if(method==='Page.addScriptToEvaluateOnNewDocument'){
      options(params,['source']);if(typeof params.source!=='string'||channel.preloads.length>=64)unavailable();
      const result=await native('script.addPreloadScript',{functionDeclaration:`() => {\n${params.source}\n}`,contexts:[channel.id]},undefined,until,(_ack,result)=>{if(typeof result.script!=='string'||!result.script)unavailable();channel.preloads.push(result.script);});
      return {identifier:result.script};
     }
     const normalized=fetchPatterns(params);
     if(channel.intercepts.length>=64)unavailable();
     const result=await native('network.addIntercept',{contexts:[channel.id],phases:['beforeRequestSent','responseStarted']},controller.isArmed&&!controller.current()?controller:undefined,until,(_ack,result)=>{if(typeof result.intercept!=='string'||!result.intercept)unavailable();channel.intercepts.push(result.intercept);channel.patterns=normalized;});
     return result;
    }finally{channel.configuring=false;}
   }
   if(method==='Page.navigate'){
    options(params,['url']);if(typeof params.url!=='string')unavailable();
    const url=new URL(params.url);if(url.username||url.password||!ownedPageOrigins.has(url.origin)&&params.url!=='about:blank')throw Error('Outside owned Firefox page origin');
    const result=await sendNative('browsingContext.navigate',{context,url:params.url,wait:'none'});
    if(result.navigation!==null&&(typeof result.navigation!=='string'||!result.navigation))unavailable();
    return {frameId:context,...(result.navigation===null?{}:{loaderId:result.navigation})};
   }
   if(method==='Page.bringToFront'){options(params,[]);if(context!==channel.id)unavailable();return sendNative('browsingContext.activate',{context});}
   if(method==='Network.enable'){
    if(!channel.collector){const result=await sendNative('network.addDataCollector',{dataTypes:['request'],maxEncodedDataSize:8*1024*1024,collectorType:'blob',contexts:[channel.id]});if(typeof result.collector!=='string'||!result.collector)unavailable();channel.collector=result.collector;}
    return sendNative('session.subscribe',{events:['network.beforeRequestSent','network.responseStarted','network.responseCompleted','network.fetchError'],contexts:[channel.id]});
   }
   if(method==='Page.enable'||method==='Page.setLifecycleEventsEnabled')return sendNative('session.subscribe',{events:['browsingContext.load','browsingContext.domContentLoaded'],contexts:[channel.id]});
   if(method==='Target.setAutoAttach'){
    const error=Error('FIREFOX_CAPABILITY_HOLD: owned iframe pause before initialization is not proved');error.code='FIREFOX_CAPABILITY_HOLD';throw error;
   }
   if(method==='Page.getFrameTree'){
    const result=await sendNative('browsingContext.getTree',{root:context});if(!Array.isArray(result.contexts)||result.contexts.length!==1)unavailable();
    const tree=c=>({frame:{id:c.context,url:c.url},...(c.children?.length?{childFrames:c.children.map(tree)}:{})});return {frameTree:tree(result.contexts[0])};
   }
   if(method==='Page.reload')return sendNative('browsingContext.reload',{context,...(params.ignoreCache===undefined?{}:{ignoreCache:params.ignoreCache}),wait:'none'});
   if(method==='Page.captureScreenshot'){
    if(params.format!=='png'||Object.keys(params).some(k=>!['format','captureBeyondViewport'].includes(k))||Object.hasOwn(params,'captureBeyondViewport')&&typeof params.captureBeyondViewport!=='boolean')throw Error('Unsupported Firefox screenshot options');
    return sendNative('browsingContext.captureScreenshot',{context,origin:params.captureBeyondViewport===true?'document':'viewport',format:{type:'image/png'}});
   }
   if(method==='Runtime.evaluate'){
    if(params.awaitPromise!==true||params.returnByValue!==true)throw Error('Unsupported Firefox evaluation options');
    let result;try{result=await sendNative('script.evaluate',{expression:params.expression,target:{context},awaitPromise:true,resultOwnership:'none',serializationOptions:{maxObjectDepth:null}});}catch(error){if(['no such frame','no such realm'].includes(error.nativeCode))throw Error('Cannot find context with specified id',{cause:error});throw error;}
    if(result.type==='exception')return {exceptionDetails:result.exceptionDetails};if(result.type!=='success')unavailable();return {result:{value:decoded(result.result)}};
   }
   const held=channel.requests.get(params.requestId);if(!held)throw Error('Unknown owned Firefox request');
   if(method==='Network.getRequestPostData')return {postData:(await postData(channel,held.event,until)).toString('base64'),base64Encoded:true};
   if(method==='Fetch.getResponseBody'){
    if(!held.event.response||!controller.current())unavailable();const identity=producer();if(!identity||!Number.isSafeInteger(identity.pid)||typeof identity.start!=='string')unavailable();
    const key=identity.pid+':'+identity.start;let getter=channel.getters.get(key);if(!getter){if(channel.getters.size>=32)unavailable();getter=createGetter({directory,enrollment:controller.bindings,producer:identity,contexts:channel.contexts,controller});channel.getters.set(key,getter);}
    const result=getter.getResponseBody(held.event);held.getter=getter;return result;
   }
   if(method==='Fetch.continueRequest'){held.responseWanted=channel.patterns.length>0&&params.interceptResponse===true;return resolveRequest(channel,held,'network.continueRequest',{request:params.requestId},until);}
   let nativeMethod,nativeParams;
   if(method==='Fetch.continueResponse'){nativeMethod='network.continueResponse';nativeParams={request:params.requestId};}
   else if(method==='Fetch.failRequest'){nativeMethod='network.failRequest';nativeParams={request:params.requestId};}
   else if(method==='Fetch.fulfillRequest'){
    const bodyless=params.responseCode===204&&!Object.hasOwn(params,'body');
    if(!Number.isInteger(params.responseCode)||!bodyless&&typeof params.body!=='string'||!Array.isArray(params.responseHeaders))unavailable();
    nativeMethod='network.provideResponse';nativeParams={request:params.requestId,statusCode:params.responseCode,...(bodyless?{}:{body:{type:'base64',value:params.body}}),headers:params.responseHeaders.map(h=>({name:h.name,value:{type:'string',value:h.value}}))};
   }else throw Error('Unsupported Firefox driver command: '+method);
   return resolveRequest(channel,held,nativeMethod,nativeParams,until);
  }
  channel.send=text=>{let message;try{message=JSON.parse(text);if(!Number.isSafeInteger(message.id)||message.id<=0)unavailable();}catch(error){fatal(error);return;}void mapped(message.method,message.params,message.sessionId,process.hrtime.bigint()+15_000_000_000n).then(result=>channel.emit({id:message.id,result}),error=>channel.emit({id:message.id,error:{message:error.message}}));};
  channel.close=async()=>{
   if(!channels.has(channel.id))return;
   if(channel.configuring||channel.registering)throw Error('Firefox channel configuration pending');
   channel.closing=true;
   channel.initialization=null;channel.readyChildren.clear();
   const until=process.hrtime.bigint()+15_000_000_000n;
   await disableFetch(channel,until);
   if(channel.blockIntercept){await native('network.removeIntercept',{intercept:channel.blockIntercept},undefined,until);channel.blockIntercept=null;channel.blockedURLs=[];}
   for(const script of [...channel.preloads]){await native('script.removePreloadScript',{script},undefined,until);channel.preloads.splice(channel.preloads.indexOf(script),1);}
   if(channel.collector)await native('network.removeDataCollector',{collector:channel.collector},undefined,until);
   for(const subscription of channel.subscriptions)await native('session.unsubscribe',{subscriptions:[subscription]},undefined,until);
   for(const getter of channel.getters.values())getter.close();
   await native('browsingContext.close',{context:channel.id},undefined,until);channels.delete(channel.id);
  };
  try{await native('browsingContext.navigate',{context:channel.id,url,wait:'none'});}catch(error){try{await channel.close();}catch{/* Original failure remains. */}throw error;}
  return {id:channel.id,socket:channel,close:channel.close,armFutureChildren,onChildInitialized,validateChildInitialized};
 }
 async function close(){
  const errors=[];for(const channel of [...channels.values()])try{await channel.close();}catch(error){errors.push(error);}
  if(wire&&wire.readyState===1&&!failure)try{await native('session.end');}catch(error){errors.push(error);}
  stopped=true;record({kind:'wire-close-requested',stopped,pending:[...pending.values()].map(w=>({id:w.command.id,method:w.command.method}))});wire?.close();for(const [id,w]of pending){pending.delete(id);clearTimeout(w.timer);w.reject(Error('Firefox transport shutdown'));}
  if(errors.length)throw new AggregateError(errors,'Firefox transport closure unavailable');
 }
 function cacheLeafProof(file){
  if(stopped||failure)return null;
  for(const channel of channels.values())for(const getter of channel.getters.values()){const proof=getter.cacheLeafProof(file);if(proof)return proof;}
  return null;
 }
 return {open,close,ready:ensureWire,cacheLeafProof,get observerFailed(){return observerFailed;},get cleanupDeferred(){return cleanupDeferred;}};
}
