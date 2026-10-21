import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {test} from 'node:test';
import vm from 'node:vm';

// These tests read public source and evaluate only extracted launcher bodies.
// Every process, listener, /proc, DB and application edge below is inert.
const root = new URL('../../', import.meta.url);
const read = name => readFileSync(new URL(name, root));
const launcher = read('frontend/tests/release-owned/run-current-built-acceptance.mjs').toString();
const fixturePath = 'frontend/tests/release-owned/fixtures/';
const paidBytes = read(fixturePath + 'current-built-cohort.json');
const recoveryBytes = read(fixturePath + 'current-built-recovery-fixtures.json');
const paid = JSON.parse(paidBytes), recovery = JSON.parse(recoveryBytes);
const provenance = JSON.parse(read(fixturePath + 'provenance.json'));
const digest = value => createHash('sha256').update(value).digest('hex');
const plain = value => JSON.parse(JSON.stringify(value));

const expectedPaid = [
  ...[1, 2].flatMap(seat => ['creature', 'player'].flatMap(mode =>
    [0, 1].map(cold => `sunc-${seat}-${mode}-${cold}`))),
  ...[1, 2].flatMap(seat => [0, 1].flatMap(reverse =>
    [0, 1].map(cold => `brain-${seat}-${reverse}-${cold}`))),
  ...[1, 2].flatMap(seat => ['empty', 'one', 'two-reverse-click'].flatMap(pitch =>
    [0, 1].map(cold => `march-${seat}-${pitch}-${cold}`))),
  ...[1, 2].flatMap(seat => ['base', 'kicker_1', 'kicker_2', 'kicker_1_2']
    .map(choice => `pair-${seat}-${choice}`)),
  ...[1, 2].flatMap(seat => ['base', 'kicker'].map(choice => `single-${seat}-${choice}`)),
];
const expected50 = [...expectedPaid, 'recovery:lost-response', 'recovery:overlap-stale',
  'recovery:pending-start', 'origin:trusted', 'origin:hostile', 'origin:null',
  'origin:duplicate', 'natural:HH', 'natural:humanseat1-AI', 'natural:humanseat2-AI'];
const factoryArgs = ['-m', 'uvicorn', 'tests.firefox_body_cache_app:create_app', '--factory',
  '--host', '127.0.0.1', '--port', '18001'];
const chromeArgs = ['-m', 'uvicorn', 'tests.current_built_browser_server:app',
  '--host', '127.0.0.1', '--port', '18001'];

function functionText(name) {
  const found = launcher.match(new RegExp(`^(?:async )?function ${name}\\([^\\n]*\\) \\{\\n[\\s\\S]*?^\\}`, 'm'));
  assert.ok(found, `Launcher needs private ${name}(), not a guessed test implementation`);
  return found[0];
}
function subject(names, globals, declarations) {
  const context = vm.createContext({assert, path, digest, ...globals});
  new vm.Script(`${declarations}\n${names.map(functionText).join('\n')}\n` +
    `globalThis.subject = {${names.join(',')}};`, {filename: 'owned-launcher-functions.mjs'})
    .runInContext(context);
  return {context, methods: context.subject};
}
const shared = `
  const root='/owned/source', out='/owned/evidence/native-browser';
  const python='/pinned/venv/bin/python', deps='/pinned/node_modules';
  const chrome='/pinned/chrome', firefox='/pinned/firefox';
  const ports={backend:18001,frontend:18002,cdp:18003,hostile:18004};
  const db='/owned/runtime/sql/api.db', bodyCacheDirectory=out+'/firefox-body-cache';
  let backend=null, backendReady=false, shuttingDown=false, failure=null;
`;
const bindings = Object.freeze({run_nonce: '1'.repeat(32), source_binding: '2'.repeat(64),
  api_origin: 'http://127.0.0.1:18001', frontend_origin: 'http://127.0.0.1:18002'});

test('[static] exact public 40+2 input bytes join their historical source pins', () => {
  assert.equal(digest(paidBytes), '13a783a49e3e93de4b68b37cffb18e4bbbc6f2935fe3ad9c3013a0eba8d024ce');
  assert.equal(digest(recoveryBytes), '25743f919492d92e1fefcdf845a8775975350fb1db0b6d893758ca4159e0e7db');
  assert.equal(provenance.schema_version, 1);
  assert.equal(typeof provenance.schema_version, 'number');
  assert.equal(provenance.input_source_commit, 'd65791a54ba14c3de05b1b0defb66b8f3f7d4e52');
  assert.equal(provenance.runner_pins_sha256, '15007d7cc1930834beba36b6712db1d1443e1d2d3eeeb96e841c442a401619b1');
  assert.equal(provenance.public_inputs_only, true);
  for (const [name, bytes] of [['current-built-cohort.json', paidBytes],
    ['current-built-recovery-fixtures.json', recoveryBytes]]) {
    assert.equal(provenance.files[name].sha256, digest(bytes));
    assert.equal(provenance.files[name].bytes, bytes.length);
  }
});

test('[static] original fifty order is forty paid plus three recovery four origin three BO3', () => {
  assert.deepEqual(paid.map(row => row.id), expectedPaid);
  assert.deepEqual(recovery.map(row => row.id), ['recovery-lost-response', 'recovery-overlap-stale']);
  assert.equal(new Set([...paid, ...recovery].map(row => row.id)).size, 42);
  for (const row of [...paid, ...recovery]) {
    assert.ok(row.seat === 1 || row.seat === 2);
    assert.equal(typeof row.cold, 'boolean');
  }
  assert.deepEqual(provenance.original50_order, expected50);
  assert.equal(new Set(expected50).size, 50);
});

test('[static] original paid natural driver transport and cache programs remain exact', () => {
  const unchanged = {
    'frontend/tests/release-owned/browser-current-paid-acceptance.mjs': 'df0e8491163c649235664c534ed15481c0451a1eae0309c1dc4efc94e8ab8c43',
    'frontend/tests/release-owned/browser-native-human-bo3.mjs': '344b3922fd6e7d19aafd17a782775c09d95866ef3069444d10b321bdca237d5b',
    'frontend/tests/release-owned/browser-native-human-bo3-seat2.mjs': '0c9d0d8779070c44722590ea03901301573486cf3550319bceb867742d62bc9d',
    'frontend/tests/release-owned/browser-driver.mjs': 'f9fea24ab58823dfc5cca9f43f6b227c2846289c266cd86cded8a5d2543ecef2',
    'frontend/tests/browser-driver.mjs': 'a8c9893acbef01ae224f43488a4f6fd6ce68858bfc837db677dfd38d0ae70115',
    'frontend/tests/firefox-transport.mjs': '91642e527c8f694cf85036afcdc2a9bb438bacd782e2b1673180c96194b0e973',
    'backend/tests/firefox_body_cache_app.py': '1f090dba3f37b6d27df7dbe76554020880a43fc9e994b054fba5eefc66203cb7',
    'backend/tests/current_built_browser_server.py': '0550d53c8d754b98bc81e276de265b05323d2940457c2436dafa7a295ac04ff3',
  };
  for (const [name, sha] of Object.entries(unchanged)) assert.equal(digest(read(name)), sha, name);
});

test('[static] original work teardown total episode and action bounds stay intact', () => {
  for (const token of ['2250000 - (Date.now() - started)', '2400000 - (Date.now() - started)',
    'maxActionsPerEpisode: 6000', '1500000,\'Controlled40\'', '180000,\'Recovery3\'',
    '120000,\'Origin4\'', "mode === 'human_vs_human' ? 900000 : 1200000"]) {
    assert.ok(launcher.includes(token), token);
  }
  assert.match(launcher, /status\.episodes\.length === 3/);
  assert.match(launcher, /status\.paid\?\.length===40/);
  assert.match(launcher, /status\.recovery\?\.length===3/);
  assert.match(launcher, /status\.origins\?\.length===4/);
});

test('[static] real publisher is created before the first genuine factory start', () => {
  const publisher = launcher.search(/\benrollment\s*=\s*createEnrollment\s*\(/);
  const start = launcher.lastIndexOf('  await startBackend();');
  assert.ok(publisher >= 0, 'Missing genuine createEnrollment call in owned launcher');
  assert.ok(publisher < start, 'Publisher must exist before importing the real fixture');
  assert.match(functionText('startBackend'), /tests\.firefox_body_cache_app:create_app/);
  assert.match(functionText('startBackend'), /MTG_RELEASE_BODY_CACHE_ENROLLMENT/);
  const cache = read('backend/tests/firefox_body_cache_app.py').toString();
  assert.ok(cache.indexOf('broker._control()') < cache.indexOf('from tests.current_built_browser_server import app'));
});

test('[static] transport producer uses the current backend getter not a captured first PID', () => {
  assert.match(launcher, /producer\s*:\s*currentBackendIdentity\b/);
  assert.match(functionText('currentBackendIdentity'), /backend/);
});

test('[static] genuine BiDi readiness and once binding precede all application cases', () => {
  const ready = launcher.indexOf('await firefoxTransport.ready()');
  const bound = launcher.indexOf('configureFirefoxTransport(firefoxTransport)');
  const first = launcher.indexOf('status.paid=await deadline(');
  assert.ok(ready >= 0 && bound > ready && bound < first, 'Await real BiDi readiness before once binding/cases');
  assert.match(launcher, /controller\s*:\s*enrollment\b/);
  assert.match(launcher, /createFirefoxTransport\s*\(/);
});

test('[static] native ACK and realm contracts remain in the actual unchanged transport', () => {
  const transport = read('frontend/tests/firefox-transport.mjs').toString();
  assert.match(transport, /receipt\?\.acceptReply\(message\)/);
  assert.match(transport, /session\.capabilities\?\.browserName!==\x27firefox\x27/);
  assert.match(transport, /browserVersion\?\.startsWith\(\x27158\.\x27\)/);
  assert.match(transport, /script\.realmCreated/);
  assert.match(transport, /publish\(true\);armed\.activated=true/);
});

function admission(vendor) {
  const loaded = subject(['authorizeChild'], {strictNative: vendor === 'firefox',
    roleCounts: new Map(), authorizedFuserPaths: [], viteConfig: '/owned/vite.mjs'},
    shared + `const browserVendor=${JSON.stringify(vendor)};`);
  // Real argv and the source's expected argv must inhabit the same VM realm.
  return {methods: {authorizeChild(label, executable, args, cwd) {
    loaded.context.argvJSON = JSON.stringify(args);
    const argv = vm.runInContext('JSON.parse(argvJSON)', loaded.context);
    return loaded.methods.authorizeChild(label, executable, argv, cwd);
  }}};
}
test('[protocol] Firefox backend admission requires the exact real factory argv', () => {
  admission('firefox').methods.authorizeChild('backend', '/pinned/venv/bin/python', factoryArgs, '/owned/source/backend');
});
test('[protocol] unchanged Chrome direct-fixture backend admission remains available', () => {
  admission('chrome').methods.authorizeChild('backend', '/pinned/venv/bin/python', chromeArgs, '/owned/source/backend');
});
test('[protocol] foreign or augmented factory argv is rejected before child creation', () => {
  for (const args of [[...factoryArgs, '--reload'], factoryArgs.map(arg =>
    arg === 'tests.firefox_body_cache_app:create_app' ? 'foreign.module:app' : arg)]) {
    assert.throws(() => admission('firefox').methods.authorizeChild('backend', '/pinned/venv/bin/python', args, '/owned/source/backend'));
  }
});

function backendSubject(names = ['startBackend'], readyError) {
  const events = [], children = [];
  let next = 700;
  const globals = {
    enrollment: {bindings},
    start(label, executable, args, cwd, env) {
      const child = {pid: ++next, label, exitCode: null, signalCode: null};
      children.push(child); events.push({kind: 'start', executable, args, cwd, env}); return child;
    },
    async readFile(file) {
      events.push({kind: 'read', file});
      if (file.startsWith('/proc/')) return '701 (python) ' + [...Array(19).fill('0'), String(next * 10)].join(' ');
      return 'same closed public DB bytes';
    },
    async ready() { if (readyError) throw readyError; },
    async storageReceipts() {
      return children.map(child => ({pid: child.pid, stage: 'ready', registered: true, ready: true,
        owner_fd: 4, admissions_open: true, backups: [{verified_by_successful_lifespan: true}]}));
    },
    async stop(child) { events.push({kind: 'stop', pid: child.pid}); child.exitCode = 0; },
    async checkFuser() { return {exit: 1, stdout: '', stderr: ''}; },
    async readLedger() { return {controller: {difficulties: {'1': 'master_plus'}}}; },
    async writeFile() {},
  };
  const loaded = subject(names, globals, shared + "const browserVendor='firefox';");
  return {...loaded, events, children};
}
test('[protocol] factory start forwards exact real-controller and source bindings', async () => {
  const s = backendSubject(); await s.methods.startBackend();
  const call = s.events.find(row => row.kind === 'start');
  assert.deepEqual(plain(call.args), factoryArgs);
  assert.equal(call.env.MTG_RELEASE_BODY_CACHE_ROOT, '/owned/evidence/native-browser/firefox-body-cache');
  assert.equal(call.env.MTG_RELEASE_BODY_CACHE_ENROLLMENT, call.env.MTG_RELEASE_BODY_CACHE_ROOT + '/enrollment.json');
  assert.equal(call.env.MTG_BROKER_RUN_NONCE, bindings.run_nonce);
  assert.equal(call.env.MTG_BROKER_SOURCE_BINDING, bindings.source_binding);
  assert.equal(call.env.MTG_BUILT_PAGE_ORIGIN, bindings.frontend_origin);
});
test('[protocol] partial backend startup retains the actual readiness error and registered child', async () => {
  const primary = new Error('inert factory readiness failure');
  const s = backendSubject(['startBackend'], primary);
  await assert.rejects(s.methods.startBackend(), error => error === primary);
  assert.equal(s.children.length, 1);
  assert.equal(vm.runInContext('backendReady', s.context), false);
});
test('[protocol] prior shutdown admission rejects a new backend before any child edge', async () => {
  const s = backendSubject(); vm.runInContext('shuttingDown=true', s.context);
  await assert.rejects(s.methods.startBackend()); assert.equal(s.children.length, 0);
});
test('[protocol] producer identity is unavailable before the actual backend exists', () => {
  const s = backendSubject(['currentBackendIdentity']);
  assert.throws(() => s.methods.currentBackendIdentity());
});
test('[protocol] genuine restart changes the getter identity without rewriting prior results', async () => {
  const s = backendSubject(['startBackend', 'restartBackend', 'currentBackendIdentity']);
  await s.methods.startBackend(); const first = s.methods.currentBackendIdentity();
  assert.deepEqual(plain(first), {pid: 701, start: '7010'});
  await s.methods.restartBackend('public-owned-match'); const second = s.methods.currentBackendIdentity();
  assert.deepEqual(plain(second), {pid: 702, start: '7020'});
  assert.deepEqual(plain(first), {pid: 701, start: '7010'});
  assert.ok(s.events.find(row => row.kind === 'stop' && row.pid === 701));
});
test('[protocol] a closed backend cannot be advertised as a current cache producer', async () => {
  const s = backendSubject(['startBackend', 'currentBackendIdentity']);
  await s.methods.startBackend(); s.children[0].exitCode = 0;
  assert.throws(() => s.methods.currentBackendIdentity());
});
test('[protocol] malformed PID or start identity is rejected rather than string-coerced', () => {
  const s = backendSubject(['currentBackendIdentity']);
  for (const value of [{pid: true, startTicks: 10}, {pid: 10, startTicks: true},
    {pid: 10, startTicks: 'not-native-start'}, {pid: 10, startTicks: 0}]) {
    s.context.invalid = {...value, exitCode: null, signalCode: null};
    vm.runInContext('backend=invalid', s.context);
    assert.throws(() => s.methods.currentBackendIdentity());
  }
});

async function phases({failAt} = {}) {
  const at = launcher.indexOf('  const assertAlive=()=>');
  const end = launcher.indexOf('\n  })()]);', at);
  assert.ok(at >= 0 && end > at, 'Keep the original bounded fifty-case orchestration');
  const events = []; let armed = null;
  const enrollment = {bindings, get isArmed() { return armed !== null; },
    async withEnrolledBodyEpisode(name, callback) {
      events.push('enable:' + name); armed = name;
      try { return await callback(); } finally { armed = null; events.push('disable:' + name); }
    }};
  async function part(name, size) {
    events.push(name); assert.equal(armed, null, 'First47 must be capture-disabled');
    if (failAt === name) throw failAt;
    return Array.from({length: size}, (_, i) => ({id: i}));
  }
  const context = vm.createContext({assert, path, enrollment, cohort: paid, api: bindings.api_origin,
    frontend: bindings.frontend_origin, out: '/owned/evidence/native-browser', fixtureToken: 'public-test-token',
    failure: null, backend: {exitCode: null}, ports: {hostile: 18004}, status: {episodes: []},
    deadline: async promise => await promise,
    runPaidBuiltCases: () => part('paid40', 40), runBuiltRecovery: () => part('recovery3', 3),
    runBuiltOrigins: () => part('origins4', 4), readFile: async () => '{"metadata":{"id":"public-match"}}',
    restartBackend: async () => ({controller: {difficulties: {'1': 'master_plus'}}}),
    async runNativeHumanBo3({mode}) {
      assert.equal(armed, mode, 'Actual original helper must run inside its enrollment window');
      events.push(mode); if (failAt === mode) throw failAt; return {mode};
    },
    async runNativeHumanBo3Seat2() {
      assert.equal(armed, 'player_vs_ai-seat2'); events.push('player_vs_ai-seat2'); return {mode: 'seat2'};
    },
  });
  let error;
  try { await new vm.Script(`(async()=>{${launcher.slice(at, end)};return status;})()`)
    .runInContext(context); } catch (caught) { error = caught; }
  return {events, error, armed, status: context.status};
}
test('[protocol] first47 stay disabled and all three original BO3 calls have exact windows', async () => {
  const result = await phases(); assert.equal(result.error, undefined);
  assert.deepEqual(result.events, ['paid40', 'recovery3', 'origins4',
    'enable:human_vs_human', 'human_vs_human', 'disable:human_vs_human',
    'enable:player_vs_ai', 'player_vs_ai', 'disable:player_vs_ai',
    'enable:player_vs_ai-seat2', 'player_vs_ai-seat2', 'disable:player_vs_ai-seat2']);
  assert.equal(result.status.episodes.length, 3); assert.equal(result.armed, null);
});
test('[protocol] failed original BO3 disables its window and never starts a later episode', async () => {
  const result = await phases({failAt: 'human_vs_human'});
  assert.equal(result.error, 'human_vs_human'); assert.equal(result.armed, null);
  assert.deepEqual(result.events.slice(3), ['enable:human_vs_human', 'human_vs_human', 'disable:human_vs_human']);
});
test('[protocol] failed original origin control never arms or starts natural play', async () => {
  const result = await phases({failAt: 'origins4'});
  assert.equal(result.error, 'origins4');
  assert.deepEqual(result.events, ['paid40', 'recovery3', 'origins4']); assert.equal(result.armed, null);
});

async function teardown({partial = false, primary = null, transportError, controllerError} = {}) {
  const at = launcher.lastIndexOf('\nfinally {\n  shuttingDown = true;');
  const end = launcher.lastIndexOf('\nif (failure)');
  assert.ok(at >= 0 && end > at, 'Retain the bounded launcher finally path');
  const tail = launcher.slice(at + '\nfinally {'.length, end);
  const body = tail.slice(0, tail.lastIndexOf('}'));
  const events = [], saved = [];
  const context = vm.createContext({assert, path, failure: primary, shuttingDown: false,
    watchdog: null, budgetWatch: null, hardDeadline: null, hostileServer: null,
    allocations: new Set(), children: [{label: 'backend', pid: 701, exitCode: 0, signalCode: null}],
    firefoxTransport: partial ? undefined : {async close() { events.push('transport'); if (transportError) throw transportError; }},
    enrollment: {close() { events.push('publisher'); if (controllerError) throw controllerError; }},
    clearTimeout() {}, clearInterval() {},
    async stop(child) { events.push('stop:' + child.label); },
    async closedReceipt() { events.push('closed-receipt'); },
    deadline: async promise => await promise,
    async writeFile(file, data) { saved.push({file, data}); },
    console: {log() {}, error() {}}, process: {kill() { assert.fail('Unexpected signal'); },
      exit() { assert.fail('Unexpected early exit'); }},
    status: {episodes: [1, 2, 3], paid: Array(40), recovery: Array(3), origins: Array(4)},
    started: Date.now(), closureProven: false, out: '/owned/evidence/native-browser'});
  await new vm.Script(`(async()=>{${body};return status;})()`).runInContext(context);
  return {events, saved, failure: context.failure, status: context.status};
}
test('[protocol] successful teardown closes native transport backend cache then publisher', async () => {
  const result = await teardown();
  assert.ok(result.events.indexOf('transport') >= 0);
  assert.ok(result.events.indexOf('transport') < result.events.indexOf('stop:backend'));
  assert.ok(result.events.indexOf('stop:backend') < result.events.indexOf('publisher'));
  assert.equal(result.status.success, true);
});
test('[protocol] startup failure before transport construction still retires its real publisher', async () => {
  const primary = new Error('inert startup failure');
  const result = await teardown({partial: true, primary});
  assert.ok(result.events.includes('publisher')); assert.ok(result.events.includes('stop:backend'));
  assert.equal(result.failure, primary); assert.equal(result.status.success, false);
});
test('[protocol] transport teardown failure cannot mask primary failure or bypass remaining cleanup', async () => {
  const primary = new Error('inert primary'), cleanup = new Error('inert transport close');
  const result = await teardown({primary, transportError: cleanup});
  assert.equal(result.failure, primary);
  assert.ok(result.events.includes('transport') && result.events.includes('publisher'));
  assert.ok(result.events.includes('stop:backend')); assert.equal(result.status.success, false);
});
test('[protocol] publisher cleanup failure prevents a successful application receipt', async () => {
  const cleanup = new Error('inert publisher close'); const result = await teardown({controllerError: cleanup});
  assert.equal(result.failure, cleanup); assert.equal(result.status.success, false);
});

async function closure({unknownOwned = false, unknownForeign = false} = {}) {
  const saved = [];
  const children = unknownOwned ? [{label: 'backend', pid: 701, exitCode: 0, signalCode: null}] : [];
  const eacces = () => Object.assign(new Error('inert unreadable identity'), {code: 'EACCES'});
  const globals = {children, unknownOwned, unknownForeign, eacces,
    allocations: new Set(), ports: {}, process: {pid: 100},
    createServer() { return {once() { return this; }, listen(_port, _host, done) { done(); }, close(done) { done(); }}; },
    async realpath() { throw eacces(); }, async readlink() { assert.fail('No real FD read'); },
    async stat() { assert.fail('No real filesystem stat'); },
    async checkFuser() { return {exit: 1, stdout: '', stderr: ''}; },
    async writeFile(file, data) { saved.push({file, data}); },
    async readFile() { return JSON.stringify({denials: [], jobs: {}, ordinary_pool_disposed: true,
      zero_checkouts: true, workers_empty: true, shutdown_admission_closed: true,
      no_emergency_dispose: true, canaries: [1, 2, 3], shutdown_complete: true}); },
    async checkPins() {}, async outputBudget() { return {}; },
  };
  const loaded = subject(['closedReceipt'], globals, shared);
  // Make protocol containers in the subject's existing realm, as native I/O does.
  vm.runInContext(`
    globalThis.storageInventory = async function () {
      return {allowed: [], actual: [], receipts: Array.from(children, () => ({}))};
    };
    globalThis.readdir = async function (name) {
      if (name === '/proc') return unknownOwned ? ['701'] : unknownForeign ? ['999'] : [];
      if (name === '/proc/701/fd' || name === '/proc/999/fd') throw eacces();
      if (name === '/owned/evidence/native-browser') return Array.from(children, child => 'server-closure-' + child.pid + '.json');
      return [];
    };
  `, loaded.context);
  let error; try { await loaded.methods.closedReceipt(); } catch (caught) { error = caught; }
  return {error, saved};
}
test('[protocol] known clean owned closure still succeeds without a global host-quiet claim', async () => {
  const result = await closure(); assert.equal(result.error, undefined);
  assert.ok(result.saved.some(row => row.file.endsWith('/CLOSURE.json')));
});
test('[protocol] unreadable owned child identity remains UNKNOWN rather than clean closure', async () => {
  const result = await closure({unknownOwned: true});
  assert.ok(result.error, 'Owned identity unreadable must prevent a clean closure receipt');
});
test('[protocol] unrelated unreadable process stays a visibility limit not invented owned leakage', async () => {
  const result = await closure({unknownForeign: true}); assert.equal(result.error, undefined);
  const receipt = JSON.parse(result.saved.find(row => row.file.endsWith('/CLOSURE.json')).data);
  assert.ok(receipt.inaccessible.includes(999));
});
