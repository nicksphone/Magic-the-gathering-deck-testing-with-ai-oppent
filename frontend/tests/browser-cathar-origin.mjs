import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('./browser-cathar.mjs', import.meta.url), 'utf8');
const begin = source.indexOf('function startBackend() {');
const end = source.indexOf('\ntry {', begin);
assert.ok(begin > 0 && end > begin, 'Extract the actual startup and restart functions');

function launcher(frontendPort) {
  const starts = [], readiness = [], stops = [];
  const frontend = `http://127.0.0.1:${frontendPort}`;
  const context = vm.createContext({
    assert, path, frontend, runtime: '/owned/cathar', python: '/owned/python', token: 'fixture-token',
    ports: { backend: 41337 }, api: 'http://127.0.0.1:41337',
    start(label, executable, args, cwd, extraEnv) {
      const child = { pid: 100 + starts.length };
      starts.push({ label, executable, args: [...args], cwd, extraEnv, child });
      return child;
    },
    async ready(url, child, owned) { readiness.push({ url, child, owned }); },
    async stop(child) { stops.push(child); },
    async fixtureRequest() { return { pid: starts.at(-1).child.pid }; },
  });
  vm.runInContext(`let backend;\n${source.slice(begin, end)}\nglobalThis.launch = {startBackend, restartBackend};`, context);
  return { ...context.launch, frontend, starts, readiness, stops };
}

for (const port of [37689, 61877]) {
  test(`Cathar startup trusts only its actual dynamic frontend ${port}`, async () => {
    const current = launcher(port);
    await current.startBackend();
    assert.equal(current.starts[0].extraEnv.MTG_TRUSTED_ORIGINS, current.frontend);
    assert.ok(!current.frontend.includes('*'));
  });
}

test('The real restart path configures the same exact frontend on both processes', async () => {
  const current = launcher(37689);
  await current.startBackend();
  await current.restartBackend();
  assert.equal(current.starts.length, 2);
  assert.deepEqual(current.stops, [current.starts[0].child]);
  assert.notEqual(current.starts[0].child.pid, current.starts[1].child.pid);
  for (const started of current.starts) {
    assert.equal(started.extraEnv.MTG_TRUSTED_ORIGINS, current.frontend);
  }
});

test('Startup retains the real isolated command, fixture identity and readiness check', async () => {
  const current = launcher(37689);
  await current.startBackend();
  const started = current.starts[0];
  assert.equal(started.label, 'backend');
  assert.equal(started.executable, '/owned/python');
  assert.deepEqual(started.args, ['-m', 'uvicorn', 'tests.cathar_fixture_server:app',
    '--host', '127.0.0.1', '--port', '41337']);
  assert.equal(started.cwd, '/owned/cathar/backend');
  assert.equal(started.extraEnv.MTG_CATHAR_FIXTURE_ROOT, '/owned/cathar');
  assert.equal(started.extraEnv.MTG_CATHAR_FIXTURE_TOKEN, 'fixture-token');
  assert.deepEqual(current.readiness, [{ url: 'http://127.0.0.1:41337/fixture/cathar/status',
    child: started.child, owned: true }]);
});
