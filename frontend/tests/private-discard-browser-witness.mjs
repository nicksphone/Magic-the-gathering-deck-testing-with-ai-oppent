import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {test, after} from 'node:test';
import vm from 'node:vm';
import {build, stop} from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const compiled = await build({
  entryPoints: [new URL('./human-actions.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external',
  jsx: 'automatic', loader: {'.css': 'empty'},
  define: {'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://fixture.invalid')},
});
after(() => stop());
const driver = await readFile(new URL('./browser-human-actions.mjs', import.meta.url), 'utf8');
const witness = driver.match(/^  const discardedId = await evaluate\((".*")\);$/m);
assert.ok(witness, 'Exercise the actual browser discardedId expression, not a replacement helper');
const expression = JSON.parse(witness[1]);

function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}

function textContent(value) {
  if (Array.isArray(value)) return value.map(textContent).join('');
  if (value && typeof value === 'object') return textContent(value.props?.children);
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function fixture(seat, reversed = false) {
  // Declared public selector protocol, not invented canonical Oracle or a game replay.
  const ids = Array.from({length: 7}, (_, index) => `offered-${seat}-${index}`);
  const options = reversed ? [...ids].reverse() : [...ids];
  const pending = {kind: 'discard', player_id: seat, label: 'Choose cards to discard', count: 1};
  const move = {type: 'choose_mechanic', ...pending, options,
    option_labels: Object.fromEntries(ids.map(id => [id, 'Island']))};
  const match = {id: `declared-game-${seat}`, game_number: 1, priority_player: seat,
    controllers: {'1': 'human', '2': 'human'}, pending_mechanic_choice: pending,
    players: Object.fromEntries([1, 2].map(player => [String(player), {
      hand: (player === seat ? ids : ['other-seat-card']).map(id => ({id, name: 'Island'})),
      battlefield: [], graveyard: [], mana_pool: {},
    }]))};
  const finished = {...match, pending_mechanic_choice: null};
  const legal = {player_id: seat, moves: [move]};
  const fixtureWindow = {fixtureActions: []};
  const calls = [], stores = {harness: [], controls: []};
  let mounted, store, cursor;
  const hooks = {...React, useEffect() {}, useMemo: fn => fn(), useState(initial) {
    const slot = cursor++;
    const state = store;
    if (!(slot in state)) state[slot] = typeof initial === 'function' ? initial() : initial;
    return [state[slot], value => {
      state[slot] = typeof value === 'function' ? value(state[slot]) : value;
    }];
  }};
  const context = {console, exports: {}, window: fixtureWindow,
    document: {getElementById: () => ({})},
    require: name => name === 'react' ? hooks : name === 'react-dom/client'
      ? {createRoot: () => ({render: tree => {mounted = tree;}})} : require(name),
    fetch: async (url, settings) => {
      calls.push({url, settings});
      if (url.startsWith('http://fixture.invalid/fixture?')) {
        assert.equal(settings.method, 'POST');
        return {ok: true, json: async () => match};
      }
      if (url.endsWith('/action')) {
        assert.equal(settings.method, 'POST');
        return {ok: true, json: async () => finished};
      }
      assert.equal(url, `http://fixture.invalid/matches/${match.id}/legal-moves`);
      return {ok: true, json: async () => calls.some(call => call.url.endsWith('/action'))
        ? {player_id: seat, moves: []} : legal};
    }};
  vm.runInNewContext(compiled.outputFiles[0].text, context);
  function render(type, props, name) {
    store = stores[name]; cursor = 0;
    return nodes(type(props));
  }
  return {seat, ids, options, pending, move, legal, match, calls, fixtureWindow,
    async load() {
      const reset = render(mounted.type, {}, 'harness')
        .find(node => node.type === 'button' && node.props.children === 'Reset Fixture');
      assert.ok(reset);
      await reset.props.onClick();
    },
    controls() {
      const component = render(mounted.type, {}, 'harness')
        .find(node => node.type?.name === 'Controls');
      assert.ok(component);
      return render(component.type, component.props, 'controls');
    },
    expectedId() {return vm.runInNewContext(expression, {window: fixtureWindow});},
  };
}

for (const seat of [1, 2]) for (const reversed of [false, true]) {
  test(`seat ${seat}: public prompt, actual offered ${reversed ? 'reversed' : 'ordinary'} last checkbox`, async () => {
    const sample = fixture(seat, reversed);
    await sample.load();
    assert.equal(sample.fixtureWindow.fixtureState.pending_mechanic_choice, sample.pending);
    assert.equal(sample.pending.options, undefined);
    assert.equal(sample.pending.effect_payload, undefined);
    assert.equal(sample.pending.resolving_item, undefined);
    const expected = sample.options.at(-1);
    assert.equal(sample.expectedId(), expected);
    assert.equal(sample.fixtureWindow.fixtureMoves, sample.legal.moves,
      'Witness must use the same actual authorized GET response passed to Controls');
    function panel() {
      const tree = sample.controls();
      const discard = tree.find(node => node.props?.className === 'block-panel'
        && textContent(node).includes(sample.pending.label));
      assert.ok(discard, 'Same actual discard panel as the original browser selector');
      return nodes(discard);
    }
    let tree = panel();
    const checkboxes = tree.filter(node => node.type === 'input' && node.props.type === 'checkbox');
    assert.equal(checkboxes.length, sample.options.length);
    assert.equal(tree.find(node => node.type === 'button' && node.props.children === 'Confirm Selection').props.disabled, true);
    assert.equal(sample.fixtureWindow.fixtureActions.length, 0);
    checkboxes.at(-1).props.onChange({target: {checked: true}});
    tree = panel();
    assert.equal(tree.filter(node => node.type === 'input' && node.props.type === 'checkbox').at(-1).props.checked, true);
    const confirm = tree.find(node => node.type === 'button' && node.props.children === 'Confirm Selection');
    assert.equal(confirm.props.disabled, false);
    confirm.props.onClick();
    await new Promise(resolve => setImmediate(resolve));
    const actions = sample.calls.filter(call => call.url.endsWith('/action'));
    assert.equal(actions.length, 1);
    assert.deepEqual(JSON.parse(actions[0].settings.body), {
      player_id: seat, action: {type: 'choose_mechanic', card_ids: [expected]},
    });
    assert.equal(sample.fixtureWindow.fixtureState.pending_mechanic_choice, null);
    assert.equal(sample.fixtureWindow.fixtureMoves.length, 0, 'Refresh must clear a resolved offered choice');
    assert.equal(sample.pending.options, undefined, 'Witness must not reintroduce public private-card options');
  });
}

for (const seat of [1, 2]) {
  test(`seat ${seat}: missing or other-actor offered choice cannot supply the witness`, async () => {
    const sample = fixture(seat);
    await sample.load();
    sample.fixtureWindow.fixtureMoves = [];
    assert.throws(() => sample.expectedId());
    sample.fixtureWindow.fixtureMoves = [{...sample.move, player_id: 3 - seat}];
    assert.throws(() => sample.expectedId());
    assert.equal(sample.fixtureWindow.fixtureActions.length, 0);
    assert.equal(sample.calls.filter(call => call.url.endsWith('/action')).length, 0);
  });
}
