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
assert.equal(process.argv.length, 2, 'Suspend gate has one declared ten-case scope; no arguments accepted');
const started = Date.now();
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
const deps = await realpath(process.env.MTG_FRONTEND_DEPS || path.join(source, 'frontend/node_modules'));
const chrome = process.env.MTG_CHROMIUM || execFileSync('bash', ['-c', 'command -v google-chrome || command -v chromium'], { encoding: 'utf8' }).trim();
const archiveBase = process.env.MTG_SUSPEND_ARCHIVE || '/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/suspend-browser';
let existing = path.resolve(archiveBase);
while (true) { try { await stat(existing); break; } catch (error) { if (error.code !== 'ENOENT') throw error; existing = path.dirname(existing); } }
if (process.env.GITHUB_ACTIONS === 'true') {
  assert.ok(process.env.RUNNER_TEMP && process.env.MTG_SUSPEND_ARCHIVE, 'Hosted CI requires explicit RUNNER_TEMP evidence');
  const runnerTemp = await realpath(process.env.RUNNER_TEMP);
  const resolvedArchive = path.join(await realpath(existing), path.relative(existing, path.resolve(archiveBase)));
  const relative = path.relative(runnerTemp, resolvedArchive);
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), 'Hosted evidence must stay inside RUNNER_TEMP');
} else {
  assert.match(execFileSync('findmnt', ['-n', '-T', existing, '-o', 'FSTYPE'], { encoding: 'utf8' }).trim().split(/\r?\n/).at(-1), /^nfs4?$/, 'Local Suspend evidence requires mounted NFS');
}
assert.equal(await realpath(execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: source, encoding: 'utf8' }).trim()), await realpath(source), 'Source root must match the Git inventory');
const runtime = await mkdtemp(path.join(tmpdir(), 'mtg-suspend-browser-run-'));
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
  const response = await fetch(`${api}/fixture/suspend${route}`, { method, headers: { 'X-Suspend-Fixture': token }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Fixture ${route}: ${response.status} ${await response.text()}`);
  return response.json();
}
async function ready(url, child, owned = false) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, `Owned service exited: ${url}`);
    try {
      const response = await fetch(url, { headers: owned ? { 'X-Suspend-Fixture': token } : {}, signal: AbortSignal.timeout(1000) });
      if (response.ok) { if (owned) assert.equal((await response.json()).source_root, runtime); return; }
    } catch { /* Cold startup only, bounded by deadline. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Owned service startup timeout: ${url}`);
}
function startBackend() {
  backend = start('backend', python, ['-m', 'uvicorn', 'tests.suspend_fixture_server:app', '--host', '127.0.0.1', '--port', String(ports.backend)], path.join(runtime, 'backend'), {
    MTG_SUSPEND_FIXTURE_ROOT: runtime, MTG_SUSPEND_FIXTURE_TOKEN: token,
  });
  return ready(`${api}/fixture/suspend/status`, backend, true);
}
async function restartBackend() {
  const previous = (await fixtureRequest('/status')).pid;
  await stop(backend);
  await startBackend();
  assert.notEqual((await fixtureRequest('/status')).pid, previous, 'Must restart a real backend process');
}

try {
  const gitFiles = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', 'backend', 'frontend'], { cwd: source, encoding: 'utf8' }).split('\0').filter(Boolean);
  const files = [...new Set([...gitFiles, 'frontend/tests/suspend_fixture_server.py', 'frontend/tests/browser-suspend.mjs'])]
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
  await writeFile(path.join(runtime, '.suspend-browser-owned'), token);
  await copyFile(path.join(runtime, 'frontend/tests/suspend_fixture_server.py'), path.join(runtime, 'backend/tests/suspend_fixture_server.py'));
  await writeFile(path.join(runtime, 'source-manifest.json'), JSON.stringify({ revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' }).trim(), files: manifest }, null, 2));
  // Keep Vite's .vite-temp/config caches local, not in external node_modules.
  await mkdir(path.join(runtime, 'frontend/node_modules'));
  for (const entry of await readdir(deps)) {
    if (!entry.startsWith('.')) await symlink(path.join(deps, entry), path.join(runtime, 'frontend/node_modules', entry));
  }
  await writeFile(path.join(runtime, 'frontend/vite.suspend.config.mjs'), `import {defineConfig} from 'vite';import react from '@vitejs/plugin-react';export default defineConfig({plugins:[react()],cacheDir:${JSON.stringify(path.join(runtime, 'vite-cache'))},server:{proxy:{'/card-images':{target:${JSON.stringify(api)}}}}});`);
  await startBackend();
  const vite = start('frontend', process.execPath, [path.join(deps, 'vite/bin/vite.js'), '--config', 'vite.suspend.config.mjs', '--host', '127.0.0.1', '--port', String(ports.frontend), '--strictPort'], path.join(runtime, 'frontend'), { VITE_API_BASE_URL: api });
  const chromium = start('chromium', chrome, ['--headless', '--disable-dev-shm-usage', '--no-first-run', ...(process.env.MTG_BROWSER_NO_SANDBOX === '1' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(runtime, 'profile')}`, '--remote-debugging-address=127.0.0.1', `--remote-debugging-port=${ports.cdp}`, 'about:blank'], runtime);
  await ready(frontend, vite);
  await ready(`${process.env.MTG_BROWSER_ORIGIN}/json/version`, chromium);
  await mkdir(path.join(runtime, 'evidence'));

  for (const seat of [1, 2]) for (const scenario of ['rift-cast', 'creature-cast', 'no-target', 'decline', 'unpayable']) {
    const fixture = await fixtureRequest(`?seat=${seat}&scenario=${scenario}`, 'POST');
    const id = fixture.match.id;
    const route = `/${id}`;
    const query = `?source_id=${encodeURIComponent(fixture.source_id)}`;
    const browser = await openBrowser(`${frontend}/`);
    const { evaluate, waitFor, click, reload, command } = browser;
    const getAudit = () => fixtureRequest(`${route}/audit${query}`);
    const getState = () => fetch(`${api}/matches/${id}`).then(response => response.json());
    const label = `${seat}-${scenario}`;
    async function loaded() {
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('[role=alert]')");
    }
    async function checkpoint(stage) {
      const audit = await getAudit();
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.json`), JSON.stringify(audit, null, 2));
      const screenshot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.png`), Buffer.from(screenshot.data, 'base64'));
      return audit;
    }
    async function passOnce() {
      const before = await getState();
      await waitFor(`Number(document.querySelector('.battlefield')?.dataset.matchRevision) === ${before.revision}`);
      await click('Pass Priority');
      await waitForApiState(`${api}/matches/${id}`, state => state.revision > before.revision);
      await loaded();
    }
    async function restore() {
      const before = await getAudit();
      const after = await fixtureRequest(`${route}/restore${query}`, 'POST');
      assert.equal(after.snapshot_sha256, before.snapshot_sha256);
      await reload(); await loaded();
      assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
    }
    try {
      await command('Emulation.setDeviceMetricsOverride', { width: seat === 2 ? 430 : 1440, height: seat === 2 ? 900 : 1000, deviceScaleFactor: 1, mobile: seat === 2 });
      await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload(); await loaded();
      await checkpoint('hand');
      if (scenario === 'unpayable') {
        assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Suspend '))"), false);
        const before = await getAudit();
        await restore();
        assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
        assert.equal(before.source.zone, 'hand');
      } else {
        const before = await getState();
        await waitFor(`[...document.querySelectorAll('[data-hand-card-id="${fixture.source_id}"] button')].some(b => b.textContent.includes(${JSON.stringify(`Suspend ${fixture.name} (${fixture.cost}; ${fixture.time_counters} time counter`)}))`);
        await click(`Suspend ${fixture.name}`);
        await waitForApiState(`${api}/matches/${id}`, state => state.revision > before.revision);
        await loaded();
        const suspended = await checkpoint('suspended');
        assert.equal(suspended.source.zone, 'exile');
        assert.equal(suspended.source.counters.time, fixture.time_counters);
        assert.equal(suspended.snapshot.stack.length, 0);
        assert.equal(suspended.snapshot.priority_player, seat);
        assert.equal(suspended.snapshot.spells_cast_this_turn[String(seat)], 0);
        assert.ok(Object.values(suspended.snapshot.players[String(seat)].mana_pool).every(amount => amount === 0));
        await restore();
        for (let count = fixture.time_counters; count > 0; count--) {
          const entered = await fixtureRequest(`${route}/upkeep${query}`, 'POST');
          assert.equal(entered.snapshot.stack.at(-1).effect_key, 'suspend_upkeep');
          assert.equal(entered.source.counters.time, count);
          await reload(); await loaded();
          await passOnce(); await passOnce();
          const removed = await checkpoint(`counter-${count-1}`);
          assert.equal(removed.source.counters.time ?? 0, count-1);
          assert.equal(removed.snapshot.pending_mechanic_choice, null);
          if (count === 1) assert.equal(removed.snapshot.stack.at(-1).effect_key, 'suspend_cast_trigger');
          else assert.equal(removed.snapshot.stack.length, 0);
        }
        await passOnce(); await passOnce();
        await waitFor("document.querySelector('.suspend-cast-panel') !== null");
        const pending = await checkpoint('cast-choice');
        assert.equal(pending.snapshot.pending_mechanic_choice.kind, 'suspend_cast');
        assert.equal(pending.snapshot.pending_mechanic_choice.player_id, seat);
        await restore();
        if (scenario === 'rift-cast' && seat === 2) {
          const old = await getAudit();
          await restartBackend();
          assert.equal((await getAudit()).snapshot_sha256, old.snapshot_sha256);
          await reload(); await loaded();
          await waitFor("document.querySelector('.suspend-cast-panel') !== null");
          await checkpoint('process-restarted-choice');
        }
        if (scenario === 'no-target' || scenario === 'decline') {
          if (scenario === 'no-target') {
            await waitFor("document.querySelector('.suspend-cast-panel')?.innerText.includes('No legal cast is available')");
            assert.equal(await evaluate(`document.querySelector('[data-hand-card-id="${fixture.source_id}"]') !== null`), false);
          }
          const current = await getState();
          await click('Decline suspended casting');
          await waitForApiState(`${api}/matches/${id}`, state => state.revision > current.revision && !state.pending_mechanic_choice);
          const declined = await checkpoint('declined');
          assert.equal(declined.source.zone, 'exile');
          assert.equal(declined.source.counters.time ?? 0, 0);
          assert.equal(declined.snapshot.stack.length, 0);
          await restore();
          assert.equal(await evaluate("document.querySelector('.suspend-cast-panel') !== null"), false);
        } else {
          await waitFor(`document.querySelector('[data-hand-card-id="${fixture.source_id}"]') !== null`);
          if (scenario === 'rift-cast') {
            await waitFor(`document.querySelector('[data-hand-card-id="${fixture.source_id}"] select[aria-label="Player target"] option[value="${3-seat}"]') !== null`);
            await evaluate(`(() => { const select = document.querySelector('[data-hand-card-id="${fixture.source_id}"] select[aria-label="Player target"]'); select.value = '${3-seat}'; select.dispatchEvent(new Event('change', {bubbles:true})); })()`);
          }
          const current = await getState();
          await click(`Cast ${fixture.name}`);
          await waitForApiState(`${api}/matches/${id}`, state => state.revision > current.revision && !state.pending_mechanic_choice);
          const cast = await checkpoint('cast');
          assert.equal(cast.source.zone, 'stack');
          assert.equal(cast.snapshot.stack.length, 1);
          assert.equal(cast.snapshot.spells_cast_this_turn[String(seat)], 1);
          if (scenario === 'rift-cast') assert.equal(cast.snapshot.stack[0].payload.__announced_targets.target_player, 3-seat);
          else assert.equal(cast.source.suspend_haste.controller, seat);
          const life = cast.snapshot.players[String(3-seat)].life;
          await restore();
          await passOnce(); await passOnce();
          const resolved = await checkpoint('resolved');
          if (scenario === 'rift-cast') {
            assert.equal(resolved.source.zone, 'graveyard');
            assert.equal(resolved.snapshot.players[String(3-seat)].life, life-3);
          } else {
            assert.equal(resolved.source.zone, 'battlefield');
            const state = await getState();
            assert.ok(state.players[String(seat)].battlefield.find(card => card.id === fixture.source_id).keywords.includes('haste'));
            await waitFor(`document.querySelector('[data-card-id="${fixture.source_id}"]')?.innerText.includes('haste')`);
          }
        }
      }
      await loaded();
      const observed = await fixtureRequest(`/actions?match_id=${id}`);
      assert.ok(observed.every(row => row.status === 200));
      if (scenario !== 'unpayable') {
        const first = observed[0].body.action;
        assert.deepEqual(first, { type: 'suspend', card_id: fixture.source_id });
        assert.ok(observed.some(row => row.body.action.type === (scenario === 'decline' || scenario === 'no-target' ? 'choose_mechanic' : 'cast_spell')));
      } else assert.equal(observed.length, 0);
      requests.push(...observed.map(row => ({ ...row, scenario: label })));
      results.push({ seat, scenario, result: 'PASS', actual_app_actions: observed.length });
      console.log(`PASS ${label}: real App Suspend/cast/decline, targets and durable continuations`);
    } catch (error) {
      await checkpoint('failure').catch(() => {});
      await writeFile(path.join(runtime, `evidence/${label}-failure-body.txt`), await evaluate('document.body.innerText').catch(() => 'Browser context unavailable'));
      throw error;
    } finally { await browser.close(); }
  }
  assert.equal(results.length, 10);
  success = true;
} catch (error) { failure = error; console.error(error.stack); }
finally {
  for (const child of [...children].reverse()) await stop(child);
  await writeFile(path.join(runtime, 'results.json'), JSON.stringify({ success, expected_cases: 10, elapsed_ms: Date.now()-started, results, requests, ports,
    processes: children.map(child => ({ label: child.label, pid: child.pid, exit_code: child.exitCode, signal: child.signalCode })),
    failure: failure?.stack, fixture_claim: 'Canonical controlled positions/upkeeps; no natural historical game claim.' }, null, 2));
  const tar = path.join(archive, 'private/runtime-evidence.tar.gz');
  execFileSync('tar', ['--exclude=./profile', '--exclude=./frontend/node_modules', '--exclude=./vite-cache', '--exclude=*/__pycache__', '--exclude=*/image_cache', '--exclude=./.suspend-browser-owned', '-czf', tar, '-C', runtime, '.']);
  execFileSync('gzip', ['-t', tar]);
  await copyFile(path.join(runtime, 'results.json'), path.join(archive, 'results.json'));
  const sha = createHash('sha256').update(await readFile(tar)).digest('hex');
  await writeFile(path.join(archive, 'SHA256SUMS'), `${sha}  private/runtime-evidence.tar.gz\n`);
  console.log(`ARCHIVE ${archive} SHA256=${sha} success=${success}`);
  execFileSync(python, ['-c', "import hashlib,sys,tarfile;from pathlib import Path\nr=Path(sys.argv[1]);t=tarfile.open(sys.argv[2]);n=0\nfor m in t:\n if m.isfile():\n  assert hashlib.sha256(t.extractfile(m).read()).digest()==hashlib.sha256((r/m.name).read_bytes()).digest(),m.name;n+=1\nprint('Verified archived files:',n)", runtime, tar], { stdio: 'inherit' });
  if (success) await rm(runtime, { recursive: true });
  else console.error(`Retained failed runtime for diagnosis: ${runtime}`);
}
if (!success) process.exitCode = 1;
