import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {build, stop} from 'esbuild';
import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
let built;
const api = () => built ??= build({entryPoints: [new URL('../src/api/forge.ts', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'esm', define: {'import.meta.env.VITE_API_BASE_URL': '"/api"'}})
  .then(result => import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`));

for (const key of ['selection', 'stack_selection']) {
  test(`anonymous native ${key} retains strict identity without inventing a class label`, async () => {
    const {parseForgeSnapshot, makeForgeAnswer} = await api();
    const value = fixture();
    value.question.kind = 'input:';
    value.info[key] = {input: '', generation: 92, priority_epoch: 87, revision: 320,
      actor: value.actor_id, chosen: [], ...(key === 'selection' ? {min: 1, max: 1} : {})};
    assert.deepEqual(parseForgeSnapshot(value), value);
    assert.equal(makeForgeAnswer(value, [uuid(2)], 'explicit-action').request_id, value.question.request_id);
    for (const change of [v => {v.info[key].actor = 19;}, v => {v.info[key].generation = -1;},
      v => {v.info[key].revision = true;}, v => {v.info[key].input = null;},
      v => {v.info[key].unknown = true;}, v => {v.info[key].chosen = [null];}]) {
      const bad = structuredClone(value); change(bad);
      assert.throws(() => parseForgeSnapshot(bad), /Invalid Forge/);
    }
  });
}
