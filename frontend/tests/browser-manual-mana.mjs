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
assert.ok(process.argv.length === 2 || (process.argv.length === 3 && process.argv[2] === '--shortcuts'), 'Only the default14 or --shortcuts6 declared scopes are supported');
const shortcuts = process.argv[2] === '--shortcuts';
const scenarios = shortcuts ? ['land-preset', 'mixed-preset', 'mixed-sphere-preset'] : ['tower', 'witch', 'cairns', 'grove', 'reflection', 'sphere', 'plain'];
const expectedCases = scenarios.length * 2;
const started = Date.now();
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
const deps = await realpath(process.env.MTG_FRONTEND_DEPS || path.join(source, 'frontend/node_modules'));
const chrome = process.env.MTG_CHROMIUM || execFileSync('bash', ['-c', 'command -v google-chrome || command -v chromium'], { encoding: 'utf8' }).trim();
const archiveBase = process.env.MTG_MANA_ARCHIVE || '/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/manual-mana-ui';
let existing = path.resolve(archiveBase);
while (true) { try { await stat(existing); break; } catch (error) { if (error.code !== 'ENOENT') throw error; existing = path.dirname(existing); } }
if (process.env.GITHUB_ACTIONS === 'true') {
  assert.ok(process.env.RUNNER_TEMP && process.env.MTG_MANA_ARCHIVE, 'Hosted CI requires explicit RUNNER_TEMP evidence');
  const runnerTemp = await realpath(process.env.RUNNER_TEMP);
  const resolvedArchive = path.join(await realpath(existing), path.relative(existing, path.resolve(archiveBase)));
  const relative = path.relative(runnerTemp, resolvedArchive);
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), 'Hosted evidence must stay inside RUNNER_TEMP');
} else {
  assert.match(execFileSync('findmnt', ['-n', '-T', existing, '-o', 'FSTYPE'], { encoding: 'utf8' }).trim().split(/\r?\n/).at(-1), /^nfs4?$/, 'Local manual mana evidence requires mounted NFS');
}
assert.equal(await realpath(execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: source, encoding: 'utf8' }).trim()), await realpath(source), 'Source root must match the Git inventory');
const runtime = await mkdtemp(path.join(tmpdir(), 'mtg-manual-mana-browser-run-'));
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
  const response = await fetch(`${api}/fixture/manual-mana${route}`, { method, headers: { 'X-Mana-Fixture': token }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Fixture ${route}: ${response.status} ${await response.text()}`);
  return response.json();
}
async function ready(url, child, owned = false) {
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, `Owned service exited: ${url}`);
    try {
      const response = await fetch(url, { headers: owned ? { 'X-Mana-Fixture': token } : {}, signal: AbortSignal.timeout(1000) });
      if (response.ok) { if (owned) assert.equal((await response.json()).source_root, runtime); return; }
    } catch { /* Cold startup only, bounded by deadline. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Owned service startup timeout: ${url}`);
}
function startBackend() {
  backend = start('backend', python, ['-m', 'uvicorn', 'tests.manual_mana_fixture_server:app', '--host', '127.0.0.1', '--port', String(ports.backend)], path.join(runtime, 'backend'), {
    MTG_MANA_FIXTURE_ROOT: runtime, MTG_MANA_FIXTURE_TOKEN: token,
  });
  return ready(`${api}/fixture/manual-mana/status`, backend, true);
}
async function restartBackend() {
  const previous = (await fixtureRequest('/status')).pid;
  await stop(backend);
  await startBackend();
  assert.notEqual((await fixtureRequest('/status')).pid, previous, 'Must restart a real backend process');
}

try {
  const gitFiles = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', 'backend', 'frontend'], { cwd: source, encoding: 'utf8' }).split('\0').filter(Boolean);
  const files = [...new Set([...gitFiles, 'frontend/tests/manual_mana_fixture_server.py', 'frontend/tests/browser-manual-mana.mjs'])]
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
  await writeFile(path.join(runtime, '.mana-browser-owned'), token);
  await copyFile(path.join(runtime, 'frontend/tests/manual_mana_fixture_server.py'), path.join(runtime, 'backend/tests/manual_mana_fixture_server.py'));
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

  for (const seat of [1, 2]) for (const scenario of scenarios) {
    const fixture = await fixtureRequest(`?seat=${seat}&scenario=${scenario}`, 'POST');
    const id = fixture.match.id;
    const label = `${seat}-${scenario}`;
    const browser = await openBrowser(`${frontend}/`);
    const {evaluate, waitFor, reload, command} = browser;
    const selector = `[data-mana-source="${fixture.source_id}"][data-mana-index="${fixture.ability_index}"]`;
    const getAudit = () => fixtureRequest(`/${id}/audit`);
    const getState = () => fetch(`${api}/matches/${id}`).then(response => response.json());
    async function loaded() {
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('[role=alert]')");
    }
    async function checkpoint(stage) {
      const audit = await getAudit();
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.json`), JSON.stringify(audit, null, 2));
      const screenshot = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true});
      await writeFile(path.join(runtime, `evidence/${label}-${stage}.png`), Buffer.from(screenshot.data, 'base64'));
      return audit;
    }
    async function select(css, value) {
      await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(css)});if(!e || e.matches(':disabled')) throw new Error('Unavailable select');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,${JSON.stringify(String(value))});e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    }
    async function restore() {
      const before = await getAudit();
      assert.equal((await fixtureRequest(`/${id}/restore`, 'POST')).snapshot_sha256, before.snapshot_sha256);
      await reload(); await loaded();
      assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
    }
    try {
      await command('Emulation.setDeviceMetricsOverride', {width: seat === 2 ? 430 : 1440, height: 1000, deviceScaleFactor: 1, mobile: seat === 2});
      await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload(); await loaded();
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).closest('details').open=true`);
      const before = await checkpoint('before');
      const payload = await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`).then(response => response.json());
      const move = payload.moves.find(m => m.type === 'activate_mana_ability' && m.card_id === fixture.source_id && m.ability_index === fixture.ability_index);
      assert.ok(move.activation_costs && Array.isArray(move.hybrid_symbols));
      assert.ok(!JSON.stringify(payload).includes(fixture.foreign_hand_id));
      assert.ok(!JSON.stringify(move.activation_costs).includes(fixture.foreign_creature_id));
      for (const symbol of move.hybrid_symbols) {
        assert.ok(Array.isArray(symbol.choices)); assert.equal(symbol.options, undefined);
      }
      await writeFile(path.join(runtime, `evidence/${label}-public-legal-moves.json`), JSON.stringify(payload, null, 2));
      assert.equal((await getAudit()).snapshot_sha256, before.snapshot_sha256);
      assert.equal(await evaluate(`document.body.innerHTML.includes(${JSON.stringify(fixture.foreign_hand_id)})`), false);
      const invalid = {type:'activate_mana_ability',card_id:fixture.source_id,ability_index:fixture.ability_index,color:fixture.output.color,output_bundle:fixture.output.output_bundle};
      if (scenario === 'tower') invalid.payment_choices={sacrifice_card_ids:[fixture.foreign_creature_id]};
      else if (scenario === 'witch') invalid.payment_choices={discard_card_ids:[fixture.foreign_hand_id]};
      else if (scenario !== 'plain') invalid.color='C';
      else invalid.output_bundle={U:2};
      const rejection = await fetch(`${api}/matches/${id}/action`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({player_id:seat,action:invalid})});
      assert.equal(rejection.status,422);
      assert.equal((await getAudit()).snapshot_sha256,before.snapshot_sha256);
      await restore();
      if (seat === 2 && scenario === 'witch') {
        const old=(await getAudit()).snapshot_sha256;
        await restartBackend(); assert.equal((await getAudit()).snapshot_sha256,old);
        await reload(); await loaded();
      }
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).closest('details').open=true`);
      if (shortcuts) {
        const landPreset = scenario === 'land-preset' || scenario === 'mixed-sphere-preset';
        const css = landPreset ? '.land-members button' : `[data-card-id="${fixture.source_id}"] button`;
        if (landPreset) await evaluate("document.querySelector('.land-members').open=true");
        const label = await evaluate(`document.querySelector(${JSON.stringify(css)}).textContent`);
        if (scenario !== 'land-preset') assert.match(label,/1 U \+ 1 G/,'Preset displays the entire mandatory BASE vector in WUBRGC order');
        await waitFor(`!document.querySelector(${JSON.stringify(css)}).matches(':disabled')`);
        await evaluate(`document.querySelector(${JSON.stringify(css)}).click()`);
      } else if (scenario !== 'plain') {
        assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector+' fieldset button')}).matches(':disabled')`), true);
        const index = move.output_options.findIndex(o=>o.color===fixture.output.color && JSON.stringify(o.output_bundle)===JSON.stringify(fixture.output.output_bundle));
        assert.ok(index>=0);
        await select(`${selector} select[aria-label^="Base mana output"]`,index);
        if (move.hybrid_symbols.length) {
          assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector+' fieldset button')}).matches(':disabled')`), true,'No default branch, including the only affordable branch');
          await select(`${selector} select[aria-label^="Mana hybrid symbol"]`,fixture.branch);
        }
        if (fixture.selected_id) {
          assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector+' fieldset button')}).matches(':disabled')`),true,'Resource remains unselected');
          await evaluate(`(() => {const box=[...document.querySelectorAll(${JSON.stringify(selector+' input[type=checkbox]')})].find(e=>e.getAttribute('aria-label').includes(${JSON.stringify(fixture.selected_id)}));if(!box || box.matches(':disabled'))throw new Error('Unavailable own-card resource');box.click();})()`);
        }
        assert.equal((await getAudit()).snapshot_sha256,before.snapshot_sha256,'Draft selections cannot mutate backend');
        await waitFor(`!document.querySelector(${JSON.stringify(selector+' fieldset button')}).matches(':disabled')`);
        await evaluate(`document.querySelector(${JSON.stringify(selector+' fieldset button')}).click()`);
      } else {
        await evaluate(`document.querySelector(${JSON.stringify(selector+' button')}).click()`);
      }
      await waitForApiState(`${api}/matches/${id}`,s=>s.revision>before.revision);
      await loaded();
      const paid=await checkpoint('paid');
      const pool=Object.fromEntries(Object.entries(paid.snapshot.players[String(seat)].mana_pool).filter(([,n])=>n>0));
      assert.deepEqual(pool,fixture.expected_pool);
      assert.equal(paid.snapshot.cards[fixture.source_id].tapped,true);
      if(fixture.selected_id) {
        assert.equal(paid.snapshot.cards[fixture.selected_id].zone,'graveyard');
        assert.notEqual(paid.snapshot.cards[fixture.unselected_id].zone,'graveyard');
      }
      assert.equal(paid.snapshot.stack.length,0);
      await restore();
      const actions=await fixtureRequest(`/actions?match_id=${id}`);
      assert.equal(actions.filter(a=>a.status===200).length,1);
      const submitted=actions.find(a=>a.status===200).body.action;
      if(scenario==='plain' || scenario==='land-preset') assert.equal(submitted.output_bundle,undefined,'Legacy plain action stays omitted-bundle');
      else assert.deepEqual(submitted.output_bundle,fixture.output.output_bundle);
      assert.equal(submitted.type,scenario==='land-preset'?'tap_land_for_mana':'activate_mana_ability');
      if(move.hybrid_symbols.length)assert.deepEqual(submitted.hybrid_choices,[fixture.branch]);
      if(fixture.selected_id) assert.deepEqual(submitted.payment_choices[scenario==='witch'?'discard_card_ids':'sacrifice_card_ids'],[fixture.selected_id]);
      requests.push(...actions);results.push({seat,scenario,source_id:fixture.source_id,public_move:move,submitted,pool,restored:true});
      console.log(`PASS ${label}: actual App explicit payment/base choices, checked HTTP, private view and restore`);
    } catch(error) {
      await checkpoint('failure').catch(()=>{});
      await writeFile(path.join(runtime,`evidence/${label}-failure-body.txt`),await evaluate('document.body.innerText').catch(()=> 'Browser context unavailable'));
      throw error;
    } finally {await browser.close();}
  }
  assert.equal(results.length,expectedCases);
  success = true;
} catch (error) { failure = error; console.error(error.stack); }
finally {
  for (const child of [...children].reverse()) await stop(child);
  await writeFile(path.join(runtime, 'results.json'), JSON.stringify({ success, expected_cases: expectedCases, scope: shortcuts ? 'shortcut-audit6' : 'manual-mana14', elapsed_ms: Date.now()-started, results, requests, ports,
    processes: children.map(child => ({ label: child.label, pid: child.pid, exit_code: child.exitCode, signal: child.signalCode })),
    failure: failure?.stack, fixture_claim: 'Explicit canonical mana positions; no natural historical game claim.' }, null, 2));
  const tar = path.join(archive, 'private/runtime-evidence.tar.gz');
  execFileSync('tar', ['--exclude=./profile', '--exclude=./frontend/node_modules', '--exclude=./vite-cache', '--exclude=*/__pycache__', '--exclude=*/image_cache', '--exclude=./.mana-browser-owned', '-czf', tar, '-C', runtime, '.']);
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
