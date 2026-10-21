import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readdir, lstat, stat, rename, readFile, rm, mkdir, unlink, realpath} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {test} from 'node:test';
import {subject, variants, OUT, TEMP, FINAL, EPOCH, failure, firefoxSubject} from './public-storage-owner-rename-fixture.mjs';

// This whole public-only cohort declares 20 protocol cases plus one owned-FS case.
// No launcher module, application, token, /proc, service, or guard is imported.
const cases = [
  {name: 'stable owned receipt is charged with no producer exception', async run(variant) {
    const s = subject(variant, {stable: true});
    const result = await s.run();
    assert.equal(result.bytes, s.bytes.length);
    assert.equal(s.tempStats, 0);
    assert.equal(s.calls.signals.length, 0);
  }},
  {name: 'one authenticated rename restarts with fresh counters and charges final once', async run(variant) {
    const s = subject(variant);
    const result = await s.run();
    assert.equal(result.bytes, s.bytes.length);
    assert.equal(s.tempStats, 1);
    assert.ok(s.calls.readdir.filter(name => name === OUT).length >= 2);
    assert.equal(s.calls.signals.length, 0);
  }},
  {name: 'preexisting final is not charged twice after the partial walk is discarded', async run(variant) {
    const s = subject(variant, {oldFinal: true, extraFiles: [['fixed.bin', 123]]});
    const result = await s.run();
    assert.equal(result.bytes, s.bytes.length + 123);
    assert.equal(s.tempStats, 1);
  }},
  {name: 'recreated owned temporary is charged rather than silently skipped', async run(variant) {
    const s = subject(variant, {recreated: true});
    const result = await s.run();
    assert.equal(result.bytes, s.expectedBytes());
    assert.ok(result.bytes > s.bytes.length);
  }},
  {name: 'second matching producer race fails closed without another restart', async run(variant) {
    const s = subject(variant, {secondRace: true});
    await assert.rejects(s.run(), error => error === s.second);
    assert.equal(s.tempStats, 2);
    assert.equal(s.calls.signals.length, 0);
  }},
  {name: 'unrelated missing leaf preserves its original ENOENT', async run(variant) {
    const s = subject(variant, {temp: OUT + '/unknown.tmp'});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.tempStats, 1);
  }},
  {name: 'permission failure is never converted to a publication race', async run(variant) {
    const s = subject(variant, {code: 'EACCES'});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.tempStats, 1);
  }},
  {name: 'error.path must equal the actual disappearing entry', async run(variant) {
    const s = subject(variant, {errorPath: '/foreign/owner.tmp'});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.tempStats, 1);
  }},
  {name: 'nested or unrelated directory cannot claim the direct publisher role', async run(variant) {
    const s = subject(variant, {temp: OUT + '/nested/' + path.basename(TEMP)});
    await assert.rejects(s.run());
    assert.equal(s.calls.forbidden.length, 0);
  }},
  {name: 'unknown producer PID or epoch cannot join another final receipt', async run(variant) {
    for (const temp of [TEMP.replace('-301-', '-999-'), TEMP.replace(EPOCH, 'b'.repeat(32))]) {
      const s = subject(variant, {temp});
      await assert.rejects(s.run());
      assert.equal(s.tempStats, 1);
    }
  }},
  {name: 'changed producer birth cannot authenticate a good filename', async run(variant) {
    const s = subject(variant, {receipt: {start_ticks: 9999}});
    await assert.rejects(s.run());
    assert.equal(s.tempStats, 1);
  }},
  {name: 'canonical root retarget or final symlink is not followed or accepted', async run(variant) {
    for (const option of [{redirectRoot: true}, {finalInfo: {kind: 'symlink'}}]) {
      const s = subject(variant, option);
      await assert.rejects(s.run());
      assert.equal(s.calls.forbidden.length, 0);
    }
  }},
  {name: 'foreign owner nonregular final and extra links remain rejected', async run(variant) {
    for (const finalInfo of [{uid: 999}, {kind: 'directory'}, {nlink: 2}]) {
      const s = subject(variant, {finalInfo});
      await assert.rejects(s.run());
      assert.equal(s.tempStats, 1);
    }
  }},
  {name: 'missing final or mismatched receipt epoch cannot resolve the lost temporary', async run(variant) {
    for (const option of [{missingFinal: true}, {receipt: {epoch: 'b'.repeat(32)}}]) {
      const s = subject(variant, option);
      await assert.rejects(s.run());
      assert.equal(s.tempStats, 1);
    }
  }},
  {name: 'verification read failures still fail closed', async run(variant) {
    const s = subject(variant, {finalPermission: failure('EACCES', FINAL)});
    await assert.rejects(s.run());
    assert.equal(s.calls.forbidden.length, 0);
  }},
  {name: 'authenticated rename cannot bypass aggregate output cap', async run(variant) {
    const s = subject(variant, {extraFiles: [['large.bin', 1536 * 1024 * 1024]]});
    await assert.rejects(s.run(), /Owned output exceeds aggregate 1\.5 GiB/);
    assert.equal(s.tempStats, 1);
  }},
  {name: 'fresh pass keeps current storage accounting instead of inventing zero bytes', async run(variant) {
    const s = subject(variant, {storageBytes: 1024 * 1024});
    const result = await s.run();
    assert.equal(result.bytes, s.bytes.length);
    assert.equal(result.storageBytes, 1024 * 1024);
  }},
  {name: 'existing profile screenshot and journal caps remain exact', async run(variant) {
    for (const [extraFiles, message] of [
      [[['profile/large.bin', 512 * 1024 * 1024 + 1]], /Profile exceeds 512 MiB/],
      [[['large.log', 256 * 1024 * 1024 + 1]], /Per-journal byte limit/],
      [Array.from({length: 65}, (_, i) => [`image-${i}.png`, 1]), /Screenshot count exceeds 64/],
    ]) {
      const s = subject(variant, {stable: true, extraFiles});
      await assert.rejects(s.run(), message);
    }
  }},
  {name: 'original Chrome missing-cache exception remains separate and unchanged', async run(variant) {
    const s = subject(variant, {stable: true, chrome: true});
    const result = await s.run();
    assert.equal(result.observedChromeCacheRaceCount, 1);
    assert.equal(result.profileBytes, 0);
    assert.equal(s.calls.write.filter(name => name.endsWith('/chrome-cache-races.json')).length, 1);
  }},
  {name: 'no authentic backend identity means no producer exception', async run(variant) {
    const s = subject(variant, {noProducer: true});
    await assert.rejects(s.run());
    assert.equal(s.tempStats, 1);
    assert.equal(s.calls.signals.length, 0);
  }},
];

for (const variant of variants) {
  for (const entry of cases) {
    test(`${variant}: ${entry.name}`, {concurrency: false}, async () => entry.run(variant));
  }
}

test('owned native filesystem proves readdir-before-rename then ENOENT and same final inode', async () => {
  const evidence = process.env.UNIT_EVIDENCE ?? tmpdir();
  assert.equal(typeof evidence, 'string', 'Parent-owned unit evidence required');
  assert.ok(path.isAbsolute(evidence));
  const directory = await mkdtemp(path.join(evidence, 'atomic-owner-control-'));
  const source = path.join(directory, 'publication.tmp');
  const target = path.join(directory, 'publication.json');
  const bytes = Buffer.from('{"protocol_only":true}\n');
  try {
    await writeFile(source, bytes, {mode: 0o600, flag: 'wx'});
    const listed = await readdir(directory, {withFileTypes: true});
    const before = await lstat(source);
    assert.equal(listed.length, 1);
    assert.ok(listed[0].isFile());
    await rename(source, target);
    await assert.rejects(stat(source), error => error.code === 'ENOENT' && error.path === source);
    const after = await lstat(target);
    assert.equal(after.dev, before.dev);
    assert.equal(after.ino, before.ino);
    assert.equal(after.nlink, 1);
    assert.deepEqual(await readFile(target), bytes);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('Firefox XDG cache disappearance counts Firefox once and Chrome zero', async () => {
  const s = firefoxSubject();
  const result = await s.run();
  assert.equal(result.bytes, 0);
  assert.equal(result.observedFirefoxCacheRaceCount, 1);
  assert.equal(result.observedChromeCacheRaceCount, 0);
  assert.equal(s.calls.write.length, 1);
  assert.equal(s.calls.signals.length, 0);
});

test('recreated regular Firefox cache leaf is charged rather than skipped', async () => {
  const s = firefoxSubject({recreated: {size: 123}});
  const result = await s.run();
  assert.equal(result.bytes, 123);
  assert.equal(result.observedFirefoxCacheRaceCount, 1);
  assert.equal(result.observedChromeCacheRaceCount, 0);
  assert.equal(s.calls.signals.length, 0);
});

test('Firefox exception rejects unrelated errors paths and unsafe filesystem boundaries', async () => {
  for (const options of [
    {code: 'EACCES'}, {errorPath: '/foreign'}, {leafError: 'EACCES'},
    {leaf: OUT + '/profile/unrelated'},
    {redirect: OUT}, {redirect: OUT + '/cache'}, {redirect: OUT + '/cache/fontconfig'},
    {rootInfo: {uid: 999}}, {rootInfo: {mode: 0o40755}},
    {cacheInfo: {kind: 'symlink'}}, {cacheInfo: {uid: 999}},
    {parentInfo: {kind: 'symlink'}}, {parentInfo: {mode: 0o40777}},
    {drift: 'root'}, {drift: 'cache'}, {drift: 'parent'},
    {recreated: {kind: 'symlink'}}, {recreated: {kind: 'directory'}},
    {recreated: {uid: 999}},
  ]) {
    const s = firefoxSubject(options);
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox cache exception requires actual live child birth and executable twice', async () => {
  for (const options of [
    {noChild: true}, {shutdown: true}, {child: {exitCode: 0}},
    {child: {signalCode: 'SIGTERM'}}, {identity: {pid: 999}},
    {birthBefore: '9999'}, {birthAfter: '9999'},
    {exeAfter: '/foreign'}, {identity: {exe: '/foreign'}},
  ]) {
    const s = firefoxSubject(options);
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox race ledger and recreated bytes cannot bypass existing finite caps', async () => {
  for (const [options, message] of [
    [{ledger: Array(4096).fill({})}, /Finite Firefox cache race count/],
    [{ledger: [{padding: 'x'.repeat(2 * 1024 * 1024)}]}, /Bounded Firefox cache race ledger/],
    [{recreated: {size: 1536 * 1024 * 1024 + 1}}, /Owned output exceeds aggregate 1\.5 GiB/],
  ]) {
    const s = firefoxSubject(options);
    await assert.rejects(s.run(), message);
    assert.equal(s.calls.signals.length, 0);
  }
});

test('actual outputBudget sees readdir then genuine Firefox cache unlink and stat ENOENT', async () => {
  const evidence = process.env.UNIT_EVIDENCE ?? tmpdir();
  const directory = await mkdtemp(path.join(evidence, 'firefox-cache-unlink-'));
  const cache = path.join(directory, 'cache'), parent = path.join(cache, 'fontconfig');
  const leaf = path.join(parent, 'CACHEDIR.TAG.LCK');
  let removed = false;
  try {
    await mkdir(cache, {mode: 0o700});
    await mkdir(parent, {mode: 0o700});
    await writeFile(leaf, 'owned-public-cache', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({out: directory, uid: process.getuid(), io: {
      readdir, lstat, realpath, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        assert.equal(removed, false);
        await unlink(file); removed = true;
        return stat(file);
      },
    }});
    const result = await s.run();
    assert.equal(removed, true);
    assert.equal(s.initial.code, 'ENOENT');
    assert.equal(s.initial.path, leaf);
    assert.equal(result.bytes, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(JSON.parse(await readFile(path.join(directory, 'firefox-cache-races.json'))).length, 1);
    assert.equal(s.calls.signals.length, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('owned recreated hardlinked Firefox cache leaf is conservatively charged', async () => {
  const s = firefoxSubject({recreated: {nlink: 2, size: 123}});
  const result = await s.run();
  assert.equal(result.bytes, 123);
  assert.equal(result.observedFirefoxCacheRaceCount, 1);
  assert.equal(result.observedChromeCacheRaceCount, 0);
  assert.equal(s.calls.signals.length, 0);
});

test('recreated lstat snapshot is charged after another genuine unlink without resolving the leaf', async () => {
  const evidence = process.env.UNIT_EVIDENCE ?? tmpdir();
  const directory = await mkdtemp(path.join(evidence, 'firefox-recreated-unlink-'));
  const cache = path.join(directory, 'cache'), parent = path.join(cache, 'fontconfig');
  const leaf = path.join(parent, 'public-cache-entry');
  const recreated = Buffer.from('recreated public cache bytes');
  let observed, resolutions = 0;
  try {
    await mkdir(cache, {mode: 0o700});
    await mkdir(parent, {mode: 0o700});
    await writeFile(leaf, 'original public cache bytes', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({out: directory, uid: process.getuid(), io: {
      readdir, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        await unlink(file);
        let gone;
        try { await stat(file); }
        catch (error) { gone = error; }
        assert.equal(gone.code, 'ENOENT');
        assert.equal(gone.path, file);
        await writeFile(file, recreated, {mode: 0o600, flag: 'wx'});
        throw gone;
      },
      lstat: async file => {
        const metadata = await lstat(file);
        if (file === leaf) {
          observed = metadata;
          await unlink(file);
        }
        return metadata;
      },
      realpath: async file => {
        if (file === leaf) resolutions++;
        return realpath(file);
      },
    }});
    const result = await s.run();
    assert.ok(observed.isFile());
    assert.equal(observed.size, recreated.length);
    assert.equal(result.bytes, observed.size);
    assert.equal(resolutions, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    await assert.rejects(lstat(leaf), error => error.code === 'ENOENT' && error.path === leaf);
    const rows = JSON.parse(await readFile(path.join(directory, 'firefox-cache-races.json')));
    assert.equal(rows[0].chargedBytes, observed.size);
    assert.equal(rows[0].outcome, 'recreated-regular-charged');
    assert.equal(s.calls.signals.length, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('Firefox body-cache metrics accepts exactly five direct transient suffixes without reading bodies', async () => {
  for (const suffix of ['.body', '.json', '.claim', '.release', '.release.next']) {
    const s = firefoxSubject({bodyCache: true,
      leaf: OUT + '/firefox-body-cache/' + 'a'.repeat(32) + suffix});
    const result = await s.run();
    assert.equal(result.bytes, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.write.length, 1);
    assert.ok(s.calls.read.every(name => name === '/proc/301/stat'));
    assert.equal(s.calls.signals.length, 0);
  }
});

test('body-cache recreated regular and hardlinked metrics charge the last observed size without following the leaf', async () => {
  for (const nlink of [1, 2]) {
    const s = firefoxSubject({bodyCache: true, recreated: {size: 123, nlink}});
    const result = await s.run();
    assert.equal(result.bytes, 123);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.resolve.includes(s.leaf), false);
    assert.ok(s.calls.read.every(name => name === '/proc/301/stat'));
    assert.equal(s.calls.signals.length, 0);
  }
});

test('body-cache exception excludes enrollment permanent unknown malformed and nested names', async () => {
  for (const name of ['enrollment.json', 'enrollment.json.next', 'unknown.tmp',
    'a'.repeat(31) + '.claim', 'A'.repeat(32) + '.claim',
    'a'.repeat(32) + '.body.next', 'a'.repeat(32) + '.json.backup',
    'nested/' + 'a'.repeat(32) + '.claim']) {
    const s = firefoxSubject({bodyCache: true, leaf: OUT + '/firefox-body-cache/' + name});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.calls.signals.length, 0);
  }
  const s = firefoxSubject({bodyCache: true, leaf: OUT + '/profile/' + 'a'.repeat(32) + '.claim'});
  await assert.rejects(s.run(), error => error === s.initial);
});

test('body-cache metrics requires the retained current backend and actual birth and executable on both sides', async () => {
  for (const options of [
    {noChild: true}, {shutdown: true}, {child: {label: 'firefox'}},
    {child: {pid: -1}}, {child: {exitCode: 0}}, {child: {signalCode: 'SIGTERM'}},
    {child: {startTicks: 0}}, {child: {startTicks: '3010'}},
    {birthBefore: '9999'}, {birthAfter: '9999'},
    {exeBefore: '/foreign'}, {exeAfter: '/foreign'}, {replaceBackend: true},
  ]) {
    const s = firefoxSubject({bodyCache: true, ...options});
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('body-cache metrics rejects nonmissing errors unsafe or changed directories and recreated nonregular foreign leaves', async () => {
  for (const options of [
    {code: 'EACCES'}, {errorPath: '/foreign'}, {leafError: 'EACCES'},
    {redirect: OUT}, {redirect: OUT + '/firefox-body-cache'},
    {rootInfo: {uid: 999}}, {rootInfo: {mode: 0o40755}},
    {cacheInfo: {kind: 'symlink'}}, {cacheInfo: {uid: 999}}, {cacheInfo: {mode: 0o40755}},
    {drift: 'root'}, {drift: 'cache'},
    {recreated: {kind: 'symlink'}}, {recreated: {kind: 'directory'}},
    {recreated: {uid: 999}}, {recreated: {mode: 0o100666}},
  ]) {
    const s = firefoxSubject({bodyCache: true, ...options});
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('body-cache transient metrics shares the finite Firefox ledger and unchanged aggregate cap', async () => {
  for (const [options, message] of [
    [{ledger: Array(4096).fill({})}, /Finite Firefox cache race count/],
    [{ledger: [{padding: 'x'.repeat(2 * 1024 * 1024)}]}, /Bounded Firefox cache race ledger/],
    [{recreated: {size: 1536 * 1024 * 1024 + 1}}, /Owned output exceeds aggregate 1\.5 GiB/],
  ]) {
    const s = firefoxSubject({bodyCache: true, ...options});
    await assert.rejects(s.run(), message);
    assert.equal(s.calls.signals.length, 0);
  }
});

test('actual outputBudget observes a genuine direct body-cache claim unlink after readdir', async () => {
  const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), 'body-cache-unlink-'));
  const cache = path.join(directory, 'firefox-body-cache');
  const leaf = path.join(cache, 'a'.repeat(32) + '.claim');
  let removed = false;
  try {
    await mkdir(cache, {mode: 0o700});
    await writeFile(leaf, 'public protocol claim bytes', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({bodyCache: true, out: directory, uid: process.getuid(), io: {
      readdir, lstat, realpath, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        assert.equal(removed, false);
        await unlink(file); removed = true;
        return stat(file);
      },
    }});
    const result = await s.run();
    assert.equal(removed, true);
    assert.equal(s.initial.code, 'ENOENT');
    assert.equal(s.initial.path, leaf);
    assert.equal(result.bytes, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.signals.length, 0);
    const rows = JSON.parse(await readFile(path.join(directory, 'firefox-cache-races.json')));
    assert.equal(rows.length, 1);
    assert.equal(rows[0].chargedBytes, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('body-cache recreated lstat then genuine unlink conservatively charges without resolving or reading the leaf', async () => {
  const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), 'body-cache-recreated-'));
  const cache = path.join(directory, 'firefox-body-cache');
  const leaf = path.join(cache, 'b'.repeat(32) + '.body');
  const bytes = Buffer.from('public synthetic body bytes');
  let observed;
  try {
    await mkdir(cache, {mode: 0o700});
    await writeFile(leaf, 'old public bytes', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({bodyCache: true, out: directory, uid: process.getuid(), io: {
      readdir, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        await unlink(file);
        let gone;
        try { await stat(file); } catch (error) { gone = error; }
        assert.equal(gone.code, 'ENOENT');
        await writeFile(file, bytes, {mode: 0o600, flag: 'wx'});
        throw gone;
      },
      lstat: async file => {
        const info = await lstat(file);
        if (file === leaf) { observed = info; await unlink(file); }
        return info;
      },
      realpath: async file => {
        assert.notEqual(file, leaf, 'Metrics must not follow the transient leaf');
        return realpath(file);
      },
    }});
    const result = await s.run();
    assert.ok(observed.isFile());
    assert.equal(observed.size, bytes.length);
    assert.equal(result.bytes, bytes.length);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.signals.length, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('Firefox VM ownership binds a nondefault UID while its original protocol default stays 1000', async () => {
  const original = firefoxSubject();
  assert.equal(original.context.process.getuid(), 1000);
  const s = firefoxSubject({uid: 31337});
  assert.equal(s.context.process.getuid(), 31337);
  const result = await s.run();
  assert.equal(result.observedFirefoxCacheRaceCount, 1);
  assert.equal(result.observedChromeCacheRaceCount, 0);
  const foreign = firefoxSubject({uid: 31337, cacheInfo: {uid: 1000}});
  await assert.rejects(foreign.run(), /Owned Firefox cache directory required/);
});

test('body-cache metrics cannot borrow Chrome or Brave backend ownership', async () => {
  for (const vendor of ['chrome', 'brave']) {
    const s = firefoxSubject({bodyCache: true, vendor});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.calls.read.length, 0);
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox owned profile accepts volatile leaves by domain, not a SQLite filename list', async () => {
  for (const name of ['storage.sqlite-journal', 'cookies.sqlite-wal', 'places.sqlite-shm',
    'prefs.js.tmp', 'nested/owned-cache-leaf']) {
    const s = firefoxSubject({profile: true, leaf: OUT + '/profile/' + name});
    const result = await s.run();
    assert.equal(result.bytes, 0);
    assert.equal(result.profileBytes, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.ok(s.calls.read.every(file => file === '/proc/501/stat'));
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox owned profile charges recreated regular and hardlinked leaves without following them', async () => {
  for (const nlink of [1, 2]) {
    const s = firefoxSubject({profile: true, recreated: {size: 123, nlink}});
    const result = await s.run();
    assert.equal(result.bytes, 123);
    assert.equal(result.profileBytes, 123);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.resolve.includes(s.leaf), false);
    assert.ok(s.calls.read.every(file => file === '/proc/501/stat'));
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox profile exception rejects other vendors and paths outside its exact owned subtree', async () => {
  for (const vendor of ['chrome', 'brave']) {
    const s = firefoxSubject({profile: true, vendor});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.calls.read.length, 0);
    assert.equal(s.calls.signals.length, 0);
  }
  for (const leaf of [OUT + '/profile-other/storage.sqlite-journal',
    OUT + '/unknown/storage.sqlite-journal', OUT + '/storage.sqlite-journal']) {
    const s = firefoxSubject({profile: true, leaf});
    await assert.rejects(s.run(), error => error === s.initial);
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox profile exception requires stable canonical owned directories and safe recreated metadata', async () => {
  for (const options of [
    {code: 'EACCES'}, {errorPath: '/foreign'}, {leafError: 'EACCES'},
    {redirect: OUT}, {redirect: OUT + '/profile'},
    {redirect: OUT + '/profile/nested'},
    {rootInfo: {uid: 999}}, {rootInfo: {mode: 0o40755}},
    {cacheInfo: {kind: 'symlink'}}, {cacheInfo: {uid: 999}},
    {cacheInfo: {mode: 0o40755}}, {parentInfo: {uid: 999}},
    {drift: 'root'}, {drift: 'cache'}, {drift: 'parent'},
    {recreated: {kind: 'symlink'}}, {recreated: {kind: 'directory'}},
    {recreated: {uid: 999}}, {recreated: {mode: 0o100666}},
  ]) {
    const s = firefoxSubject({profile: true, leaf: OUT + '/profile/nested/owned-leaf', ...options});
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox profile exception rejects process death, changed birth or executable and replaced identity', async () => {
  for (const options of [
    {noChild: true}, {shutdown: true}, {child: {exitCode: 0}},
    {child: {signalCode: 'SIGTERM'}}, {identity: {pid: 999}},
    {birthBefore: '9999'}, {birthAfter: '9999'},
    {exeBefore: '/foreign'}, {exeAfter: '/foreign'},
    {exitAfter: true}, {replaceIdentity: true},
  ]) {
    const s = firefoxSubject({profile: true, ...options});
    await assert.rejects(s.run());
    assert.equal(s.calls.signals.length, 0);
  }
});

test('Firefox profile missing leaves retain the same bounded ledger and existing profile byte cap', async () => {
  for (const [options, message] of [
    [{ledger: Array(4096).fill({})}, /Finite Firefox cache race count/],
    [{ledger: [{padding: 'x'.repeat(2 * 1024 * 1024)}]}, /Bounded Firefox cache race ledger/],
    [{recreated: {size: 512 * 1024 * 1024 + 1}}, /Profile exceeds 512 MiB/],
  ]) {
    const s = firefoxSubject({profile: true, ...options});
    await assert.rejects(s.run(), message);
    assert.equal(s.calls.signals.length, 0);
  }
});

test('actual outputBudget observes genuine Firefox profile journal unlink after readdir', async () => {
  const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), 'firefox-profile-unlink-'));
  const profile = path.join(directory, 'profile');
  const leaf = path.join(profile, 'storage.sqlite-journal');
  let removed = false;
  try {
    await mkdir(profile, {mode: 0o700});
    await writeFile(leaf, 'public synthetic journal bytes', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({profile: true, out: directory, uid: process.getuid(), io: {
      readdir, lstat, realpath, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        assert.equal(removed, false);
        await unlink(file); removed = true;
        return stat(file);
      },
    }});
    const result = await s.run();
    assert.equal(removed, true);
    assert.equal(s.initial.code, 'ENOENT');
    assert.equal(s.initial.path, leaf);
    assert.equal(result.bytes, 0);
    assert.equal(result.profileBytes, 0);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.signals.length, 0);
    assert.equal(JSON.parse(await readFile(path.join(directory, 'firefox-cache-races.json'))).length, 1);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('Firefox profile recreated lstat then genuine unlink charges the snapshot without following its leaf', async () => {
  const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), 'firefox-profile-recreated-'));
  const profile = path.join(directory, 'profile');
  const leaf = path.join(profile, 'cookies.sqlite-wal');
  const bytes = Buffer.from('public recreated profile bytes');
  let observed;
  try {
    await mkdir(profile, {mode: 0o700});
    await writeFile(leaf, 'old public bytes', {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({profile: true, out: directory, uid: process.getuid(), io: {
      readdir, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        await unlink(file);
        let gone;
        try { await stat(file); } catch (error) { gone = error; }
        assert.equal(gone.code, 'ENOENT');
        await writeFile(file, bytes, {mode: 0o600, flag: 'wx'});
        throw gone;
      },
      lstat: async file => {
        const info = await lstat(file);
        if (file === leaf) { observed = info; await unlink(file); }
        return info;
      },
      realpath: async file => {
        assert.notEqual(file, leaf, 'Metrics must not follow a profile leaf');
        return realpath(file);
      },
    }});
    const result = await s.run();
    assert.ok(observed.isFile());
    assert.equal(result.bytes, bytes.length);
    assert.equal(result.profileBytes, bytes.length);
    assert.equal(result.observedFirefoxCacheRaceCount, 1);
    assert.equal(result.observedChromeCacheRaceCount, 0);
    assert.equal(s.calls.signals.length, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

test('actual Firefox profile directory replacement during a leaf race fails closed without touching old content', async () => {
  const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), 'firefox-profile-replaced-'));
  const profile = path.join(directory, 'profile'), moved = path.join(directory, 'moved-profile');
  const leaf = path.join(profile, 'places.sqlite-shm');
  const bytes = 'old owned public profile bytes';
  let replaced = false;
  try {
    await mkdir(profile, {mode: 0o700});
    await writeFile(leaf, bytes, {mode: 0o600, flag: 'wx'});
    const s = firefoxSubject({profile: true, out: directory, uid: process.getuid(), io: {
      readdir, lstat, realpath, writeFile,
      stat: async file => {
        assert.equal(file, leaf);
        await rename(profile, moved);
        await mkdir(profile, {mode: 0o700});
        replaced = true;
        return stat(file);
      },
    }});
    await assert.rejects(s.run());
    assert.equal(replaced, true);
    assert.equal(await readFile(path.join(moved, path.basename(leaf)), 'utf8'), bytes);
    assert.equal(s.calls.signals.length, 0);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
});

for (const vendor of ['chrome', 'brave']) {
  test(`${vendor} profile walk does not install Firefox directory anchors`, async () => {
    const directory = await mkdtemp(path.join(process.env.UNIT_EVIDENCE ?? tmpdir(), vendor + '-profile-walk-'));
    const profile = path.join(directory, 'profile'), nested = path.join(profile, 'nested');
    const leaf = path.join(nested, 'ordinary-owned-profile.bin');
    const bytes = 'public existing vendor profile bytes';
    const anchors = new Set([profile, nested]), calls = [];
    try {
      await mkdir(profile, {mode: 0o700});
      await mkdir(nested, {mode: 0o700});
      await writeFile(leaf, bytes, {mode: 0o600, flag: 'wx'});
      const s = firefoxSubject({profile: true, vendor, out: directory, uid: process.getuid(), io: {
        readdir, stat, writeFile,
        lstat: async file => {
          if (anchors.has(file)) calls.push(['lstat', file]);
          return lstat(file);
        },
        realpath: async file => {
          if (anchors.has(file)) calls.push(['realpath', file]);
          return realpath(file);
        },
      }});
      const result = await s.run();
      assert.equal(result.bytes, Buffer.byteLength(bytes));
      assert.equal(result.profileBytes, Buffer.byteLength(bytes));
      assert.deepEqual(calls, [], 'Existing vendor traversal must not acquire Firefox profile anchors');
      assert.equal(result.observedFirefoxCacheRaceCount, 0);
      assert.equal(result.observedChromeCacheRaceCount, 0);
      assert.equal(s.calls.read.length, 0);
      assert.equal(s.calls.write.length, 0);
      assert.equal(s.calls.signals.length, 0);
      assert.equal(await readFile(leaf, 'utf8'), bytes);
    } finally {
      await rm(directory, {recursive: true, force: true});
    }
  });
}
