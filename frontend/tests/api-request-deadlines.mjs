import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const server = await createServer({
  configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom', logLevel: 'silent',
});
const originalFetch = globalThis.fetch;
const originalTimeout = AbortSignal.timeout;
const deadlines = [];
const requests = [];
const player = { life: 20, hand: [], battlefield: [], graveyard: [], graveyard_count: 0, exile: [], exile_count: 0 };
const state = {
  id: 'match-1', step: 'precombat_main', turn: 1, active_player: 1, priority_player: 1,
  score: { 1: 0, 2: 0 }, stack: [], log: [], blocks: {}, players: { 1: player, 2: player },
};

try {
  const { api } = await server.ssrLoadModule('/src/api/client.ts');
  AbortSignal.timeout = milliseconds => {
    deadlines.push(milliseconds);
    return new AbortController().signal;
  };
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init });
    return new Response(JSON.stringify(url.endsWith('/health') ? { ok: true } : state), {
      headers: { 'Content-Type': 'application/json' },
    });
  };
  assert.equal((await api.autoplay('match-1', 1, { revision: 4, key: 'same-write-key' })).id, state.id);
  await api.getMatch('match-1');
  await api.health();
  await api.act('match-1', 1, { type: 'pass_priority' });
  await api.simulateBatch([], [], 1, 'master');
  assert.deepEqual(deadlines, [600000, 30000, 30000, 30000, 600000]);
  assert.equal(requests[0].init.method, 'POST');
  assert.equal(requests[0].init.headers['Idempotency-Key'], 'same-write-key');
  assert.equal(requests[0].init.headers['X-Match-Revision'], '4');
  assert(requests.every(request => request.init.signal instanceof AbortSignal));
  console.log('PASS actual API client: bounded AI deadline, ordinary deadlines, write headers and response validation');
} finally {
  globalThis.fetch = originalFetch;
  AbortSignal.timeout = originalTimeout;
  await server.close();
}
