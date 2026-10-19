import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const humanOpponent = process.env.MTG_HUMAN_BO3_OPPONENT === 'human';
const named = await (await fetch(`${backend}/decks/builtin/${encodeURIComponent('Mono Red Aggro')}`)).json();
const deck = named.deck_text.trim().split('\n').map(line => {
  const [, quantity, card_name] = line.trim().match(/^(\d+) (.+)$/) ?? [];
  if (!quantity) throw new Error(`Invalid built-in deck line: ${line}`);
  return { quantity: Number(quantity), card_name };
});
const started = await fetch(`${backend}/matches/start`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    deck_a: deck, deck_b: [{ quantity: 60, card_name: 'Island' }],
    controller_a: 'human', controller_b: humanOpponent ? 'human' : 'ai',
    mode: humanOpponent ? 'human_vs_human' : 'player_vs_ai', best_of: 3, seed: 73,
  }),
});
if (!started.ok) throw new Error(`Could not start human BO3: ${started.status} ${await started.text()}`);
let state = await started.json();
const id = state.id;
const preferred = ['Monastery Swiftspear', 'Soul-Scar Mage', 'Kumano Faces Kakkazan', 'Lightning Bolt', 'Lava Spike', 'Rift Bolt', 'Skewer the Critics', 'Skullcrack'];
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close } = browser;
const counts = {};

async function syncAfter(action, revision) {
  counts[action] = (counts[action] ?? 0) + 1;
  const deadline = Date.now() + 15000;
  do {
    await new Promise(resolve => setTimeout(resolve, 75));
    state = await (await fetch(`${backend}/matches/${id}`)).json();
  } while (state.revision <= revision && Date.now() < deadline);
  assert.ok(state.revision > revision, `${action} did not advance revision ${revision}; alert=${await evaluate("document.querySelector('[role=alert]')?.innerText")}`);
  await waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision === '${state.revision}' && !document.body.innerText.includes('Match operation pending')`);
}

try {
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play')");
  const observed = new Set([1]);
  for (let step = 0; step < (humanOpponent ? 1800 : 500) && !state.match_complete; step++) {
    const revision = state.revision;
    if (state.winner !== null) {
      for (const playerId of [1, 2]) {
        if (state.controllers[String(playerId)] !== 'human' || state.sideboarding[String(playerId)].applied) continue;
        const sideboardRevision = state.revision;
        await evaluate(`(() => { const select = document.querySelector('select[aria-label="Sideboarding player"]'); select.value = '${playerId}'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
        await waitFor(`document.querySelector('select[aria-label="Sideboarding player"]').value === '${playerId}'`);
        await click('Confirm No Swaps');
        await syncAfter(`sideboard-${playerId}`, sideboardRevision);
        assert.equal(state.sideboarding[String(playerId)].applied, true);
      }
      const chooser = state.next_play_draw_chooser;
      const nextGameRevision = state.revision;
      await click(chooser && state.controllers[String(chooser)] === 'human' ? `P${chooser} Play First` : 'Start Next Game');
      await syncAfter('next-game', nextGameRevision);
      observed.add(state.game_number);
      continue;
    }
    const legal = await (await fetch(`${backend}/matches/${id}/legal-moves`)).json();
    if (legal.revision !== revision) { state = await (await fetch(`${backend}/matches/${id}`)).json(); continue; }
    const moves = legal.moves;
    const choose = type => moves.find(move => move.type === type);
    if (legal.player_id === 2) {
      if (!humanOpponent) {
        await click('AI Step x30');
        await syncAfter('ai-step', revision);
      } else if (state.pregame_pending) {
        await click('Keep Hand');
        await syncAfter('seat-2-keep', revision);
      } else if (choose('play_land')) {
        await click('Play Land Island');
        await syncAfter('seat-2-land', revision);
      } else {
        await click(step % 2 ? 'Next Step' : 'Pass Priority');
        await syncAfter('seat-2-pass', revision);
      }
      continue;
    }
    if (choose('choose_trigger_order')) {
      await evaluate("document.querySelector('.trigger-order-panel button').click()");
      await syncAfter('trigger-order', revision);
    } else if (choose('choose_mechanic')) {
      const move = choose('choose_mechanic');
      if (!['cleanup_discard', 'mulligan_bottom'].includes(move.kind)) throw new Error(`Unexpected human choice: ${move.kind}`);
      await evaluate(`(() => { const boxes = [...document.querySelectorAll('.block-panel input[type=checkbox]')]; boxes.slice(0, ${move.count}).forEach(box => box.click()); })()`);
      await click('Confirm Selection');
      await syncAfter(move.kind, revision);
    } else if (state.pregame_pending) {
      const hand = state.players['1'].hand;
      const mulligans = state.mulligan_count['1'];
      if (hand.filter(card => card.name === 'Mountain').length < 2 && mulligans < 2 && choose('mulligan')) {
        await click('Mulligan');
        await syncAfter('mulligan', revision);
      } else {
        const remaining = Math.max(0, mulligans - (state.mulligan_bottomed?.['1'] ?? 0));
        const bottom = hand.filter(card => card.name !== 'Mountain').slice(0, remaining);
        for (const card of bottom) {
          const label = `Bottom ${card.name} ${card.id}`;
          await evaluate(`[...document.querySelectorAll('input[type=checkbox]')].find(box => box.getAttribute('aria-label') === ${JSON.stringify(label)}).click()`);
        }
        await click('Keep Hand');
        await syncAfter('keep', revision);
      }
    } else if (choose('play_land')) {
      await click('Play Land Mountain');
      await syncAfter('land', revision);
    } else if (choose('attack')) {
      await click('Attack all eligible');
      await click('Submit Attackers');
      await syncAfter('attack', revision);
    } else {
      const cast = preferred.map(name => moves.find(move => move.type === 'cast_spell' && move.card_name === name)).find(Boolean);
      if (cast && ['precombat_main', 'postcombat_main'].includes(state.step) && state.active_player === 1 && state.stack.length === 0) {
        if (cast.target_hints?.player_targets?.length) {
          await evaluate(`(() => { const box = [...document.querySelectorAll('.cast-card-box')].find(box => [...box.querySelectorAll('button')].some(button => button.textContent.startsWith(${JSON.stringify(`Cast ${cast.card_name}`)}))); const select = [...box.querySelectorAll('select')].find(select => select.options[0]?.text === 'Target Player'); select.value = '2'; select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
        }
        await click(`Cast ${cast.card_name}`);
        await syncAfter('cast', revision);
      } else {
        await click(step % 2 ? 'Next Step' : 'Pass Priority');
        await syncAfter('pass', revision);
      }
    }
  }
  assert.equal(state.match_complete, true, `Human BO3 unfinished: game=${state.game_number} turn=${state.turn} counts=${JSON.stringify(counts)}`);
  assert.equal(state.score['1'], 2);
  assert.deepEqual([...observed].sort(), [1, 2]);
  assert.ok((counts.mulligan ?? 0) >= 1);
  assert.ok((counts.land ?? 0) >= 2 && (counts.cast ?? 0) >= 2 && (counts.attack ?? 0) >= 1);
  await waitFor("document.querySelector('.sideboard-panel')?.innerText.includes('Match Complete')");
  console.log(`PASS natural ${humanOpponent ? 'human-vs-human' : 'human-vs-AI'} BO3 through UI controls: ${JSON.stringify(counts)}`);
} finally { await close(); }
