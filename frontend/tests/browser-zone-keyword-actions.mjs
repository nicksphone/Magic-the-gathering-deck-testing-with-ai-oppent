import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const frontend = 'http://127.0.0.1:15173';
async function get(path) {
  const response = await fetch(api + path);
  assert.equal(response.status, 200, path);
  return response.json();
}

for (const seat of [1, 2]) for (const kind of ['foretell', 'cycle_card', 'ninjutsu']) {
  const response = await fetch(`${api}/fixture/zone-keyword?seat=${seat}&kind=${kind}`, {method: 'POST'});
  assert.equal(response.status, 200, 'Registered complete-RAW fixture is mandatory');
  const fixture = await response.json();
  const browser = await openBrowser(frontend + '/');
  const {evaluate, waitFor, click, reload, close} = browser;
  const calls = [];
  const facts = async () => {
    const value = await get(`/fixture/zone-keyword/${fixture.id}/facts`);
    assert.ok(Array.isArray(value.action_requests));
    calls.splice(0, calls.length, ...value.action_requests);
    return value;
  };
  const current = () => get(`/matches/${fixture.id}`);
  async function settled() {
    const view = await current();
    await waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision === ${JSON.stringify(String(view.revision))} && !document.body.innerText.includes('Match operation pending')`);
    return facts();
  }
  async function action(label, expectedType, player) {
    const before = await current();
    await facts();
    const count = calls.length;
    await click(label);
    await waitFor(`(async () => {const r = await fetch(${JSON.stringify(api + '/matches/' + fixture.id)}); return r.ok && (await r.json()).revision === ${before.revision + 1};})()`);
    const after = await settled();
    assert.equal(calls.length, count + 1, 'Exactly one accepted public request');
    const receipt = calls.at(-1);
    assert.equal(receipt.status, 200);
    assert.equal(receipt.body.player_id, player);
    assert.equal(receipt.body.action.type, expectedType);
    return after;
  }
  async function resolve(label, destination) {
    let value = await facts();
    for (let n = 0; n < 2; n++) {
      assert.equal(value.stack_size, 1, label + ': real ability is pending');
      value = await action('Pass Priority', 'pass_priority', value.priority_player);
      if (kind === 'ninjutsu') {
        assert.equal(value.first_attacker_zone, 'battlefield');
        assert.ok(value.attackers.includes(fixture.attacker_ids[0]));
        assert.equal(value.attacker_zone, 'hand');
      }
    }
    assert.equal(value.stack_size, 0, label + ': ability resolved');
    assert.equal(value.zone, destination);
    return value;
  }
  try {
    await waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    const initial = await settled();
    assert.equal(initial.zone, 'hand');
    assert.equal(initial.hand_count, 1);
    assert.equal(initial.lands_tapped, 0);
    assert.equal(initial.stack_size, 0);

    if (kind === 'foretell') {
      const result = await action('Foretell Doomskar', kind, seat);
      assert.equal(calls.at(-1).body.action.card_id, fixture.card_id);
      assert.equal(result.zone, 'exile');
      assert.equal(result.face_down, true);
      assert.equal(result.stack_size, 0);
      assert.equal(result.priority_player, seat);
      assert.equal(result.hand_count, 0);
      assert.equal(result.library_count, initial.library_count);
      assert.equal(result.exile_count, 1);
      assert.equal(result.owner_can_look, true);
      assert.equal(result.opponent_can_look, false);
      assert.equal(result.public_exile_hidden, true);
      assert.equal(result.opponent_exile_hidden, true);
      assert.equal(result.owner_exile_visible, true);
      assert.equal(result.name_in_log, false);
      assert.equal(result.foretells, 1);
      assert.equal(result.spells_cast, 0);
      assert.equal(result.lands_tapped, 2);
      assert.equal(result.mana_remaining, 0);
    } else if (kind === 'cycle_card') {
      const paid = await action('Cycle Hollow One', kind, seat);
      assert.equal(calls.at(-1).body.action.card_id, fixture.card_id);
      assert.equal(paid.zone, 'graveyard');
      assert.equal(paid.hand_count, 0);
      assert.equal(paid.library_count, initial.library_count);
      assert.equal(paid.stack_size, 1);
      assert.equal(paid.lands_tapped, 2);
      assert.equal(paid.mana_remaining, 0);
      const result = await resolve('Cycling', 'graveyard');
      assert.equal(result.hand_count, 1);
      assert.equal(result.library_count, initial.library_count - 1);
      assert.equal(result.graveyard_count, 1);
    } else {
      assert.equal(fixture.attacker_ids.length, 2);
      assert.equal(fixture.attacker_id, fixture.attacker_ids[1], 'Select the SECOND attacker deliberately');
      assert.notEqual(fixture.attacker_ids[0], fixture.attacker_ids[1]);
      const beforeSelection = await current();
      const selectionCalls = calls.length;
      await click('Attack all eligible');
      await waitFor("document.body.innerText.includes('No attack has been declared.')");
      const selected = await facts();
      assert.equal(calls.length, selectionCalls, 'Selection must not send an action');
      assert.equal((await current()).revision, beforeSelection.revision);
      assert.deepEqual(selected.attackers, []);
      let combat = await action('Submit Attackers', 'attack', seat);
      assert.deepEqual(calls.at(-1).body.action.attackers, fixture.attacker_ids);
      assert.deepEqual(combat.attackers, fixture.attacker_ids);
      for (let n = 0; n < 4 && combat.step !== 'declare_blockers'; n++) {
        combat = await action('Pass Priority', 'pass_priority', combat.priority_player);
        assert.equal(combat.first_attacker_zone, 'battlefield');
        assert.ok(combat.attackers.includes(fixture.attacker_ids[0]));
      }
      assert.equal(combat.step, 'declare_blockers', 'Must reach genuine blocking step');
      const unblocked = await action('Declare blockers (0)', 'block', 3 - seat);
      assert.deepEqual(calls.at(-1).body.action.blocks, {});
      assert.equal(unblocked.blockers_declared, true);
      assert.deepEqual(unblocked.blocks, {});
      assert.equal(unblocked.priority_player, seat);
      assert.deepEqual(unblocked.attackers, fixture.attacker_ids);
      assert.equal(unblocked.first_attacker_zone, 'battlefield');
      const paid = await action(`Ninjutsu Ninja of the Deep Hours: return ${fixture.attacker_id}`, kind, seat);
      const payload = calls.at(-1).body.action;
      assert.equal(payload.card_id, fixture.card_id);
      assert.equal(payload.return_card_id, fixture.attacker_id);
      assert.equal(paid.attacker_zone, 'hand');
      assert.equal(paid.zone, 'hand', 'Ninja moves only on ability resolution');
      assert.equal(paid.hand_count, 2);
      assert.equal(paid.stack_size, 1);
      assert.equal(paid.lands_tapped, 2);
      assert.equal(paid.mana_remaining, 0);
      assert.ok(!paid.attackers.includes(fixture.attacker_id));
      assert.equal(paid.first_attacker_zone, 'battlefield');
      assert.ok(paid.attackers.includes(fixture.attacker_ids[0]));
      const result = await resolve('Ninjutsu', 'battlefield');
      assert.equal(result.attacker_zone, 'hand');
      assert.equal(result.hand_count, 1);
      assert.equal(result.tapped, true);
      assert.ok(result.attackers.includes(fixture.card_id));
      assert.equal(result.attack_target, `player:${3 - seat}`);
      assert.equal(result.first_attacker_zone, 'battlefield');
      assert.deepEqual(result.attackers, [fixture.attacker_ids[0], fixture.card_id]);
    }
    // Numeric/coordinate-only receipt; never publish private match snapshots.
    console.log(JSON.stringify({seat, kind, accepted: calls.length, outcome: 'PASS'}));
  } finally {
    try { await evaluate("localStorage.removeItem('mtg.activeMatch')"); }
    finally { await close(); }
  }
}
