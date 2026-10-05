import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { openBrowser } from './browser-driver.mjs';
const origin = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15483';
for (const seat of [1, 2]) for (const kind of ['normal', 'generic', 'hybrid', 'target', 'band', 'restriction', 'empty']) {
  const browser = await openBrowser(`${origin}/tests/attack-all.html?case=${seat}-${kind}`);
  const { evaluate, waitFor, click } = browser;
  const writes = () => evaluate('window.attackEvidence.writes');
  async function select(label, value) {
    await evaluate(`(() => {const s=document.querySelector('select[aria-label="${label}"]'); s.value=${JSON.stringify(value)}; s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  }
  try {
    await waitFor("document.querySelector('#attack-declaration')");
    await click('Resume automatic play');
    await new Promise(resolve => setTimeout(resolve, 2000));
    assert.deepEqual(await writes(), [], 'human declaration must not autoplay');
    if (kind === 'empty') {
      assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Attack all eligible').disabled"), true);
      console.log(`PASS seat ${seat} empty: disabled, no autoplay/write`);
      continue;
    }
    await click('Select all');
    await waitFor("document.querySelectorAll('#attack-declaration input[type=checkbox]:checked').length===2");
    assert.deepEqual(await writes(), [], 'Select all never declares');
    await click('Clear attackers');
    await waitFor("document.querySelectorAll('#attack-declaration input[type=checkbox]:checked').length===0");
    if (kind === 'target') {
      await select('Defender for hero', 'walker');
      await waitFor("document.querySelector('select[aria-label=" + JSON.stringify('Defender for hero') + "]').value==='walker'");
    }
    if (kind === 'band') {
      await evaluate(`(() => { const data=new DataTransfer(); const source=document.querySelector('.card[aria-label^="hero;"]'); const target=document.querySelector('.card[aria-label^="bear;"]'); if(!source||!target) throw Error('Missing battlefield cards'); source.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:data})); target.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data})); })()`);
      await waitFor("document.querySelectorAll('.combat-band').length===2");
    }
    await click('Attack all eligible');
    if (!['normal', 'restriction'].includes(kind)) {
      await waitFor("document.body.innerText.includes('No attack has been declared.')");
      assert.deepEqual(await writes(), [], 'tax/complex shortcut must not write');
      assert.equal(await evaluate("document.querySelectorAll('#attack-declaration input[type=checkbox]:checked').length"), 2);
      if (kind === 'hybrid') {
        assert.equal(await evaluate("document.querySelector('#attack-declaration button[type=submit]').disabled"), true);
        await evaluate("document.querySelector('#attack-declaration').requestSubmit()");
        assert.deepEqual(await writes(), [], 'required payment blocks submission');
        await select('Attack payment 1 for hero', 'U');
        await waitFor("!document.querySelector('#attack-declaration button[type=submit]').disabled");
      }
      await click('Submit Attackers');
    }
    await waitFor("window.attackEvidence.writes.length===1");
    await waitFor("!document.querySelector('#attack-declaration')");
    const recorded = await writes();
    assert.equal(recorded.length, 1);
    assert.equal(recorded[0].body.player_id, seat);
    const action = recorded[0].body.action;
    assert.equal(action.type, 'attack');
    assert.deepEqual(action.attackers, ['hero', 'bear']);
    assert.deepEqual(action.attack_targets, kind === 'target' ? { hero: 'walker' } : {});
    assert.deepEqual(action.bands, kind === 'band' ? [['hero', 'bear']] : []);
    if (kind === 'hybrid') assert.deepEqual(action.hybrid_choices, ['U']);
    if (['normal', 'restriction'].includes(kind)) {
      const replay = spawnSync(process.env.MTG_TEST_PYTHON || 'python3', ['tests/attack-all-engine.py', JSON.stringify(recorded[0].body)],
        { encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
      assert.equal(replay.status, 0, replay.stderr + replay.stdout);
      console.log(replay.stdout.trim());
    }
    console.log(`PASS seat ${seat} ${kind}: eligible-only, explicit review/payment where needed, exactly one action, no human autoplay`);
  } finally { await browser.close(); }
}
// Two synchronous clicks before React re-renders exercise App's mutation gate.
const browser = await openBrowser(`${origin}/tests/attack-all.html?case=2-normal`);
try {
  await browser.waitFor("document.querySelector('#attack-declaration')");
  await browser.evaluate("(() => { const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Attack all eligible'); b.click(); b.click(); })()");
  await browser.waitFor("!document.querySelector('#attack-declaration')");
  assert.equal(await browser.evaluate('window.attackEvidence.writes.length'), 1);
  console.log('PASS rapid double click: App mutation gate sends exactly one action');
} finally { await browser.close(); }
