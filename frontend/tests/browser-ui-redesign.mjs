import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { openBrowser } from './browser-driver.mjs';
const backend = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10200';
const frontend = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15174';
const evidence = process.env.MTG_UI_EVIDENCE;
assert.ok(evidence, 'Set MTG_UI_EVIDENCE to a local test scratch directory');
await mkdir(evidence, {recursive:true});
const { evaluate, command, waitFor, click, reload, close } = await openBrowser(frontend);
const results = [];
async function setup(path) {
  const response = await fetch(backend + path, {method:'POST'});
  assert.equal(response.status,200);
  const state = await response.json();
  await evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(state.id)})`);
  await reload();
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");
  return state;
}
async function capture(name) {
  await evaluate('document.activeElement?.blur(); window.scrollTo(0,0)');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});
  const shot = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile(`${evidence}/${name}.png`,Buffer.from(shot.data,'base64'));
}
async function viewport(width,height) { await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false}); }
async function fits() { assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),true,'Page has horizontal overflow'); }
async function key(key,code=key) { await command('Input.dispatchKeyEvent',{type:'keyDown',key,code});await command('Input.dispatchKeyEvent',{type:'keyUp',key,code}); }
async function pointerClick(prefix) {
  const point = await evaluate(`(() => { const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim().startsWith(${JSON.stringify(prefix)})&&!b.matches(':disabled')); if(!b)throw Error('Missing action'); b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  await command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});
}
try {
  for (const seat of [1,2]) {
    await viewport(1440,1000);
    const state = await setup(`/fixture/table?seat=${seat}`);
    assert.ok(await evaluate(`document.querySelector('.player .seat-label').textContent.includes('P${seat}')`));
    assert.equal(await evaluate("document.querySelectorAll('.opponent .hand-card').length"),0);
    assert.equal(await evaluate("document.querySelectorAll('.player .hand-card').length"),15);
    assert.equal(await evaluate("document.querySelectorAll('.player .cards .card').length"),14);
    assert.equal(await evaluate("document.querySelectorAll('.player .land-stack').length"),1);
    assert.equal(await evaluate("document.querySelector('.playable-hand').scrollWidth > document.querySelector('.playable-hand').clientWidth"),true);
    await fits();
    await capture(`crowded-seat-${seat}-desktop`);
    // Exact individual land ID, not a guessed name or one auto-selected by the server.
    const selected = state.players[String(seat)].battlefield.filter(c => c.name === 'Swamp' && !c.tapped)[1];
    await evaluate(`(() => { const details = document.querySelector('.player .land-members'); details.open=true; const select=details.querySelector('select'); select.value=${JSON.stringify(selected.id)}; select.dispatchEvent(new Event('change',{bubbles:true})); })()`);
    await pointerClick('Tap selected for B');
    await waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision !== ${JSON.stringify(String(state.revision))}`);
    const after = await (await fetch(`${backend}/matches/${state.id}`)).json();
    assert.equal(after.players[String(seat)].battlefield.find(c => c.id === selected.id).tapped,true);
    assert.equal(after.players[String(seat)].battlefield.filter(c => c.name === 'Swamp' && c.tapped).length,4);
    results.push(`seat ${seat}: crowded canonical board, hidden opposing hand, 15-card scroll and exact land ID action persisted`);
  }
  await key('Tab');
  await evaluate("document.querySelector('.player .card').focus()");
  await waitFor("document.querySelector('.card-hover-preview')");
  assert.equal(await evaluate("document.querySelector('.card-hover-preview').parentElement === document.body"),true);
  assert.equal(await evaluate("getComputedStyle(document.activeElement).outlineStyle !== 'none'"),true);
  await key('Enter');
  await evaluate("document.querySelector('.card-hover-preview').focus()");
  await waitFor("document.activeElement.classList.contains('card-hover-preview')");
  assert.equal(await evaluate("(() => {const r=document.querySelector('.card-hover-preview').getBoundingClientRect();return r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight})()"),true);
  const previewShot = await command('Page.captureScreenshot',{format:'png'});
  await writeFile(`${evidence}/keyboard-inspection.png`,Buffer.from(previewShot.data,'base64'));
  await key('Escape');
  await waitFor("!document.querySelector('.card-hover-preview')");
  assert.ok(await evaluate("document.activeElement.hasAttribute('data-card-id')"));
  await key('Tab');
  assert.equal(await evaluate("document.activeElement !== document.body"),true);
  results.push('keyboard focus outline, Enter-pinned portal inspection, viewport bounds, Escape dismissal and Tab navigation');
  await evaluate("document.activeElement?.blur(); document.querySelector('.playable-hand').scrollIntoView({block:'center'})");
  await key('Escape');
  const handShot = await command('Page.captureScreenshot',{format:'png'});
  await writeFile(`${evidence}/long-hand.png`,Buffer.from(handShot.data,'base64'));
  await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await evaluate("getComputedStyle(document.querySelector('button')).transitionDuration"),'0s');
  results.push('reduced motion disables transitions');
  for (const [width,height,name] of [[1024,768,'laptop'],[390,844,'mobile']]) {
    await viewport(width,height); await fits(); await capture(`crowded-${name}`);
    assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Pass Priority' && b.getBoundingClientRect().width>0)"),true);
  }
  await viewport(1440,1000);
  await evaluate("document.documentElement.style.zoom='2'");
  await fits(); await capture('crowded-200-percent');
  await evaluate("document.documentElement.style.zoom=''");
  results.push('1024px laptop, 390px mobile, 200% CSS zoom: no page overflow; essential controls remain available');
  await setup('/fixture/table?seat=2&ai_opponent=true&crowded=false');
  assert.ok(await evaluate("document.querySelector('.player .seat-label').textContent.includes('P1')"));
  assert.equal(await evaluate("document.querySelectorAll('.hand-card.playable').length"),0);
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Pass Priority').disabled"),true);
  assert.equal(await evaluate("document.querySelectorAll('.opponent .hand-card').length"),0);
  results.push('AI holds priority: human seat one remains local, opponent hand hidden, no AI casts exposed as human actions');
  await setup('/fixture?face_kind=scry');
  assert.ok(await evaluate("document.body.innerText.includes('Confirm Selection')"));
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Pass Priority').disabled"),true);
  await capture('active-choice-desktop');
  await viewport(390,844); await fits(); await capture('active-choice-mobile');
  assert.ok(await evaluate("document.querySelector('.choice-notice').textContent.includes('Choice required')"));
  await evaluate("document.querySelector('.choice-notice').click()");
  await waitFor("location.hash === '#match-controls'");
  const choiceShot = await command('Page.captureScreenshot',{format:'png'});
  await writeFile(`${evidence}/active-choice-mobile-controls.png`,Buffer.from(choiceShot.data,'base64'));
  await viewport(1440,1000);
  await setup('/fixture');
  await click('Cast Llanowar Elves');
  await waitFor("document.querySelector('.stack-item')?.textContent.includes('Llanowar Elves')");
  await capture('active-stack-desktop');
  await viewport(390,844); await fits();
  await evaluate("document.querySelector('.stack-log').scrollIntoView()");
  const shot = await command('Page.captureScreenshot',{format:'png'});
  await writeFile(`${evidence}/active-stack-mobile.png`,Buffer.from(shot.data,'base64'));
  results.push('real pending scry blocks pass; real permitted library cast appears in persistent stack, desktop/mobile');
  await viewport(1440,1000);
  for(let index=0;index<8;index++) {
    const revision=await evaluate("document.querySelector('[data-match-revision]').dataset.matchRevision");
    await click('Pass Priority');
    await waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision !== ${JSON.stringify(revision)}`);
  }
  await evaluate("document.querySelector('.match-log').open=true");
  assert.equal(await evaluate("document.querySelectorAll('#match-log-lines p').length"),5);
  await click('Show more log events');
  assert.ok(await evaluate("document.querySelectorAll('#match-log-lines p').length > 5"));
  await click('Show fewer log events');
  assert.equal(await evaluate("document.querySelectorAll('#match-log-lines p').length"),5);
  results.push('real match log has a five-event preview with working show-more/show-fewer controls');
  await writeFile(`${evidence}/checks.json`,JSON.stringify(results,null,2));
  console.log(results.map(result=>'PASS '+result).join('\n'));
} finally { await close(); }
