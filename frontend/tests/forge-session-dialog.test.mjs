// Labelled native-wire/render contracts, not native games or card-rule fixtures.
import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build, stop} from 'esbuild';
import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
const require = createRequire(import.meta.url);
const {createElement} = require('react');
const {renderToStaticMarkup} = require('react-dom/server');

async function api() {
  const built = await build({entryPoints: [new URL('../src/api/forge.ts', import.meta.url).pathname],
    bundle: true, write: false, platform: 'node', format: 'esm', define: {'import.meta.env': '{}'}});
  return import('data:text/javascript;base64,' + Buffer.from(built.outputFiles[0].text).toString('base64'));
}

function confirmation(labels) {
  const s = fixture(); s.question.kind = 'confirm';
  s.question.choices = [{token: uuid(2), display: true}, {token: uuid(3), display: false}];
  s.info = {prompt: 'SYNTHETIC confirmation', labels};
  return s;
}

test('actual confirm wire shape accepts boolean choices with native labels', async () => {
  const {parseForgeSnapshot, forgeChoiceLabel} = await api();
  const s = confirmation(['Keep this', 'Decline this']);
  assert.equal(parseForgeSnapshot(s).question.choices[0].display, true);
  assert.equal(forgeChoiceLabel(true, s.info), 'Keep this');
  assert.equal(forgeChoiceLabel(false, s.info), 'Decline this');
});

test('native labels(null) empty list keeps a valid binary confirmation', async () => {
  const {parseForgeSnapshot, forgeChoiceLabel} = await api();
  const s = confirmation([]);
  assert.equal(parseForgeSnapshot(s).question.choices.length, 2);
  assert.equal(forgeChoiceLabel(true, s.info), 'Yes');
  assert.equal(forgeChoiceLabel(false, s.info), 'No');
});

test('binary confirmation still rejects malformed labels and ambiguous domains', async () => {
  const {parseForgeSnapshot} = await api();
  for (const labels of [['one'], ['one', 'two', 'three'], [true, false], null])
    assert.throws(() => parseForgeSnapshot(confirmation(labels)));
  const duplicate = confirmation(['yes', 'no']); duplicate.question.choices[1].display = true;
  assert.throws(() => parseForgeSnapshot(duplicate));
});

test('one-click native selection shows underlying total bounds and actual chosen card', async () => {
  const s = fixture(); const first = s.question.choices[0].display;
  const second = {...first, card_id: 43, face: {...first.face, name: 'SYNTHETIC second'}};
  s.question.kind = 'input:InputSelectEntitiesFromList';
  s.question.choices = [{token: uuid(2), display: first}, {token: uuid(3), display: second}];
  s.info.selection = {min: 2, max: 2, chosen: [first], input: 'InputSelectEntitiesFromList',
    generation: 1, priority_epoch: 1, revision: 1, actor: s.actor_id};
  const built = await build({entryPoints: [new URL('../src/components/ForgeGame.tsx', import.meta.url).pathname],
    bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    loader: {'.css': 'empty'}, define: {'import.meta.env': '{}'}});
  const module = {exports: {}};
  new Function('require','module','exports',built.outputFiles[0].text)(require,module,module.exports);
  const html = renderToStaticMarkup(createElement(module.exports.ForgeChoices, {snapshot:s,disabled:false,onAnswer(){}}));
  assert.match(html, /Choose 2 total/);
  assert.match(html, /1 selected/);
  assert.match(html, /Selected:.*SYNTHETIC Island/);
  assert.equal((html.match(/data-native-token=/g) ?? []).length, 2);
});
