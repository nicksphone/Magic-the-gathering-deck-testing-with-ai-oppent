import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { openBrowser } from './browser-driver.mjs';
const backend = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
const browser = await openBrowser('http://127.0.0.1:15173/');
const {evaluate,waitFor,click,command,close,onIntercept} = browser;
async function fresh() {
  const fixture = await (await fetch(`${backend}/fixture`, {method:'POST'})).json();
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play') && [...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))");
  return fixture.id;
}
try {
  await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
  await evaluate("document.querySelector('.saved-games').open = true; document.querySelectorAll('.tool-disclosure').forEach(el => el.open = true)");
  if (process.argv.includes('--verify-restart')) {
    await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play')");
    const id = await evaluate("localStorage.getItem('mtg.activeMatch')");
    const state = await (await fetch(`${backend}/matches/${id}`)).json();
    assert.equal(state.revision, 1);
    assert.equal(state.players['2'].battlefield.filter(c => c.id === 'forest').length, 1);
    assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))"), false);
    console.log('PASS App restores persisted state after a real backend process restart');
  } else {
  const historyResponse = await fetch(`${backend}/fixture/history`, {method:'POST'});
  assert.equal(historyResponse.status, 200);
  await click('Refresh saved matches');
  await waitFor("document.querySelectorAll('#saved-match-list button').length === 3 && [...document.querySelectorAll('button')].some(b => b.textContent === 'Show more saved matches')");
  await click('Show more saved matches');
  await waitFor("document.querySelectorAll('#saved-match-list button').length === 6");
  await click('Show fewer saved matches');
  await waitFor("document.querySelectorAll('#saved-match-list button').length === 3");
  assert.equal(await evaluate("getComputedStyle(document.querySelector('#saved-match-list')).overflowY"), 'auto');
  console.log('PASS saved-match preview limits rows, expands incrementally and collapses without crowding controls');
  await evaluate("document.querySelector('#diagnostic-history .sim-status-row button').click()");
  await waitFor("document.querySelectorAll('#diagnostic-run-list li').length === 3");
  await click('Show more diagnostic runs');
  await waitFor("document.querySelectorAll('#diagnostic-run-list li').length === 6");
  await click('Show fewer diagnostic runs');
  await waitFor("document.querySelectorAll('#diagnostic-run-list li').length === 3");
  assert.equal(await evaluate("getComputedStyle(document.querySelector('#diagnostic-run-list')).overflowY"), 'auto');
  console.log('PASS diagnostic history preview expands and collapses while remaining scroll bounded');
  let id = await fresh();
  await evaluate("(() => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.startsWith('Play Land Forest')); button.click(); button.click(); })()");
  await waitFor("!document.body.innerText.includes('Match operation pending') && ![...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))");
  let state = await (await fetch(`${backend}/matches/${id}`)).json();
  assert.equal(state.revision,1);
  assert.equal(state.players['2'].battlefield.filter(c => c.id === 'forest').length,1);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");
  assert.equal(await evaluate("localStorage.getItem('mtg.activeMatch')"),id);
  assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))"),false);
  console.log('PASS full App refresh restores match and overlapping land intents apply once');

  id = await fresh();
  const warmStatus = await evaluate(`fetch(${JSON.stringify(`${backend}/matches/${id}/action`)}, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Match-Revision': '0', 'Idempotency-Key': '00000000000000000000000000000000'},
    body: JSON.stringify({player_id: 99, action: {type: 'pass_priority'}}),
  }).then(response => response.status)`);
  assert.equal(warmStatus >= 400 && warmStatus < 500, true);
  assert.equal((await (await fetch(`${backend}/matches/${id}`)).json()).revision, 0);
  let discarded = false;
  onIntercept(async event => {
    if (event.request.method === 'POST' && event.responseStatusCode === 200 && !discarded) {
      discarded = true;
      await command('Fetch.failRequest',{requestId:event.requestId,errorReason:'Failed'});
    } else await command('Fetch.continueResponse',{requestId:event.requestId});
  });
  await command('Fetch.enable',{patterns:[{urlPattern:'*/matches/*/action',requestStage:'Response'}]});
  await click('Play Land Forest');
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play') && ![...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))");
  await command('Fetch.disable');
  state = await (await fetch(`${backend}/matches/${id}`)).json();
  assert.equal(discarded,true);
  assert.equal(state.revision,1);
  assert.equal(state.players['2'].battlefield.filter(c=>c.id==='forest').length,1);
  console.log('PASS lost accepted response reconciles authoritative state without replaying write');
  if (process.env.MTG_UI_EVIDENCE) {
    await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await evaluate('window.scrollTo(0,0)');
    const shot = await command('Page.captureScreenshot',{format:'png'});
    await writeFile(`${process.env.MTG_UI_EVIDENCE}/reconciled-api-error.png`,Buffer.from(shot.data,'base64'));
  }
  }
} finally { await close(); }
