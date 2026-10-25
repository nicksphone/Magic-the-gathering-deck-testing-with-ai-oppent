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

test('opt-in request survives revision advances and labels the captured snapshot', async t => {
  const h = harness(match()); t.after(h.dispose);
  assert.equal(h.requests.length, 0); h.enable();
  for (const revision of [11, 12, 13]) {h.match = match({revision}); h.render();}
  assert.equal(h.requests.length, 1, 'Autoplay must not cancel/refetch on every revision');
  h.requests[0].resolve(snapshot()); const tree = await h.settle();
  assert.match(text(tree), /Synthetic debug vector/);
  assert.match(text(tree), /snapshot.*revision 10/i); assert.match(text(tree), /current.*revision 13/i);
});
test('explicit refresh alone fetches a newer snapshot and shows empty hand honestly', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  h.requests[0].resolve(snapshot()); await h.settle();
  h.match = match({revision: 14}); h.render(); h.refresh(); assert.equal(h.requests.length, 2);
  h.requests[1].resolve(snapshot({revision: 14, hands: {'2': []}}));
  const tree = await h.settle(); assert.match(text(tree), /snapshot.*revision 14/i); assert.match(text(tree), /Empty hand/);
  assert.doesNotMatch(text(tree), /Synthetic debug vector/);
});
test('permission failure stays visible across revisions until an explicit retry', async t => {
  const h = harness(match()); t.after(h.dispose); h.enable();
  h.requests[0].reject(Error('403: MTG_DEBUG_HANDS=1 required')); await h.settle();
  h.match = match({revision: 20}); const tree = h.render();
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
