import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { waitForApiState } from './browser-driver.mjs';

const source = (await readFile(new URL('./browser-combat-capacity.mjs', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '');
const run = new (Object.getPrototypeOf(async function () {}).constructor)(
  'assert', 'openBrowser', 'fetch', 'waitForApiState', 'console', source);
const originalFetch = globalThis.fetch;

async function episode({ rejectedRead = false, committedBlocks = true } = {}) {
  let seat, submitted, reads;
  const writes = [], messages = [];
  const fetch = async (url, options) => {
    if (url.includes('/fixture?')) {
      assert.equal(options.method, 'POST');
      seat = Number(url.at(-1));
      submitted = false;
      reads = 0;
      return { status: 200, json: async () => ({ id: `match-${seat}`, revision: 0 }) };
    }
    assert.ok(submitted, 'Do not read the payment result before submitting');
    if (rejectedRead) return { ok: false, status: 403 };
    // The App clears legal moves before the mutation commits. The first API
    // read is deliberately stale even though Declare Blockers has disappeared.
    const committed = ++reads >= 2;
    return { ok: true, json: async () => ({
      revision: committed ? 1 : 0, attackers: ['a', 'b'],
      blocks: committed && committedBlocks ? { a: ['wall'], b: ['wall'] } : {},
      players: { [3 - seat]: { battlefield: [
        { id: 'wall', name: 'Wall of Glare' },
        { id: 'elf', name: 'Llanowar Elves', tapped: committed },
      ], mana_pool: { G: committed ? 0 : 1 } } },
      log: committed ? ['Player pays {1} in block costs'] : [],
    }) };
  };
  const openBrowser = async () => ({
    evaluate: async () => {}, command: async () => {}, waitFor: async () => {},
    click: async (label) => {
      assert.equal(label, 'Submit Blocks');
      assert.equal(submitted, false, 'Do not retry a mutation');
      submitted = true;
      writes.push(seat);
    },
    close: async () => {},
  });
  globalThis.fetch = fetch;
  try { await run(assert, openBrowser, fetch, waitForApiState, { log: (...args) => messages.push(args) }); }
  finally { globalThis.fetch = originalFetch; }
  assert.deepEqual(writes, [1, 2]);
  assert.equal(messages.length, 2);
}

await episode();
await assert.rejects(episode({ rejectedRead: true }), /State request failed: 403/);
await assert.rejects(episode({ committedBlocks: false }), { code: 'ERR_ASSERTION' });
console.log('PASS actual combat automation waits for committed revisions, never retries writes, and retains block/payment assertions');
