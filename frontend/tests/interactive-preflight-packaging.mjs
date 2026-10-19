import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import ts from 'typescript';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const htmlPath = join(frontend, 'tests/interactive-preflight.html');
const supplier = '/tests/interactive-preflight.tsx';
const minimalWrapper = '<!doctype html><html><body><div id="root"></div>'
  + `<script type="module" src="${supplier}"></script></body></html>`;

function entrypoint(html) {
  assert.match(html, /<!doctype html>/i);
  assert.match(html, /<div\s+id=["']root["']\s*>\s*<\/div>/i);
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
  assert.equal(scripts.length, 1, 'Ship one module entrypoint, not a replacement fixture');
  const [, attributes, body] = scripts[0];
  assert.match(attributes, /\btype=["']module["']/);
  const sources = [...attributes.matchAll(/\bsrc=["']([^"']+)["']/g)];
  assert.equal(sources.length, 1);
  assert.equal(sources[0][1], supplier, 'Load the complete original TSX fixture');
  assert.equal(body.trim(), '', 'No inline substitute for the actual fixture');
  return join(frontend, supplier.slice(1));
}

// Check public source imports without executing the fixture, App or backend.
function sourceClosure(entry) {
  const visited = new Set();
  const manifest = JSON.parse(readFileSync(join(frontend, 'package.json'), 'utf8'));
  const dependencies = new Set(Object.keys({ ...manifest.dependencies, ...manifest.devDependencies }));
  function visit(path) {
    const local = relative(frontend, path);
    assert.ok(local && !local.startsWith('..'), 'Fixture imports stay inside frontend source');
    assert.ok(existsSync(path), `Missing public fixture source: ${local}`);
    if (visited.has(path)) return;
    visited.add(path);
    if (!/\.(?:tsx?|m?js)$/.test(path)) return;
    const tree = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true);
    for (const statement of tree.statements) {
      if (!ts.isImportDeclaration(statement) && !ts.isExportDeclaration(statement)) continue;
      const module = statement.moduleSpecifier;
      if (!module || !ts.isStringLiteral(module)) continue;
      const specifier = module.text;
      if (!specifier.startsWith('.')) {
        const name = specifier.startsWith('@') ? specifier.split('/').slice(0, 2).join('/') : specifier.split('/')[0];
        assert.ok(dependencies.has(name), `Declare fixture dependency: ${name}`);
        continue;
      }
      const base = resolve(dirname(path), specifier);
      const candidates = extname(base) ? [base] : [
        ...['.ts', '.tsx', '.mjs', '.js', '.css', '.json'].map(extension => base + extension),
        join(base, 'index.ts'), join(base, 'index.tsx'), join(base, 'index.js'),
      ];
      const dependency = candidates.find(candidate => existsSync(candidate));
      assert.ok(dependency, `Missing public import: ${local} -> ${specifier}`);
      visit(dependency);
    }
  }
  visit(entry);
  return visited;
}

test('published browser entrypoint ships the complete original fixture source closure', () => {
  const driver = readFileSync(join(frontend, 'tests/browser-interactive-preflight.mjs'), 'utf8');
  assert.match(driver, /Page\.navigate[^\n]*\/tests\/interactive-preflight\.html/);
  assert.ok(existsSync(htmlPath), 'Git/archive must ship the driver\'s interactive-preflight.html');
  const entry = entrypoint(readFileSync(htmlPath, 'utf8'));
  const closure = sourceClosure(entry);
  assert.ok(closure.has(join(frontend, 'src/App.tsx')));
  const fixture = readFileSync(entry, 'utf8');
  assert.match(fixture, /window\.interactiveFixture\s*=\s*fixture;/);
  assert.match(fixture, /window\.fetch\s*=\s*async/);
  assert.match(fixture, /createRoot\(document\.getElementById\("root"\)!\)\.render\(<StrictMode><App\s*\/><\/StrictMode>\)/);
});

test('entrypoint rejects another fixture or a path outside the canonical supplier', () => {
  for (const path of ['/tests/human-actions.tsx', '/src/main.tsx', '/../private.tsx']) {
    assert.throws(() => entrypoint(minimalWrapper.replace(supplier, path)), assert.AssertionError);
  }
});

test('entrypoint rejects an inline replacement for the complete fixture', () => {
  assert.throws(() => entrypoint(minimalWrapper.replace('</script>', 'window.interactiveFixture = {};</script>')), assert.AssertionError);
});

test('entrypoint rejects a second script instead of silently accepting a partial fixture', () => {
  assert.throws(() => entrypoint(minimalWrapper.replace('</body>', '<script type="module" src="/src/main.tsx"></script></body>')), assert.AssertionError);
});
