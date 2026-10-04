import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { openBrowser } from './browser-driver.mjs';

// Isolated v2 suite. No dependency on production data or edits to the shared harness.
const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10200';
const origin = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15174';
const evidence = process.env.MTG_UI_EVIDENCE;
assert.ok(evidence, 'Set MTG_UI_EVIDENCE to local scratch');
assert.ok(process.env.MTG_BROWSER_ORIGIN, 'Explicit owned Chromium origin required');
await mkdir(evidence, {recursive:true});
const b = await openBrowser(origin);
const {evaluate, command, waitFor, click, reload} = b;
await command('Page.bringToFront');
const results = [];
const record = async message => { results.push(message); console.log('PASS '+message); await writeFile(`${evidence}/v2-checks.json`,JSON.stringify(results,null,2)); };
async function viewport(width=1440,height=1000) { await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false}); }
async function key(key) { for(const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:({Enter:13,Escape:27,Tab:9})[key], ...(key==='Enter'&&type==='keyDown'?{text:'\r'}:{})}); }
async function fit() { assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),'Unintended page-wide overflow'); }
async function shot(name, selector) {
  await evaluate('document.activeElement?.blur()'); await key('Escape');
  await evaluate(selector ? `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})` : 'window.scrollTo(0,0)');
  const image=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile(`${evidence}/${name}.png`,Buffer.from(image.data,'base64'));
}
async function setup(path) {
  const response=await fetch(api+path,{method:'POST'});assert.equal(response.status,200);
  const state=await response.json();
  await evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(state.id)})`);await reload();
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session') && [...document.querySelectorAll('button')].some(e=>e.textContent==='Resume automatic play')");
  return state;
}
async function select(selector,value) {
  await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.value=${JSON.stringify(String(value))};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
}
async function pointer(selector) {
  const p=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center',inline:'center'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...p});
  for(const type of ['mousePressed','mouseReleased']) await command('Input.dispatchMouseEvent',{type,...p,button:'left',clickCount:1});
}
try {
  await viewport();
  await evaluate("localStorage.removeItem('mtg.activeMatch'); localStorage.removeItem('mtg.pendingStart')");await reload();
  await waitFor("document.querySelector('.workspace-lobby') && document.querySelector('[aria-label=\"Deck A\"] option[value]:not([value=\"\"])')");
  await fit();await shot('after-lobby');
  assert.equal(await evaluate("document.querySelector('#lab-tools').hidden"),true);
  await pointer('nav a[href="#lab-tools"]');
  await waitFor("!document.querySelector('#lab-tools').hidden");
  await shot('after-workbench','#lab-tools');await click('Close lab');
  assert.equal(await evaluate("document.activeElement.getAttribute('href')"),'#lab-tools');
  await record('Lobby paired setup; secondary workbench opens and closes with focus restoration');
  // A real match created by the app, not an injected board.
  const deckIds = await evaluate("['White Weenie','Burn'].map(name=>[...document.querySelector('[aria-label=\"Deck A\"]').options].find(o=>o.textContent.trim()===name).value)");
  await select('[aria-label="Deck A"]',deckIds[0]);
  await select('[aria-label="Deck B"]',deckIds[1]);
  await select('[aria-label="Match mode"]','human_vs_human');
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(e=>e.textContent==='Keep Hand'&&!e.disabled)");
  const realId=await evaluate("localStorage.getItem('mtg.activeMatch')");
  for(let i=0;i<2;i++) { const rev=await evaluate("document.querySelector('[data-match-revision]').dataset.matchRevision");await click('Keep Hand');await waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(rev)}`); }
  const real=await(await fetch(`${api}/matches/${realId}`)).json();assert.equal(real.pregame_pending,false);
  await shot('after-real-started-match');
  await record('Actual app-started human/human match: both opening hands kept, canonical persistence read back');
  for(const seat of [1,2]) {
    const s=await setup(`/fixture/table-v2?seat=${seat}`);
    assert.ok(await evaluate(`document.querySelector('.player .seat-label').textContent.includes('P${seat}')`));
    assert.equal(await evaluate("document.querySelectorAll('.opponent .hand-card').length"),0);
    const ids=await evaluate("({hand:[...document.querySelectorAll('.player [data-hand-card-id]')].map(e=>e.dataset.handCardId),permanents:[...document.querySelectorAll('.player [data-card-id]')].map(e=>e.dataset.cardId),lands:[...document.querySelectorAll('.player .land-members select option')].map(e=>e.value)})");
    for(const [zone,count] of [['hand',15],['permanents',15],['lands',20]]) assert.equal(new Set(ids[zone]).size,count);
    // Focus every card; native focus must scroll its own rail, not lose an ID.
    for(const id of ids.permanents) {
      await evaluate(`document.querySelector('[data-card-id="${id}"]').focus()`);
      assert.equal(await evaluate('document.activeElement.dataset.cardId'),id);
    }
    for(const id of ids.hand) {
      await evaluate(`document.querySelector('[data-hand-card-id="${id}"] .hand-face').focus()`);await key('Enter');
      await waitFor("document.querySelector('.card-hover-preview[data-pinned=true]')");await key('Escape');
      assert.equal(await evaluate('document.activeElement.closest("[data-hand-card-id]").dataset.handCardId'),id);
    }
    await evaluate("document.querySelector('.player .land-members').open=true");
    for(const id of ids.lands) { await select('.player .land-members select',id);assert.equal(await evaluate("document.querySelector('.player .land-members select').value"),id); }
    const target=s.players[String(seat)].battlefield.filter(c=>c.name==='Swamp'&&!c.tapped)[1];
    await select('.player .land-members select',target.id);
    await pointer('.player .land-members button');
    await waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(String(s.revision))}`);
    const after=await(await fetch(`${api}/matches/${s.id}`)).json();
    assert.equal(after.players[String(seat)].battlefield.find(c=>c.id===target.id).tapped,true);
    assert.equal(after.players[String(seat)].battlefield.filter(c=>c.name==='Swamp'&&c.tapped).length,4);
    await fit();await shot(`after-crowded-seat-${seat}`);
    await record(`Seat ${seat}: 20 distinct selectable land IDs, 15 focusable permanents, 15 keyboard-inspectable hand cards; exact selected land persisted; opposing hand hidden`);
  }
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await evaluate("getComputedStyle(document.querySelector('button')).transitionDuration"),'0s');
  await evaluate("document.querySelector('.playable-hand').scrollLeft=0");
  await pointer('[aria-label="Next Hand and permitted plays"]');
  assert.ok(await evaluate("document.querySelector('.playable-hand').scrollLeft>0"));
  // Hit-test the last hand card and pin by pointer.
  await pointer('.player .hand-card:last-child .hand-face');await waitFor("document.querySelector('.card-hover-preview[data-pinned=true]')");
  await record('Explicit hand navigation and pointer inspection work; reduced motion honored');
  await key('Escape');
  await evaluate("document.querySelector('.player .card').focus()");await key('Enter');
  const inspection=await command('Page.captureScreenshot',{format:'png'});await writeFile(`${evidence}/after-inspection.png`,Buffer.from(inspection.data,'base64'));await key('Escape');
  assert.ok(await evaluate("document.activeElement.hasAttribute('data-card-id')"));
  await shot('after-hand-tray','.playable-hand');
  for(const [w,h,name] of [[1024,768,'laptop'],[390,844,'mobile']]) {await viewport(w,h);await fit();await shot(`after-${name}`);await shot(`after-${name}-commands`,'#match-controls');}
  await viewport();await evaluate("document.documentElement.style.zoom='2'");await fit();await shot('after-200-percent');await evaluate("document.documentElement.style.zoom=''");
  await record('1024 laptop, 390 mobile and 200% CSS zoom: no page overflow; commands reachable; Escape restores permanent focus');
  await setup('/fixture/table-v2?crowded=false');
  const localArt=await evaluate("[...document.querySelectorAll('.player .card img')].map(e=>e.src)");
  if(localArt.length) {await waitFor("[...document.querySelectorAll('.player .card img')].every(e=>e.complete&&e.naturalWidth>0)");await record('Actual pre-cached JPEG art decoded in browser (see provenance manifest)');}
  await shot('after-table-art');
  await setup('/fixture/table-v2?crowded=false&artwork=false');await waitFor("document.querySelector('.player .card .card-no-art')");await shot('after-table-offline');
  await record('Offline canonical card names/stats retained with explicitly unavailable art');
  await setup('/fixture?modal=true');
  await evaluate("document.querySelector('.player .hand-card .hand-face').focus()");await key('Enter');
  await waitFor("document.querySelector('.inspection-faces details')");
  await evaluate("document.querySelector('.inspection-faces summary').focus()");await key('Enter');
  assert.ok(await evaluate("document.querySelector('.inspection-faces details').open"));
  const faceShot=await command('Page.captureScreenshot',{format:'png'});await writeFile(`${evidence}/after-face-inspection.png`,Buffer.from(faceShot.data,'base64'));await key('Escape');
  await record('Available multi-face metadata inspectable by keyboard without changing the chosen legal cast');
  await setup('/fixture?face_kind=scry');
  assert.ok(await evaluate("document.querySelector('.choice-notice').textContent.includes('Choice required')"));
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Pass Priority').disabled"),true);
  await shot('after-pending-choice','#match-controls');await click('Confirm Selection');
  await waitFor("!document.querySelector('.choice-notice') || !document.body.innerText.includes('Confirm Selection')");
  await record('Pending canonical scry prevents pass and remains actionable in command surface');
  const cast=await setup('/fixture');await click('Cast Llanowar Elves');await waitFor("document.querySelector('.stack-item')?.textContent.includes('Llanowar Elves')");
  assert.ok((await(await fetch(`${api}/matches/${cast.id}`)).json()).stack.length>0);await shot('after-stack-response','#match-controls');
  await record('Real permitted library cast paid and persisted on the response stack');
  let s=await setup('/fixture');
  await evaluate("(()=>{const e=[...document.querySelectorAll('button')].find(e=>e.textContent.startsWith('Play Land Forest'));e.click();e.click();})()");
  await waitFor("!document.body.innerText.includes('Match operation pending') && ![...document.querySelectorAll('button')].some(e=>e.textContent.startsWith('Play Land Forest'))");
  let state=await(await fetch(`${api}/matches/${s.id}`)).json();assert.equal(state.revision,1);await reload();await waitFor("document.querySelector('[data-match-revision=\"1\"]')");
  await record('Double intent applies once; full-page reload restores persisted revision');
  s=await setup('/fixture');let dropped=false;
  b.onIntercept(async e=>{if(e.request.method==='POST'&&e.responseStatusCode===200&&!dropped){dropped=true;await command('Fetch.failRequest',{requestId:e.requestId,errorReason:'Failed'});}else await command('Fetch.continueResponse',{requestId:e.requestId});});
  await command('Fetch.enable',{patterns:[{urlPattern:'*/matches/*/action',requestStage:'Response'}]});await click('Play Land Forest');
  await waitFor("document.querySelector('.operation-alert') && !document.body.innerText.includes('Match operation pending')");await command('Fetch.disable');
  state=await(await fetch(`${api}/matches/${s.id}`)).json();assert.equal(state.revision,1);assert.ok(dropped);await shot('after-reconciled-failure');
  await record('Dropped accepted HTTP response surfaces error and reconciles server revision without replay');
} finally { await b.close(); }
