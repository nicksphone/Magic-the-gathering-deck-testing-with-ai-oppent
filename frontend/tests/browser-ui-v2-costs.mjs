import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';
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
 const s=await setup('/fixture');let held;
 b.onIntercept(e=>{held=e;});
 await b.command('Fetch.enable',{patterns:[{urlPattern:'*/matches/*/action',requestStage:'Response'}]});
 await b.click('Play Land Forest');
 await b.waitFor("document.body.innerText.includes('Match operation pending')");
 assert.equal(await b.evaluate("[...document.querySelectorAll('#table fieldset,#match-controls fieldset')].every(e=>e.disabled)"),true);
 for(let n=0;!held&&n<100;n++)await new Promise(r=>setTimeout(r,20));assert.ok(held);
 await b.command('Fetch.continueResponse',{requestId:held.requestId});await b.command('Fetch.disable');
 await b.waitFor("!document.body.innerText.includes('Match operation pending')");
 const final=await waitForApiState(`${api}/matches/${s.id}`,state=>state.revision===1);assert.equal(final.players['2'].battlefield.filter(c=>c.id==='forest').length,1);
 console.log('PASS v2 held real response: all gameplay controls disabled while pending; exactly one mutation persisted');
} finally {await b.close();}
