import assert from 'node:assert/strict';
import {mkdtemp, writeFile, readdir, lstat, stat, rename, readFile, rm} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {test} from 'node:test';
import {subject, variants, OUT, TEMP, FINAL, EPOCH, failure} from './public-storage-owner-rename-fixture.mjs';

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
