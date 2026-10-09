import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createServer } from 'node:net';
import { createServer as createHTTPServer } from 'node:http';
import { mkdir, readFile, writeFile, readdir, readlink, lstat, stat, statfs, realpath, symlink } from 'node:fs/promises';
import { openSync, closeSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runNativeHumanBo3 } from './browser-native-human-bo3.mjs';
import { runNativeHumanBo3Seat2 } from './browser-native-human-bo3-seat2.mjs';
import {runPaidBuiltCases, runBuiltRecovery, runBuiltOrigins} from './browser-current-paid-acceptance.mjs';

process.umask(0o077);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const project = path.dirname(root);
const ownedRoot = process.env.MTG_BROWSER_OWNED_ROOT;
const qualifiedCommit = process.env.MTG_BROWSER_QUALIFIED_COMMIT;
assert.equal(typeof ownedRoot, 'string', 'MTG_BROWSER_OWNED_ROOT is required');
assert.ok(path.isAbsolute(ownedRoot) && path.resolve(ownedRoot) === ownedRoot, 'Canonical absolute owned root required');
assert.equal(project, ownedRoot, 'Computed owned root must match required configuration');
assert.equal(await realpath(ownedRoot), ownedRoot, 'Owned root must not traverse symlinks');
assert.equal(typeof qualifiedCommit, 'string', 'MTG_BROWSER_QUALIFIED_COMMIT is required');
assert.equal(qualifiedCommit.length, 40, 'Exact Git commit length required');
assert.match(qualifiedCommit, /^[0-9a-f]{40}$/, 'Exact lowercase Git commit required');
assert.equal(process.env.MTG_BROWSER_NO_SANDBOX, '1', 'Exact isolated test-only Chrome launch contract');
const out = path.join(project, 'evidence/native-browser');
const python = '/tmp/mtg-fresh-deps-restored-dVBzUV/venv/bin/python';
const deps = '/home/nick/mtg-deck-testing-lab/frontend/node_modules';
const chrome = '/snap/chromium/3551/usr/lib/chromium-browser/chrome';
const db = path.join(project, 'runtime/sql/api.db');
const viteConfig = path.join(root, 'frontend/.native-browser-vite.config.mjs');
const digest = data => createHash('sha256').update(data).digest('hex');
const children = [];
const roleCounts = new Map();
const allocations = new Set();
const ports = {};
let backend, failure, watchdog, hardDeadline, rejectInterrupted, hostileServer, budgetWatch;
let budgetChecking = false, fuserChecking = false;
let backendReady = false;
let shuttingDown = false, closureProven = false;
const started = Date.now();
const status = { pin: qualifiedCommit, episodes: [], ports };

const ownerLock = db + '.capacity-owner.lock';
const ownerEpochs = new Map();
const closedBackupHashes = new Map();
let lockIdentity;

async function storageReceipts() {
  const names = (await readdir(out)).filter(name => /^storage-owner-\d+-[a-f0-9]{32}\.json$/.test(name));
  for (const name of names) {
    const receipt = JSON.parse(await readFile(path.join(out, name), 'utf8'));
    assert.match(receipt.epoch, /^[a-f0-9]{32}$/);
    assert.equal(name, `storage-owner-${receipt.pid}-${receipt.epoch}.json`);
    const child = children.find(c => c.label === 'backend' && c.pid === receipt.pid
      && c.startTicks === receipt.start_ticks);
    assert.ok(child, 'Owner receipt PID/startticks must match actual backend child');
    const previous = ownerEpochs.get(receipt.epoch);
    if (previous) assert.equal(previous.pid, receipt.pid, 'Epoch reused by another process');
    assert.equal(receipt.lock.path, ownerLock);
    assert.ok(receipt.backups.length <= 1, 'One actual backup attempt per lifespan');
    for (const backup of receipt.backups) {
      assert.equal(backup.path, db + '.before-capacity-' + receipt.epoch + '.db');
      if (backup.sha256 !== null) assert.match(backup.sha256, /^[a-f0-9]{64}$/);
    }
    if (receipt.lock.identity !== null) {
      if (lockIdentity) assert.deepEqual(receipt.lock.identity, lockIdentity, 'Retained lock inode changed');
      else lockIdentity = receipt.lock.identity;
      assert.equal(receipt.lock.bytes, 0);
    }
    ownerEpochs.set(receipt.epoch, receipt);
  }
  assert.ok(ownerEpochs.size <= 32, 'Actual lifespan count exceeds32');
  return [...ownerEpochs.values()];
}

async function storageInventory({closed = false} = {}) {
  const receipts = await storageReceipts();
  const backups = receipts.flatMap(r => r.backups);
  assert.ok(backups.length <= 32, 'Backup count exceeds32');
  assert.equal(new Set(backups.map(b => b.path)).size, backups.length);
  const allowed = new Set([db, ownerLock]);
  for (const base of [db, ...backups.map(b => b.path)])
    for (const suffix of ['', '-wal', '-shm', '-journal']) allowed.add(base + suffix);
  const actual = [];
  for (const name of await readdir(path.dirname(db))) {
    if (!name.startsWith(path.basename(db))) continue;
    const file = path.join(path.dirname(db), name);
    assert.ok(allowed.has(file), `Undeclared storage artifact: ${file}`);
    const info = await lstat(file).catch(error => {
      if (error.code === 'ENOENT' && /-(wal|shm|journal)$/.test(file)) return null;
      throw error;
    });
    if (info === null) continue;
    assert.ok(info.isFile() && !info.isSymbolicLink() && info.nlink === 1, 'Storage artifact must be single-link regular');
    const sidecar = /-(wal|shm|journal)$/.test(file);
    assert.ok(info.size <= (file === ownerLock ? 0 : file === db || sidecar ? 256 : 128) * 1024 * 1024);
    if (closed) assert.ok(!sidecar, `Unclosed storage sidecar: ${file}`);
    actual.push({path: file, bytes: info.size, dev: info.dev, ino: info.ino});
  }
  const bytes = actual.reduce((total, item) => total + item.bytes, 0);
  assert.ok(bytes <= 1024 * 1024 * 1024, 'Storage aggregate exceeds1GiB');
  if (lockIdentity && actual.some(a => a.path === ownerLock)) {
    const info = actual.find(a => a.path === ownerLock);
    assert.deepEqual([info.dev, info.ino], lockIdentity);
  }
  for (const [file, expected] of closedBackupHashes) {
    assert.ok(actual.some(a => a.path === file), 'Earlier successful backup removed');
    assert.equal(digest(await readFile(file)), expected, 'Earlier closed backup mutated');
  }
  if (closed) {
    for (const receipt of receipts) {
      assert.equal(receipt.stage, 'closed', 'Actual owner failed ordinary shutdown');
      assert.equal(receipt.owner_fd, null); assert.equal(receipt.registered, false);
      assert.equal(receipt.ready, false); assert.equal(receipt.admissions_open, false);
      assert.equal(receipt.producers, 0);
      for (const backup of receipt.backups) {
        if (!backup.verified_by_successful_lifespan) {
          assert.fail(`Failed/unqualified backup attempt retained: ${backup.path}`);
        }
        assert.equal(backup.exists, true);
        assert.ok(Object.values(backup.sidecars).every(value => value === false));
        assert.equal(digest(await readFile(backup.path)), backup.sha256);
        closedBackupHashes.set(backup.path, backup.sha256);
      }
    }
  }
  return {bytes, actual, allowed: [...allowed].sort(), receipts};
}

async function storageFuserPaths() {
  const storage = await storageInventory({closed: true});
  return [db, ...storage.actual.map(a => a.path).filter(file => file !== db).sort()];
}

async function missingLiveChromeCacheLeaf(error, file, entry) {
  const cache = path.join(out, 'profile/Default/Cache/Cache_Data');
  const child = children.find(c => c.label === 'chromium');
  const identity = child?.budgetIdentity;
  const record = async (reason, extra = {}) => {
    const races = outputBudget.cacheRaces ??= [];
    assert.ok(races.length < 4096, 'Finite Chrome cache race count');
    races.push({file, reason, identity, UTC: new Date().toISOString(), ...extra});
    const ledger = JSON.stringify(races);
    assert.ok(Buffer.byteLength(ledger) <= 2 * 1024 * 1024, 'Bounded cache race ledger');
    await writeFile(path.join(out, 'chrome-cache-races.json'), ledger);
  };
  const reject = async reason => { await record(reason); return false; };
  if (shuttingDown || error.code !== 'ENOENT' || error.path !== file || !entry.isFile()
      || path.dirname(file) !== cache || !/^(?:[a-f0-9]{16}_[0-9]+|todelete_[a-f0-9]{16}_[0-9]+_[0-9]+)$/.test(entry.name)
      || !identity || identity.pid !== child.pid || child.exitCode !== null || child.signalCode !== null)
    return reject('scope-or-live-child-rejected');
  assert.equal(await realpath(cache), cache, 'Chrome cache must not redirect');
  const alive = async () => {
    if (shuttingDown || child.exitCode !== null || child.signalCode !== null) return false;
    const proc = await readFile('/proc/' + child.pid + '/stat', 'utf8');
    const startTicks = proc.slice(proc.lastIndexOf(')') + 2).split(/\s+/)[19];
    return startTicks === identity.startTicks && await realpath('/proc/' + child.pid + '/exe') === identity.exe;
  };
  if (!await alive()) return reject('native-identity-rejected-before-lstat');
  let leaf;
  try { leaf = await lstat(file); }
  catch (gone) { if (gone.code !== 'ENOENT' || gone.path !== file) throw gone; }
  if (leaf && !leaf.isFile()) return reject('recreated-leaf-not-regular');
  if (!await alive()) return reject('native-identity-rejected-after-lstat');
  // A recreated regular leaf is charged, never silently skipped from the cap.
  const result = {size: leaf?.size ?? 0, outcome: leaf ? 'recreated-regular-charged' : 'confirmed-missing'};
  await record(result.outcome, {chargedBytes: result.size, dev: leaf?.dev, ino: leaf?.ino});
  return result;
}

async function outputBudget() {
  let bytes = 0, profileBytes = 0, screenshots = 0;
  async function walk(directory) {
    for (const entry of await readdir(directory, {withFileTypes: true})) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(file);
      else if (entry.isFile()) {
        let size;
        try { size = (await stat(file)).size; }
        catch (error) {
          const race = await missingLiveChromeCacheLeaf(error, file, entry);
          if (!race) throw error;
          size = race.size;
        }
        bytes += size;
        if (file.startsWith(path.join(out, 'profile') + '/')) profileBytes += size;
        if (entry.name.endsWith('.png')) screenshots++;
        if (/\.(log|jsonl)$/.test(entry.name)) assert.ok(size <= 256 * 1024 * 1024, 'Per-journal byte limit');
      }
      // Do not follow Chrome's profile singleton/socket symlinks outside the owned tree.
    }
  }
  await walk(out);
  assert.ok(profileBytes <= 512 * 1024 * 1024, 'Profile exceeds 512 MiB');
  assert.ok(screenshots <= 64, 'Screenshot count exceeds 64');
  assert.ok(bytes <= 1536 * 1024 * 1024, 'Owned output exceeds aggregate 1.5 GiB');
  const media = path.join(root, 'backend/card_data/image_cache');
  const mediaNames = await readdir(media).catch(error => {
    if (error.code === 'ENOENT' && !backendReady) return [];
    throw error;
  });
  const svg = mediaNames.filter(name => name.endsWith('.svg'));
  assert.ok(svg.length <= 512, 'Media count exceeds 512');
  for (const name of svg) {
    const file = path.join(media, name);
    assert.ok((await lstat(file)).isFile(), 'Generated media must be regular files');
    assert.ok((await stat(file)).size <= 65536, 'SVG exceeds 64 KiB');
  }
  const storage = await storageInventory();
  assert.ok(bytes + storage.bytes <= 2560 * 1024 * 1024, 'Combined owned output exceeds2.5GiB');
  return {bytes, storageBytes: storage.bytes, profileBytes, screenshots, svgCount: svg.length,
    observedChromeCacheRaceCount: outputBudget.cacheRaces?.length ?? 0,
    enforcement: 'cooperative 1s checkpoints plus producer SVG pre-write checks; not a kernel quota'};
}

async function deadline(promise, ms, label) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} deadline`)), ms);
  })]); } finally { clearTimeout(timer); }
}

async function absent(file) {
  try { await lstat(file); assert.fail(`Existing path: ${file}`); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}
async function checkPins() {
  const pins = JSON.parse(await readFile(path.join(project, 'runner/source-pins.json'), 'utf8'));
  for (const [file, hash] of Object.entries(pins)) {
    assert.equal(digest(await readFile(path.join(root, file))), hash, file);
  }
}
async function allocate() {
  assert.ok(!shuttingDown && !failure, 'No port allocation after interruption/shutdown');
  const s = createServer();
  allocations.add(s);
  try {
    await new Promise((resolve, reject) => { s.once('error', reject); s.listen(0, '127.0.0.1', resolve); });
    assert.ok(!shuttingDown && !failure, 'Allocation completed after shutdown');
    const p = s.address().port;
    assert.ok(![9999, 5173, 10199, 15173, 19222, 48343, 48344].includes(p));
    return p;
  } finally { await new Promise(resolve => s.close(resolve)); allocations.delete(s); }
}
function authorizeChild(label, executable, args, cwd) {
  const limits = {build: 1, preview: 1, chromium: 1, backend: 32, ledger: 31,
    'restart-fuser': 31, 'closure-fuser': 1};
  assert.ok(Object.hasOwn(limits, label), `Undeclared child role: ${label}`);
  const count = (roleCounts.get(label) ?? 0) + 1;
  assert.ok(count <= limits[label], `Child role exhausted: ${label}`);
  const vite = path.join(deps, 'vite/bin/vite.js');
  if (label === 'backend') {
    assert.equal(executable, python); assert.equal(cwd, path.join(root, 'backend'));
    assert.deepEqual(args, ['-m', 'uvicorn', 'tests.current_built_browser_server:app',
      '--host', '127.0.0.1', '--port', String(ports.backend)]);
  } else if (label === 'ledger') {
    assert.equal(executable, python); assert.equal(cwd, path.join(root, 'backend'));
    assert.equal(args.length, 3); assert.equal(args[0], path.join(root, 'backend/tests/current_built_browser_server.py'));
    assert.equal(args[1], '--closed-ledger'); assert.match(args[2], /^[a-z0-9-]+$/);
  } else if (label.endsWith('fuser')) {
    assert.equal(executable, '/usr/bin/fuser'); assert.equal(cwd, path.join(root, 'backend'));
    assert.deepEqual(args, authorizedFuserPaths);
  } else if (label === 'build') {
    assert.equal(executable, process.execPath); assert.equal(cwd, path.join(root, 'backend'));
    assert.deepEqual(args, [vite, 'build', '--config', viteConfig]);
  } else if (label === 'preview') {
    assert.equal(executable, process.execPath); assert.equal(cwd, path.join(root, 'frontend'));
    assert.deepEqual(args, [vite, 'preview', '--config', viteConfig, '--host', '127.0.0.1',
      '--port', String(ports.frontend), '--strictPort']);
  } else {
    assert.equal(executable, chrome); assert.equal(cwd, root);
    assert.deepEqual(args, ['--headless', '--no-first-run', '--disable-dev-shm-usage',
      '--disable-background-networking', '--no-default-browser-check', '--password-store=basic',
      '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
      '--no-sandbox',
      `--user-data-dir=${path.join(out, 'profile')}`, '--remote-debugging-address=127.0.0.1',
      `--remote-debugging-port=${ports.cdp}`, 'about:blank']);
  }
  roleCounts.set(label, count);
}
function ownedEnvironment(executable, env) {
  const own = {...process.env, ...env, PYTHONDONTWRITEBYTECODE: '1',
    TMPDIR: path.join(out, 'tmp'), TMP: path.join(out, 'tmp'), TEMP: path.join(out, 'tmp')};
  if (executable === python) own.MTG_DATABASE_PATH = db;
  if (executable === chrome) {
    for (const name of Object.keys(own)) if (name.startsWith('SNAP') ||
      ['CHROMIUM_FLAGS', 'CHROME_WRAPPER', 'DBUS_SESSION_BUS_ADDRESS', 'DISPLAY', 'WAYLAND_DISPLAY',
        'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'LD_DEBUG'].includes(name)) delete own[name];
    Object.assign(own, {HOME: path.join(out, 'home'),
      XDG_CONFIG_HOME: path.join(out, 'config'), XDG_CACHE_HOME: path.join(out, 'cache'),
      XDG_DATA_HOME: path.join(out, 'data'), XDG_STATE_HOME: path.join(out, 'state'),
      XDG_RUNTIME_DIR: path.join(out, 'runtime'), CHROME_CONFIG_HOME: path.join(out, 'config')});
  }
  return own;
}

function start(label, executable, args, cwd, env = {}) {
  assert.ok(!shuttingDown && !failure, 'No new owned service after interruption/shutdown');
  authorizeChild(label, executable, args, cwd);
  const fd = openSync(path.join(out, `${label}.log`), 'a', 0o600);
  const child = spawn(executable, args, { cwd, detached: true, stdio: ['ignore', fd, fd],
    env: ownedEnvironment(executable, env) });
  closeSync(fd);
  child.label = label;
  child.done = new Promise(resolve => { child.once('exit', resolve); child.once('error', resolve); });
  children.push(child);
  assert.ok(!shuttingDown, 'Service registration during shutdown');
  console.log(`OWN ${label} pid=${child.pid} UTC=${new Date().toISOString()} root=${root} ports=${JSON.stringify(ports)}`);
  return child;
}
async function stop(child) {
  if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return;
  try { process.kill(-child.pid, 'SIGTERM'); } catch (e) { if (e.code !== 'ESRCH') throw e; }
  let timer;
  await Promise.race([child.done, new Promise(resolve => { timer = setTimeout(resolve, 5000); })]);
  clearTimeout(timer);
  if (child.exitCode === null && child.signalCode === null) {
    try { process.kill(-child.pid, 'SIGKILL'); } catch (e) { if (e.code !== 'ESRCH') throw e; }
    await deadline(child.done, 2000, `Owned KILL exit ${child.label}`);
    assert.fail(`Forced kill required: ${child.label}`);
  }
}
async function capture(label, executable, args, ms, env = {}) {
  assert.ok((!shuttingDown && !failure) || (shuttingDown && label === 'closure-fuser'),
    'Only closure-fuser may spawn after interruption/shutdown');
  authorizeChild(label, executable, args, path.join(root, 'backend'));
  const child = spawn(executable, args, { cwd: path.join(root, 'backend'), detached: true,
    env: ownedEnvironment(executable, env), stdio: ['ignore', 'pipe', 'pipe'] });
  child.label = label;
  let stdout = '', stderr = '', error, code, bytes = 0;
  const collect = (chunk, stream) => {
    bytes += chunk.length;
    if (bytes > 16 * 1024 * 1024) {
      error ??= `${label} combined output exceeds 16 MiB`;
      try { process.kill(-child.pid, 'SIGTERM'); } catch (e) { if (e.code !== 'ESRCH') throw e; }
      return;
    }
    if (stream === 'stdout') stdout += chunk; else stderr += chunk;
  };
  child.stdout.on('data', b => collect(b, 'stdout')); child.stderr.on('data', b => collect(b, 'stderr'));
  child.done = new Promise(resolve => {
    child.once('error', e => { error = e.message; });
    child.once('close', exit => { code = exit; resolve(); });
  });
  children.push(child);
  assert.ok(!shuttingDown || label === 'closure-fuser', 'Diagnostic registration during shutdown');
  console.log(`OWN ${label} pid=${child.pid} UTC=${new Date().toISOString()} root=${root}`);
  try { await deadline(child.done, ms, label); }
  finally {
    try { await stop(child); }
    finally {
      await writeFile(path.join(out, `${label}-${child.pid??'spawn-error'}.json`), JSON.stringify({
        pid: child.pid, argv: [executable, ...args], exit: code, signal: child.signalCode,
        error, stdout, stderr, UTC: new Date().toISOString() }, null, 2));
    }
  }
  assert.equal(error, undefined, `${label} spawn error`);
  return { exit: code, stdout, stderr };
}
let authorizedFuserPaths;
async function checkFuser(label) {
  const end = Date.now() + 5000;
  const wait = async () => {
    assert.ok(Date.now() < end, 'Owned budget reader/fuser section did not quiesce within5s');
    await new Promise(resolve => setTimeout(resolve, 10));
  };
  while (fuserChecking) await wait();
  fuserChecking = true;
  try {
    // The periodic backup hasher is an owned FD holder, not a database owner.
    while (budgetChecking) await wait();
    authorizedFuserPaths = await storageFuserPaths();
    const result = await capture(label, '/usr/bin/fuser', authorizedFuserPaths, 5000);
    assert.equal(result.exit, 1); assert.equal(result.stdout, ''); assert.equal(result.stderr, '');
    return result;
  } finally { fuserChecking = false; }
}
async function ready(url, child) {
  const end = Date.now() + 90000;
  while (Date.now() < end) {
    assert.ok(!shuttingDown && !failure, 'No readiness continuation during shutdown');
    assert.equal(child.exitCode, null, `Service exited: ${child.label}`);
    try { if ((await fetch(url, { signal: AbortSignal.timeout(1000) })).ok) return; }
    catch { /* Read-only readiness polling, never a mutation retry. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.fail(`Service readiness deadline: ${url}`);
}
async function startBackend() {
  assert.ok(!shuttingDown && !failure, 'No backend restart after shutdown');
  backendReady = false;
  backend = start('backend', python, ['-m', 'uvicorn', 'tests.current_built_browser_server:app',
    '--host', '127.0.0.1', '--port', String(ports.backend)], path.join(root, 'backend'), {
    MTG_BUILT_BACKEND_PORT: String(ports.backend),
    MTG_BUILT_PAGE_ORIGIN: `http://127.0.0.1:${ports.frontend}`,
    MTG_TRUSTED_ORIGINS: `http://127.0.0.1:${ports.frontend}`,
    TMPDIR: path.join(out, 'tmp'), SQLITE_TMPDIR: path.join(out, 'tmp') });
  const processStat = await readFile(`/proc/${backend.pid}/stat`, 'utf8');
  backend.startTicks = Number(processStat.slice(processStat.lastIndexOf(')') + 2).split(/\s+/)[19]);
  assert.ok(Number.isSafeInteger(backend.startTicks) && backend.startTicks > 0);
  await ready(`http://127.0.0.1:${ports.backend}/health`, backend);
  assert.ok(!shuttingDown && !failure, 'Backend became ready after shutdown');
  const owners = await storageReceipts();
  const owner = owners.find(receipt => receipt.pid === backend.pid);
  assert.ok(owner && owner.stage === 'ready' && owner.registered && owner.ready
    && owner.owner_fd !== null && owner.admissions_open && owner.backups.length === 1);
  assert.equal(owner.backups[0].verified_by_successful_lifespan, true);
  backendReady = true;
}
async function readLedger(mid) {
  assert.ok(!shuttingDown && !failure, 'No ledger child during shutdown');
  const result = await capture('ledger', python,
    [path.join(root, 'backend/tests/current_built_browser_server.py'), '--closed-ledger', mid], 30000,
    { MTG_BUILT_BACKEND_PORT: String(ports.backend) });
  assert.equal(result.exit, 0, result.stderr); assert.equal(result.stderr, '');
  return JSON.parse(result.stdout);
}
async function restartBackend(mid) {
  assert.ok(!shuttingDown && !failure, 'No restart continuation during shutdown');
  const oldPid = backend.pid;
  await stop(backend);
  assert.ok(!shuttingDown && !failure, 'Shutdown while stopping prior backend');
  const before = digest(await readFile(db));
  const fuser = await checkFuser('restart-fuser');
  const ledger=await readLedger(mid);
  assert.ok(!shuttingDown && !failure, 'Shutdown while reading closed ledger');
  assert.equal(digest(await readFile(db)),before,'Read-only child changed closed DB');
  await startBackend();
  assert.notEqual(backend.pid, oldPid);
  await writeFile(path.join(out, `restart-${backend.pid}.json`), JSON.stringify({ oldPid, newPid: backend.pid,
    closedDBBefore: before, fuser, ledger, UTC: new Date().toISOString() }, null, 2));
  return ledger;
}
async function closedReceipt() {
  assert.equal(allocations.size, 0, 'All temporary port allocations must close');
  const storage = await storageInventory({closed: true});
  assert.equal(storage.receipts.length, children.filter(c => c.label === 'backend').length);
  const targets = new Set(storage.allowed);
  const identities = new Set(storage.actual.map(a => `${a.dev}:${a.ino}`));
  const refs = [], inaccessible = [], unreadableFDs = [];
  for (const entry of await readdir('/proc')) {
    if (!/^\d+$/.test(entry) || Number(entry) === process.pid) continue;
    try {
      const cwd = await realpath(`/proc/${entry}/cwd`);
      if (cwd === root || cwd.startsWith(root + '/')) refs.push({ pid: Number(entry), cwd });
    } catch (error) { if (error.code !== 'ENOENT') inaccessible.push(Number(entry)); }
    try {
      for (const fd of await readdir(`/proc/${entry}/fd`)) {
        try { const fdPath = `/proc/${entry}/fd/${fd}`;
          const target = await readlink(fdPath);
          const canonical = target.endsWith(' (deleted)') ? target.slice(0, -10) : target;
          const info = await stat(fdPath);
          if (targets.has(canonical) || identities.has(`${info.dev}:${info.ino}`))
            refs.push({ pid: Number(entry), fd, target, dev: info.dev, ino: info.ino });
        } catch (error) { if (error.code !== 'ENOENT')
          unreadableFDs.push({pid: Number(entry), fd, error: error.code}); }
      }
    } catch { inaccessible.push(Number(entry)); }
  }
  const journals = (await readdir(path.dirname(db))).filter(n => n.startsWith('api.db-'));
  for (const p of Object.values(ports)) {
    const s = createServer();
    await new Promise((resolve, reject) => { s.once('error', reject); s.listen(p, '127.0.0.1', resolve); });
    await new Promise(resolve => s.close(resolve));
  }
  const fuser = await checkFuser('closure-fuser');
  const receipt = { refs, inaccessible, unreadableFDs, journals, fuser, storage,
    processes: children.map(c => ({ label: c.label, pid: c.pid, exit: c.exitCode, signal: c.signalCode })),
    inputScope: 'reviewed file hashes, not generated media/full-tree equality', UTC: new Date().toISOString() };
  await writeFile(path.join(out, 'CLOSURE.json'), JSON.stringify(receipt, null, 2));
  assert.deepEqual(refs, []); assert.deepEqual(journals, []);
  assert.ok(children.every(c => c.exitCode !== null || c.signalCode !== null), 'All tracked children must exit');
  const serverReceipts=(await readdir(out)).filter(n => /^server-closure-\d+\.json$/.test(n));
  assert.equal(serverReceipts.length,children.filter(c=>c.label==='backend').length,'Every real server must close');
  for (const file of serverReceipts) {
    const d = JSON.parse(await readFile(path.join(out, file), 'utf8'));
    assert.deepEqual(d.denials, []); assert.deepEqual(d.jobs, {}); assert.equal(d.ordinary_pool_disposed,true);assert.equal(d.zero_checkouts,true);assert.equal(d.workers_empty,true);assert.equal(d.shutdown_admission_closed,true);assert.equal(d.no_emergency_dispose,true);assert.equal(d.canaries.length,3);
    assert.equal(d.shutdown_complete, true, 'Real lifespan shutdown must complete before receipt');
  }
  for (const child of children.filter(c => c.label === 'backend')) {
    assert.ok(child.exitCode === 0 || (child.exitCode === null && child.signalCode === 'SIGTERM'), 'Backend actual0 or -TERM plus genuine shutdown receipt required');
  }
  await checkPins();
  await writeFile(path.join(out, 'OUTPUT-BOUNDS.json'), JSON.stringify(await outputBudget(), null, 2));
}

assert.equal(process.argv.length, 2);
const grant=JSON.parse(await readFile(path.join(project,'runner/EXECUTION-GRANT.json'),'utf8'));
assert.deepEqual(grant,{root:project,source:root,commit:status.pin,scope:'built-app-40paid-3recovery-3BO3-4origin',explicit_parent_grant:true,seconds:2400});
const cohort=JSON.parse(await readFile(path.join(project,'runner/cohort.json'),'utf8'));
assert.equal(cohort.length,40);
process.env.MTG_CDP_DIAGNOSTIC_DIR=path.join(out,'cdp-observations');
const fixtureToken=(await readFile(path.join(project,'runner/fixture-token'),'utf8')).trim();
assert.match(fixtureToken,/^[0-9a-f]{64}$/);
const runnerPins=JSON.parse(await readFile(path.join(project,'runner/runner-pins.json'),'utf8'));
for(const [name,hash] of Object.entries(runnerPins)) assert.equal(digest(await readFile(path.join(project,'runner',name))),hash,name);
const externalPins=JSON.parse(await readFile(path.join(project,'runner/external-readonly-pins.json'),'utf8'));
for(const [file,hash] of Object.entries(externalPins)) assert.equal(digest(await readFile(file)),hash,file);
const execPins=JSON.parse(await readFile(path.join(project,'runner/executable-pins.json'),'utf8'));
assert.equal(process.execPath,execPins.node.path);
for(const row of Object.values(execPins)) {
  assert.equal(await realpath(row.path), row.realpath, `Executable target changed: ${row.path}`);
  assert.equal(digest(await readFile(row.path)),row.SHA256,row.path);
}
assert.ok(Number(process.versions.node.split('.')[0])>=22 && typeof WebSocket==='function');
const dependencyPins=JSON.parse(await readFile(path.join(project,'runner/dependency-pins-executable.json'),'utf8'));
for(const [file,hash] of Object.entries(dependencyPins)) assert.equal(digest(await readFile(path.join(deps,file))),hash,file);
const dependencyLinks=JSON.parse(await readFile(path.join(project,'runner/dependency-links.json'),'utf8'));
for(const [file,target] of Object.entries(dependencyLinks)) {
  assert.equal(await readlink(path.join(deps,file)),target,`Dependency link changed: ${file}`);
}
const runtimeRoot=path.dirname(path.dirname(python));
for(const line of (await readFile(path.join(project,'runner/runtime-nonpip.sha256'),'utf8')).trim().split('\n')) {const [hash,file]=line.split('  ');assert.equal(digest(await readFile(path.join(runtimeRoot,file))),hash,file);}
const stdlibPins=JSON.parse(await readFile(path.join(project,'runner/stdlib-pins.json'),'utf8'));
for(const [file,hash] of Object.entries(stdlibPins)) assert.equal(digest(await readFile(file)),hash,file);
const versions=JSON.parse(await readFile(path.join(project,'runner/runtime-packages.json'),'utf8'));
const installed=new Map();
const site=path.join(runtimeRoot,'lib/python3.12/site-packages');
for(const directory of await readdir(site)) if(directory.endsWith('.dist-info')) {const m=await readFile(path.join(site,directory,'METADATA'),'utf8');const name=m.match(/^Name: (.+)$/m)?.[1];const version=m.match(/^Version: (.+)$/m)?.[1];if(name&&version) installed.set(name.toLowerCase().replace(/[-_.]+/g,'-'),version);}
for(const row of versions) assert.equal(installed.get(row.name.toLowerCase().replace(/[-_.]+/g,'-')),row.version,row.name);
assert.ok((await stat(python)).isFile() && ((await stat(python)).mode & 0o111), 'Parent-qualified pinned recovery interpreter required; no unreviewed substitution');
assert.ok((await lstat(chrome)).isFile() || (await lstat(chrome)).isSymbolicLink(), 'Existing cached Chromium required');
assert.ok((await lstat(path.join(deps,'vite/bin/vite.js'))).isFile());
assert.equal(await readFile(path.join(project, '.built-browser-owned'), 'utf8'), root);
for (let p = root;; p = path.dirname(p)) { assert.equal((await lstat(p)).isSymbolicLink(), false); if (p === '/') break; }
await absent(path.join(root, '.git')); await absent(path.join(root, 'backend/mtg_lab.db')); await absent(db); await absent(path.join(root, 'frontend/node_modules'));
await absent(viteConfig);
assert.ok(!(await readdir(path.dirname(db))).some(n => n.startsWith('api.db')));
await absent(out);
const capacity = await statfs(root, {bigint: true});
assert.ok(capacity.bavail * capacity.bsize >= 3221225472n, 'At least 3 GiB initially free');
await checkPins();
await mkdir(out, { mode: 0o700 });
await writeFile(path.join(out, 'ONCE-STARTED.json'), JSON.stringify({ pid: process.pid, started: new Date().toISOString(),
  maxSeconds: 2400, maxActionsPerEpisode: 6000, noRetry: true }));
function interrupted(signal) {
  shuttingDown = true;
  failure ??= new Error(signal);
  rejectInterrupted?.(failure);
  for(const c of children) if(c.pid&&c.exitCode===null&&c.signalCode===null) {
    try {process.kill(-c.pid,'SIGTERM');}catch{/* Owned process may already have exited. */}
  }
}
process.on('SIGTERM', () => interrupted('Overall bound/SIGTERM'));
process.on('SIGINT', () => interrupted('SIGINT'));
try {
  const interruption = new Promise((_, reject) => { rejectInterrupted = reject; });
  watchdog = setTimeout(() => interrupted('2250-second work deadline; reserve teardown time'),
    Math.max(1, 2250000 - (Date.now() - started)));
  hardDeadline = setTimeout(() => {
    for (const c of children) if (c.pid && c.exitCode === null && c.signalCode === null) {
      try { process.kill(-c.pid, 'SIGKILL'); } catch { /* Owned child already gone. */ }
    }
    console.error('2400-second hard bound: closure UNPROVEN; SQL lease NOT released');
    process.exit(1);
  }, Math.max(1, 2400000 - (Date.now() - started)));
  budgetWatch = setInterval(async () => {
    if (budgetChecking || shuttingDown || fuserChecking) return;
    budgetChecking = true;
    try { await outputBudget(); }
    catch (error) { interrupted(`Output bound: ${error.message}`); }
    finally { budgetChecking = false; }
  }, 1000);
  await Promise.race([interruption, (async () => {
  ports.backend = await allocate(); ports.frontend = await allocate(); ports.cdp = await allocate(); ports.hostile = await allocate();
  assert.ok(!shuttingDown && !failure, 'No preparation after allocation shutdown');
  assert.equal(new Set(Object.values(ports)).size, 4);
  const modules = path.join(root, 'frontend/node_modules');
  await mkdir(modules);
  for (const name of await readdir(deps)) if (!name.startsWith('.')) {
    assert.ok(!shuttingDown && !failure, 'No dependency-link continuation after shutdown');
    await symlink(path.join(deps, name), path.join(modules, name));
  }
  assert.ok(!shuttingDown && !failure, 'No config preparation after shutdown');
  const api = `http://127.0.0.1:${ports.backend}`, frontend = `http://127.0.0.1:${ports.frontend}`;
  for (const name of ['tmp', 'home', 'config', 'cache', 'data', 'state', 'runtime']) await mkdir(path.join(out, name), {mode: 0o700});
  const dist=path.join(out,'dist');
  await writeFile(viteConfig, `import react from ${JSON.stringify(path.join(deps,'@vitejs/plugin-react/dist/index.js'))};export default {root:${JSON.stringify(path.join(root,'frontend'))},plugins:[react()],cacheDir:${JSON.stringify(path.join(out,'vite-cache'))},build:{outDir:${JSON.stringify(dist)},emptyOutDir:false},preview:{host:'127.0.0.1',port:${ports.frontend},strictPort:true}};`);
  const build=await capture('build',process.execPath,[path.join(deps,'vite/bin/vite.js'),'build','--config',viteConfig],120000,{VITE_API_BASE_URL:api});
  assert.equal(build.exit,0,'Fresh fullApp production build required');
  const built={}; let builtBytes=0;
  async function hashTree(directory,base){for(const entry of await readdir(directory,{withFileTypes:true})){const file=path.join(directory,entry.name);if(entry.isDirectory())await hashTree(file,base);else if(entry.isFile()){builtBytes+=(await stat(file)).size;assert.ok(builtBytes<=128*1024*1024,'Built dist exceeds 128 MiB');built[path.relative(base,file)]=digest(await readFile(file));}else assert.fail('Built asset symlink');}}
  await hashTree(dist,dist);assert.ok(built['index.html']);assert.ok(Object.keys(built).length<=2048,'Built asset count');
  await writeFile(path.join(out,'BUILD-PINS.json'),JSON.stringify(built,null,2));
  await startBackend();
  const vite=start('preview',process.execPath,[path.join(deps,'vite/bin/vite.js'),'preview','--config',viteConfig,'--host','127.0.0.1','--port',String(ports.frontend),'--strictPort'],path.join(root,'frontend'));
  hostileServer=createHTTPServer((request,response)=>{if(request.method!=='GET'||!['/','/null'].includes(request.url)){response.writeHead(404).end();return;}response.setHeader('Content-Type','text/html');response.end('<!doctype html><title>Owned Origin control</title><body>Owned Origin control</body>');});
  await new Promise((resolve,reject)=>{hostileServer.once('error',reject);hostileServer.listen(ports.hostile,'127.0.0.1',resolve);});
  const chromium = start('chromium', chrome, ['--headless', '--no-first-run', '--disable-dev-shm-usage',
    '--disable-background-networking', '--no-default-browser-check', '--password-store=basic',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
    '--no-sandbox',
    `--user-data-dir=${path.join(out,'profile')}`, '--remote-debugging-address=127.0.0.1',
    `--remote-debugging-port=${ports.cdp}`, 'about:blank'], root);
  const chromeStat = await readFile(`/proc/${chromium.pid}/stat`, 'utf8');
  chromium.budgetIdentity = Object.freeze({pid: chromium.pid,
    startTicks: chromeStat.slice(chromeStat.lastIndexOf(')') + 2).split(/\s+/)[19],
    exe: await realpath(`/proc/${chromium.pid}/exe`)});
  assert.equal(chromium.budgetIdentity.exe, await realpath(chrome), 'Actual cached Chrome identity');
  await writeFile(path.join(out, 'chrome-native-identity.json'), JSON.stringify(chromium.budgetIdentity));
  await ready(frontend, vite); await ready(`http://127.0.0.1:${ports.cdp}/json/version`, chromium);
  const served = {};
  for (const [name, hash] of Object.entries(built)) {
    assert.ok(!failure && !shuttingDown);
    const response = await fetch(frontend + '/' + name, {signal: AbortSignal.timeout(5000)});
    assert.equal(response.status, 200, `Built asset unavailable: ${name}`);
    const data = Buffer.from(await response.arrayBuffer());
    assert.equal(digest(data), hash, `Served asset differs from fresh dist: ${name}`);
    served[name] = {SHA256: hash, bytes: data.length, mime: response.headers.get('content-type')};
  }
  const html = await readFile(path.join(dist, 'index.html'), 'utf8');
  assert.ok(!html.includes('/@vite/client') && !html.includes('/src/main.tsx'), 'No development entry served');
  assert.match(html, /<script\b[^>]*src="[^"\n]*\/assets\//, 'Production bundled App entry required');
  await writeFile(path.join(out, 'SERVED-BUILD.json'), JSON.stringify(served, null, 2));
  process.env.MTG_BROWSER_ORIGIN = `http://127.0.0.1:${ports.cdp}`;
  process.env.MTG_FRONTEND_ORIGIN = frontend;
  const assertAlive=()=>{assert.ok(!failure);assert.equal(backend.exitCode,null);};
  status.paid=await deadline(runPaidBuiltCases({cases:cohort,api,frontend,out,token:fixtureToken,restartBackend,assertAlive}),1500000,'Controlled40');
  status.recovery=await deadline(runBuiltRecovery({api,frontend,out,token:fixtureToken,restartBackend,assertAlive}),180000,'Recovery3');
  const lastFixture=JSON.parse(await readFile(path.join(out,'fixture-'+cohort.at(-1).id+'.json'),'utf8'));
  status.origins=await deadline(runBuiltOrigins({api,frontend,hostile:`http://127.0.0.1:${ports.hostile}`,out,token:fixtureToken,mid:lastFixture.metadata.id,assertAlive}),120000,'Origin4');
  for (const mode of ['human_vs_human', 'player_vs_ai']) {
    assert.ok(!failure);
    const maxMilliseconds = mode === 'human_vs_human' ? 900000 : 1200000;
    status.episodes.push(await deadline(runNativeHumanBo3({ mode, api, frontend, out, restartBackend,
      maxMilliseconds,
      assertAlive: () => { assert.ok(!failure); assert.equal(backend.exitCode, null); } }),
    maxMilliseconds, `${mode} episode`));
  }
  status.episodes.push(await deadline(runNativeHumanBo3Seat2({mode: 'player_vs_ai',
    api, frontend, out, maxMilliseconds: 1200000,
    restartBackend: async mid => {
      const ledger = await restartBackend(mid);
      assert.equal(ledger.controller.difficulties['1'], 'master_plus', 'Actual retained AI seat1 difficulty');
      return ledger;
    },
    assertAlive: () => { assert.ok(!failure); assert.equal(backend.exitCode, null); }}),
    1200000, 'player_vs_ai seat2 reversed whole decks episode'));
  })()]);
} catch (error) { failure ??= error; }
finally {
  shuttingDown = true;
  clearTimeout(watchdog);
  clearInterval(budgetWatch);
  if(hostileServer) {try{hostileServer.closeAllConnections();await new Promise(resolve=>hostileServer.close(resolve));}catch(error){failure??=error;}}
  try { await deadline(Promise.all([...allocations].map(async s => {
    await new Promise(resolve => s.close(resolve)); allocations.delete(s);
  })), 1000, 'Temporary listener closure'); } catch (error) { failure ??= error; }
  await Promise.all([...children].reverse().map(async c => {
    try { await stop(c); } catch (error) { failure ??= error; }
  }));
  try { await deadline(closedReceipt(), 8000, 'OS closure'); closureProven = true; }
  catch (error) { failure ??= error; }
  status.elapsedMilliseconds = Date.now() - started; status.failure = failure?.stack;
  status.closureProven = closureProven;
  status.success = !failure && status.episodes.length === 3 && status.paid?.length===40 && status.recovery?.length===3 && status.origins?.length===4;
  await writeFile(path.join(out, 'RESULT.json'), JSON.stringify(status, null, 2));
  console.log(`TERMINAL success=${status.success} UTC=${new Date().toISOString()} evidence=${out}`);
  if (closureProven) clearTimeout(hardDeadline);
  else {
    for (const c of children) if (c.pid && c.exitCode === null && c.signalCode === null) {
      try { process.kill(-c.pid, 'SIGKILL'); } catch { /* Only tracked owned groups. */ }
    }
    console.error('Bounded supervisor exit: closure UNPROVEN; SQL lease NOT released');
    process.exit(1);
  }
}
if (failure) { console.error(failure.stack); process.exitCode = 1; }
