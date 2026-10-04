import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { openBrowser } from './browser-driver.mjs';
const backend=process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10200';
const {evaluate,waitFor,click,command,onIntercept,close}=await openBrowser(process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15174');
async function fill(selector,value) {
  await evaluate(`(() => {const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
}
try {
  await waitFor("document.querySelector('.deck-panel') && !document.body.innerText.includes('Restoring saved session')");
  await evaluate("document.querySelector('.deck-panel').parentElement.open=true");
  const name=`UI canonical Swamp fixture ${Date.now()}`;
  await fill('[aria-label="Deck name"]',name);
  await fill('[aria-label="Deck list"]','60 Swamp');
  await click('Save Deck');
  await waitFor("document.querySelector('.deck-panel .status').textContent.startsWith('Saved deck #')",45000);
  const response=await fetch(`${backend}/decks`);assert.equal(response.status,200);
  const decks=await response.json();const imported=decks.find(deck=>deck.name===name);
  assert.ok(imported);assert.deepEqual(imported.mainboard,[{quantity:60,card_name:'Swamp'}]);
  await evaluate("document.querySelector('.match-setup').open=true");
  for(const label of ['Deck A','Deck B']) {
    await waitFor(`document.querySelector('[aria-label="${label}"] option[value="${imported.id}"]')`);
    await evaluate(`(() => {const el=document.querySelector('[aria-label="${label}"]');el.value=${JSON.stringify(String(imported.id))};el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  }
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of')).disabled"),false);
  console.log('PASS deck imported through visible controls, canonical list persisted and selectable for both seats');
  onIntercept(async event=>command('Fetch.failRequest',{requestId:event.requestId,errorReason:'Failed'}));
  await command('Fetch.enable',{patterns:[{urlPattern:'*/decks/import*',requestStage:'Request'}]});
  await click('Save Deck');
  await waitFor("document.querySelector('.deck-panel [role=alert]')?.textContent.includes('Deck request failed')");
  await command('Fetch.disable');
  console.log('PASS network failure in deck tools is visible rather than an unhandled promise');
  await evaluate("document.querySelector('.deck-panel').scrollIntoView({block:'start'})");
  if(process.env.MTG_UI_EVIDENCE){const shot=await command('Page.captureScreenshot',{format:'png'});await writeFile(`${process.env.MTG_UI_EVIDENCE}/deck-import-error.png`,Buffer.from(shot.data,'base64'));}
  const colors=await evaluate("(() => {const s=getComputedStyle(document.documentElement);return ['--text','--muted','--gold'].map(k=>[k,s.getPropertyValue(k).trim()])})()");
  function luminance(hex){const rgb=hex.replace('#','').match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4);return rgb[0]*0.2126+rgb[1]*0.7152+rgb[2]*0.0722;}
  const ratios=colors.map(([name,color])=>[name,(luminance(color)+0.05)/(luminance('#263438')+0.05)]);
  ratios.forEach(([,ratio])=>assert.ok(ratio>=4.5));
  console.log('PASS base text/muted/gold contrast against lightest flat card surface: '+JSON.stringify(ratios));
} finally {await close();}
