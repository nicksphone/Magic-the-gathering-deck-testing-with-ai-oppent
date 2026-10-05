import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN;
const evidence = process.env.MTG_OFFICER_EVIDENCE;
const phase = process.argv[2];
const scenariosFile = `${evidence}/pending-scenarios.json`;
async function request(url, method = 'GET', body) {
  const response = await fetch(api + url, {method, headers: {'Content-Type': 'application/json'},
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000)});
  assert.equal(response.status, 200, `${method} ${url}: ${await response.clone().text()}`);
  return response.json();
}
async function action(id, seat, action) {return request(`/matches/${id}/action`, 'POST', {player_id: seat, action});}
async function privacy(fixture, ai = false) {
  const id = fixture.match.id, seat = fixture.seat;
  const state = await request(`/matches/${id}`);
  const other = await request(`/matches/${id}/legal-moves?player_id=${3-seat}`);
  assert.deepEqual(other.moves, []);
  const serialized = JSON.stringify(state);
  for (const name of Object.values(fixture.labels)) assert.ok(!serialized.includes(name), `Private inspected name leaked in match GET: ${name}`);
  assert.ok(!serialized.includes('inspected_cards'));
  assert.ok(!serialized.includes('oracle_text":"Draw a card. Scry 1.'));
  if (ai) {
    const forbidden = await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`);
    assert.equal(forbidden.status, 403);
    assert.deepEqual(Object.keys(state.pending_mechanic_choice).sort(), ['kind', 'label', 'player_id']);
    for (const cid of fixture.top_ids) assert.ok(!serialized.includes(cid), 'AI inspection IDs leaked');
  } else {
    const legal = await request(`/matches/${id}/legal-moves?player_id=${seat}`);
    assert.equal(legal.moves.length, 1);
    const choice = legal.moves[0];
    assert.deepEqual(choice.inspected_cards.map(c => c.id), [...fixture.top_ids].reverse());
    assert.deepEqual(choice.options, fixture.eligible ? [...fixture.top_ids.slice(0, 2), '__none__'] : ['__none__']);
    for (const row of choice.inspected_cards) assert.equal(row.name, fixture.labels[row.id]);
  }
  return state;
}

if (phase === 'prepare') {
  const scenarios = [];
  for (const seat of [1, 2]) for (const eligible of [false, true]) {
    const fixture = await request(`/fixture/officer?seat=${seat}&eligible=${eligible}`, 'POST');
    const id = fixture.match.id;
    const legal = await request(`/matches/${id}/legal-moves?player_id=${seat}`);
    const activation = legal.moves.find(m => m.type === 'activate_ability');
    assert.equal(activation.mana_cost, '{3}{W}');
    assert.ok(!JSON.stringify(activation).includes('inspected_cards'));
    let state = await action(id, seat, {type: 'activate_ability', card_id: fixture.source_id, ability_index: 0});
    assert.equal(state.stack.length, 1);
    assert.equal(Object.values(state.players[seat].mana_pool).reduce((a, b) => a + b, 0), 0);
    for (let i = 0; i < 2; i++) state = await action(id, state.priority_player, {type: 'pass_priority'});
    assert.equal(state.pending_mechanic_choice.kind, 'topdeck_reveal_creature');
    await privacy(fixture);
    const internal = await request(`/fixture/officer-status/${id}`);
    assert.deepEqual(internal.libraries[seat], fixture.top_ids);
    scenarios.push({...fixture, pending_revision: state.revision, server_pid: internal.pid});
    console.log(`PASS HTTP P${seat} ${eligible ? 'qualifying' : 'no-hit'}: legal cost, payment, resolution, private GET/actor-only legal preview`);
  }
  for (const seat of [1, 2]) for (const eligible of [false, true]) {
    const fixture = await request(`/fixture/officer?seat=${seat}&eligible=${eligible}&ai=true`, 'POST');
    await privacy(fixture, true);
    console.log(`PASS HTTP AI P${seat} ${eligible ? 'qualifying' : 'no-hit'}: serialized pending redacted and actor legal-moves forbidden`);
  }
  await fs.writeFile(scenariosFile, JSON.stringify(scenarios, null, 2));
} else if (phase === 'browser') {
  const scenarios = JSON.parse(await fs.readFile(scenariosFile, 'utf8'));
  for (const fixture of scenarios) {
    const id = fixture.match.id, seat = fixture.seat;
    await privacy(fixture);
    const restored = await request(`/fixture/officer-status/${id}`);
    assert.notEqual(restored.pid, fixture.server_pid, 'Must restart actual backend process');
    assert.equal((await request(`/matches/${id}`)).revision, fixture.pending_revision);
    assert.deepEqual(restored.libraries[seat], fixture.top_ids);
    const browser = await openBrowser(process.env.MTG_FRONTEND_ORIGIN + '/');
    const {evaluate, waitFor, reload, click, command, close} = browser;
    try {
      await command('Network.enable');
      await command('Network.setBlockedURLs', {urls: ['https://*']});
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor(`document.querySelector('[aria-label="Privately inspected cards"] details') && document.body.innerText.includes('P${seat}')`);
      if (await evaluate(`[...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Pause automatic play'))`)) await click('Pause automatic play');
      assert.ok(await evaluate(`document.body.innerText.includes('Resume automatic play')`));
      const summaries = await evaluate(`Array.from(document.querySelectorAll('[aria-label="Privately inspected cards"] summary')).map(el => el.textContent)`);
      assert.equal(summaries.length, 4);
      for (const name of Object.values(fixture.labels)) assert.ok(summaries.some(text => text.includes(name)));
      assert.equal(summaries.filter(text => text.includes('(selectable)')).length, fixture.eligible ? 2 : 0);
      assert.equal(summaries.filter(text => text.includes('(not selectable)')).length, fixture.eligible ? 2 : 4);
      await evaluate(`document.querySelector('[aria-label="Privately inspected cards"] details').open = true`);
      assert.ok(await evaluate(`Boolean(document.querySelector('[aria-label="Privately inspected cards"] details p')?.textContent)`));
      const screenshot = await command('Page.captureScreenshot', {format: 'png'});
      await fs.writeFile(`${evidence}/P${seat}-${fixture.eligible ? 'qualifying' : 'no-hit'}-inspection.png`, Buffer.from(screenshot.data, 'base64'));
      // Reload the browser while the private persisted decision remains pending.
      await reload();
      await waitFor(`document.querySelectorAll('[aria-label="Privately inspected cards"] summary').length === 4`);
      if (await evaluate(`[...document.querySelectorAll('button')].some(b => b.textContent.startsWith('Pause automatic play'))`)) await click('Pause automatic play');
      let chosen;
      if (fixture.eligible) {
        chosen = fixture.top_ids[0];
        await evaluate(`(() => {
          const panel = document.querySelector('[aria-label="Privately inspected cards"]').parentElement;
          const label = [...panel.querySelectorAll('label')].find(el => el.textContent.includes(${JSON.stringify(fixture.labels[chosen])}));
          if (!label?.querySelector('input')) throw new Error('Missing eligible checkbox');
          label.querySelector('input').click();
        })()`);
        await click('Confirm Selection');
      } else {
        assert.equal(await evaluate(`document.querySelector('[aria-label="Privately inspected cards"]').parentElement.querySelectorAll('input[type="checkbox"]').length`), 0);
        await click('Acknowledge inspected cards');
      }
      const state = await waitForApiState(`${api}/matches/${id}`, s => !s.pending_mechanic_choice);
      assert.equal(state.stack.length, 0);
      const internal = await request(`/fixture/officer-status/${id}`);
      assert.equal(internal.draws[seat], 0);
      assert.deepEqual(internal.failed_draws, []);
      assert.equal(internal.trigger_staging, false);
      assert.deepEqual(state.players[seat].hand.map(c => c.id), chosen ? [chosen] : []);
      assert.deepEqual(new Set(internal.libraries[seat]), new Set(fixture.top_ids.filter(cid => cid !== chosen)));
      for (const cid of fixture.top_ids) assert.equal(Boolean(internal.observations[3-seat]?.[cid]), cid === chosen);
      await waitFor(`!document.querySelector('[aria-label="Privately inspected cards"]')`);
      console.log(`PASS BROWSER P${seat} ${fixture.eligible ? 'qualifying reveal' : 'no-hit acknowledgement'}: real process restore, rendered inspector, reload, UI selection, bottoming and reveal privacy`);
    } finally {await close();}
  }
} else throw new Error('Expected prepare or browser phase');
