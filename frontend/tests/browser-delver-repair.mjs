import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { createServer } from 'node:net';
import { mkdtemp, mkdir, readFile, writeFile, copyFile, symlink, realpath, stat, readdir, rm } from 'node:fs/promises';
import { openSync, closeSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runDelverRepairAudit } from './delver-repair-probe.mjs';

process.umask(0o077);
assert.ok(process.argv.length===2||(process.argv.length===3&&process.argv[2]==='--inspection-copy'), 'Use no flags for 12 flows, or --inspection-copy for two ineligible-card copy checks');
const inspectionOnly=process.argv[2]==='--inspection-copy';
const expectedCases = inspectionOnly?2:12;
const started = Date.now();
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
const deps = await realpath(process.env.MTG_FRONTEND_DEPS || path.join(source, 'frontend/node_modules'));
const chrome = process.env.MTG_CHROMIUM || execFileSync('bash', ['-c', 'command -v google-chrome || command -v chromium'], { encoding: 'utf8' }).trim();
const archiveBase = process.env.MTG_HUMAN_TRANSFORM_ARCHIVE || '/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/human-transform-audit';
let existing = path.resolve(archiveBase);
while (true) { try { await stat(existing); break; } catch (error) { if (error.code !== 'ENOENT') throw error; existing = path.dirname(existing); } }
if (process.env.GITHUB_ACTIONS === 'true') {
  assert.ok(process.env.RUNNER_TEMP && process.env.MTG_HUMAN_TRANSFORM_ARCHIVE, 'Hosted CI requires explicit RUNNER_TEMP evidence');
  const runnerTemp = await realpath(process.env.RUNNER_TEMP);
  const resolvedArchive = path.join(await realpath(existing), path.relative(existing, path.resolve(archiveBase)));
  const relative = path.relative(runnerTemp, resolvedArchive);
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), 'Hosted evidence must stay inside RUNNER_TEMP');
} else {
  assert.match(execFileSync('findmnt', ['-n', '-T', existing, '-o', 'FSTYPE'], { encoding: 'utf8' }).trim().split(/\r?\n/).at(-1), /^nfs4?$/, 'Local human-transform evidence requires mounted NFS');
}
assert.equal(await realpath(execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: source, encoding: 'utf8' }).trim()), await realpath(source), 'Source root must match the Git inventory');
const runtime = await mkdtemp(path.join(tmpdir(), 'mtg-human-transform-browser-run-'));
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
assert.ok(Object.values(ports).every(p=>![10199,15173,19222].includes(p)));
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
  const response = await fetch(`${api}/fixture/delver-repair${route}`, { method, headers: { 'X-Human-Transform-Fixture': token }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Fixture ${route}: ${response.status} ${await response.text()}`);
  return response.json();
}
async function ready(url, child, owned = false) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, `Owned service exited: ${url}`);
    try {
      const response = await fetch(url, { headers: owned ? { 'X-Human-Transform-Fixture': token } : {}, signal: AbortSignal.timeout(1000) });
      if (response.ok) { if (owned) assert.equal((await response.json()).source_root, runtime); return; }
    } catch { /* Cold startup only, bounded by deadline. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Owned service startup timeout: ${url}`);
}
function startBackend() {
  backend = start('backend', python, ['-m', 'uvicorn', 'tests.delver_repair_fixture_server:app', '--host', '127.0.0.1', '--port', String(ports.backend)], path.join(runtime, 'backend'), {
    MTG_HUMAN_TRANSFORM_ROOT: runtime, MTG_HUMAN_TRANSFORM_TOKEN: token,
  });
  return ready(`${api}/fixture/delver-repair/status`, backend, true);
}
async function restartBackend() {
  const previous = (await fixtureRequest('/status')).pid;
  await stop(backend);
  await startBackend();
  assert.notEqual((await fixtureRequest('/status')).pid, previous, 'Must restart a real backend process');
}

try {
  const gitFiles = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', 'backend', 'frontend'], { cwd: source, encoding: 'utf8' }).split('\0').filter(Boolean);
  const files = [...new Set([...gitFiles, 'frontend/tests/human_transform_fixture_server.py', 'frontend/tests/browser-human-transform-audit.mjs'])]
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
  await writeFile(path.join(runtime, '.human-transform-owned'), token);
  await copyFile(path.join(runtime, 'frontend/tests/human_transform_fixture_server.py'), path.join(runtime, 'backend/tests/human_transform_fixture_server.py'));
  await copyFile(path.join(runtime, 'frontend/tests/delver_repair_fixture_server.py'), path.join(runtime, 'backend/tests/delver_repair_fixture_server.py'));
  await writeFile(path.join(runtime, 'source-manifest.json'), JSON.stringify({ revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' }).trim(), files: manifest }, null, 2));
  // Keep Vite's .vite-temp/config caches local, not in external node_modules.
  await mkdir(path.join(runtime, 'frontend/node_modules'));
  for (const entry of await readdir(deps)) {
    if (!entry.startsWith('.')) await symlink(path.join(deps, entry), path.join(runtime, 'frontend/node_modules', entry));
  }
  await writeFile(path.join(runtime, 'frontend/vite.mana.config.mjs'), `import {defineConfig} from 'vite';import react from '@vitejs/plugin-react';export default defineConfig({plugins:[react()],cacheDir:${JSON.stringify(path.join(runtime, 'vite-cache'))},server:{proxy:{'/card-images':{target:${JSON.stringify(api)}}}}});`);
  await startBackend();
  const vite = start('frontend', process.execPath, [path.join(deps, 'vite/bin/vite.js'), '--config', 'vite.mana.config.mjs', '--host', '127.0.0.1', '--port', String(ports.frontend), '--strictPort'], path.join(runtime, 'frontend'), { VITE_API_BASE_URL: api });
  const chromium = start('chromium', chrome, ['--headless', '--disable-dev-shm-usage', '--no-first-run', ...(process.env.MTG_BROWSER_NO_SANDBOX === '1' ? ['--no-sandbox'] : []), `--user-data-dir=${path.join(runtime, 'profile')}`, '--remote-debugging-address=127.0.0.1', `--remote-debugging-port=${ports.cdp}`, 'about:blank'], runtime);
  await ready(frontend, vite);
  await ready(`${process.env.MTG_BROWSER_ORIGIN}/json/version`, chromium);
  await mkdir(path.join(runtime, 'evidence'));

  const audit = await runDelverRepairAudit({api, frontend, runtime, fixtureRequest, restartBackend, caseNames:inspectionOnly?['delver-ineligible']:undefined});
  results.push(...audit.results);
  requests.push(...audit.actions);
  assert.equal(results.length,expectedCases);
  success = results.every(row => row.checks.every(check => check.status === "PASS"));
} catch (error) { failure = error; console.error(error.stack); }
finally {
  for (const child of [...children].reverse()) await stop(child);
  await writeFile(path.join(runtime, 'results.json'), JSON.stringify({ success, expected_cases: expectedCases, scope: inspectionOnly?'delver-inspection-copy2':'delver-repair12', elapsed_ms: Date.now()-started, results, requests, ports,
    processes: children.map(child => ({ label: child.label, pid: child.pid, exit_code: child.exitCode, signal: child.signalCode })),
    failure: failure?.stack, fixture_claim: 'Canonical explicit human-transform positions; no historical game or policy claim.' }, null, 2));
  const tar = path.join(archive, 'private/runtime-evidence.tar.gz');
  execFileSync('tar', ['--exclude=./profile', '--exclude=./frontend/node_modules', '--exclude=./vite-cache', '--exclude=*/__pycache__', '--exclude=*/image_cache', '--exclude=./.human-transform-owned', '-czf', tar, '-C', runtime, '.']);
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
