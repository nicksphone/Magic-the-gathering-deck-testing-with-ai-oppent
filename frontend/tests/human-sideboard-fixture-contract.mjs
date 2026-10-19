import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const react = require('react');
const compiled = await build({
  entryPoints: [new URL('./human-actions.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external',
  jsx: 'automatic', loader: { '.css': 'empty' },
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://fixture.invalid') },
});
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}

for (const playerId of [1, 2]) for (const status of [200, 422]) {
  const match = { id: 'game', winner: 1, controllers: { 1: 'human', 2: 'human' },
    sideboarding: { 1: { applied: false }, 2: { applied: false } } };
  const accepted = structuredClone(match);
  accepted.sideboarding[playerId].applied = true;
  const calls = [], updates = [];
  const fixtureWindow = { fixtureActions: [] };
  let mounted, index = 0;
  const initial = [match, [], playerId, '', true];
  const hooks = { ...react, useEffect() {}, useState() {
    const slot = index++;
    return [initial[slot], value => updates.push({ slot, value })];
  } };
  const context = { console, exports: {}, document: { getElementById: () => ({}) },
    window: fixtureWindow,
    require: name => name === 'react' ? hooks : name === 'react-dom/client'
      ? { createRoot: () => ({ render: tree => { mounted = tree; } }) } : require(name),
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (url.endsWith('/sideboard')) {
        return { ok: status === 200, status, json: async () => accepted };
      }
      assert.equal(url, 'http://fixture.invalid/matches/game/legal-moves');
      return { ok: true, json: async () => ({ player_id: playerId, moves: [] }) };
    } };
  vm.runInNewContext(compiled.outputFiles[0].text, context);
  const controls = nodes(mounted.type()).find(node => node.type?.name === 'Controls');
  assert.ok(controls);
  await controls.props.onApplySideboard(playerId, [], []);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls[0]?.url, 'http://fixture.invalid/matches/game/sideboard',
    'The real fixture callback must send sideboard confirmations, not do nothing');
  assert.equal(calls[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].options.body), { player_id: playerId, cards_out: [], cards_in: [] });
  if (status === 200) {
    assert.equal(calls.length, 2);
    assert.equal(fixtureWindow.fixtureState.sideboarding[playerId].applied, true);
    assert.equal(fixtureWindow.fixtureState.sideboarding[3 - playerId].applied, false);
    assert.equal(updates.filter(update => update.slot === 4).at(-1).value, true);
  } else {
    assert.equal(calls.length, 1, 'Rejected confirmation must not refresh or pretend acceptance');
    assert.equal(fixtureWindow.fixtureState, undefined);
    assert.match(updates.find(update => update.slot === 3).value, /Sideboard HTTP 422/);
    assert.equal(updates.filter(update => update.slot === 4).at(-1).value, false);
  }
}
console.log('PASS real human-fixture sideboard callback: both seats, explicit no-swaps, accepted refresh and rejected response');
