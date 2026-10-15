import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import childProcess from 'node:child_process';
import fs from 'node:fs';
import fsPromises from 'node:fs/promises';
import {syncBuiltinESMExports} from 'node:module';
import {EventEmitter} from 'node:events';
import {PassThrough} from 'node:stream';

const moduleURL = new URL('./browser-vendor-preflight.mjs', import.meta.url);
const implementation = await import(moduleURL).catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND' && error.url === moduleURL.href) return {};
  throw error;
});
const api = name => {
  assert.equal(typeof implementation[name], 'function', `${name} must be implemented`);
  return implementation[name];
};
const inputs = vendor => ({
  MTG_BROWSER_VENDOR: vendor,
  MTG_CHROME: vendor === 'chrome' ? '/opt/google/chrome/chrome' : '/opt/brave.com/brave/brave',
  MTG_BROWSER_NO_SANDBOX: '0',
});
const identity = {platform: 'linux', uid: 1000};
const config = vendor => api('validateVendorInputs')(inputs(vendor), identity);
const regular = {isFile: () => true, uid: 0, gid: 0, nlink: 1, mode: 0o100755};
const helper = {...regular, mode: 0o104755};
const sandbox = () => ({rows: [
  ['Layer 1 Sandbox', 'Namespace'], ['PID namespaces', 'Yes'],
  ['Network namespaces', 'Yes'], ['Seccomp-BPF sandbox', 'Yes'],
], evaluation: 'You are adequately sandboxed.'});

test('installation diagnostics contain only actual stat operands and the fixed path', () => {
  const info = {...regular, isDirectory: () => false, isSymbolicLink: () => false, privateValue: 'PRIVATE'};
  assert.deepEqual(api('describeInstalledPath')('/opt/google/chrome/chrome', info), {
    path: '/opt/google/chrome/chrome', uid: 0, gid: 0, mode: '755', links: 1,
    regular_file: true, directory: false, symlink: false,
  });
});

test('explicit Chrome and Brave contracts are independent and preserve caller input', () => {
  for (const vendor of ['chrome', 'brave']) {
    const env = Object.freeze(inputs(vendor));
    const actual = api('validateVendorInputs')(env, {...identity, selectedBrowser: env.MTG_CHROME});
    assert.equal(actual.vendor, vendor);
    assert.equal(actual.binary, env.MTG_CHROME);
    assert.equal(actual.packageName, vendor === 'chrome' ? 'google-chrome-stable' : 'brave-browser');
    assert.equal(actual.helper, env.MTG_CHROME.replace(/[^/]+$/, 'chrome-sandbox'));
    assert.equal(Object.isFrozen(actual), true);
    assert.deepEqual(env, inputs(vendor));
  }
});

test('vendor, selected executable, path and sandbox mode must match exactly', () => {
  const validate = api('validateVendorInputs');
  for (const patch of [
    {MTG_BROWSER_VENDOR: undefined}, {MTG_BROWSER_VENDOR: 'chromium'},
    {MTG_BROWSER_VENDOR: 'Chrome'}, {MTG_CHROME: '/usr/bin/google-chrome'},
    {MTG_CHROME: '/opt/google/chrome/../chrome/chrome'}, {MTG_CHROME: '/opt/google/chrome/chrome\n'},
    {MTG_CHROME: '/opt/brave.com/brave/brave'}, {MTG_BROWSER_NO_SANDBOX: undefined},
    {MTG_BROWSER_NO_SANDBOX: '1'}, {MTG_BROWSER_NO_SANDBOX: 0},
  ]) assert.throws(() => validate({...inputs('chrome'), ...patch}, identity), /VENDOR_INPUTS/);
  assert.throws(() => validate(inputs('chrome'), {...identity, selectedBrowser: '/opt/brave.com/brave/brave'}), /VENDOR_INPUTS/);
});

test('Linux nonroot is mandatory, without coercion', () => {
  for (const bad of [{platform: 'darwin', uid: 1000}, {platform: 'linux', uid: 0},
    {platform: 'linux', uid: '1000'}, {platform: 'linux', uid: NaN}]) {
    assert.throws(() => api('validateVendorInputs')(inputs('chrome'), bad), /VENDOR_INPUTS/);
  }
});

test('vendor identity is a literal string, never a coercible object', () => {
  assert.throws(() => api('validateVendorInputs')({...inputs('chrome'), MTG_BROWSER_VENDOR: Object('chrome')}, identity), /VENDOR_INPUTS/);
  assert.throws(() => api('parseVendorVersion')('unknown', 'Brave Browser 155.1.97.57\n'), /VENDOR_VERSION/);
});

test('ambient loader, wrapper, sandbox and passive-trace overrides are rejected', () => {
  for (const key of ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'CHROME_DEVEL_SANDBOX',
    'CHROMIUM_FLAGS', 'CHROME_WRAPPER', 'CHROME_FLAGS', 'MTG_PASSIVE_CDP_EVIDENCE']) {
    assert.throws(() => api('validateVendorInputs')({...inputs('chrome'), [key]: 'PRIVATE'}, identity), /VENDOR_INPUTS/);
  }
});

test('installed main ELF and root-installed setuid helper have strict ownership/modes', () => {
  assert.equal(api('validateInstalledFiles')(regular, helper), true);
  for (const bad of [{...regular, uid: 1000}, {...regular, gid: 1000}, {...regular, nlink: 2},
    {...regular, mode: 0o100777}, {...regular, mode: 0o104755}, {...regular, isFile: () => false}]) {
    assert.throws(() => api('validateInstalledFiles')(bad, helper), /VENDOR_INSTALLATION/);
  }
  for (const bad of [{...helper, uid: 1000}, {...helper, mode: 0o100755},
    {...helper, mode: 0o104777}, {...helper, nlink: 2}]) {
    assert.throws(() => api('validateInstalledFiles')(regular, bad), /VENDOR_INSTALLATION/);
  }
});

test('package ownership covers both exact files and installed status', () => {
  for (const vendor of ['chrome', 'brave']) {
    const c = config(vendor);
    const data = {installed: `${c.packageName}\tinstall ok installed\t155.0.1-1\tamd64\n`,
      ownership: `${c.packageName}: ${c.binary}\n${c.packageName}: ${c.helper}\n`};
    assert.deepEqual(api('validatePackageMetadata')(c, data), {name: c.packageName, version: '155.0.1-1', architecture: 'amd64'});
    for (const change of [{installed: data.installed.replace('installed', 'unpacked')},
      {ownership: `${c.packageName}: ${c.binary}\n`},
      {ownership: data.ownership.replaceAll(c.packageName, 'chromium')},
      {installed: data.installed.replace('155.0.1-1', 'PRIVATE://token')},
      {ownership: data.ownership + data.ownership}]) {
      assert.throws(() => api('validatePackageMetadata')(c, {...data, ...change}), /VENDOR_PACKAGE/);
    }
  }
});

test('actual version output must be finite numeric and vendor-specific', () => {
  assert.equal(api('parseVendorVersion')('chrome', 'Google Chrome 155.0.8059.79\n'), '155.0.8059.79');
  assert.equal(api('parseVendorVersion')('brave', 'Brave Browser 155.1.97.57\n'), '155.1.97.57');
  for (const value of ['Chromium 155.0.1.2', 'Google Chrome PRIVATE', 'Google Chrome 155.0.1.2\nPRIVATE']) {
    assert.throws(() => api('parseVendorVersion')('chrome', value), /VENDOR_VERSION/);
  }
});

test('runtime version is observed from the actual DevTools endpoint, not CLI text', () => {
  assert.deepEqual(api('parseDevToolsVersion')('Chrome/155.0.8059.79'), {product: 'Chrome', version: '155.0.8059.79'});
  assert.deepEqual(api('parseDevToolsVersion')('HeadlessChrome/155.0.8059.79'), {product: 'HeadlessChrome', version: '155.0.8059.79'});
  for (const bad of [undefined, 'Chrome/PRIVATE', 'Chrome/155.0.1.2\nPRIVATE', 'https://private/155.0.1.2']) {
    assert.throws(() => api('parseDevToolsVersion')(bad), /VENDOR_VERSION/);
  }
});

test('startup failure diagnostics classify messages without returning their text', () => {
  for (const [message, classification] of [
    ['Failed to move to new namespace: Operation not permitted', 'namespace-error'],
    ['No usable sandbox!', 'no-usable-sandbox'],
    ['error while loading shared libraries: libX.so', 'shared-library-error'],
    ['chrome_crashpad_handler: --database is required', 'crashpad-database-required'],
    ['Missing X server or $DISPLAY', 'display-error'],
    ['PRIVATE unknown message', 'unclassified'],
  ]) {
    const bytes = Buffer.from(message);
    const facts = api('startupStderrFacts')(bytes, bytes.length);
    assert.deepEqual(facts.classifications, [classification]);
    assert.equal(facts.total_bytes, bytes.length);
    assert.equal(facts.truncated, false);
    assert.match(facts.prefix_sha256, /^[a-f0-9]{64}$/);
    assert.equal(JSON.stringify(facts).includes(message), false);
  }
});

test('startup stderr capture is bounded and never publishes private paths or bytes', () => {
  const bytes = Buffer.from('PRIVATE:/home/private/'.repeat(2000));
  const facts = api('startupStderrFacts')(bytes, bytes.length);
  assert.equal(facts.captured_bytes, 8192);
  assert.equal(facts.truncated, true);
  assert.equal(JSON.stringify(facts).includes('PRIVATE'), false);
  assert.equal(JSON.stringify(facts).includes('/home/'), false);
});

test('direct process exit completes cleanup even when a descendant retains stderr', async () => {
  const child = new EventEmitter();
  child.stderr = new PassThrough();
  const observed = api('observeVendorChild')(child);
  child.stderr.write('No usable sandbox! PRIVATE');
  child.emit('exit', 132, 'SIGTRAP');
  let timer;
  const result = await Promise.race([observed.closed,
    new Promise(resolve => { timer = setTimeout(() => resolve('not-reaped'), 100); })]);
  clearTimeout(timer);
  assert.deepEqual(result, {code: 132, signal: 'SIGTRAP'});
  assert.equal(child.stderr.destroyed, true);
  assert.equal(observed.facts().stream_ended, false);
  assert.equal(observed.facts().pipe_destroyed_at_reap, true);
  assert.deepEqual(observed.facts().classifications, ['no-usable-sandbox']);
  assert.equal(JSON.stringify(observed.facts()).includes('PRIVATE'), false);
  const firstReaped = observed.facts();
  Object.defineProperty(child.stderr, 'readableEnded', {value: true});
  child.emit('close', 132, 'SIGTRAP');
  assert.deepEqual(observed.facts(), firstReaped, 'later pipe close must not rewrite the reap snapshot');
});

test('failed-spawn close without an exit event still resolves and releases its pipe', async () => {
  const child = new EventEmitter();
  child.stderr = new PassThrough();
  const observed = api('observeVendorChild')(child);
  child.emit('close', -2, null);
  assert.deepEqual(await observed.closed, {code: -2, signal: null});
  assert.equal(child.stderr.destroyed, true);
});

test('DevToolsActivePort accepts only one bounded numeric port and browser UUID path', () => {
  assert.equal(api('parseDevToolsActivePort')('32123\n/devtools/browser/12345678-1234-1234-1234-123456789abc\n').port, 32123);
  for (const value of ['0\n/devtools/browser/x', '65536\n/devtools/browser/x',
    '32123\nws://foreign/devtools/browser/12345678-1234-1234-1234-123456789abc',
    '32123\n/devtools/browser/12345678-1234-1234-1234-123456789abc\nPRIVATE', 'x'.repeat(513)]) {
    assert.throws(() => api('parseDevToolsActivePort')(value), /VENDOR_DEVTOOLS/);
  }
});

test('Chrome155 expected-renderer predicate accepts Namespace and SUID only with both layers', () => {
  for (const layer of ['Namespace', 'SUID']) {
    const row = sandbox(); row.rows[0][1] = layer;
    const result = api('parseSandboxStatus')(row);
    assert.equal(result.first_layer, layer);
    assert.equal(result.seccomp_bpf, true);
    assert.equal(result.actual_renderer_attestation, false);
    assert.equal(result.basis, 'browser-reported expected renderer sandbox status');
  }
});

test('sandbox missing/negative/ambiguous status and optimistic evaluation fail closed', () => {
  for (const index of [0, 1, 2, 3]) {
    const bad = sandbox(); bad.rows[index][1] = index === 0 ? 'None' : 'No';
    assert.throws(() => api('parseSandboxStatus')(bad), /VENDOR_SANDBOX/);
  }
  const missing = sandbox(); missing.rows.pop();
  const duplicate = sandbox(); duplicate.rows.push(duplicate.rows[0]);
  for (const bad of [missing, duplicate, {...sandbox(), evaluation: 'You are NOT adequately sandboxed.'}]) {
    assert.throws(() => api('parseSandboxStatus')(bad), /VENDOR_SANDBOX/);
  }
});

test('check-config executes the real CLI branch with child and filesystem operations barred', async t => {
  let attempts = 0;
  const forbidden = () => { attempts++; throw new Error('UNEXPECTED_NATIVE_OR_FILE_IO'); };
  for (const name of ['spawn', 'execFile']) t.mock.method(childProcess, name, forbidden);
  for (const name of ['lstat', 'stat', 'realpath', 'readFile', 'mkdtemp', 'mkdir', 'open']) t.mock.method(fsPromises, name, forbidden);
  t.mock.method(fs, 'createReadStream', forbidden);
  syncBuiltinESMExports();
  try {
    const result = await api('main')(['--check-config', inputs('chrome').MTG_CHROME], inputs('chrome'));
    assert.equal(result.mode, 'check-config');
    assert.equal(result.vendor, 'chrome');
    assert.equal(result.native_started, false);
    assert.equal(result.installation_verified, false);
    await assert.rejects(api('main')(['--check-config', '/usr/bin/chromium'], inputs('chrome')), /VENDOR_INPUTS/);
    assert.equal(attempts, 0);
  } finally { t.mock.restoreAll(); syncBuiltinESMExports(); }
});

test('imports cannot dispatch the CLI and native mode requires an explicit report argument', async () => {
  await assert.rejects(api('main')([], inputs('chrome')), /VENDOR_USAGE/);
  await assert.rejects(api('main')(['--report', '/tmp/a', 'extra'], inputs('chrome')), /VENDOR_USAGE/);
  const source = await readFile(moduleURL, 'utf8');
  assert.match(source, /import\.meta\.url\s*===\s*pathToFileURL\(process\.argv\[1\]\)\.href/);
  assert.equal(source.includes("'--no-sandbox'"), false);
});
