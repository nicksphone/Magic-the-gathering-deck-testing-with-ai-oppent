import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { createServer } from 'node:net';
import { mkdtemp, mkdir, readFile, writeFile, copyFile, symlink, realpath, stat, readdir, rm } from 'node:fs/promises';
import { openSync, closeSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

process.umask(0o077);
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
const deps = await realpath(process.env.MTG_FRONTEND_DEPS || path.join(source, 'frontend/node_modules'));
const chrome = process.env.MTG_CHROMIUM || execFileSync('bash', ['-c', 'command -v google-chrome || command -v chromium'], { encoding: 'utf8' }).trim();
const archiveBase = process.env.MTG_CATHAR_ARCHIVE || '/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/cathar-browser';
let existing = path.resolve(archiveBase);
while (true) { try { await stat(existing); break; } catch (error) { if (error.code !== 'ENOENT') throw error; existing = path.dirname(existing); } }
if (process.env.GITHUB_ACTIONS === 'true') {
  assert.ok(process.env.RUNNER_TEMP && process.env.MTG_CATHAR_ARCHIVE, 'Hosted CI requires explicit RUNNER_TEMP evidence');
  const runnerTemp = await realpath(process.env.RUNNER_TEMP);
  const resolvedArchive = path.join(await realpath(existing), path.relative(existing, path.resolve(archiveBase)));
  const relative = path.relative(runnerTemp, resolvedArchive);
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), 'Hosted evidence must stay inside RUNNER_TEMP');
} else {
  assert.match(execFileSync('findmnt', ['-n', '-T', existing, '-o', 'FSTYPE'], { encoding: 'utf8' }).trim().split(/\r?\n/).at(-1), /^nfs4?$/, 'Local Cathar evidence requires mounted NFS');
}
assert.equal(await realpath(execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: source, encoding: 'utf8' }).trim()), await realpath(source), 'Source root must match the Git inventory');
const runtime = await mkdtemp(path.join(tmpdir(), 'mtg-cathar-browser-run-'));
assert.ok(!execFileSync('stat', ['-f', '-c', '%T', runtime], { encoding: 'utf8' }).trim().startsWith('nfs'), 'SQLite runtime must be local');
const archive = path.join(archiveBase, path.basename(runtime));
await mkdir(path.join(archive, 'private'), { recursive: true, mode: 0o700 });
const token = randomUUID();
const children = [];
const results = [];
const requests = [];
let backend;
let failure;
let success = false;

async function port() {
  const server = createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const value = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return value;
}
const ports = { backend: await port(), frontend: await port(), cdp: await port() };
assert.equal(new Set(Object.values(ports)).size, 3);
const api = `http://127.0.0.1:${ports.backend}`;
const frontend = `http://127.0.0.1:${ports.frontend}`;
process.env.MTG_BROWSER_ORIGIN = `http://127.0.0.1:${ports.cdp}`;
process.env.MTG_FRONTEND_ORIGIN = frontend;

function start(label, executable, args, cwd, extraEnv = {}) {
  const fd = openSync(path.join(runtime, `${label}.log`), 'a', 0o600);
  const child = spawn(executable, args, { cwd, detached: true, stdio: ['ignore', fd, fd], env: { ...process.env, ...extraEnv } });
  closeSync(fd);
  child.label = label;
  child.done = new Promise(resolve => { child.once('exit', resolve); child.once('error', resolve); });
  children.push(child);
  console.log(`OWN ${label} PID=${child.pid} runtime=${runtime} ports=${JSON.stringify(ports)}`);
  return child;
}
async function stop(child) {
  if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return;
  try { process.kill(-child.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  let timer;
  await Promise.race([child.done, new Promise(resolve => { timer = setTimeout(resolve, 5000); })]);
  clearTimeout(timer);
  if (child.exitCode === null && child.signalCode === null) { process.kill(-child.pid, 'SIGKILL'); await child.done; }
}
async function fixtureRequest(route, method = 'GET') {
  const response = await fetch(`${api}/fixture/cathar${route}`, { method, headers: { 'X-Cathar-Fixture': token }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Fixture ${route}: ${response.status} ${await response.text()}`);
  return response.json();
}
async function ready(url, child, owned = false) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, `Owned service exited: ${url}`);
    try {
      const response = await fetch(url, { headers: owned ? { 'X-Cathar-Fixture': token } : {}, signal: AbortSignal.timeout(1000) });
      if (response.ok) { if (owned) assert.equal((await response.json()).source_root, runtime); return; }
    } catch { /* Cold startup only, bounded by deadline. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Owned service startup timeout: ${url}`);
}
function startBackend() {
  backend = start('backend', python, ['-m', 'uvicorn', 'tests.cathar_fixture_server:app', '--host', '127.0.0.1', '--port', String(ports.backend)], path.join(runtime, 'backend'), {
    MTG_CATHAR_FIXTURE_ROOT: runtime, MTG_CATHAR_FIXTURE_TOKEN: token,
  });
  return ready(`${api}/fixture/cathar/status`, backend, true);
}
async function restartBackend() {
  const previous = (await fixtureRequest('/status')).pid;
  await stop(backend);
  await startBackend();
  assert.notEqual((await fixtureRequest('/status')).pid, previous, 'Must restart a real backend process');
}

try {
  const gitFiles = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', 'backend', 'frontend'], { cwd: source, encoding: 'utf8' }).split('\0').filter(Boolean);
  const files = [...new Set([...gitFiles, 'frontend/tests/cathar_fixture_server.py', 'frontend/tests/browser-cathar.mjs'])]
    .filter(file => !file.split('/').some(part => ['node_modules', '.venv', '__pycache__', '.pytest_cache', 'image_cache', 'diagnostics', 'cache', 'training_runs'].includes(part)) && !/\.(db|sqlite|sqlite3)(-|$)/.test(file));
  const manifest = [];
  for (const file of files) {
    assert.ok(!path.isAbsolute(file) && !file.split('/').includes('..'));
    assert.equal(await realpath(path.join(source, file)), path.join(source, file), `Source symlink is not a frozen regular file: ${file}`);
    const content = await readFile(path.join(source, file));
    await mkdir(path.dirname(path.join(runtime, file)), { recursive: true });
    await writeFile(path.join(runtime, file), content);
    manifest.push({ file, sha256: createHash('sha256').update(content).digest('hex') });
  }
  await writeFile(path.join(runtime, '.cathar-browser-owned'), token);
  await copyFile(path.join(runtime, 'frontend/tests/cathar_fixture_server.py'), path.join(runtime, 'backend/tests/cathar_fixture_server.py'));
  await writeFile(path.join(runtime, 'source-manifest.json'), JSON.stringify({ revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' }).trim(), files: manifest }, null, 2));
  // Keep Vite's .vite-temp/config caches local, not in external node_modules.
  await mkdir(path.join(runtime, 'frontend/node_modules'));
  for (const entry of await readdir(deps)) {
    if (!entry.startsWith('.')) await symlink(path.join(deps, entry), path.join(runtime, 'frontend/node_modules', entry));
  }
  await writeFile(path.join(runtime, 'frontend/vite.cathar.config.mjs'), `import {defineConfig} from 'vite';import react from '@vitejs/plugin-react';export default defineConfig({plugins:[react()],cacheDir:${JSON.stringify(path.join(runtime, 'vite-cache'))},server:{proxy:{'/card-images':{target:${JSON.stringify(api)}}}}});`);
  await startBackend();
  const vite = start('frontend', process.execPath, [path.join(deps, 'vite/bin/vite.js'), '--config', 'vite.cathar.config.mjs', '--host', '127.0.0.1', '--port', String(ports.frontend), '--strictPort'], path.join(runtime, 'frontend'), { VITE_API_BASE_URL: api });
  const chromium = start('chromium', chrome, ['--headless', '--disable-dev-shm-usage', '--no-first-run', ...(process.env.MTG_BROWSER_NO_SANDBOX === '1' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(runtime, 'profile')}`, '--remote-debugging-address=127.0.0.1', `--remote-debugging-port=${ports.cdp}`, 'about:blank'], runtime);
  await ready(frontend, vite);
  await ready(`${process.env.MTG_BROWSER_ORIGIN}/json/version`, chromium);
  await mkdir(path.join(runtime, 'evidence'));

  for (const seat of [1, 2]) for (const scenario of ['day-ledger', 'night-transform-pending', 'source-blink-pending']) {
    const fixture = await fixtureRequest(`?seat=${seat}&designation=${scenario === 'night-transform-pending' ? 'night' : 'day'}`, 'POST');
    const id = fixture.match.id;
    const route = `/${id}`;
    const query = `?source_id=${encodeURIComponent(fixture.source_id)}`;
    const browser = await openBrowser(`${frontend}/`);
    const { evaluate, waitFor, click, reload, command } = browser;
    const getAudit = () => fixtureRequest(`${route}/audit${query}`);
    const getState = () => fetch(`${api}/matches/${id}`).then(response => response.json());
    const cardAt = (state, owner, zone, cid) => state.players[String(owner)][zone].find(card => card.id === cid);
    const label = `${seat}-${scenario}`;
    async function checkpoint(stage) {
      const audit = await getAudit();
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.json`), JSON.stringify(audit, null, 2));
      if (stage !== 'failure' && audit.source.zone === 'battlefield') {
        const expected = `${audit.source.power}/${audit.source.toughness}`;
        await waitFor(`(() => { const tile = document.querySelector('[data-card-id="${fixture.source_id}"]'); return tile?.innerText.includes(${JSON.stringify(audit.source.name)}) && tile.innerText.includes(${JSON.stringify(expected)}); })()`);
      }
      const screenshot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.png`), Buffer.from(screenshot.data, 'base64'));
      return audit;
    }
    async function loaded() {
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('[role=alert]')");
    }
    async function passUntil(predicate) {
      for (let count = 0; count < 8; count++) {
        const state = await getState();
        if (predicate(state)) return state;
        assert.ok(!state.pending_trigger_order, 'Missing human trigger control must not be bypassed');
        await click('Pass Priority');
        await waitForApiState(`${api}/matches/${id}`, next => next.revision > state.revision);
      }
      throw new Error(`No expected state after actual UI passes: ${label}`);
    }
    async function target(cid) {
      const response = await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`);
      const legal = (await response.json()).moves.filter(move => move.type === 'choose_trigger_target');
      const index = legal.findIndex(move => move.target_card_id === cid);
      assert.ok(index >= 0, 'Canonical chosen target must be legal');
      assert.ok(legal.every(move => fixture.target_ids.includes(move.target_card_id)), 'Only opposing canonical targets');
      await waitFor(`document.querySelectorAll('.trigger-target-panel button').length === ${legal.length}`);
      const before = await getState();
      await evaluate(`(() => { const b = document.querySelectorAll('.trigger-target-panel button')[${index}]; if (!b || b.disabled) throw new Error('Missing human target control'); b.click(); })()`);
      await waitForApiState(`${api}/matches/${id}`, next => next.revision > before.revision && !next.pending_trigger_order);
      assert.equal((await getAudit()).snapshot.stack.at(-1).payload.target_card_id, cid);
    }
    async function restore() {
      const before = await getAudit();
      const restored = await fixtureRequest(`${route}/restore${query}`, 'POST');
      assert.equal(restored.snapshot_sha256, before.snapshot_sha256);
      await reload(); await loaded();
      assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
    }
    async function transition(operation) {
      await fixtureRequest(`${route}/transition${query}&operation=${operation}`, 'POST');
      await reload(); await loaded();
    }
    async function bounce() {
      const cid = fixture.source_id;
      await waitFor(`document.querySelector('[data-hand-card-id="${fixture.bounce_id}"] select option[value="${cid}"]') !== null`);
      await evaluate(`(() => { const select = [...document.querySelectorAll('[data-hand-card-id="${fixture.bounce_id}"] select')].find(s => [...s.options].some(o => o.value === ${JSON.stringify(cid)})); if (!select) throw new Error('Missing human Unsummon target control'); select.value = ${JSON.stringify(cid)}; select.dispatchEvent(new Event('change', {bubbles:true})); })()`);
      await click('Cast Unsummon');
      await passUntil(state => !!cardAt(state, seat, 'hand', cid) && state.stack.length === 0);
    }
    try {
      await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
      await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload(); await loaded();
      await click('Cast Brutal Cathar');
      const entered = await passUntil(state => !!cardAt(state, seat, 'battlefield', fixture.source_id));
      const initial = await checkpoint('entry');
      assert.equal(initial.source.power, scenario === 'night-transform-pending' ? 3 : 2);
      assert.equal(initial.source.toughness, scenario === 'night-transform-pending' ? 3 : 2);
      assert.equal(initial.source.face, scenario === 'night-transform-pending' ? 1 : 0);
      if (scenario === 'night-transform-pending') {
        assert.equal(initial.source.name, 'Moonrage Brute');
        assert.equal(entered.stack.length, 0); assert.equal(entered.pending_trigger_order, null);
        const legal = await (await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`)).json();
        assert.ok(legal.moves.every(move => move.type !== 'choose_trigger_target'));
        assert.equal(await evaluate("document.querySelector('.trigger-target-panel') === null"), true);
        await restore();
        await transition('day');
      }
      await waitFor("document.querySelector('.trigger-target-panel') !== null");
      await restore();
      if (seat === 1 && scenario === 'day-ledger') {
        const before = await getAudit(); await restartBackend(); await reload(); await loaded();
        assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
        await checkpoint('pending-choice-process-restart');
      }
      const chosen = fixture.target_ids[1];
      await target(chosen);
      const incarnation = (await getAudit()).source.incarnation;
      if (scenario === 'source-blink-pending') {
        await transition('blink-at-night');
        assert.notEqual((await getAudit()).source.incarnation, incarnation);
        await restore();
        await passUntil(state => state.stack.length === 0);
        const audit = await checkpoint('stale-trigger-cleanup');
        assert.equal(audit.linked_exiles.length, 0);
        assert.ok(cardAt(await getState(), 3-seat, 'battlefield', chosen));
      } else {
        if (scenario === 'night-transform-pending') {
          await transition('night');
          assert.equal((await getAudit()).source.incarnation, incarnation);
          if (seat === 2) {
            const before = await getAudit(); await restartBackend(); await reload(); await loaded();
            assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
            await checkpoint('pending-exile-process-restart');
          }
        }
        await passUntil(state => !!cardAt(state, 3-seat, 'exile', chosen));
        const linked = await checkpoint('linked-exile');
        assert.equal(linked.linked_exiles.length, 1);
        assert.equal(linked.linked_exiles[0].source_timestamp, incarnation);
        assert.deepEqual(linked.linked_exiles[0].card_ids, [chosen]);
        await restore();
        if (scenario === 'day-ledger') {
          await transition('night');
          const night = await checkpoint('night-preserves-ledger');
          assert.equal(night.source.name, 'Moonrage Brute');
          assert.equal(night.source.incarnation, incarnation);
          assert.deepEqual(night.linked_exiles, linked.linked_exiles);
        }
        await bounce();
        const returned = await checkpoint('source-departure-return');
        assert.equal(returned.linked_exiles.length, 0);
        assert.ok(cardAt(await getState(), 3-seat, 'battlefield', chosen));
        await restore();
      }
      const observed = await fixtureRequest(`/actions?match_id=${id}`);
      assert.ok(observed.every(request => request.status === 200), 'Actual App actions must succeed');
      requests.push(...observed.map(request => ({ ...request, scenario: label })));
      assert.ok(observed.some(request => request.body.action.type === 'choose_trigger_target' && request.body.action.target_card_id === chosen));
      results.push({ seat, scenario, result: 'PASS', actual_app_actions: requests.filter(request => request.scenario === label).length });
      console.log(`PASS ${label}: actual App HTTP actions, canonical faces, snapshot/reload and linked rules`);
    } catch (error) {
      await checkpoint('failure').catch(() => {});
      await writeFile(path.join(runtime, `evidence/${label}-failure-body.txt`), await evaluate('document.body.innerText').catch(() => 'Browser context unavailable'));
      throw error;
    } finally { await browser.close(); }
  }
  success = true;
} catch (error) { failure = error; console.error(error.stack); }
finally {
  for (const child of [...children].reverse()) await stop(child);
  await writeFile(path.join(runtime, 'results.json'), JSON.stringify({ success, results, requests, ports,
    processes: children.map(child => ({ label: child.label, pid: child.pid, exit_code: child.exitCode, signal: child.signalCode })),
    failure: failure?.stack, fixture_claim: 'Controlled canonical positions; no natural historical game claim.' }, null, 2));
  const tar = path.join(archive, 'private/runtime-evidence.tar.gz');
  execFileSync('tar', ['--exclude=./profile', '--exclude=./frontend/node_modules', '--exclude=./vite-cache', '--exclude=*/__pycache__', '--exclude=*/image_cache', '--exclude=./.cathar-browser-owned', '-czf', tar, '-C', runtime, '.']);
  execFileSync('gzip', ['-t', tar]);
  await copyFile(path.join(runtime, 'results.json'), path.join(archive, 'results.json'));
  const sha = createHash('sha256').update(await readFile(tar)).digest('hex');
  await writeFile(path.join(archive, 'SHA256SUMS'), `${sha}  private/runtime-evidence.tar.gz\n`);
  console.log(`ARCHIVE ${archive} SHA256=${sha} success=${success}`);
  // Verify each saved regular file against scratch before successful disposal.
  execFileSync(python, ['-c', "import hashlib,sys,tarfile;from pathlib import Path\nr=Path(sys.argv[1]);t=tarfile.open(sys.argv[2]);n=0\nfor m in t:\n if m.isfile():\n  assert hashlib.sha256(t.extractfile(m).read()).digest()==hashlib.sha256((r/m.name).read_bytes()).digest(),m.name;n+=1\nprint('Verified archived files:',n)", runtime, tar], { stdio: 'inherit' });
  if (success) await rm(runtime, { recursive: true });
  else console.error(`Retained failed runtime for diagnosis: ${runtime}`);
}
if (!success) process.exitCode = 1;
