import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = (await readFile(new URL('./browser-human-bo3.mjs', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '');

// Execute the real driver's first between-games branch, not a simulated game.
for (const [name, opponent, applied] of [
  ['human versus AI', 'ai', [false, false]],
  ['both human seats', 'human', [false, false]],
  ['first human already confirmed', 'human', [true, false]],
  ['both humans already confirmed', 'human', [true, true]],
]) {
  test(`${name}: confirm only unfinished humans before advancing`, async () => {
    const state = { id: 'series', revision: 10, winner: 1, game_number: 1,
      match_complete: false, next_play_draw_chooser: 2,
      controllers: { 1: 'human', 2: opponent },
      sideboarding: { 1: { applied: applied[0] }, 2: { applied: applied[1] } } };
    const humans = [1, 2].filter(id => state.controllers[id] === 'human');
    const expected = humans.filter(id => !state.sideboarding[id].applied);
    const confirmed = [], events = [];
    const finishedBranch = new Error('Observed next-game revision through the UI');
    let selected = '1', nextRequested = false, nextReads = 0, closed = false;
    const select = {
      get value() { return selected; },
      set value(value) { selected = value; },
      dispatchEvent(event) {
        assert.equal(event.type, 'change');
        assert.ok(humans.includes(Number(selected)), 'Only human seats are offered');
      },
    };
    const document = {
      body: { innerText: '' },
      querySelector(selector) {
        if (selector === '.battlefield') return { dataset: { matchRevision: String(state.revision) } };
        if (selector === 'select[aria-label="Sideboarding player"]') return select;
        return null;
      },
      querySelectorAll(selector) {
        assert.equal(selector, 'button');
        return [{ textContent: 'Resume automatic play' }];
      },
    };
    const context = vm.createContext({ document, localStorage: { setItem() {} },
      Event: class { constructor(type) { this.type = type; } } });
    const browser = {
      evaluate: async expression => vm.runInContext(expression, context),
      command: async method => assert.equal(method, 'Page.reload'),
      async click(label) {
        if (label === 'Confirm No Swaps') {
          const id = Number(selected);
          assert.equal(state.sideboarding[id].applied, false, 'Never reconfirm a disabled seat');
          state.sideboarding[id].applied = true;
          state.revision++;
          confirmed.push(id);
          events.push(`confirm:${id}`);
        } else {
          assert.ok(humans.every(id => state.sideboarding[id].applied),
            'The real next-game control is disabled until every human confirms');
          assert.equal(label, opponent === 'human' ? 'P2 Play First' : 'Start Next Game');
          events.push('next-game');
          nextRequested = true;
        }
      },
      async waitFor(expression) {
        assert.equal(Boolean(vm.runInContext(expression, context)), true, expression);
        if (nextRequested && expression.includes('dataset.matchRevision')) {
          assert.equal(state.game_number, 2, 'A sideboard receipt is not a next-game receipt');
          throw finishedBranch;
        }
      },
      async close() { closed = true; },
    };
    const fetch = async url => {
      if (url.includes('/decks/builtin/')) return { json: async () => ({ deck_text: '60 Mountain' }) };
      if (url.endsWith('/matches/start')) return { ok: true, json: async () => structuredClone(state) };
      assert.equal(url, 'http://127.0.0.1:10199/matches/series');
      // The first GET after clicking Next Game is deliberately still the old state.
      if (nextRequested && ++nextReads === 2) {
        state.game_number = 2;
        state.revision++;
        state.winner = null;
      }
      return { json: async () => structuredClone(state) };
    };
    const program = vm.runInNewContext(`(async () => { ${source}\n})()`, {
      assert, fetch, openBrowser: async () => browser,
      process: { env: { MTG_HUMAN_BO3_OPPONENT: opponent } },
      setTimeout: callback => callback(), console,
    });
    await assert.rejects(program, error => error === finishedBranch);
    assert.deepEqual(confirmed, expected);
    assert.deepEqual(events, [...expected.map(id => `confirm:${id}`), 'next-game']);
    assert.equal(nextReads, 2, 'Wait for the new game, not the prior sideboard revision');
    assert.equal(closed, true);
  });
}
