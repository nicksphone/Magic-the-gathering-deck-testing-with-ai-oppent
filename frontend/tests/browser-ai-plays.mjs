import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {openBrowser} from './browser-driver.mjs';

const origin=process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15177';
const browser=await openBrowser(origin+'/tests/interactive-preflight.html');
const {evaluate,waitFor,click,command,reload,close}=browser;
try {
  await waitFor('window.interactiveFixture');
  await evaluate(`(() => {
    const player=(id,name)=>({id,name,life:20,hand:[],hand_count:0,battlefield:[],graveyard:[],graveyard_count:0,exile:[],exile_count:0,library_count:50,mana_pool:{}});
    const state={id:'synthetic-ai-notices',revision:1,game_number:1,turn:2,active_player:1,priority_player:1,step:'precombat_main',winner:null,
      score:{1:0,2:0},mode:'player_vs_ai',controllers:{1:'human',2:'ai'},players:{1:player(1,'Player A'),2:player(2,'Player B')},stack:[],
      log:Array.from({length:120},(_,i)=>i===50?'Player B casts/activates Old public spell.':'Public baseline '+i)};
    const receipts={demo:{payload:{},state}};
    sessionStorage.setItem('interactiveFixture.receipts',JSON.stringify(receipts));
    localStorage.setItem('mtg.activeMatch',state.id);
  })()`);
  await reload();
  await waitFor("document.querySelector('.turn-command-actions button:not(#automatic-play-toggle):not(:disabled)') && window.interactiveFixture");
  assert.equal(await evaluate("document.querySelectorAll('.ai-play-notice').length"),0,'Restoring does not replay the old log');
  await evaluate(`(() => {
    const state=structuredClone(window.interactiveFixture.receipts.demo.state);
    state.revision=2;state.players[1].life=17;
    state.log=[...state.log.slice(3),'Player B casts/activates Lava Spike.','Player A takes 3 damage.','Lava Spike resolves.'];
    window.interactiveFixture.nextStates.push(state);
    document.querySelector('.turn-command-actions button:not(#automatic-play-toggle)').focus();
  })()`);
  await click('Pass Priority');
  await waitFor("document.querySelector('.ai-play-notice')?.textContent.includes('Lava Spike')");
  assert.equal(await evaluate("document.querySelectorAll('.ai-play-notice').length"),1);
  assert.equal(await evaluate("document.activeElement.closest('.ai-play-notices') !== null"),false,'Announcement never steals focus');
  assert.equal(await evaluate("document.querySelector('.ai-play-notices').getAttribute('role')"),'status');
  assert.equal(await evaluate("document.querySelector('.ai-play-notices [role=dialog]')"),null);
  await evaluate(`(() => {
    const state=structuredClone(window.interactiveFixture.receipts.demo.state);
    state.revision=3;state.log=[...state.log.slice(1),'Player A passes priority.'];
    window.interactiveFixture.nextStates.push(state);
  })()`);
  await click('Pass Priority');
  await waitFor('window.interactiveFixture.actions.length===2 && !document.querySelector(".turn-command-actions button:not(#automatic-play-toggle)").disabled');
  assert.equal(await evaluate("document.querySelectorAll('.ai-play-notice').length"),1,'Unrelated revision does not replay a cast');
  await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate(`(() => {
    const state=structuredClone(window.interactiveFixture.receipts.demo.state);
    state.revision=4;state.log=[...state.log.slice(2),'Player B casts/activates Lava Spike.','Lava Spike resolves.'];
    window.interactiveFixture.nextStates.push(state);
  })()`);
  await click('Pass Priority');
  await waitFor("document.querySelectorAll('.ai-play-notice').length===2");
  const layout=await evaluate(`(() => {
    const el=document.querySelector('.ai-play-notice'),r=el.getBoundingClientRect();
    return {left:r.left,right:r.right,width:innerWidth,transparent:!document.elementFromPoint(r.left+10,r.top+10)?.closest('.ai-play-notices'),overflow:document.documentElement.scrollWidth>innerWidth+1};
  })()`);
  assert.ok(layout.left>=0 && layout.right<=layout.width+1);
  assert.equal(layout.transparent,true,'Notice cannot intercept underlying card clicks');
  assert.equal(layout.overflow,false);
  assert.equal(await evaluate('window.interactiveFixture.blockedFetches'),0);
  assert.equal(await evaluate('window.interactiveFixture.actions.length'),3,'Only explicit human clicks dispatched');
  if(process.env.MTG_UI_EVIDENCE){await mkdir(process.env.MTG_UI_EVIDENCE,{recursive:true});const shot=await command('Page.captureScreenshot',{format:'png'});await writeFile(process.env.MTG_UI_EVIDENCE+'/ai-plays-mobile.png',Buffer.from(shot.data,'base64'));}
  await waitFor("document.querySelectorAll('.ai-play-notice').length===0",10000);
  assert.equal(await evaluate("document.querySelectorAll('.recent-ai-plays li').length"),2,'Recent history survives toast expiry');
  await evaluate("document.querySelector('.recent-ai-plays').open=true");
  assert.match(await evaluate("document.querySelector('.recent-ai-plays').innerText"),/Lava Spike/);
  await reload();
  await waitFor("document.querySelector('.turn-command-actions button:not(#automatic-play-toggle):not(:disabled)')");
  assert.equal(await evaluate("document.querySelectorAll('.ai-play-notice,.recent-ai-plays li').length"),0,'Reload establishes a new baseline');
  await evaluate("document.querySelector('.debug-ai-hands input').click()");
  await waitFor("document.querySelector('.debug-ai-hand-cards')?.textContent.includes('Synthetic debug inspection card')");
  assert.equal(await evaluate('window.interactiveFixture.debugRequests'),1);
  await evaluate(`(() => {
    const state=structuredClone(window.interactiveFixture.receipts.demo.state);
    state.revision++;state.log.push('Synthetic priority update.');window.interactiveFixture.nextStates.push(state);
  })()`);
  await click('Pass Priority');
  await waitFor("document.querySelector('.debug-ai-hands small')?.textContent.includes('current match revision 5')");
  assert.equal(await evaluate('window.interactiveFixture.debugRequests'),1,'An advancing match does not cancel/restart the hand request');
  await click('Refresh AI hand snapshot');
  await waitFor('window.interactiveFixture.debugRequests===2 && !document.querySelector(".debug-ai-hands button").disabled');
  assert.match(await evaluate("document.querySelector('.debug-ai-hands small').textContent"),/revision 5/);
  await evaluate('window.interactiveFixture.debugDenied=true');
  await click('Refresh AI hand snapshot');
  await waitFor("document.querySelector('.debug-ai-hands [role=alert]')?.textContent.includes('inspection disabled')");
  assert.equal(await evaluate('window.interactiveFixture.blockedFetches'),0);
  console.log('PASS real App synthetic updates: resolved AI casts, rolling tail, repeats, 6s lifetime/history, mobile, focus, click-through; opt-in debug snapshot, revision stability, explicit refresh/errors; no real API/game mutations');
} finally { await close(); }
