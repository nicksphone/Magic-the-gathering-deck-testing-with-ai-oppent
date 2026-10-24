import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const frontend = 'http://127.0.0.1:15173';
const zero = {W: 0, U: 0, B: 0, R: 0, G: 0, C: 0};
const pile = '.player-row.player .land-stack';
const individual = `${pile} select[aria-label="Individual Island"]`;
const count = `${pile} select[aria-label="Number of Island to tap"]`;
async function get(path) {
  const response = await fetch(api + path);
  assert.equal(response.status, 200, path);
  return response.json();
}

for (const seat of [1, 2]) for (const kind of ['tap_land_for_mana', 'tap_nonland_for_mana', 'tap_lands_bulk']) {
  const response = await fetch(`${api}/fixture/built-app-mana?seat=${seat}`, {method: 'POST'});
  assert.equal(response.status, 200, 'Canonical fixture is mandatory');
  const fixture = await response.json();
  const browser = await openBrowser(frontend + '/');
  const {evaluate, waitFor, reload, close} = browser;
  const current = () => get(`/matches/${fixture.id}`);
  const facts = () => get(`/fixture/built-app-mana/${fixture.id}/facts`);
  async function settled() {
    const view = await current();
    await waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision === ${JSON.stringify(String(view.revision))} && !document.body.innerText.includes('Match operation pending')`);
    return facts();
  }
  async function clickExact(selector, text) {
    const lookup = `[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e => e.textContent.trim() === ${JSON.stringify(text)} && !e.matches(':disabled'))`;
    await waitFor(`${lookup}.length === 1`);
    await evaluate(`(() => {const nodes = ${lookup}; if (nodes.length !== 1) throw Error('Expected one enabled DOM control'); nodes[0].click();})()`);
  }
  async function select(selector, value) {
    await waitFor(`document.querySelectorAll(${JSON.stringify(selector)}).length === 1`);
    await evaluate(`(() => {const e = document.querySelector(${JSON.stringify(selector)}); if (e.matches(':disabled')) throw Error('Disabled selector'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(e, ${JSON.stringify(value)}); e.dispatchEvent(new Event('change', {bubbles:true}));})()`);
    await waitFor(`document.querySelector(${JSON.stringify(selector)})?.value === ${JSON.stringify(value)}`);
  }
  try {
    await waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    const before = await settled();
    const revision = (await current()).revision;
    const actor = before.players[String(seat)];
    const opponent = before.players[String(3 - seat)];
    assert.equal(await evaluate("document.querySelector('.player-row.player .seat-label').textContent.trim().startsWith(" + JSON.stringify(`P${seat} `) + ")"), true);
    assert.equal(fixture.land_ids.length, 3);
    assert.equal(new Set(fixture.land_ids).size, 3);
    for (const player of Object.values(before.players)) {
      assert.deepEqual(player.pool, zero);
      assert.deepEqual(player.snow_pool, zero);
      assert.deepEqual(player.restricted_pool, []);
      assert.deepEqual(Object.values(player.land_tapped), [false, false, false]);
      assert.equal(player.ring_tapped, false);
      assert.equal(player.spells_cast, 0);
      assert.equal(player.battlefield_ids.length, 4);
      assert.deepEqual(Object.values(player.source_zones), ['battlefield', 'battlefield', 'battlefield', 'battlefield']);
      assert.equal(player.hand_count, 0);
      assert.equal(player.library_count, 56);
    }
    assert.deepEqual(before.action_requests, []);
    assert.equal(before.stack_size, 0);
    assert.deepEqual(before.position, {active_player: seat, priority_player: seat,
      step: 'precombat_main', turn: 5, winner: null});

    let expected;
    let buttonSelector;
    let buttonText;
    if (kind === 'tap_land_for_mana') {
      await clickExact(`${pile} summary`, 'Individual lands (3)');
      assert.deepEqual(await evaluate(`[...document.querySelector(${JSON.stringify(individual)}).options].map(o => o.value)`), fixture.land_ids);
      await select(individual, fixture.land_ids[1]);
      expected = {type: kind, card_id: fixture.land_ids[1], color: 'U'};
      buttonSelector = `${pile} .land-members button`;
      buttonText = 'Tap selected for U';
    } else if (kind === 'tap_nonland_for_mana') {
      expected = {type: kind, card_id: fixture.ring_id, color: 'C'};
      buttonSelector = '.player-row.player .card button[title="Activate Sol Ring for C"]';
      buttonText = 'Add 2 C';
    } else {
      await select(count, '2');
      expected = {type: kind, land_name: 'Island', count: 2, color: 'U'};
      buttonSelector = `${pile} button`;
      buttonText = 'Add U';
    }
    // Selection/review is not an action: no hidden POST, tap, or revision change.
    assert.equal((await current()).revision, revision);
    assert.deepEqual(await facts(), before);
    await clickExact(buttonSelector, buttonText);
    await waitFor(`(async () => {const r = await fetch(${JSON.stringify(api + '/matches/' + fixture.id)}); return r.ok && (await r.json()).revision === ${revision + 1};})()`);
    const after = await settled();
    assert.equal((await current()).revision, revision + 1);
    assert.equal(after.action_requests.length, 1, 'ONE public request, not one per bulk source');
    assert.deepEqual(after.action_requests[0], {body: {player_id: seat, action: expected}, status: 200});
    const result = after.players[String(seat)];
    const tapped = kind === 'tap_lands_bulk' ? [true, true, false]
      : kind === 'tap_land_for_mana' ? [false, true, false] : [false, false, false];
    assert.deepEqual(result.land_tapped, Object.fromEntries(fixture.land_ids.map((id, i) => [id, tapped[i]])));
    assert.equal(result.ring_tapped, kind === 'tap_nonland_for_mana');
    assert.deepEqual(result.pool, {...zero, [kind === 'tap_nonland_for_mana' ? 'C' : 'U']: kind === 'tap_land_for_mana' ? 1 : 2});
    const unchanged = ({pool, land_tapped, ring_tapped, ...rest}) => rest;
    assert.deepEqual(unchanged(result), unchanged(actor));
    assert.deepEqual(after.players[String(3 - seat)], opponent, 'Every retained opponent fact unchanged');
    assert.equal(after.stack_size, 0);
    assert.equal(after.players['1'].spells_cast, 0);
    assert.equal(after.players['2'].spells_cast, 0);
    assert.deepEqual(after.position, before.position);
    console.log(JSON.stringify({seat, kind, accepted: 1, outcome: 'PASS'}));
  } finally {
    try { await evaluate("localStorage.removeItem('mtg.activeMatch')"); }
    finally { await close(); }
  }
}
