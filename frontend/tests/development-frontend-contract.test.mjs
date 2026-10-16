import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {stop} from 'esbuild';
import {createHash} from 'node:crypto';

const root = fileURLToPath(new URL('../', import.meta.url));
const implementation = process.env.MTG_DEV_BUILD_IMPLEMENTATION || new URL('./prepare-development-frontend.mjs', import.meta.url).href;
const {buildDevelopmentFrontend} = await import(implementation);
const ownedOutput = process.env.MTG_DEV_BUILD_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(), 'mtg-development-build-'));
const outDir = path.join(ownedOutput, 'built');
const result = await buildDevelopmentFrontend({root, configFile: path.join(root, 'vite.config.ts'), outDir});
const output = (Array.isArray(result) ? result : [result]).flatMap(value => value.output);
const chunks = output.filter(value => value.type === 'chunk');
const modules = chunks.flatMap(value => Object.keys(value.modules));
const code = chunks.map(value => value.code).join('\n');
const read = name => fs.readFileSync(new URL(name, import.meta.url), 'utf8');
const proof = chunks.find(value => value.isEntry && value.facadeModuleId?.endsWith('/ci-development-runtime/probe.html'));
const app = chunks.find(value => value.isEntry && value.facadeModuleId === path.join(root, 'index.html'));
const savedDeps = process.env.MTG_FRONTEND_DEPS;
const savedRuntime = process.env.MTG_OFFICER_RUNTIME;
process.env.MTG_FRONTEND_DEPS = root;
process.env.MTG_OFFICER_RUNTIME = ownedOutput;
let officer;
try {
  officer = await buildDevelopmentFrontend({root,
    configFile: path.join(root, 'tests/vite-activated-top-selection.mjs'),
    outDir: path.join(ownedOutput, 'officer')});
} finally {
  if (savedDeps === undefined) delete process.env.MTG_FRONTEND_DEPS; else process.env.MTG_FRONTEND_DEPS = savedDeps;
  if (savedRuntime === undefined) delete process.env.MTG_OFFICER_RUNTIME; else process.env.MTG_OFFICER_RUNTIME = savedRuntime;
}

after(async () => {
  stop();
  await globalThis[Symbol.for('mtg.build.guard')]?.closed();
  if (!process.env.MTG_DEV_BUILD_OUTPUT) fs.rmSync(ownedOutput, {recursive: true});
});

test('actual bundle uses the real development React module, not production React', () => {
  assert.ok(modules.some(id => id.endsWith('/react/cjs/react.development.js')));
  assert.equal(modules.some(id => id.includes('/react/cjs/react.production.')), false);
});

test('actual bundle retains development ReactDOM warnings and StrictMode replay machinery', () => {
  assert.ok(modules.some(id => id.endsWith('/react-dom/cjs/react-dom.development.js')));
  assert.match(code, /invokePassiveEffectMountInDEV/);
  assert.match(code, /commitDoubleInvokeEffectsInDEV/);
});

test('actual application bundle selects the development JSX runtime', () => {
  assert.ok(modules.some(id => id.endsWith('/react/cjs/react-jsx-dev-runtime.development.js')));
});

test('actual probe bundle records development environment constants', () => {
  assert.ok(proof);
  assert.match(proof.code, /nodeEnv:\s*["']development["']/);
  assert.match(proof.code, /dev:\s*true/);
  assert.match(proof.code, /prod:\s*false/);
});

test('real App and proof entries reach exactly the same bundled React module', () => {
  assert.ok(app && proof);
  const owners = chunks.filter(value => Object.keys(value.modules).some(id => /\/react\/cjs\/react\.(?:development|production\.min)\.js$/.test(id)));
  assert.equal(owners.length, 1);
  function reaches(entry, file, seen = new Set()) {
    if (entry.fileName === file) return true;
    if (seen.has(entry.fileName)) return false;
    seen.add(entry.fileName);
    return entry.imports.some(name => {
      const dependency = chunks.find(value => value.fileName === name);
      return dependency && reaches(dependency, file, seen);
    });
  }
  assert.equal(reaches(app, owners[0].fileName), true);
  assert.equal(reaches(proof, owners[0].fileName), true);
});

test('both real HTML entries are emitted without HMR or Fast Refresh runtime', () => {
  assert.ok(fs.existsSync(path.join(outDir, 'index.html')));
  assert.ok(fs.existsSync(path.join(outDir, 'tests/fixtures/ci-development-runtime/probe.html')));
  const html = output.filter(value => value.type === 'asset' && value.fileName.endsWith('.html')).map(value => String(value.source)).join('\n');
  assert.doesNotMatch(code + html, /\/@vite\/client|vite:ws:disconnect|vite-ping|\/@react-refresh/);
});

test('probe uses real React hooks without App instrumentation or mocked DOM', () => {
  const source = read('./fixtures/ci-development-runtime/probe.mjs');
  assert.match(source, /import React, \{StrictMode, useEffect\} from 'react'/);
  assert.match(source, /import \{createRoot\} from 'react-dom\/client'/);
  assert.match(source, /counts\.renders\+\+/);
  assert.match(source, /counts\.mounts\+\+/);
  assert.match(source, /counts\.cleanups\+\+/);
  assert.doesNotMatch(source, /from ['"].*App|mock|setTimeout|fetch\(/);
});

test('future native proof requires exact genuine replay counts and a distinct typed banner', () => {
  const location = new URL('./browser-development-runtime-proof.mjs', import.meta.url);
  const source = fs.existsSync(location) ? fs.readFileSync(location, 'utf8') : '';
  assert.match(source, /renders: 2, mounts: 2, cleanups: 1/);
  assert.match(source, /DEVELOPMENT_RUNTIME_PROOF/);
  assert.match(source, /openBrowser/);
  assert.doesNotMatch(source, /console\.log\(['"](?:PASS|Browser CI:)/);
});

test('ordinary launcher builds development assets and proves replay before its original stages', () => {
  const source = read('./run-browser-ci.sh');
  assert.match(source, /NODE_ENV=development VITE_API_BASE_URL=.*prepare-development-frontend\.mjs/);
  assert.match(source, /vite\/bin\/vite\.js["']? preview/);
  assert.ok(source.indexOf('browser-development-runtime-proof.mjs') < source.indexOf("echo 'Browser CI: async readiness helper'"));
  assert.equal((source.match(/^echo 'Browser CI: /gm) || []).length, 45);
});

test('nested Officer uses the same helper and checks replay before original browser cases', () => {
  const source = read('./run-activated-top-selection.sh');
  assert.match(source, /NODE_ENV=development.*prepare-development-frontend\.mjs/);
  assert.match(source, /vite\/bin\/vite\.js["']? preview/);
  assert.match(source, /mkdir "\$root\/frontend\/node_modules"/);
  assert.ok(source.indexOf('browser-development-runtime-proof.mjs') < source.indexOf('timeout 240s node'));
});

test('ordinary npm production build stays production and the App StrictMode wrapper is unchanged', () => {
  const pkg = JSON.parse(read('../package.json'));
  assert.equal(pkg.scripts.build, 'tsc -b && vite build');
  assert.match(read('../src/main.tsx'), /<React.StrictMode>\s*<App \/>\s*<\/React.StrictMode>/);
});

test('actual Officer configuration also builds shared development React without HMR', () => {
  const output = (Array.isArray(officer) ? officer : [officer]).flatMap(value => value.output);
  const chunks = output.filter(value => value.type === 'chunk');
  assert.equal(chunks.filter(value => Object.keys(value.modules).some(id => id.endsWith('/react/cjs/react.development.js'))).length, 1);
  assert.equal(chunks.some(value => Object.keys(value.modules).some(id => id.endsWith('/react-dom/cjs/react-dom.development.js'))), true);
  assert.equal(chunks.some(value => value.isEntry && value.facadeModuleId?.endsWith('/ci-development-runtime/probe.html')), true);
  assert.doesNotMatch(chunks.map(value => value.code).join('\n'), /\/@vite\/client|vite:ws:disconnect|vite-ping|\/@react-refresh/);
});

test('helper refuses an implicit or explicit production NODE_ENV before building', async () => {
  const {buildDevelopmentFrontend} = await import('./prepare-development-frontend.mjs');
  const saved = process.env.NODE_ENV;
  try {
    for (const value of [undefined, 'production', 'test']) {
      if (value === undefined) delete process.env.NODE_ENV; else process.env.NODE_ENV = value;
      assert.throws(() => buildDevelopmentFrontend({root, configFile: path.join(root, 'vite.config.ts'), outDir}), /requires NODE_ENV=development/);
    }
  } finally { process.env.NODE_ENV = saved; }
});

// Protocol tests do not execute React or establish native replay qualification.
async function runProof({environment = {nodeEnv: 'development', dev: true, prod: false},
  counts = {renders: 2, mounts: 2, cleanups: 1}, failure, closeFailure} = {}) {
  const source = read('./browser-development-runtime-proof.mjs');
  const body = source.slice(source.indexOf('const frontend ='));
  assert.ok(body.startsWith('const frontend ='));
  const calls = [], output = [];
  const browser = {
    async waitFor(expression) { calls.push(['wait', expression]); if (failure) throw failure; },
    async evaluate(expression) { calls.push(['evaluate', expression]); return expression.endsWith('.environment') ? environment : {environment, counts, reactVersion: 'protocol-only'}; },
    async close() { calls.push(['close']); if (closeFailure) throw closeFailure; },
  };
  let error;
  try {
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
    await new AsyncFunction('openBrowser', 'assert', 'process', 'console', body)(
      async url => { calls.push(['open', url]); return browser; }, assert,
      {env: {MTG_FRONTEND_ORIGIN: 'http://127.0.0.1:15237'}}, {log: (...args) => output.push(args)});
  } catch (caught) { error = caught; }
  return {calls, output, error};
}

test('runtime verifier protocol prints only after exact counts and successful page closure', async () => {
  const result = await runProof();
  assert.equal(result.error, undefined);
  assert.equal(result.calls[0][1], 'http://127.0.0.1:15237/tests/fixtures/ci-development-runtime/probe.html');
  assert.equal(result.calls.at(-1)[0], 'close');
  assert.equal(result.output.length, 1);
  assert.equal(result.output[0][0], 'DEVELOPMENT_RUNTIME_PROOF');
});

test('runtime verifier protocol rejects production flags and still closes the page', async () => {
  const result = await runProof({environment: {nodeEnv: 'production', dev: false, prod: true}});
  assert.equal(result.error?.code, 'ERR_ASSERTION');
  assert.equal(result.output.length, 0);
  assert.equal(result.calls.at(-1)[0], 'close');
});

for (const counts of [{renders: 1, mounts: 2, cleanups: 1}, {renders: 2, mounts: 1, cleanups: 0}, {renders: 2, mounts: 2, cleanups: 2}]) {
  test(`runtime verifier protocol rejects non-replay counts ${JSON.stringify(counts)}`, async () => {
    const result = await runProof({counts});
    assert.equal(result.error?.code, 'ERR_ASSERTION');
    assert.equal(result.output.length, 0);
    assert.equal(result.calls.at(-1)[0], 'close');
  });
}

test('runtime verifier protocol retains the primary failure if page closure also fails', async () => {
  const primary = new Error('protocol primary'), cleanup = new Error('protocol cleanup');
  const result = await runProof({failure: primary, closeFailure: cleanup});
  assert.ok(result.error instanceof AggregateError);
  assert.deepEqual(result.error.errors, [primary, cleanup]);
  assert.equal(result.output.length, 0);
});

test('runtime verifier protocol cannot emit proof when page closure fails', async () => {
  const cleanup = new Error('protocol cleanup');
  const result = await runProof({closeFailure: cleanup});
  assert.equal(result.error, cleanup);
  assert.equal(result.output.length, 0);
});

const originalFixtureRoutes = ['tests/attack-all.html', 'tests/human-actions.html',
  'tests/interactive-preflight.html', 'tests/simulation-preflight.html'];
function htmlFiles(directory, relative = '') {
  return fs.readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
    const name = path.posix.join(relative, entry.name);
    return entry.isDirectory() ? htmlFiles(path.join(directory, entry.name), name)
      : entry.isFile() && entry.name.endsWith('.html') ? [name] : [];
  });
}
for (const route of originalFixtureRoutes) {
  test(`actual build emits original ${route} and real module chunks, not the SPA fallback`, () => {
    const asset = output.find(value => value.type === 'asset' && value.fileName === route);
    assert.ok(asset, `Missing original fixture HTML: ${route}`);
    const html = fs.readFileSync(path.join(outDir, route), 'utf8');
    assert.equal(html, String(asset.source));
    const scripts = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/g)].map(match => match[1]);
    assert.ok(scripts.length > 0);
    for (const script of scripts) {
      const file = new URL(script, `https://fixture.invalid/${route}`).pathname.slice(1);
      assert.ok(chunks.some(chunk => chunk.fileName === file), 'HTML must reference a genuine emitted chunk');
      assert.ok(fs.statSync(path.join(outDir, file)).isFile());
      assert.match(file, /\.js$/); assert.doesNotMatch(script, /\.tsx?(?:[?#]|$)/);
    }
    const expected = ['index.html', ...htmlFiles(path.join(root, 'tests')).map(file => `tests/${file}`)].sort();
    assert.deepEqual(expected, ['index.html', ...originalFixtureRoutes, 'tests/fixtures/ci-development-runtime/probe.html'].sort());
    assert.deepEqual(output.filter(value => value.type === 'asset' && value.fileName.endsWith('.html')).map(value => value.fileName).sort(), expected);
    const browserSources = fs.readdirSync(path.join(root, 'tests')).filter(file => /^browser-.*\.mjs$/.test(file))
      .map(file => fs.readFileSync(path.join(root, 'tests', file), 'utf8')).join('\n');
    for (const match of browserSources.matchAll(/\/tests\/[a-zA-Z0-9_./-]+\.html/g)) assert.ok(expected.includes(match[0].slice(1)), 'Existing literal browser HTML route must be built');
    const entry = chunks.find(chunk => chunk.isEntry && chunk.facadeModuleId === path.join(root, route));
    const owner = chunks.find(chunk => Object.keys(chunk.modules).some(id => id.endsWith('/react/cjs/react.development.js')));
    const reaches = (chunk, seen = new Set()) => {
      if (!chunk || seen.has(chunk.fileName)) return false;
      if (chunk === owner) return true;
      seen.add(chunk.fileName);
      return chunk.imports.some(file => reaches(chunks.find(value => value.fileName === file), seen));
    };
    assert.ok(owner && reaches(entry), 'Fixture must share genuine development React');
    assert.doesNotMatch(html + code, /\/@vite\/client|vite:ws:disconnect|vite-ping|\/@react-refresh/);
    const officerOutput = (Array.isArray(officer) ? officer : [officer]).flatMap(value => value.output);
    assert.ok(officerOutput.some(value => value.type === 'asset' && value.fileName === route), 'Nested Officer uses the same complete fixture catalogue');
  });
}


test('actual simulation fixture retains its unchanged top-level await in the emitted module', () => {
  const entry = chunks.find(chunk => chunk.isEntry && chunk.facadeModuleId === path.join(root, 'tests/simulation-preflight.html'));
  assert.ok(entry);
  assert.match(entry.code, /(?:^|\n)\s*await\s+\w+\.startSimulateBatchJob\(/m);
  assert.equal(createHash('sha256').update(read('./simulation-preflight.tsx')).digest('hex'), '5992aea422e2fd9d76626039f5e6cffbb6c6bb88761a5d80ac592cc400cddf9d');
});

test('native default production build target and configuration remain unchanged', async () => {
  const {resolveConfig} = await import('vite');
  const config = await resolveConfig({root, configFile: path.join(root, 'vite.config.ts')}, 'build', 'production');
  assert.deepEqual(config.build.target, ['es2020', 'edge88', 'firefox78', 'chrome87', 'safari14']);
  assert.equal(createHash('sha256').update(read('../vite.config.ts')).digest('hex'), 'fec71d5fefd160d586ca8b5448d0d0f770f261751c9b2310273a31fe75671514');
  assert.equal(JSON.parse(read('../package.json')).scripts.build, 'tsc -b && vite build');
});
