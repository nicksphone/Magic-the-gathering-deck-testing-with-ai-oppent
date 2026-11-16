import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

// Declared canonical midgame episodes. No claim of natural opening-hand history.
const backend = 'http://127.0.0.1:10199';
const frontend = 'http://127.0.0.1:15173';
const warningOnly = process.env.MTG_BATTLE_WARNING_ONLY === '1';
const browser = await openBrowser(`${frontend}/`);
const {evaluate, waitFor, click, command, reload, close} = browser;
let state;
let id;

async function read(path) {
  const response = await fetch(`${backend}${path}`, {signal: AbortSignal.timeout(15000)});
  assert.equal(response.status, 200, path);
  return response.json();
}

async function load(seat, mode, variant = 'funded') {
  assert.ok(['funded', 'unsupported', 'simultaneous'].includes(variant));
  const suffix = variant === 'funded' ? '' : `/${variant}`;
  const response = await fetch(`${backend}/fixture/battle-payment${suffix}?seat=${seat}&mode=${mode}`, {
    method: 'POST', signal: AbortSignal.timeout(15000),
  });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  assert.equal(fixture.scope, 'declared canonical midgame');
  id = fixture.match.id;
  state = fixture.match;
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)}); localStorage.removeItem('mtg.pendingStart');`);
  await command('Page.reload');
  await visible();
  await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Resume automatic play')");
  return fixture;
}

async function visible() {
  await waitFor(`document.querySelector('.battlefield')?.dataset.matchId === ${JSON.stringify(id)} && document.querySelector('.battlefield')?.dataset.matchRevision === '${state.revision}' && !document.body.innerText.includes('Match operation pending')`);
}

async function sync(before) {
  const deadline = Date.now() + 15000;
  do {
    state = await read(`/matches/${id}`);
    if (state.revision > before) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  } while (Date.now() < deadline);
  assert.ok(state.revision > before, `No accepted revision after ${before}`);
  await visible();
}

async function press(label) {
  const before = state.revision;
  await click(label);
  await sync(before);
}

async function legal() {
  const result = await read(`/matches/${id}/legal-moves`);
  assert.equal(result.revision, state.revision);
  return result;
}

async function search() {
  const menu = await legal();
  const choice = menu.moves.find(move => move.type === 'choose_mechanic' && move.kind === 'search_library');
  assert.ok(choice, 'Expected an actual library-search control');
  const count = Math.min(choice.count, choice.options.length);
  const heading = `${choice.label} (P${choice.player_id})`;
  await evaluate(`(() => {
    const panel = [...document.querySelectorAll('div.block-panel')].find(el => el.querySelector(':scope > h3')?.textContent === ${JSON.stringify(heading)});
    if (!panel) throw new Error('Missing actor-bound search panel');
    const boxes = [...panel.querySelectorAll('input[type=checkbox]')].filter(box => !box.disabled);
    if (boxes.length < ${count}) throw new Error('Missing selectable search options');
    for (const box of boxes.slice(0, ${count})) if (!box.checked) box.click();
  })()`);
  await press('Confirm Selection');
}

async function advanceUntil(predicate, label) {
  for (let step = 0; step < 160; step++) {
    if (predicate(state)) return;
    assert.equal(state.winner, null, `Unexpected game end before ${label}`);
    const menu = await legal();
    const human = state.controllers[String(menu.player_id)] === 'human';
    if (human && menu.moves.some(move => move.type === 'choose_trigger_order')) {
      const before = state.revision;
      await evaluate(`(() => {
        const button = document.querySelector('.trigger-order-panel button');
        if (!button) throw new Error('Missing real simultaneous-trigger order control');
        button.click();
      })()`);
      await sync(before);
    } else if (human && state.pending_mechanic_choice?.kind === 'search_library') await search();
    else if (human && menu.moves.some(move => move.type === 'block')) await press('Submit Blocks');
    else await press('Next Step');
  }
  assert.fail(`Did not reach ${label}`);
}

async function cast(predicate) {
  const menu = await legal();
  const move = menu.moves.find(candidate => candidate.type === 'cast_spell' && predicate(candidate));
  assert.ok(move, 'Expected the real cast offer');
  await press(`Cast ${move.card_name ?? move.card_view.name}`);
}

async function episode(seat, mode) {
  const fixture = await load(seat, mode);
  await cast(move => move.card_id === fixture.battle);
  await advanceUntil(s => s.pending_mechanic_choice?.kind === 'search_library', 'Battle search');
  await search();
  let battle = state.players[String(seat)].battlefield.find(card => card.id === fixture.battle);
  assert.equal(battle.defense, 3);
  assert.equal(battle.battle_protector, 3 - seat);
  assert.equal(state.players[String(seat)].battlefield.filter(card => card.name === 'Forest').length, 8);
  assert.ok(await evaluate("document.querySelector('.battlefield').textContent.includes('Defense 3')"));
  await advanceUntil(s => s.step === 'declare_attackers', 'Battle attack');
  // Select without submitting to the default player defender; then target the Siege.
  await click('Select all');
  await waitFor("document.querySelectorAll('select[aria-label^=\"Defender for\"]').length === 3");
  await evaluate(`(() => {
    for (const select of document.querySelectorAll('select[aria-label^="Defender for"]')) {
      select.value = ${JSON.stringify('battle:' + fixture.battle)};
      select.dispatchEvent(new Event('change', {bubbles: true}));
    }
  })()`);
  await waitFor(`[...document.querySelectorAll('select[aria-label^="Defender for"]')].every(select => select.value === ${JSON.stringify('battle:' + fixture.battle)})`);
  await press('Submit Attackers');
  assert.deepEqual(new Set(state.attackers), new Set(fixture.attackers));
  assert.ok(Object.values(state.attack_targets).every(target => target === 'battle:' + fixture.battle));
  await advanceUntil(s => s.pending_mechanic_choice?.kind === 'effect_cast', 'Siege defeat choice');
  await cast(move => move.card_id === fixture.battle && move.selected_face_index === 1);
  await advanceUntil(s => s.players[String(seat)].battlefield.some(card => card.id === fixture.battle), 'back-face entry');
  battle = state.players[String(seat)].battlefield.find(card => card.id === fixture.battle);
  assert.equal(battle.name, 'Awakened Skyclave');
  assert.equal(battle.power, 4);
  assert.ok(battle.types.includes('Creature') && battle.types.includes('Land'));
  await cast(move => move.card_name === "Summoner's Pact");
  await advanceUntil(s => s.pending_mechanic_choice?.kind === 'deferred_upkeep_payment', 'next-own-upkeep payment');
  assert.equal(state.active_player, seat);
  assert.equal(state.pending_mechanic_choice.player_id, seat);
  const due = state.revision;
  await command('Page.reload');
  await visible();
  assert.equal((await read(`/matches/${id}`)).revision, due, 'Refresh must not pay or advance the choice');
  await waitFor(`document.body.textContent.includes('Pay {2}{G}{G} or lose the game (P${seat})')`);
  await press('Pay {2}{G}{G}');
  assert.equal(state.pending_mechanic_choice, null);
  assert.equal(state.winner, null);
  assert.ok(state.log.some(line => line.includes('pays {2}{G}{G} for the delayed upkeep ability')));
  await cast(move => move.card_name === "Summoner's Pact");
  await advanceUntil(s => s.pending_mechanic_choice?.kind === 'deferred_upkeep_payment', 'second upkeep payment');
  await press('Decline payment; lose the game');
  assert.equal(state.winner, 3 - seat);
  await waitFor(`document.querySelector('.game-result')?.textContent.includes('P${3 - seat} wins')`);
  assert.equal(await evaluate("document.body.textContent.includes('Unsupported mechanic choice:')"), false);
  console.log(`PASS declared canonical midgame ${mode} seat ${seat}: Battle combat/transform, Pact pay/decline, pending-choice refresh, game result`);
}

const paymentKind = 'deferred_upkeep_payment';
const paymentCount = () => state.log.filter(line => line.includes('pays {2}{G}{G} for the delayed upkeep ability.')).length;

async function simultaneous(seat) {
  const fixture = await load(seat, 'human_vs_human', 'simultaneous');
  const forests = () => state.players[String(seat)].battlefield.filter(card => card.name === 'Forest');
  assert.equal(forests().length, 8);
  assert.equal(state.pending_mechanic_choice, null);
  assert.equal(paymentCount(), 0);
  for (const pact of fixture.pacts) {
    await cast(move => move.card_id === pact);
    await advanceUntil(s => s.pending_mechanic_choice?.kind === 'search_library', 'real Pact search');
    await search();
  }
  await advanceUntil(s => s.pending_trigger_order !== null, 'simultaneous upkeep order');
  assert.equal(state.active_player, seat);
  assert.equal(state.step, 'upkeep');
  assert.equal(state.pending_trigger_order.current_controller, seat);
  const menu = await legal();
  assert.equal(menu.moves.find(move => move.type === 'choose_trigger_order').trigger_order.length, 2);
  await advanceUntil(s => s.pending_mechanic_choice?.kind === paymentKind, 'first simultaneous debt');
  const turn = state.turn;
  assert.deepEqual(state.pending_mechanic_choice.options, ['pay', 'decline']);
  assert.equal(state.pending_mechanic_choice.player_id, seat);
  const first = state.revision;
  await press('Pay {2}{G}{G}');
  assert.equal(state.revision, first + 1, 'One first payment must commit once');
  assert.equal(state.turn, turn);
  assert.equal(state.step, 'upkeep');
  assert.equal(state.winner, null);
  assert.equal(paymentCount(), 1);
  assert.ok(state.stack.some(item => item.effect_key === paymentKind) || state.pending_mechanic_choice?.kind === paymentKind, 'The first choice must leave the second obligation owed');
  await advanceUntil(s => s.pending_mechanic_choice?.kind === paymentKind, 'remaining simultaneous debt');
  assert.equal(state.turn, turn);
  assert.equal(state.step, 'upkeep');
  assert.equal(state.pending_mechanic_choice.player_id, seat);
  assert.deepEqual(state.pending_mechanic_choice.options, ['pay', 'decline']);
  assert.equal(forests().filter(card => card.tapped).length, 4);
  const pending = structuredClone(state);
  await reload();
  await visible();
  assert.deepEqual(await read(`/matches/${id}`), pending, 'Refresh must preserve the second obligation and revision');
  await waitFor(`document.body.textContent.includes('Pay {2}{G}{G} or lose the game (P${seat})')`);
  const second = state.revision;
  await press('Pay {2}{G}{G}');
  assert.equal(state.revision, second + 1, 'One second payment must commit once');
  assert.equal(state.turn, turn);
  assert.equal(state.step, 'upkeep');
  assert.equal(state.winner, null);
  assert.equal(state.pending_mechanic_choice, null);
  assert.equal(paymentCount(), 2);
  assert.equal(forests().filter(card => card.tapped).length, 8);
  await advanceUntil(s => s.step === 'draw', 'draw after both obligations');
  assert.equal(state.turn, turn);
  assert.equal(state.active_player, seat);
  assert.equal(paymentCount(), 2);
  console.log(`PASS declared canonical midgame simultaneous Pact debts seat ${seat}: real casts/order, first payment continuation, pending-second refresh, two payments once`);
}

async function unsupported(seat) {
  await load(seat, 'human_vs_human', 'unsupported');
  await waitFor(`[...document.querySelectorAll('div.block-panel > h3')].some(el => el.textContent === 'Diagnostic unsupported choice (P${seat})')`);
  const controls = await evaluate(`(() => {
    const panel = [...document.querySelectorAll('div.block-panel')].find(el => el.querySelector(':scope > h3')?.textContent === 'Diagnostic unsupported choice (P${seat})');
    if (!panel) throw new Error('Missing unsupported-choice panel');
    return {buttons: panel.querySelectorAll('button').length,
      warning: [...panel.querySelectorAll('[role=alert]')].some(el => el.textContent.includes('Unsupported mechanic choice: diagnostic_unknown'))};
  })()`);
  assert.equal(controls.warning, true, `Missing explicit unsupported-control warning for seat ${seat}`);
  assert.equal(controls.buttons, 0);
  assert.equal((await read(`/matches/${id}`)).revision, 0);
  console.log(`PASS explicit unknown-control warning, no fabricated choice button, seat ${seat}`);
}

try {
  if (warningOnly) console.log('Focused warning-only diagnostic; not the full midgame browser cohort');
  else for (const mode of ['human_vs_human', 'player_vs_ai']) {
    for (const seat of [1, 2]) await episode(seat, mode);
  }
  if (!warningOnly) for (const seat of [1, 2]) await simultaneous(seat);
  for (const seat of [1, 2]) await unsupported(seat);
} finally {
  await close();
}
