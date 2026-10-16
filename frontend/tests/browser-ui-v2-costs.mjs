import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';
import { continueRequestForPostResponse, traceStartRecoveryResponses } from './browser-start-recovery-diagnostics.mjs';
const api=process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10200';
const ui=process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15174';
assert.ok(process.env.MTG_BROWSER_ORIGIN,'Set owned Chromium endpoint');
const b=await openBrowser(ui);
async function humanIdle() {
 await b.waitFor("!document.body.innerText.includes('Match operation pending') && !document.body.innerText.includes('Restoring saved session')");
}
async function setup(path) {
 await humanIdle();
 const response=await fetch(api+path,{method:'POST'});assert.equal(response.status,200);const state=await response.json();
 await b.evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(state.id)})`);await b.reload();
 await b.waitFor(`localStorage.getItem('mtg.activeMatch') === ${JSON.stringify(state.id)} && document.querySelector('.battlefield')?.dataset.matchId === ${JSON.stringify(state.id)} && document.querySelector('.battlefield')?.dataset.matchRevision === ${JSON.stringify(String(state.revision))} && !document.body.innerText.includes('Restoring saved session') && !document.body.innerText.includes('Match operation pending') && [...document.querySelectorAll('button')].some(e=>e.textContent==='Resume automatic play')`);return state;
}
try {
 await b.command('Network.enable');
 await b.command('Page.enable');
 await b.command('Runtime.enable');
 for(const seat of [1,2]) for(const payment of ['discard','sacrifice']) {
  const s=await setup(`/fixture?face_kind=spell_cost_${seat}`);
  await b.waitFor("document.body.innerText.includes('Cast Bone Shards')");
  const paid=s.players[String(seat)][payment==='discard'?'hand':'battlefield'].find(c=>c.name===(payment==='discard'?'Island':'Grizzly Bears'));
  const target=s.players[String(3-seat)].battlefield.find(c=>c.name==='Grizzly Bears');
  await b.evaluate(`(()=>{const box=[...document.querySelectorAll('.hand-card')].find(e=>e.textContent.includes('Cast Bone Shards'));const e=[...box.querySelectorAll('select')].find(e=>[...e.options].some(o=>o.value==='base_${payment}'));e.value='base_${payment}';e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  const label=`${payment==='discard'?'Discard':'Sacrifice'} for cost Bone Shards`;
  await b.waitFor(`document.querySelector('select[aria-label="${label}"]')`);
  assert.equal(await b.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.startsWith('Cast Bone Shards')).disabled"),true);
  await b.evaluate(`(()=>{const e=document.querySelector('select[aria-label="${label}"]');for(const o of e.options)o.selected=o.value===${JSON.stringify(paid.id)};e.dispatchEvent(new Event('change',{bubbles:true}));const t=[...e.closest('.hand-card').querySelectorAll('select')].find(e=>[...e.options].some(o=>o.textContent.startsWith('Target ')));t.value=${JSON.stringify(target.id)};t.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await b.click('Cast Bone Shards');await waitForApiState(`${api}/matches/${s.id}`,state=>state.stack.length===1);
  for(let i=0;i<2;i++){await humanIdle();const rev=await b.evaluate("document.querySelector('[data-match-revision]').dataset.matchRevision");await b.click('Pass Priority');await b.waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(rev)}`);await humanIdle();}
  const final=await waitForApiState(`${api}/matches/${s.id}`,state=>state.stack.length===0);
  assert.ok(final.players[String(seat)].graveyard.some(c=>c.id===paid.id));
  assert.ok(final.players[String(3-seat)].graveyard.some(c=>c.id===target.id));
  assert.equal(final.players[String(seat)].mana_pool.B,0);
  console.log(`PASS v2 seat ${seat}: deliberate ${payment} cost required, exact target destroyed, mana paid`);
 }
 await setup('/fixture/table?seat=2&crowded=false&ai_opponent=true');
 assert.ok(await b.evaluate("document.querySelector('.player .seat-label').textContent.includes('P1')"));
 assert.equal(await b.evaluate("document.querySelectorAll('.opponent .hand-card').length"),0);
 assert.equal(await b.evaluate("document.querySelectorAll('.hand-card.playable').length"),0);
 assert.equal(await b.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Pass Priority').disabled"),true);
 console.log('PASS v2 AI priority: human viewpoint remains P1, AI hand/actions hidden');
 const s=await setup('/fixture');let held,continueHeld;
 let heldTrace,currentUrlSeen=false,otherUrlSeen=false;
 try{
 b.onIntercept(heldTrace=traceStartRecoveryResponses(b.command, async (e,command)=>{
  if(e.request.url===`${api}/matches/${s.id}/action`)currentUrlSeen=true;else otherUrlSeen=true;
  if(await continueRequestForPostResponse(command,e))return;
  if(e.request.method!=='POST'){await command('Fetch.continueResponse',{requestId:e.requestId});return;}
  held=e;
  continueHeld=()=>command('Fetch.continueResponse',{requestId:e.requestId});
 }, ui, value=>console.error('V2_HELD_RESPONSE_TRACE',JSON.stringify(value)), {backend:api}));
 await b.command('Fetch.enable',{patterns:[{urlPattern:'*/matches/*/action',requestStage:'Request'}]});
 await b.click('Play Land Forest');
 await b.waitFor("document.body.innerText.includes('Match operation pending')");
 assert.equal(await b.evaluate("[...document.querySelectorAll('#table fieldset,#match-controls fieldset')].every(e=>e.disabled)"),true);
 for(let n=0;!held&&n<100;n++)await new Promise(r=>setTimeout(r,20));assert.ok(held);
 assert.equal(held.request.method,'POST');assert.equal(held.responseStatusCode,200);
 await continueHeld();await b.command('Fetch.disable');
 await b.waitFor("!document.body.innerText.includes('Match operation pending')");
 const final=await waitForApiState(`${api}/matches/${s.id}`,state=>state.revision===1);assert.equal(final.players['2'].battlefield.filter(c=>c.id==='forest').length,1);
 console.log('PASS v2 held real response: all gameplay controls disabled while pending; exactly one mutation persisted');
 }catch(error){
  // Publish the failure-time native history before any bounded context reads can yield.
  try{heldTrace?.reportFailure();}catch{}
  try{
   const context={cause:'unknown',held:Boolean(held),currentUrlSeen,otherUrlSeen,
    ui:{status:'pending',activeMatch:null,renderedMatch:null,renderedRevision:null,pending:null,restoring:null,alert:null,controlsDisabled:null,enabledPrefixCount:null},
    canonical:{status:'pending',revision:null},runtime:{status:'pending',product:null,protocolVersion:null}};
   let collecting=true,diagnosticTimer;
   const controller=new AbortController();
   const readUi=async()=>{
    try{
     const value=await b.evaluate(`(()=>{
      return {activeMatch:localStorage.getItem('mtg.activeMatch')===${JSON.stringify(s.id)},
       renderedMatch:document.querySelector('.battlefield')?.dataset.matchId===${JSON.stringify(s.id)},
       renderedRevision:document.querySelector('.battlefield')?.dataset.matchRevision,
       pending:document.body.innerText.includes('Match operation pending'),restoring:document.body.innerText.includes('Restoring saved session'),
       alert:Boolean(document.querySelector('.operation-alert')),
       controlsDisabled:[...document.querySelectorAll('#table fieldset,#match-controls fieldset')].every(e=>e.disabled),
       enabledPrefixCount:[...document.querySelectorAll('button')].filter(b=>b.textContent.trim().startsWith('Play Land Forest')&&!b.matches(':disabled')).length};
     })()`);
     if(collecting&&value&&typeof value==='object'){
      for(const key of ['activeMatch','renderedMatch','pending','restoring','alert','controlsDisabled'])context.ui[key]=value[key]===true;
      context.ui.renderedRevision=typeof value.renderedRevision==='string'&&/^(0|[1-9]\d*)$/.test(value.renderedRevision)&&Number.isSafeInteger(Number(value.renderedRevision))?Number(value.renderedRevision):null;
      context.ui.enabledPrefixCount=Number.isSafeInteger(value.enabledPrefixCount)&&value.enabledPrefixCount>=0?value.enabledPrefixCount:null;
      context.ui.status='available';
     }else if(collecting)context.ui.status='unavailable';
    }catch{if(collecting)context.ui.status='unavailable';}
   };
   const readCanonical=async()=>{
    try{
     const response=await fetch(`${api}/matches/${s.id}`,{method:'GET',signal:controller.signal});
     if(!response.ok)throw new Error('Diagnostic state unavailable');
     const value=await response.json();
     if(!Number.isSafeInteger(value?.revision)||value.revision<0)throw new Error('Diagnostic revision unavailable');
     if(collecting)context.canonical={status:'available',revision:value.revision};
    }catch{if(collecting)context.canonical.status='unavailable';}
   };
   const readRuntime=async()=>{
    try{
     const identity=await b.browserIdentity(controller.signal);
     if(collecting)context.runtime={status:'available',product:identity.product,protocolVersion:identity.protocolVersion};
    }catch{if(collecting)context.runtime.status='unavailable';}
   };
   try{
    await Promise.race([Promise.all([readUi(),readCanonical(),readRuntime()]),new Promise(resolve=>{
     diagnosticTimer=setTimeout(()=>{
      for(const key of ['ui','canonical','runtime'])if(context[key].status==='pending')context[key].status='timed-out';
      resolve();
     },1000);
    })]);
   }finally{collecting=false;clearTimeout(diagnosticTimer);controller.abort();}
   try{console.error('V2_HELD_FAILURE_CONTEXT',JSON.stringify(context));}catch{}
  }catch{} // Diagnostic failures cannot replace the original assertion or native error.
  throw error;
 }
} finally {await b.close();}
