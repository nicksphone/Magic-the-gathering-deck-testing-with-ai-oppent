import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import test from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');
const source = await readFile(new URL('../src/components/AnalyticsPanel.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
  jsx: ts.JsxEmit.ReactJSX,
}}).outputText;

function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}

function controls(runs) {
  let arrayStates = 0;
  const hooks = {...React,
    useCallback: callback => callback,
    useEffect() {},
    useState(initial) {
      const value = typeof initial === 'function' ? initial() : initial;
      if (Array.isArray(value)) {
        arrayStates++;
        return [runs, () => {}];
      }
      return [value, () => {}];
    },
  };
  const module = {exports: {}};
  const forbidden = () => {throw new Error('Rendering must not start an API operation');};
  const imports = name => {
    if (name === 'react') return hooks;
    if (name === '../api/client') return {api: new Proxy({}, {get: () => forbidden})};
    if (name === '../api/errors') return {HttpResponseError: class extends Error {}};
    if (name === '../api/mutation-gate') return {newMutationKey: forbidden};
    assert.equal(name, 'react/jsx-runtime');
    return require(name);
  };
  // Effects are intentionally inert: this is a compiled element-name contract,
  // not a browser, API, simulation or assistive-technology acceptance test.
  const load = vm.runInNewContext(`(function(require, module, exports) {${compiled}\n})`, {
    localStorage: {getItem: () => null},
  });
  load(imports, module, module.exports);
  const tree = module.exports.AnalyticsPanel({decks: []});
  assert.equal(arrayStates, 1, 'The sole array state is the diagnostic-run fixture');
  return nodes(tree).filter(node => ['select', 'input', 'textarea'].includes(node.type));
}

const names = ['Simulation deck A', 'Simulation deck B', 'Number of simulation matches',
  'Maximum actions per simulation game', 'Simulation AI difficulty'];

test('simulator setup controls have explicit accessible names and unchanged defaults', () => {
  const fields = controls([]);
  assert.deepEqual(fields.map(field => field.props['aria-label']), names);
  assert.deepEqual(fields.map(field => field.props.value), ['', '', 20, 2000, 'master']);
  assert.deepEqual(fields.filter(field => field.type === 'input').map(field => [field.props.min, field.props.max]),
    [[5, 500], [500, 50000]]);
});

test('diagnostic comparison controls have distinct names when runs exist', () => {
  const fields = controls(['first', 'second'].map(run_name => ({run_name, modified_at: 0, summary: {}})));
  assert.deepEqual(fields.map(field => field.props['aria-label']), [...names,
    'Left diagnostic run', 'Right diagnostic run', 'Left replay game', 'Right replay game']);
  assert.deepEqual(fields.slice(-4).map(field => field.props.value), ['', '', 0, 0]);
});
