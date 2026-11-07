import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url), React = require('react');
let active;
const code = await build({entryPoints: [new URL('../src/components/AiHandDebug.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  external: ['../api/client']});
const module = {exports: {}};
new Function('require', 'module', 'exports', code.outputFiles[0].text)(name => name === 'react'
  ? {...React, useState: value => active.state(value), useEffect: (fn, deps) => active.effect(fn, deps)}
  : name === '../api/client' ? {api: {aiDebugHands: id => active.request(id)}, resolveCardMediaUrl: uri => uri}
    : require(name), module, module.exports);
const Component = module.exports.AiHandDebug;
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === 'object' ? [tree, ...nodes(tree.props?.children)] : [];
}
function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join('');
  return tree && typeof tree === 'object' ? text(tree.props?.children) : String(tree ?? '');
}
function harness(match) {
  const cells = [], effects = [], requests = [];
  let cursor, pending, dirty, tree;
  const h = {match, requests,
    state(initial) {
      const index = cursor++;
      if (!(index in cells)) cells[index] = typeof initial === 'function' ? initial() : initial;
      return [cells[index], value => {const next = typeof value === 'function' ? value(cells[index]) : value;
        if (!Object.is(next, cells[index])) {cells[index] = next; dirty = true;}}];
    },
    effect(fn, deps) {
      const index = cursor++, previous = effects[index];
      if (!previous || deps.some((value, i) => !Object.is(value, previous.deps[i]))) pending.push({index, fn, deps});
    },
    request(id) {
      return new Promise((resolve, reject) => requests.push({id, resolve, reject}));
    },
    render() {
      active = h;
      for (let turn = 0; turn < 10; turn++) {
        cursor = 0; pending = []; dirty = false; tree = Component({match: h.match});
        for (const {index, fn, deps} of pending) {effects[index]?.cleanup?.(); effects[index] = {deps, cleanup: fn()};}
        if (!dirty) return tree;
      }
      throw Error('Component failed to settle');
    },
    enable(value = true) {nodes(h.render()).find(n => n.type === 'input').props.onChange({target: {checked: value}}); return h.render();},
    refresh() {
      const button = nodes(h.render()).find(n => n.type === 'button' && /Refresh/i.test(text(n)));
      assert.ok(button, 'Explicit refresh control exists'); assert.ok(!button.props.disabled);
      button.props.onClick(); return h.render();
    },
    async settle() {await Promise.resolve(); await Promise.resolve(); return h.render();},
    dispose() {for (const effect of effects) effect?.cleanup?.();},
  };
  h.render(); return h;
}
// Synthetic protocol cards only; no real hands, HTTP, app, or backend imports.
const match = (fields = {}) => ({id: 'synthetic-a', game_number: 1, revision: 10,
  controllers: {'1': 'human', '2': 'ai'}, ...fields});
const snapshot = (fields = {}) => ({debug_only: true, match_id: 'synthetic-a', game_number: 1,
  revision: 10, turn: 3, hands: {'2': [{id: 'synthetic-private', name: 'Synthetic debug vector',
    mana_cost: '', type_line: 'Protocol vector', oracle_text: 'Not a real printed card.'}]}, ...fields});

test('in-flight reads survive revisions and coalesce stale responses toward the latest revision', async t => {
  const h = harness(match()); t.after(h.dispose);
  assert.equal(h.requests.length, 0); h.enable();
  for (const revision of [11, 12, 13]) {h.match = match({revision}); h.render();}
  assert.equal(h.requests.length, 1, 'Autoplay must not cancel/refetch on every revision');
  h.requests[0].resolve(snapshot()); const tree = await h.settle();
  assert.match(text(tree), /Synthetic debug vector/);
  assert.match(text(tree), /snapshot.*revision 10/i); assert.match(text(tree), /current.*revision 13/i);
  assert.equal(h.requests.length, 2, 'The completed stale response schedules one catch-up read');
  assert.match(text(tree), /stale/i); assert.match(text(tree), /refreshing/i);
  for (const revision of [14, 15]) {h.match = match({revision}); h.render();}
  assert.equal(h.requests.length, 2, 'Do not restart or duplicate the pending catch-up read');
  h.requests[1].resolve(snapshot({revision: 13}));
  const catchingUp = await h.settle();
  assert.match(text(catchingUp), /snapshot.*revision 13/i, 'The pending response was not cancelled by newer revisions');
  assert.match(text(catchingUp), /Synthetic debug vector/);
  assert.equal(h.requests.length, 3, 'Coalesce another read for the latest committed revision');
  h.requests[2].resolve(snapshot({revision: 15})); const fresh = await h.settle();
  assert.match(text(fresh), /snapshot.*revision 15/i);
  assert.doesNotMatch(text(fresh), /stale|refreshing/i);
  h.render(); h.render(); assert.equal(h.requests.length, 3, 'A current snapshot does not create a fetch loop');
});
test('manual same-game refresh retains the previous snapshot until an empty hand arrives', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  h.requests[0].resolve(snapshot()); await h.settle();
  const pending = h.refresh(); assert.equal(h.requests.length, 2);
  assert.match(text(pending), /Synthetic debug vector/, 'Refresh does not blank the same-game hand');
  assert.match(text(pending), /refreshing/i);
  h.requests[1].resolve(snapshot({hands: {'2': []}}));
  const tree = await h.settle(); assert.match(text(tree), /snapshot.*revision 10/i); assert.match(text(tree), /Empty hand/);
  assert.doesNotMatch(text(tree), /Synthetic debug vector/);
});
test('a committed revision starts exactly one automatic read while keeping the stale hand visible', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  assert.equal(h.requests.length, 1, 'No secondary initial request before any snapshot exists');
  h.requests[0].resolve(snapshot()); await h.settle();
  h.match = match({revision: 11}); const tree = h.render();
  assert.equal(h.requests.length, 2);
  assert.match(text(tree), /Synthetic debug vector/);
  assert.match(text(tree), /stale/i); assert.match(text(tree), /refreshing/i);
  h.match = match({revision: 12}); h.render(); assert.equal(h.requests.length, 2);
  h.requests[1].resolve(snapshot({revision: 12}));
  assert.doesNotMatch(text(await h.settle()), /stale|refreshing/i);
  assert.equal(h.requests.length, 2);
});
test('repeated stale responses get at most one automatic catch-up per committed revision', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  h.match = match({revision: 11}); h.render();
  h.requests[0].resolve(snapshot()); await h.settle();
  assert.equal(h.requests.length, 2, 'The stale initial response permits one automatic catch-up');
  h.requests[1].resolve(snapshot()); const stale = await h.settle();
  assert.equal(h.requests.length, 2, 'A second old response must not start a third automatic GET');
  assert.match(text(stale), /stale/i);
  const refresh = nodes(stale).find(n => n.type === 'button' && /Refresh/i.test(text(n)));
  assert.equal(refresh.props.disabled, false, 'Manual refresh remains available after bounded catch-up');
  h.render(); h.render(); assert.equal(h.requests.length, 2);
  h.match = match({revision: 12}); h.render();
  assert.equal(h.requests.length, 3, 'A newer committed revision permits one new automatic catch-up');
  h.requests[2].resolve(snapshot()); await h.settle();
  assert.equal(h.requests.length, 3, 'The new revision is also bounded');
  h.refresh(); assert.equal(h.requests.length, 4, 'Explicit refresh is not blocked by the automatic limit');
  h.requests[3].resolve(snapshot()); await h.settle();
  assert.equal(h.requests.length, 4, 'An old manual response does not restart automatic retries');
});
test('permission failure stays visible across revisions until an explicit retry', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  h.requests[0].reject(Error('403: MTG_DEBUG_HANDS=1 required')); await h.settle();
  for (const revision of [18, 19, 20]) {h.match = match({revision}); h.render();}
  const tree = h.render();
  assert.equal(h.requests.length, 1); assert.match(text(tree), /403.*MTG_DEBUG_HANDS/);
  assert.ok(nodes(tree).some(n => n.props?.role === 'alert'));
  h.refresh(); assert.equal(h.requests.length, 2);
  h.requests[1].resolve(snapshot({revision: 20})); assert.doesNotMatch(text(await h.settle()), /403/);
});
for (const change of [{id: 'synthetic-b'}, {game_number: 2}]) {
  test(`match/game boundary hides old data and ignores obsolete requests ${JSON.stringify(change)}`, async t => {
    const h = harness(match()); t.after(h.dispose); h.enable();
    h.requests[0].resolve(snapshot()); await h.settle(); h.refresh();
    h.match = match({...change, revision: 11});
    assert.doesNotMatch(text(h.render()), /Synthetic debug vector/);
    assert.equal(h.requests.length, 3, 'New match/game gets its own request');
    h.requests[1].resolve(snapshot()); assert.doesNotMatch(text(await h.settle()), /Synthetic debug vector/);
    h.requests[2].resolve(snapshot({match_id: h.match.id, game_number: h.match.game_number, revision: 11}));
    assert.match(text(await h.settle()), /Synthetic debug vector/);
  });
}
test('disabling hides the snapshot and ignores its late response', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable(); h.enable(false);
  h.requests[0].resolve(snapshot()); assert.doesNotMatch(text(await h.settle()), /Synthetic debug vector/);
  h.enable(); assert.equal(h.requests.length, 2);
  assert.doesNotMatch(text(h.render()), /Synthetic debug vector/);
});
