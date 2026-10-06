import assert from 'node:assert/strict';
import {baseManaOptions} from '../src/components/manual-mana-output.ts';

// Contract vectors are validation inputs, not fabricated cards or engine fixtures.
const bases = [{B: 2}, {B: 1, R: 1}, {R: 2}];
const view = {
  base_output_bundles: bases,
  output_options: [
    {color: 'B', output_bundle: bases[0]},
    {color: 'B', output_bundle: bases[1]},
    {color: 'R', output_bundle: bases[1]},
    {color: 'R', output_bundle: bases[2]},
  ],
};
const before = JSON.stringify(view);
const options = baseManaOptions(view);
assert.deepEqual(options.map(option => option.label), ['2 B', '1 B + 1 R', '1 B + 1 R', '2 R']);
assert.equal(JSON.stringify(view), before);
assert.deepEqual(baseManaOptions(view), options, 'Deterministic output options');
options[1].output_bundle.B = 9;
assert.equal(JSON.stringify(view), before, 'Returned selections do not alias authoritative view');
assert.equal(baseManaOptions({}), null, 'Absent new view preserves legacy route');
assert.deepEqual(baseManaOptions({base_output_bundles: bases}), []);
for (const invalid of [{C: 1}, {B: 0, R: 1}, {B: true}, {B: 1.5}, {S: 1}, {B: 3}, {}, []]) {
  assert.deepEqual(baseManaOptions({base_output_bundles: bases,
    output_options: [{color: 'B', output_bundle: invalid}]}), []);
}
assert.deepEqual(baseManaOptions({base_output_bundles: [{B: 1, R: 1}],
  output_options: [{color: 'C', output_bundle: {B: 1, R: 1}}]}), [], 'Replacement C is not a valid BR base anchor');
assert.deepEqual(baseManaOptions({base_output_bundles: bases, output_options: view.output_options.slice(0, 2)}), [], 'Incomplete view must not silently omit a base choice');
console.log('PASS frozen BASE-vector contract: all branches, whole vectors, anchors, fail-closed validation, no aliasing, determinism');
