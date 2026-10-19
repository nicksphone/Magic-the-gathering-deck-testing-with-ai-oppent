// Local fault injection around genuine owned writes, not native/App qualification.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createEnrollment} from './firefox-transport.mjs';

function fds() {
  return fs.readdirSync('/proc/self/fd').flatMap(fd => {
    try { return [[fd, fs.readlinkSync('/proc/self/fd/' + fd)]]; }
    catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  }).sort(([a], [b]) => Number(a) - Number(b));
}

for (const mode of ['write', 'file-fsync', 'rename', 'directory-fsync']) {
  test(`initial ${mode} failure preserves the error and cleans only its own publication`, t => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'firefox-bootstrap-fault-'));
    fs.chmodSync(directory, 0o700);
    t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
    fs.writeFileSync(path.join(directory, 'unrelated'), 'retain', {mode: 0o600, flag: 'wx'});
    const failure = new Error('injected initial publication failure');
    const method = mode === 'write' ? 'writeFileSync' : mode === 'rename' ? 'renameSync' : 'fsyncSync';
    const original = fs[method];
    t.mock.method(fs, method, (...args) => {
      if (mode === 'rename' || mode === 'write' && typeof args[0] === 'number' ||
          mode === 'file-fsync' && fs.fstatSync(args[0]).isFile() ||
          mode === 'directory-fsync' && fs.fstatSync(args[0]).isDirectory()) throw failure;
      return Reflect.apply(original, fs, args);
    });
    const before = fds();
    assert.throws(() => createEnrollment({directory, runNonce: '4'.repeat(32),
      sourceBinding: 'b'.repeat(64), apiOrigin: 'http://127.0.0.1:19000',
      frontendOrigin: 'http://127.0.0.1:15173'}), error => error === failure);
    assert.deepEqual(fs.readdirSync(directory), ['unrelated']);
    assert.equal(fs.readFileSync(path.join(directory, 'unrelated'), 'utf8'), 'retain');
    assert.deepEqual(fds(), before);
  });
}

for (const mode of ['replace-stage', 'replace-final', 'unlink-denied']) {
  test(`initial publication ${mode} reports unknown cleanup without deleting foreign leaves`, t => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'firefox-bootstrap-unknown-'));
    fs.chmodSync(directory, 0o700);
    t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
    const primary = new Error('injected startup failure'), cleanup = new Error('injected unlink failure');
    const rename = fs.renameSync, write = fs.writeFileSync, unlink = fs.unlinkSync;
    const stage = path.join(directory, 'enrollment.next'), final = path.join(directory, 'enrollment.json');
    const foreign = mode === 'replace-stage' ? stage : final;
    let foreignIdentity;
    if (mode === 'replace-stage') {
      t.mock.method(fs, 'writeFileSync', (...args) => {
        if (typeof args[0] === 'number') {
          Reflect.apply(rename, fs, [stage, path.join(directory, 'moved-owned')]);
          Reflect.apply(write, fs, [stage, 'foreign', {flag: 'wx', mode: 0o600}]);
          foreignIdentity = fs.statSync(stage).ino;
          throw primary;
        }
        return Reflect.apply(write, fs, args);
      });
    } else {
      t.mock.method(fs, 'renameSync', (...args) => {
        if (mode === 'replace-final') {
          Reflect.apply(rename, fs, args);
          Reflect.apply(rename, fs, [final, path.join(directory, 'moved-owned')]);
          fs.writeFileSync(final, 'foreign', {flag: 'wx', mode: 0o600});
          foreignIdentity = fs.statSync(final).ino;
        }
        throw primary;
      });
      if (mode === 'unlink-denied') t.mock.method(fs, 'unlinkSync', file => {
        if (file === stage) throw cleanup;
        return Reflect.apply(unlink, fs, [file]);
      });
    }
    const before = fds();
    assert.throws(() => createEnrollment({directory, runNonce: '4'.repeat(32),
      sourceBinding: 'b'.repeat(64), apiOrigin: 'http://127.0.0.1:19000',
      frontendOrigin: 'http://127.0.0.1:15173'}), error =>
      error instanceof AggregateError && error.errors[0] === primary && error.errors.length === 2);
    assert.deepEqual(fds(), before);
    if (mode !== 'unlink-denied') {
      assert.equal(fs.readFileSync(foreign, 'utf8'), 'foreign');
      assert.equal(fs.statSync(foreign).ino, foreignIdentity);
      assert.equal(fs.existsSync(path.join(directory, 'moved-owned')), true);
    } else {
      assert.equal(fs.existsSync(stage), true);
    }
  });
}

for (const mode of ['still-owned', 'closed-and-reused']) {
  test(`initial success-close ${mode} preserves descriptor ownership`, t => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'firefox-bootstrap-close-'));
    fs.chmodSync(directory, 0o700);
    t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
    const sentinel = path.join(directory, 'unrelated');
    fs.writeFileSync(sentinel, 'retain', {mode: 0o600, flag: 'wx'});
    const primary = new Error('injected success-close failure'), close = fs.closeSync;
    let intercepted = false, originalFD, originalInode, replacementFD;
    t.mock.method(fs, 'closeSync', fd => {
      const info = fs.fstatSync(fd);
      if (!intercepted && info.isFile() && fs.readlinkSync('/proc/self/fd/' + fd)
          === path.join(directory, 'enrollment.json')) {
        intercepted = true; originalFD = fd; originalInode = info.ino;
        if (mode === 'closed-and-reused') {
          Reflect.apply(close, fs, [fd]);
          replacementFD = fs.openSync(sentinel, 'r');
          assert.equal(replacementFD, fd, 'This protocol fault must actually reuse the closed number');
        }
        throw primary;
      }
      return Reflect.apply(close, fs, [fd]);
    });
    const before = fds();
    try {
      const invoke = () => createEnrollment({directory, runNonce: '4'.repeat(32),
        sourceBinding: 'b'.repeat(64), apiOrigin: 'http://127.0.0.1:19000',
        frontendOrigin: 'http://127.0.0.1:15173'});
      if (mode === 'still-owned') {
        assert.throws(invoke, error => error === primary);
        assert.deepEqual(fs.readdirSync(directory), ['unrelated']);
        assert.deepEqual(fds(), before);
      } else {
        assert.throws(invoke, error => error instanceof AggregateError && error.errors[0] === primary);
        assert.equal(fs.fstatSync(replacementFD).ino, fs.statSync(sentinel).ino);
        assert.equal(fs.readFileSync(replacementFD, 'utf8'), 'retain');
      }
      assert.equal(intercepted, true);
    } finally {
      // Fault-fixture cleanup follows assertions and cannot turn a leak into a pass.
      for (const fd of [replacementFD, originalFD]) if (fd !== undefined) {
        try {
          const info = fs.fstatSync(fd);
          if (fd === replacementFD || info.ino === originalInode) Reflect.apply(close, fs, [fd]);
        } catch (error) { if (error.code !== 'EBADF') throw error; }
      }
    }
    assert.deepEqual(fds(), before);
  });
}
