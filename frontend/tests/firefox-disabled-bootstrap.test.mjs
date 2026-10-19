// Real publisher/local files; supplied protocol replies are not native receipts.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createEnrollment} from './firefox-transport.mjs';

const apiOrigin = 'http://127.0.0.1:19000';
const frontendOrigin = 'http://127.0.0.1:15173';
const start = () => Number(fs.readFileSync('/proc/self/stat', 'utf8')
  .split(')').at(-1).trim().split(/\s+/)[19]);

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'firefox-bootstrap-unit-'));
  fs.chmodSync(directory, 0o700);
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const bindings = {directory, runNonce: '4'.repeat(32), sourceBinding: 'b'.repeat(64),
    apiOrigin, frontendOrigin};
  const file = path.join(directory, 'enrollment.json');
  return {directory, bindings, file, make: () => createEnrollment(bindings)};
}

function read(f) {
  assert.ok(fs.existsSync(f.file), 'The real publisher must publish bootstrap before returning');
  return JSON.parse(fs.readFileSync(f.file, 'utf8'));
}

function bootstrap(f) {
  assert.deepEqual(read(f), {schema_version: 1, generation: 0, enabled: false, episode: null,
    run_nonce: f.bindings.runNonce, source_binding: f.bindings.sourceBinding,
    api_origin: apiOrigin, frontend_origin: frontendOrigin, publisher_uid: process.getuid(),
    pid: process.pid, start_ticks: start(), native_top_context: null, armed_ns: '0', expires_ns: '0'});
}

function createReply(controller, id, context) {
  controller.recordCommand({id, method: 'browsingContext.create', params: {type: 'tab'}});
  const result = {context};
  assert.equal(controller.acceptReply({id, type: 'success', result}), result);
}

function intercept(controller, id, context) {
  controller.recordCommand({id, method: 'network.addIntercept', params: {contexts: [context],
    phases: ['beforeRequestSent', 'responseStarted']}});
}

test('constructor publishes exact generation-zero bootstrap with real publisher identity', t => {
  const f = fixture(t), controller = f.make();
  bootstrap(f);
  const info = fs.lstatSync(f.file);
  assert.ok(info.isFile() && !info.isSymbolicLink());
  assert.equal(info.uid, process.getuid());
  assert.equal(info.mode & 0o777, 0o600);
  assert.equal(info.nlink, 1);
  assert.deepEqual(fs.readdirSync(f.directory), ['enrollment.json']);
  assert.equal(controller.current(), null);
  assert.equal(controller.isArmed, false);
});

test('bootstrap becomes visible only through the existing owned atomic staging publication', t => {
  const f = fixture(t), rename = fs.renameSync;
  let staged;
  t.mock.method(fs, 'renameSync', (from, to) => {
    assert.equal(from, path.join(f.directory, 'enrollment.next'));
    assert.equal(to, f.file);
    assert.equal(fs.existsSync(to), false);
    const info = fs.lstatSync(from);
    assert.ok(info.isFile());
    assert.equal(info.nlink, 1);
    assert.equal(info.mode & 0o777, 0o600);
    staged = {dev: info.dev, ino: info.ino, bytes: fs.readFileSync(from)};
    return Reflect.apply(rename, fs, [from, to]);
  });
  f.make();
  bootstrap(f);
  assert.ok(staged, 'The actual publisher must use atomic staging, not a test-written control');
  const published = fs.lstatSync(f.file);
  assert.deepEqual([published.dev, published.ino], [staged.dev, staged.ino]);
  assert.deepEqual(fs.readFileSync(f.file), staged.bytes);
  assert.equal(fs.existsSync(path.join(f.directory, 'enrollment.next')), false);
});

test('disabled bootstrap confers no episode, context, or native-command authority', t => {
  const f = fixture(t), controller = f.make();
  bootstrap(f);
  const before = fs.readFileSync(f.file);
  assert.equal(controller.hasContext('unobserved-context'), false);
  assert.throws(() => controller.contextCreated({context: 'child', parent: 'unobserved-context'}));
  assert.throws(() => controller.recordCommand({id: 1, method: 'browsingContext.create', params: {type: 'tab'}}));
  assert.equal(controller.current(), null);
  assert.deepEqual(fs.readFileSync(f.file), before);
});

test('constructor refuses to adopt or replace an existing final control', t => {
  const f = fixture(t), original = Buffer.from('existing control is not owned by this publisher');
  fs.writeFileSync(f.file, original, {flag: 'wx', mode: 0o600});
  const info = fs.lstatSync(f.file);
  assert.throws(() => f.make());
  assert.deepEqual(fs.readFileSync(f.file), original);
  assert.equal(fs.lstatSync(f.file).ino, info.ino);
});

test('constructor refuses an existing staging leaf without deleting or reusing it', t => {
  const f = fixture(t), stage = path.join(f.directory, 'enrollment.next');
  fs.writeFileSync(stage, 'another publication', {flag: 'wx', mode: 0o600});
  assert.throws(() => f.make());
  assert.equal(fs.readFileSync(stage, 'utf8'), 'another publication');
  assert.equal(fs.existsSync(f.file), false);
});

test('invalid root permissions remain rejected before bootstrap publication', t => {
  const f = fixture(t);
  fs.chmodSync(f.directory, 0o755);
  assert.throws(() => f.make());
  assert.equal(fs.existsSync(f.file), false);
  assert.equal(fs.lstatSync(f.directory).mode & 0o777, 0o755);
});

test('first real episode remains inactive until the matching supplied native intercept ACK', async t => {
  const f = fixture(t), controller = f.make();
  bootstrap(f);
  await controller.withEnrolledBodyEpisode('human_vs_human', async () => {
    createReply(controller, 1, 'mock-top-1');
    bootstrap(f);
    intercept(controller, 2, 'mock-top-1');
    assert.equal(controller.current(), null);
    assert.throws(() => controller.acceptReply({id: 999, type: 'success', result: {intercept: 'wrong-ack'}}));
    bootstrap(f);
    const result = {intercept: 'mock-intercept-1'};
    assert.equal(controller.acceptReply({id: 2, type: 'success', result}), result);
    assert.equal(read(f).generation, 1);
    assert.equal(read(f).native_top_context, 'mock-top-1');
    assert.equal(controller.current().enabled, true);
    assert.equal(BigInt(read(f).expires_ns) - BigInt(read(f).armed_ns), 900_000_000_000n);
  });
  assert.equal(read(f).generation, 2);
  assert.equal(read(f).enabled, false);
  assert.equal(read(f).native_top_context, null);
});

test('bootstrap consumes none of the original six generations across the exact three windows', async t => {
  const f = fixture(t), controller = f.make(), observed = [];
  bootstrap(f);
  observed.push(read(f).generation);
  const episodes = ['human_vs_human', 'player_vs_ai', 'player_vs_ai-seat2'];
  for (const [index, episode] of episodes.entries()) {
    await controller.withEnrolledBodyEpisode(episode, async () => {
      createReply(controller, 1 + index * 2, 'mock-top-' + index);
      intercept(controller, 2 + index * 2, 'mock-top-' + index);
      controller.acceptReply({id: 2 + index * 2, type: 'success', result: {intercept: 'mock-intercept-' + index}});
      const row = read(f);
      assert.equal(row.episode, episode);
      assert.equal(row.enabled, true);
      assert.equal(BigInt(row.expires_ns) - BigInt(row.armed_ns), index ? 1_200_000_000_000n : 900_000_000_000n);
      observed.push(row.generation);
    });
    observed.push(read(f).generation);
    assert.equal(controller.current(), null);
  }
  assert.deepEqual(observed, [0, 1, 2, 3, 4, 5, 6]);
  assert.throws(() => controller.withEnrolledBodyEpisode('human_vs_human', async () => {}));
});

test('a replaced bootstrap inode cannot authorize the first enabled publication or owned deletion', async t => {
  const f = fixture(t), controller = f.make();
  bootstrap(f);
  const bytes = fs.readFileSync(f.file), replacement = path.join(f.directory, 'replacement');
  fs.writeFileSync(replacement, bytes, {flag: 'wx', mode: 0o600});
  fs.renameSync(replacement, f.file);
  await assert.rejects(controller.withEnrolledBodyEpisode('human_vs_human', async () => {
    createReply(controller, 1, 'mock-top');
    intercept(controller, 2, 'mock-top');
    controller.acceptReply({id: 2, type: 'success', result: {intercept: 'mock-intercept'}});
  }));
  assert.equal(controller.current(), null);
  assert.deepEqual(fs.readFileSync(f.file), bytes);
  assert.throws(() => controller.close());
  assert.deepEqual(fs.readFileSync(f.file), bytes);
});

test('a missing owned bootstrap cannot be silently recreated by first activation', async t => {
  const f = fixture(t), controller = f.make();
  bootstrap(f);
  fs.unlinkSync(f.file);
  await assert.rejects(controller.withEnrolledBodyEpisode('human_vs_human', async () => {
    createReply(controller, 1, 'mock-top');
    intercept(controller, 2, 'mock-top');
    controller.acceptReply({id: 2, type: 'success', result: {intercept: 'mock-intercept'}});
  }));
  assert.equal(fs.existsSync(f.file), false);
  assert.equal(controller.current(), null);
});

test('bootstrap publication errors remain the constructor error without a returned controller', t => {
  const f = fixture(t), failure = new Error('owned bootstrap rename failure');
  t.mock.method(fs, 'renameSync', () => { throw failure; });
  assert.throws(() => f.make(), error => error === failure);
  assert.equal(fs.existsSync(f.file), false);
});

test('closing before the first episode removes only the publisher-owned bootstrap', t => {
  const f = fixture(t), controller = f.make(), sentinel = path.join(f.directory, 'unrelated');
  bootstrap(f);
  fs.writeFileSync(sentinel, 'leave untouched', {flag: 'wx', mode: 0o600});
  controller.close();
  assert.equal(fs.existsSync(f.file), false);
  assert.equal(fs.readFileSync(sentinel, 'utf8'), 'leave untouched');
  assert.equal(controller.current(), null);
});
