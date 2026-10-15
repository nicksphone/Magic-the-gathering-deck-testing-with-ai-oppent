import assert from 'node:assert/strict';
import {spawn, execFile} from 'node:child_process';
import {createHash, randomBytes} from 'node:crypto';
import {constants, createReadStream} from 'node:fs';
import {lstat, stat, realpath, readFile, mkdtemp, mkdir, open} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {promisify} from 'node:util';

const vendors = Object.freeze({
  chrome: {binary: '/opt/google/chrome/chrome', packageName: 'google-chrome-stable'},
  brave: {binary: '/opt/brave.com/brave/brave', packageName: 'brave-browser'},
});
const rejectedEnvironment = ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'LD_DEBUG',
  'CHROME_DEVEL_SANDBOX', 'CHROMIUM_FLAGS', 'CHROME_WRAPPER', 'CHROME_FLAGS', 'MTG_PASSIVE_CDP_EVIDENCE'];
const fail = code => { throw new Error(code); };

export function describeInstalledPath(file, info) {
  return {path: file, uid: info.uid, gid: info.gid, mode: (info.mode & 0o7777).toString(8), links: info.nlink,
    regular_file: info.isFile(), directory: info.isDirectory(), symlink: info.isSymbolicLink()};
}

export function validateVendorInputs(env, {platform = process.platform, uid = process.getuid?.(),
  selectedBrowser = env.MTG_CHROME} = {}) {
  const selected = typeof env.MTG_BROWSER_VENDOR === 'string'
    && Object.hasOwn(vendors, env.MTG_BROWSER_VENDOR) && vendors[env.MTG_BROWSER_VENDOR];
  if (platform !== 'linux' || !Number.isSafeInteger(uid) || uid <= 0 || !selected
      || env.MTG_BROWSER_NO_SANDBOX !== '0' || env.MTG_CHROME !== selected.binary
      || selectedBrowser !== selected.binary || rejectedEnvironment.some(key => Boolean(env[key]))) fail('VENDOR_INPUTS');
  return Object.freeze({vendor: env.MTG_BROWSER_VENDOR, ...selected,
    helper: path.join(path.dirname(selected.binary), 'chrome-sandbox')});
}

export function validateInstalledFiles(binary, helper) {
  const owned = info => info.isFile() && info.uid === 0 && info.gid === 0 && info.nlink === 1;
  if (!owned(binary) || (binary.mode & 0o7022) !== 0 || (binary.mode & 0o111) !== 0o111
      || !owned(helper) || (helper.mode & 0o7777) !== 0o4755) fail('VENDOR_INSTALLATION');
  return true;
}

export function validatePackageMetadata(config, {installed, ownership}) {
  if (typeof installed !== 'string' || typeof ownership !== 'string'
      || installed.length > 4096 || ownership.length > 4096) fail('VENDOR_PACKAGE');
  const fields = installed.trimEnd().split('\t');
  if (fields.length !== 4 || fields[0] !== config.packageName || fields[1] !== 'install ok installed'
      || !/^[0-9][0-9a-z.+:~\-]{0,79}$/.test(fields[2])
      || !['amd64', 'arm64'].includes(fields[3])) fail('VENDOR_PACKAGE');
  const lines = ownership.trimEnd().split('\n');
  const expected = [config.binary, config.helper];
  if (lines.length !== 2 || !expected.every(file => lines.filter(line =>
    line === `${config.packageName}: ${file}` || line === `${config.packageName}:${fields[3]}: ${file}`).length === 1)) fail('VENDOR_PACKAGE');
  return {name: fields[0], version: fields[2], architecture: fields[3]};
}

export function parseVendorVersion(vendor, text) {
  if (!['chrome', 'brave'].includes(vendor)) fail('VENDOR_VERSION');
  const label = vendor === 'chrome' ? 'Google Chrome' : 'Brave Browser';
  const match = typeof text === 'string' && text.match(new RegExp(`^${label} ([0-9]+(?:\\.[0-9]+){2,3})\\n?$`));
  if (!match || text.length > 128) fail('VENDOR_VERSION');
  return match[1];
}

export function parseDevToolsVersion(text) {
  const match = typeof text === 'string' && text.length <= 128
    && text.match(/^([A-Za-z][A-Za-z .-]{0,31})\/([0-9]+(?:\.[0-9]+){2,3})$/);
  if (!match) fail('VENDOR_VERSION');
  return {product: match[1], version: match[2]};
}

export function startupStderrFacts(prefix, totalBytes) {
  if (!Buffer.isBuffer(prefix) || !Number.isSafeInteger(totalBytes) || totalBytes < prefix.length) fail('VENDOR_STARTUP_REPORT');
  const captured = prefix.subarray(0, 8192), text = captured.toString('utf8');
  const classifications = [
    ['namespace-error', /Failed to move to new namespace/],
    ['no-usable-sandbox', /No usable sandbox/],
    ['shared-library-error', /error while loading shared libraries/],
    ['crashpad-database-required', /chrome_crashpad_handler: --database is required/],
    ['display-error', /Missing X server or \$DISPLAY/],
  ].filter(([, pattern]) => pattern.test(text)).map(([name]) => name);
  return {total_bytes: totalBytes, captured_bytes: captured.length, truncated: totalBytes > captured.length,
    prefix_sha256: createHash('sha256').update(captured).digest('hex'),
    classifications: classifications.length ? classifications : ['unclassified']};
}

export function observeVendorChild(child) {
  let prefix = Buffer.alloc(0), bytesSeen = 0, streamEnded = false, destroyedAtReap = false, readError = false;
  child.stderr?.on('data', bytes => {
    bytesSeen += bytes.length;
    if (prefix.length < 8192) prefix = Buffer.concat([prefix, bytes.subarray(0, 8192 - prefix.length)]);
  });
  child.stderr?.on('error', () => { readError = true; });
  const closed = new Promise(resolve => {
    let reaped = false;
    const finish = (code, signal) => {
      if (reaped) return;
      reaped = true;
      streamEnded = Boolean(child.stderr?.readableEnded);
      if (child.stderr && !child.stderr.destroyed) {
        destroyedAtReap = !streamEnded;
        child.stderr.destroy();
      }
      resolve({code, signal});
    };
    // Node's close waits for inherited pipes; exit already reaps the direct child.
    child.once('exit', finish);
    child.once('close', finish); // Failed spawn has close without exit.
  });
  return {closed, facts: () => ({...startupStderrFacts(prefix, bytesSeen), count_basis: 'observed pipe bytes',
    stream_ended: streamEnded, pipe_destroyed_at_reap: destroyedAtReap, read_error: readError})};
}

export function parseDevToolsActivePort(text) {
  const match = typeof text === 'string' && text.length <= 512
    && text.match(/^([1-9][0-9]{0,4})\n(\/devtools\/browser\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\n?$/);
  if (!match || Number(match[1]) > 65535) fail('VENDOR_DEVTOOLS');
  return {port: Number(match[1]), browserPath: match[2]};
}

export function parseSandboxStatus(value) {
  const required = ['Layer 1 Sandbox', 'PID namespaces', 'Network namespaces', 'Seccomp-BPF sandbox'];
  if (!value || !Array.isArray(value.rows) || value.rows.length > 32
      || value.evaluation !== 'You are adequately sandboxed.') fail('VENDOR_SANDBOX');
  const rows = required.map(label => value.rows.filter(row => Array.isArray(row) && row.length === 2 && row[0] === label));
  if (rows.some(matches => matches.length !== 1) || !['Namespace', 'SUID'].includes(rows[0][0][1])
      || rows.slice(1).some(matches => matches[0][1] !== 'Yes')) fail('VENDOR_SANDBOX');
  // Chrome155 SetSandboxStatusData uses GetRendererSandboxStatus: expected, not per-PID attestation.
  // https://raw.githubusercontent.com/chromium/chromium/155.0.8059.79/chrome/browser/ui/webui/sandbox/sandbox_internals_ui.cc
  return {first_layer: rows[0][0][1], pid_namespaces: true, network_namespaces: true, seccomp_bpf: true,
    basis: 'browser-reported expected renderer sandbox status', actual_renderer_attestation: false};
}

async function sha256(file) {
  const hash = createHash('sha256');
  for await (const bytes of createReadStream(file)) hash.update(bytes);
  return hash.digest('hex');
}

const metadataEnvironment = {PATH: '/usr/bin:/bin', LANG: 'C.UTF-8', LC_ALL: 'C.UTF-8'};
async function command(executable, args, env = metadataEnvironment) {
  const result = await promisify(execFile)(executable, args, {env, timeout: 5000, maxBuffer: 4096, encoding: 'utf8'});
  if (result.stderr !== '') fail('VENDOR_COMMAND');
  return result.stdout;
}

async function installedVendor(config, report) {
  report.installation = {ancestors: [], files: []};
  for (let directory = path.dirname(config.binary); directory !== '/'; directory = path.dirname(directory)) {
    const info = await lstat(directory);
    report.installation.ancestors.push(describeInstalledPath(directory, info));
    if (!info.isDirectory() || info.uid !== 0 || (info.mode & 0o022) || await realpath(directory) !== directory) fail('VENDOR_INSTALLATION');
  }
  for (const file of [config.binary, config.helper]) if (await realpath(file) !== file) fail('VENDOR_INSTALLATION');
  const binary = await lstat(config.binary), helper = await lstat(config.helper);
  report.installation.files.push(describeInstalledPath(config.binary, binary), describeInstalledPath(config.helper, helper));
  validateInstalledFiles(binary, helper);
  const fd = await open(config.binary, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const magic = Buffer.alloc(4);
    const {bytesRead} = await fd.read(magic, 0, 4, 0);
    if (bytesRead !== 4 || !magic.equals(Buffer.from([0x7f, 0x45, 0x4c, 0x46]))) fail('VENDOR_ELF');
  } finally { await fd.close(); }
  const pkg = validatePackageMetadata(config, {
    installed: await command('/usr/bin/dpkg-query', ['--show', '--showformat=${Package}\t${Status}\t${Version}\t${Architecture}\n', config.packageName]),
    ownership: await command('/usr/bin/dpkg-query', ['--search', config.binary, config.helper]),
  });
  return {package: pkg, binary_sha256: await sha256(config.binary), helper_sha256: await sha256(config.helper),
    dev: binary.dev, ino: binary.ino};
}

async function ownedReport(file) {
  if (!path.isAbsolute(file) || path.resolve(file) !== file) fail('VENDOR_REPORT_PATH');
  const directory = path.dirname(file), info = await lstat(directory);
  if (await realpath(directory) !== directory || !info.isDirectory() || info.uid !== process.getuid()
      || (info.mode & 0o777) !== 0o700) fail('VENDOR_REPORT_PATH');
  return open(file, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
}

async function nativeReport(config, reportFile, env) {
  const output = await ownedReport(reportFile);
  const report = {schema: 1, vendor: config.vendor, ok: false, sandbox_disabled: false,
    checks: {}, closure_scope: 'direct child only; enclosing systemd unit owns control-group cleanup'};
  let child, closed, page, error, observedChild;
  const priorOrigin = process.env.MTG_BROWSER_ORIGIN;
  const priorFrontend = process.env.MTG_FRONTEND_ORIGIN;
  try {
    const installed = await installedVendor(config, report);
    report.package = installed.package;
    report.binary = {path: config.binary, sha256: installed.binary_sha256};
    report.helper = {path: config.helper, sha256: installed.helper_sha256, root_owned_mode: '4755'};
    const profileRoot = await mkdtemp(path.join(path.dirname(reportFile), '.vendor-preflight-'));
    for (const name of ['home', 'tmp', 'config', 'cache', 'data', 'runtime']) await mkdir(path.join(profileRoot, name), {mode: 0o700});
    const childEnvironment = {...metadataEnvironment, HOME: path.join(profileRoot, 'home'),
      TMPDIR: path.join(profileRoot, 'tmp'), XDG_CONFIG_HOME: path.join(profileRoot, 'config'),
      XDG_CACHE_HOME: path.join(profileRoot, 'cache'), XDG_DATA_HOME: path.join(profileRoot, 'data'),
      XDG_RUNTIME_DIR: path.join(profileRoot, 'runtime')};
    const profile = path.join(profileRoot, 'profile');
    child = spawn(config.binary, ['--headless', '--no-first-run', '--no-default-browser-check',
      '--disable-background-networking', '--disable-dev-shm-usage', '--enable-automation', '--lang=en-US',
      `--user-data-dir=${profile}`, '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', 'about:blank'],
    {env: childEnvironment, stdio: ['ignore', 'ignore', 'pipe']});
    observedChild = observeVendorChild(child);
    let spawnError = false;
    let spawnErrno = null;
    child.on('error', cause => {
      spawnError = true;
      spawnErrno = ['ENOENT', 'EACCES', 'ENOEXEC', 'ENOMEM', 'EAGAIN'].includes(cause.code) ? cause.code : 'OTHER';
    });
    closed = observedChild.closed;
    const startupFailure = reason => {
      report.startup_failure = {reason, spawn_errno: spawnErrno, exit_code: child.exitCode, signal: child.signalCode};
      fail('VENDOR_BROWSER_START');
    };
    let endpoint;
    const deadline = Date.now() + 20000;
    while (!endpoint) {
      if (spawnError) startupFailure('spawn-error');
      if (child.exitCode !== null || child.signalCode !== null) startupFailure('exited');
      if (Date.now() >= deadline) startupFailure('deadline');
      try {
        const file = path.join(profile, 'DevToolsActivePort'), info = await lstat(file);
        if (!info.isFile() || info.isSymbolicLink() || info.size > 512 || info.uid !== process.getuid()) fail('VENDOR_DEVTOOLS');
        endpoint = parseDevToolsActivePort(await readFile(file, 'utf8'));
      } catch (missing) { if (missing.code !== 'ENOENT') throw missing; }
      if (!endpoint) await new Promise(resolve => setTimeout(resolve, 50));
    }
    if (Date.now() >= deadline) startupFailure('deadline');
    const actual = await stat(`/proc/${child.pid}/exe`);
    if (await realpath(`/proc/${child.pid}/exe`) !== config.binary || actual.dev !== installed.dev || actual.ino !== installed.ino
        || await sha256(`/proc/${child.pid}/exe`) !== installed.binary_sha256) fail('VENDOR_PROCESS_IDENTITY');
    const status = await readFile(`/proc/${child.pid}/status`, 'utf8');
    if (!status.match(/^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$/m)?.slice(1).every(uid => uid === String(process.getuid()))) fail('VENDOR_PROCESS_IDENTITY');
    const processStat = await readFile(`/proc/${child.pid}/stat`, 'utf8');
    const start = processStat.slice(processStat.lastIndexOf(')') + 2).split(/\s+/)[19];
    if (!/^[0-9]+$/.test(start)) fail('VENDOR_PROCESS_IDENTITY');
    const origin = `http://127.0.0.1:${endpoint.port}`;
    const response = await fetch(`${origin}/json/version`, {signal: AbortSignal.timeout(5000)});
    if (!response.ok) fail('VENDOR_DEVTOOLS');
    const version = await response.json();
    if (version.webSocketDebuggerUrl !== `ws://127.0.0.1:${endpoint.port}${endpoint.browserPath}`) fail('VENDOR_DEVTOOLS');
    report.binary.runtime = {...parseDevToolsVersion(version.Browser), basis: 'running process DevTools endpoint'};
    process.env.MTG_BROWSER_ORIGIN = origin;
    delete process.env.MTG_FRONTEND_ORIGIN;
    const {openBrowser} = await import('./browser-driver.mjs');
    page = await openBrowser('about:blank');
    const nonce = randomBytes(32).toString('hex');
    await page.command('Page.navigate', {url: `data:text/html,<body>${nonce}</body>`});
    await page.waitFor(`document.body?.textContent === ${JSON.stringify(nonce)}`, 10000);
    report.checks.dom_nonce = true;
    await page.command('Page.navigate', {url: 'chrome://sandbox/'});
    await page.waitFor("['chrome:', 'brave:'].includes(location.protocol) && location.hostname === 'sandbox' && document.querySelector('#evaluation')?.textContent && document.querySelectorAll('#sandbox-status tr').length >= 4", 10000);
    const sandbox = await page.evaluate("({rows:[...document.querySelectorAll('#sandbox-status tr')].map(row=>[...row.querySelectorAll('td')].map(td=>td.textContent.trim())),evaluation:document.querySelector('#evaluation').textContent.trim()})");
    report.sandbox = parseSandboxStatus(sandbox);
    const after = await readFile(`/proc/${child.pid}/stat`, 'utf8');
    if (after.slice(after.lastIndexOf(')') + 2).split(/\s+/)[19] !== start
        || await realpath(`/proc/${child.pid}/exe`) !== config.binary
        || await sha256(config.binary) !== installed.binary_sha256
        || await sha256(config.helper) !== installed.helper_sha256) fail('VENDOR_PROCESS_IDENTITY');
    report.checks.native_identity = true;
    report.source = {declared_commit: /^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? '') ? env.GITHUB_SHA : null,
      preflight_sha256: await sha256(new URL(import.meta.url)), driver_sha256: await sha256(new URL('./browser-driver.mjs', import.meta.url))};
  } catch (caught) { error = caught; }
  finally {
    if (page) try { await page.close(); } catch { error ??= new Error('VENDOR_CDP_CLOSE'); }
    if (priorOrigin === undefined) delete process.env.MTG_BROWSER_ORIGIN; else process.env.MTG_BROWSER_ORIGIN = priorOrigin;
    if (priorFrontend === undefined) delete process.env.MTG_FRONTEND_ORIGIN; else process.env.MTG_FRONTEND_ORIGIN = priorFrontend;
    if (child) {
      const wait = async milliseconds => {
        let timer;
        try { return await Promise.race([closed, new Promise(resolve => { timer = setTimeout(() => resolve(null), milliseconds); })]); }
        finally { clearTimeout(timer); }
      };
      child.kill('SIGTERM');
      let result = await wait(10000);
      if (!result) { child.kill('SIGKILL'); result = await wait(2000); error ??= new Error('VENDOR_FORCED_CLOSE'); }
      report.checks.direct_child_closed = result !== null;
      report.child_exit_after_cleanup = result;
      report.browser_stderr = observedChild.facts();
      if (!result) error ??= new Error('VENDOR_CHILD_UNCLOSED');
    }
    report.ok = !error && report.checks.dom_nonce === true && report.checks.native_identity === true && report.checks.direct_child_closed === true;
    if (!report.ok) report.failure = /^VENDOR_[A-Z_]+$/.test(error?.message ?? '') ? error.message : 'VENDOR_PREFLIGHT_FAILED';
    try {
      const json = JSON.stringify(report, null, 2) + '\n';
      assert.ok(Buffer.byteLength(json) <= 16384, 'VENDOR_REPORT_BOUND');
      await output.writeFile(json);
    } finally { await output.close(); }
  }
  if (!report.ok) fail(report.failure);
  return report;
}

export async function main(argv = process.argv.slice(2), env = process.env) {
  if (argv.length !== 2 || !['--check-config', '--report'].includes(argv[0])) fail('VENDOR_USAGE');
  const config = validateVendorInputs(env, argv[0] === '--check-config' ? {selectedBrowser: argv[1]} : {});
  if (argv[0] === '--check-config') return {schema: 1, mode: 'check-config', vendor: config.vendor,
    binary: config.binary, native_started: false, installation_verified: false};
  return nativeReport(config, argv[1], env);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then(result => { if (result.mode === 'check-config') console.log(JSON.stringify(result)); })
    .catch(error => { console.error(/^VENDOR_[A-Z_]+$/.test(error.message) ? error.message : 'VENDOR_PREFLIGHT_FAILED'); process.exitCode = 1; });
}
