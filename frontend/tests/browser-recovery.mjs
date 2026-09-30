import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';
const backend = 'http://127.0.0.1:10199';
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
  if (process.argv.includes('--verify-restart')) {
    await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play')");
    const id = await evaluate("localStorage.getItem('mtg.activeMatch')");
    const state = await (await fetch(`${backend}/matches/${id}`)).json();
    assert.equal(state.revision, 1);
    assert.equal(state.players['2'].battlefield.filter(c => c.id === 'forest').length, 1);
    assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Play Land Forest'))"), false);
    console.log('PASS App restores persisted state after a real backend process restart');
  } else {
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
  }
} finally { await close(); }
