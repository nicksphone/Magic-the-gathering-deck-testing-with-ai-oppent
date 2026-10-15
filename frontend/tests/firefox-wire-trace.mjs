// Passive private metadata only. Never log params, expressions, headers, bodies or arbitrary text.
import {appendFileSync,mkdirSync,lstatSync} from 'node:fs';
import path from 'node:path';
const kinds=new Set(['native-command','native-reply','native-event','wire-open','wire-close','wire-error','wire-send-error','wire-close-requested']);
const methods=new Set(['session.new','session.subscribe','session.unsubscribe','session.end','browsingContext.create','browsingContext.navigate','browsingContext.reload','browsingContext.getTree','browsingContext.close','browsingContext.setViewport','browsingContext.captureScreenshot','script.evaluate','script.addPreloadScript','script.removePreloadScript','browsingContext.activate','input.performActions','network.addDataCollector','network.removeDataCollector','network.addIntercept','network.removeIntercept','network.getData','network.continueRequest','network.continueResponse','network.failRequest','network.provideResponse','network.beforeRequestSent','network.responseStarted','network.responseCompleted','network.fetchError','browsingContext.contextCreated','browsingContext.contextDestroyed','browsingContext.load','browsingContext.domContentLoaded']);
const errors=new Set(['invalid argument','no such frame','no such realm','no such request','unknown command','unknown error','invalid session id','unsupported operation','no such intercept','no such network data','no such script','javascript error']);
const reasons=new Map([['','EMPTY'],['Normal Closure','NORMAL'],['Going Away','GOING_AWAY'],['Session ended','SESSION_ENDED'],['Session deleted','SESSION_DELETED']]);
export function safeWireRow(raw){
 if(!kinds.has(raw.kind))throw Error('WIRE_OBSERVER_KIND');
 const row={kind:raw.kind};
 for(const key of ['id','code','status'])if(Number.isSafeInteger(raw[key])&&raw[key]>=0&&raw[key]<=Number.MAX_SAFE_INTEGER)row[key]=raw[key];
 if(typeof raw.wasClean==='boolean')row.wasClean=raw.wasClean;
 if(typeof raw.stopped==='boolean')row.stopped=raw.stopped;
 if(typeof raw.blocked==='boolean')row.blocked=raw.blocked;
 if(typeof raw.method==='string')row.method=methods.has(raw.method)?raw.method:'OTHER_REDACTED';
 for(const key of ['type','resultType'])if(raw[key]!==undefined)row[key]=['success','error','exception','event'].includes(raw[key])?raw[key]:'OTHER_REDACTED';
 if(raw.errorCode!==undefined)row.errorCategory=errors.has(raw.errorCode)?raw.errorCode:'OTHER_REDACTED';
 else if(raw.errorCategory!==undefined)row.errorCategory=errors.has(raw.errorCategory)?raw.errorCategory:'OTHER_REDACTED';
 if(raw.kind==='wire-close')row.reasonCategory=typeof raw.reason==='string'?(reasons.get(raw.reason)??'OTHER_REDACTED'):['EMPTY','NORMAL','GOING_AWAY','SESSION_ENDED','SESSION_DELETED','OTHER_REDACTED','UNAVAILABLE'].includes(raw.reasonCategory)?raw.reasonCategory:'UNAVAILABLE';
 if(Array.isArray(raw.pending))row.pending=raw.pending.map(p=>({id:p.id,method:methods.has(p.method)?p.method:'OTHER_REDACTED'})).filter(p=>Number.isSafeInteger(p.id)&&p.id>0);
 return row;
}
export function createWireTrace(directory){
 if(typeof directory!=='string'||!path.isAbsolute(directory)||path.resolve(directory)!==directory)throw Error('WIRE_TRACE_PATH');
 const file=path.join(directory,'cdp.jsonl');let failed=false;
 return {record(raw){
  try{
   const row=safeWireRow(raw);const line=JSON.stringify({utc:new Date().toISOString(),monotonic:process.hrtime.bigint().toString(),pid:process.pid,transport:'webdriver-bidi',...row})+'\n';
   mkdirSync(directory,{recursive:true,mode:0o700});
   let size=0;try{const info=lstatSync(file);if(!info.isFile()||info.isSymbolicLink()||info.nlink!==1)throw Error('WIRE_TRACE_KIND');size=info.size;}catch(error){if(error.code!=='ENOENT')throw error;}
   // Share the original 64MiB CDP observational file/budget; original out caps unchanged.
   if(size+Buffer.byteLength(line)>64*1024*1024)throw Error('WIRE_TRACE_LIMIT');
   appendFileSync(file,line,{mode:0o600});
  }catch{failed=true;}
 },get failed(){return failed;}};
}
