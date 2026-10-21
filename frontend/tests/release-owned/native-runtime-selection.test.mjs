import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

// PROTOCOL ONLY: read public source, then evaluate only its actual selection,
// authorization, browser-start expression and finality binding with inert I/O.
// Nothing imports the launcher, starts a child or reads a real runtime/pin file.
const launcher = readFileSync(new URL('./run-current-built-acceptance.mjs', import.meta.url), 'utf8');
const project = '/protocol/owned', root = project + '/source';
const out = project + '/evidence/native-browser';
const python = '/protocol/runtime/python/bin/python';
const deps = '/protocol/runtime/node_modules';
const executables = Object.freeze({chrome: '/protocol/runtime/chrome',
  brave: '/protocol/runtime/brave', firefox: '/protocol/runtime/firefox'});
const pinsPath = project + '/runner/executable-pins.json';
const plain = value => JSON.parse(JSON.stringify(value));
const sourceAssertion = error => error?.name === 'AssertionError' && error.code === 'ERR_ASSERTION';

function actualRange(begin, end, includeEndDeclaration = false) {
  const start = launcher.indexOf(begin), finish = launcher.indexOf(end, start);
  assert.ok(start >= 0 && finish > start, 'Actual public launcher extraction boundary required');
  const stop = includeEndDeclaration ? launcher.indexOf(';\n', finish) + 1 : finish;
  assert.ok(stop > finish || !includeEndDeclaration, 'Actual final declaration must end');
  return launcher.slice(start, stop);
}

const selection = actualRange('const browserVendor = ', 'const bodyCacheDirectory = ', true);
const browserStart = actualRange('  const chromium = browserVendor', '  const chromeStat = ');
const authorization = launcher.match(/^function authorizeChild\([^\n]*\) \{\n[\s\S]*?^\}/m)?.[0];
assert.ok(authorization, 'Actual existing authorizeChild body required');
const bindingStart = launcher.indexOf('\nclosedReceipt = closedReceipt.bind(');
const bindingEnd = launcher.indexOf(';\n', bindingStart) + 1;
assert.ok(bindingStart >= 0 && bindingEnd > bindingStart, 'Actual closedReceipt binding required');
const finalityBinding = launcher.slice(bindingStart, bindingEnd);

function pinRows() {
  const row = file => ({path: file, realpath: file, SHA256: 'a'.repeat(64)});
  return {node: row('/protocol/runtime/node/bin/node'), python: row(python),
    ...Object.fromEntries(Object.entries(executables).map(([vendor, file]) => [vendor, row(file)]))};
}

async function select(vendor, mode, options = {}) {
  const {pins = pinRows(), bind = false} = options;
  const frontendDeps = Object.hasOwn(options, 'frontendDeps') ? options.frontendDeps : deps;
  let childCalls = 0;
  const env = {MTG_BROWSER_VENDOR: vendor, MTG_BROWSER_NO_SANDBOX: mode,
    MTG_FRONTEND_DEPS: frontendDeps};
  const context = vm.createContext({assert, path, project, process: {env},
    async readFile(file, encoding) {
      if (file !== pinsPath || encoding !== 'utf8')
        throw new Error('Inert selection fixture rejected an undeclared read');
      return JSON.stringify(pins);
    },
    start() { childCalls++; throw new Error('Selection must not start any child'); },
  });
  try {
    // The binding shares the actual selection's lexical scope. No desired mode
    // boolean is injected here: any future selector must come from actual code.
    const value = await new vm.Script(`(async () => {
      ${bind ? 'let closedReceipt = options => options;' : ''}
      ${selection}
      ${bind ? finalityBinding : ''}
      return {browserVendor, python, deps, chrome, firefox, out, bodyCacheDirectory,
        ${bind ? 'requireOwnedIdentity: closedReceipt().requireOwnedIdentity' : ''}};
    })()`, {filename: 'actual-runtime-selection.protocol.mjs'})
      .runInContext(context, {timeout: 1000});
    return plain(value);
  } finally {
    if (childCalls !== 0) throw new Error('Inert selection fixture observed a forbidden child attempt');
  }
}

function cdpArgs(legacy = false) {
  return ['--headless', '--no-first-run', '--disable-dev-shm-usage',
    '--disable-background-networking', '--no-default-browser-check', '--password-store=basic',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
    ...(legacy ? ['--no-sandbox'] : []), `--user-data-dir=${out}/profile`,
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=18003', 'about:blank'];
}

const firefoxArgs = ['--headless', '--no-remote', '--profile', out + '/profile',
  '--remote-debugging-port', '18003', 'about:blank'];
const factoryArgs = ['-m', 'uvicorn', 'tests.firefox_body_cache_app:create_app', '--factory',
  '--host', '127.0.0.1', '--port', '18001'];

function nativeContext(vendor, mode, extra = {}) {
  const chrome = executables[vendor === 'brave' ? 'brave' : 'chrome'];
  return vm.createContext({assert, path, root, out, python, deps, chrome,
    firefox: executables.firefox, nativeExecutable: executables[vendor],
    browserVendor: vendor, strictNative: mode === '0',
    ports: {backend: 18001, frontend: 18002, cdp: 18003, hostile: 18004},
    roleCounts: new Map(), authorizedFuserPaths: [], viteConfig: root + '/frontend/vite.mjs',
    process: {execPath: '/protocol/runtime/node/bin/node', env: {
      MTG_BROWSER_VENDOR: vendor, MTG_BROWSER_NO_SANDBOX: mode, MTG_FRONTEND_DEPS: deps}},
    ...extra});
}

function authorize(vendor, mode, args, {label = 'chromium', binary = executables[vendor],
  cwd = root} = {}) {
  const context = nativeContext(vendor, mode, {argvJSON: JSON.stringify(args), label, binary, cwd});
  // Decode arrays inside the function's realm, matching genuine argv comparisons.
  new vm.Script(`${authorization}\nauthorizeChild(label, binary, JSON.parse(argvJSON), cwd);`,
    {filename: 'actual-child-authorization.protocol.mjs'}).runInContext(context, {timeout: 1000});
}

function spawnExpression(vendor, mode) {
  const calls = [];
  const context = nativeContext(vendor, mode, {
    start(label, binary, args, cwd) {
      calls.push({label, binary, args: plain(args), cwd});
      return {label, pid: 701, exitCode: null, signalCode: null};
    },
  });
  new vm.Script(`(() => {${browserStart}\nreturn chromium;})()`,
    {filename: 'actual-browser-start.protocol.mjs'}).runInContext(context, {timeout: 1000});
  assert.equal(calls.length, 1, 'Exactly one inert browser start expression');
  const call = calls[0];
  assert.equal(call.label, vendor === 'firefox' ? 'firefox' : 'chromium');
  assert.equal(call.binary, executables[vendor]); assert.equal(call.cwd, root);
  return call.args;
}

test('[protocol] Firefox0 selection retains provided Firefox Python and dependency pins', async () => {
  const result = await select('firefox', '0');
  assert.equal(result.firefox, executables.firefox); assert.equal(result.python, python);
  assert.equal(result.deps, deps); assert.equal(result.browserVendor, 'firefox');
});

test('[protocol] Chrome1 legacy selection retains its exact nonqualifying runtime paths', async () => {
  const result = await select('chrome', '1');
  assert.equal(result.chrome, '/snap/chromium/3551/usr/lib/chromium-browser/chrome');
  assert.equal(result.python, '/tmp/mtg-fresh-deps-restored-dVBzUV/venv/bin/python');
  assert.equal(result.deps, '/home/nick/mtg-deck-testing-lab/frontend/node_modules');
});

test('[protocol] Chrome0 selection uses the provided Chrome Python and dependency pins', async () => {
  const result = await select('chrome', '0');
  assert.equal(result.chrome, executables.chrome); assert.equal(result.python, python);
  assert.equal(result.deps, deps); assert.equal(result.browserVendor, 'chrome');
});

test('[protocol] Brave0 selection uses the provided Brave Python and dependency pins', async () => {
  const result = await select('brave', '0');
  assert.equal(result.chrome, executables.brave); assert.equal(result.python, python);
  assert.equal(result.deps, deps); assert.equal(result.browserVendor, 'brave');
});

test('[protocol] unsupported vendors reject selection before child creation', async () => {
  for (const vendor of ['chromium', 'edge', '../chrome'])
    await assert.rejects(select(vendor, '0'), sourceAssertion);
});

test('[protocol] unsupported or missing sandbox modes reject selection before child creation', async () => {
  for (const vendor of ['chrome', 'brave', 'firefox']) for (const mode of [undefined, '', '2', 'false'])
    await assert.rejects(select(vendor, mode), sourceAssertion);
});

test('[protocol] Firefox1 cannot become a sandbox-disabled native selection', async () => {
  await assert.rejects(select('firefox', '1'), sourceAssertion);
});

test('[protocol] Brave1 cannot use the legacy Chrome compatibility exception', async () => {
  await assert.rejects(select('brave', '1'), sourceAssertion);
});

test('[protocol] missing selected executable pins reject native selection without fallback', async () => {
  for (const vendor of ['firefox', 'chrome', 'brave']) {
    const pins = pinRows(); delete pins[vendor];
    await assert.rejects(select(vendor, '0', {pins}), sourceAssertion);
  }
});

test('[protocol] missing Python pins reject native selection without fallback', async () => {
  for (const vendor of ['firefox', 'chrome', 'brave']) {
    const pins = pinRows(); delete pins.python;
    await assert.rejects(select(vendor, '0', {pins}), sourceAssertion);
  }
});

test('[protocol] missing dependency roots reject native selection without fallback', async () => {
  for (const vendor of ['firefox', 'chrome', 'brave'])
    await assert.rejects(select(vendor, '0', {frontendDeps: undefined}), sourceAssertion);
});

test('[protocol] noncanonical executable Python and dependency paths reject native selection', async () => {
  for (const vendor of ['firefox', 'chrome', 'brave']) for (const file of ['relative/file', '/protocol/../escape']) {
    for (const field of [vendor, 'python']) {
      const pins = pinRows(); pins[field].path = file;
      await assert.rejects(select(vendor, '0', {pins}), sourceAssertion);
    }
    await assert.rejects(select(vendor, '0', {frontendDeps: file}), sourceAssertion);
  }
});

test('[protocol] Chrome0 authorization accepts exact sandbox-retaining CDP argv', () => {
  assert.doesNotThrow(() => authorize('chrome', '0', cdpArgs()));
});

test('[protocol] Brave0 authorization accepts exact sandbox-retaining CDP argv', () => {
  assert.doesNotThrow(() => authorize('brave', '0', cdpArgs()));
});

test('[protocol] Chrome0 authorization rejects sandbox-disabling CDP argv', () => {
  assert.throws(() => authorize('chrome', '0', cdpArgs(true)), sourceAssertion);
});

test('[protocol] Brave0 authorization rejects sandbox-disabling CDP argv', () => {
  assert.throws(() => authorize('brave', '0', cdpArgs(true)), sourceAssertion);
});

test('[protocol] Chrome1 legacy authorization retains the exact original CDP argv', () => {
  assert.doesNotThrow(() => authorize('chrome', '1', cdpArgs(true)));
});

test('[protocol] Firefox0 authorization retains the exact genuine factory argv', () => {
  assert.doesNotThrow(() => authorize('firefox', '0', factoryArgs,
    {label: 'backend', binary: python, cwd: root + '/backend'}));
});

test('[protocol] Firefox0 factory authorization rejects augmented argv', () => {
  assert.throws(() => authorize('firefox', '0', [...factoryArgs, '--reload'],
    {label: 'backend', binary: python, cwd: root + '/backend'}), sourceAssertion);
});

test('[protocol] strict CDP authorization rejects a different executable', () => {
  for (const vendor of ['chrome', 'brave'])
    assert.throws(() => authorize(vendor, '0', cdpArgs(), {binary: '/protocol/runtime/foreign'}), sourceAssertion);
});

test('[protocol] Chrome0 actual selection and finality binding require strict owned identity', async () => {
  assert.equal((await select('chrome', '0', {bind: true})).requireOwnedIdentity, true);
});

test('[protocol] Brave0 actual selection and finality binding require strict owned identity', async () => {
  assert.equal((await select('brave', '0', {bind: true})).requireOwnedIdentity, true);
});

test('[protocol] Firefox0 actual selection and finality binding retain strict owned identity', async () => {
  assert.equal((await select('firefox', '0', {bind: true})).requireOwnedIdentity, true);
});

test('[protocol] Chrome1 actual selection and finality binding remain explicitly nonqualifying', async () => {
  assert.equal((await select('chrome', '1', {bind: true})).requireOwnedIdentity, false);
});

test('[protocol] Chrome0 actual browser start retains sandboxing and the exact CDP argv', () => {
  const args = spawnExpression('chrome', '0');
  assert.equal(args.includes('--no-sandbox'), false);
  assert.equal(args.includes('--disable-setuid-sandbox'), false);
  assert.deepEqual(args, cdpArgs());
});

test('[protocol] Brave0 actual browser start retains sandboxing and the exact CDP argv', () => {
  const args = spawnExpression('brave', '0');
  assert.equal(args.includes('--no-sandbox'), false);
  assert.equal(args.includes('--disable-setuid-sandbox'), false);
  assert.deepEqual(args, cdpArgs());
});

test('[protocol] Chrome1 actual browser start preserves the exact legacy CDP argv', () => {
  assert.deepEqual(spawnExpression('chrome', '1'), cdpArgs(true));
});

test('[protocol] Firefox0 actual browser start preserves the exact BiDi argv', () => {
  assert.deepEqual(spawnExpression('firefox', '0'), firefoxArgs);
});
