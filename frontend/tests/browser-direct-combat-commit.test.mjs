// Scripted API/DOM timing, not a browser, HTTP or gameplay qualification.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {waitForApiState} from './browser-driver.mjs';

let sequence = 0;

async function scenario(t, delayed, {never = false, wrongAttackers = false} = {}) {
  const originalFetch = globalThis.fetch;
  let current, pending, staleReads = 0, closed = 0;
  const actions = [], messages = [], rendered = [];
  function submit(kind) {
    assert.equal(pending, null, 'Another UI write was submitted before its predecessor committed');
    actions.push(kind);
    const next = {...current, revision: current.revision + 1};
    if (kind === 'attack') {
      next.attackers = wrongAttackers ? ['hero'] : ['hero', 'angel'];
      next.attack_bands = [['hero', 'angel']];
    } else if (kind === 'pass') next.step = 'declare_blockers';
    else next.blocks = {hero: ['bears'], angel: ['bears']};
    pending = {kind, next, reads: kind === delayed ? 2 : 0};
  }
  const browser = {
    evaluate: async () => ({x: 12, y: 34}),
    command: async () => {}, reload: async () => {},
    waitFor: async expression => {
      // The form disappears immediately at submission, while API reads still
      // return the old revision. Only an authoritative poll can prove commit.
      const revision = expression.match(/dataset\.matchRevision === '(\d+)'/);
      if (revision) {
        assert.equal(current.revision, Number(revision[1]));
        assert.equal(pending, null, 'Rendered idle must follow the accepted API revision');
        rendered.push(current.revision);
      }
    },
    click: async label => {
      if (label === 'Declare attackers (2)') submit('attack');
      else if (label === 'Pass Priority') submit('pass');
      else if (label === 'Declare blockers (1)') submit('block');
      else assert.equal(label, 'Clear blocks');
    },
    close: async () => { closed++; },
  };
  const name = `__directCombatCommit${++sequence}`;
  const world = {openBrowser: async () => browser,
    waitForApiState: (url, predicate) => waitForApiState(url, predicate, 1000),
    log: message => messages.push(message)};
  globalThis[name] = world;
  t.after(() => { globalThis.fetch = originalFetch; delete globalThis[name]; });
  globalThis.fetch = async (url, options = {}) => {
    const parsed = new URL(url);
    assert.equal(parsed.origin, 'http://127.0.0.1:10199');
    if (parsed.pathname === '/fixture/direct-combat') {
      assert.equal(options.method, 'POST');
      pending = null;
      current = {id: `seat-${parsed.searchParams.get('seat')}`, revision: 0,
        step: 'declare_attackers', attackers: [], attack_bands: [], blocks: {}};
    } else {
      assert.equal(parsed.pathname, `/matches/${current.id}`);
      assert.equal(options.method, undefined, 'Polling never resubmits a write');
      if (pending) {
        if (pending.kind === delayed && (never || pending.reads-- > 0)) staleReads++;
        else { current = pending.next; pending = null; }
      }
    }
    return {ok: true, status: 200, json: async () => structuredClone(current)};
  };
  const source = await readFile(new URL('./browser-direct-combat.mjs', import.meta.url), 'utf8');
  const driver = `data:text/javascript,${encodeURIComponent(
    `export const openBrowser=globalThis.${name}.openBrowser;\n` +
    `export const waitForApiState=globalThis.${name}.waitForApiState;`)}`;
  const transformed = `const console={log:globalThis.${name}.log};\n` + source
    .replace("from './browser-driver.mjs'", `from ${JSON.stringify(driver)}`)
    .replace("from './visible-card-point.mjs'", `from ${JSON.stringify(new URL('./visible-card-point.mjs', import.meta.url).href)}`)
    + '\n//# sourceURL=direct-combat-scripted-timing.mjs';
  const run = () => import(`data:text/javascript,${encodeURIComponent(transformed)}`);
  return {run, actions, messages, rendered,
    staleReads: () => staleReads, closed: () => closed};
}

for (const phase of ['attack', 'pass', 'block']) {
  test(`both seats wait for ${phase} commit after early panel removal/stale API reads`, async t => {
    const world = await scenario(t, phase);
    await world.run();
    assert.deepEqual(world.actions, ['attack', 'pass', 'block', 'attack', 'pass', 'block']);
    assert.equal(world.messages.length, 2);
    assert.equal(world.closed(), 2);
    assert.equal(world.staleReads(), 4);
    assert.deepEqual(world.rendered, [1, 2, 3, 1, 2, 3]);
  });
}

test('a hidden panel with no accepted revision times out, without another write or PASS', async t => {
  const world = await scenario(t, 'attack', {never: true});
  await assert.rejects(world.run(), /API state condition timed out/);
  assert.deepEqual(world.actions, ['attack']);
  assert.equal(world.messages.length, 0);
  assert.equal(world.closed(), 1);
});

test('a committed wrong attacker result still fails the original exact assertion', async t => {
  const world = await scenario(t, 'none', {wrongAttackers: true});
  await assert.rejects(world.run(), error => {
    assert.equal(error.code, 'ERR_ASSERTION');
    assert.deepEqual(error.actual, ['hero']);
    assert.deepEqual(error.expected, ['hero', 'angel']);
    return true;
  });
  assert.deepEqual(world.actions, ['attack']);
  assert.equal(world.messages.length, 0);
  assert.equal(world.closed(), 1);
});
