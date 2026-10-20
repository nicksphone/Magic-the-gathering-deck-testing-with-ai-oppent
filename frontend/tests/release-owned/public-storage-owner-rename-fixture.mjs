// Existing launcher VM-extraction pattern; every subject filesystem API is inert.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

export const variants = ['public487'];
export const OUT = '/protocol/evidence/native-browser';
export const PID = 301;
export const EPOCH = 'a'.repeat(32);
export const TEMP = `${OUT}/storage-owner-${PID}-${EPOCH}.tmp`;
export const FINAL = TEMP.replace(/\.tmp$/, '.json');
const ROOT = '/protocol/source';
const DB = '/protocol/runtime/sql/api.db';
const MEDIA = ROOT + '/backend/card_data/image_cache';
const CACHE = OUT + '/profile/Default/Cache/Cache_Data';
const CHROME_LEAF = CACHE + '/abcdef0123456789_0';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

const launcher = readFileSync(new URL('./run-current-built-acceptance.mjs', import.meta.url), 'utf8');

function functionText(name) {
  const found = launcher.match(new RegExp(`^(?:async )?function ${name}\\([^\\n]*\\) \\{\\n[\\s\\S]*?^\\}`, 'm'));
  assert.ok(found, `Public launcher needs actual ${name}(), not a fixture projection`);
  return found[0];
}

export function failure(code, file) {
  return Object.assign(new Error(`inert ${code}`), {code, path: file});
}

export function subject(variant, options = {}) {
  assert.equal(variant, 'public487');
  const methods = ['outputBudget', 'missingLiveChromeCacheLeaf', 'storageReceipts'];
  const receipt = {
    pid: PID, start_ticks: 3010, epoch: EPOCH, stage: 'ready',
    lock: {path: DB + '.capacity-owner.lock', identity: [7, 99], bytes: 0},
    backups: [{path: DB + '.before-capacity-' + EPOCH + '.db', sha256: 'd'.repeat(64)}],
    registered: true, owner_fd: 9, ready: true, admissions_open: true,
    producers: 0, records: [], ...options.receipt,
  };
  const bytes = Buffer.from(JSON.stringify(receipt));
  const files = new Map();
  const calls = {readdir: [], stat: [], lstat: [], read: [], write: [], signals: [], forbidden: []};
  const temp = options.temp ?? TEMP;
  const initial = failure(options.code ?? 'ENOENT', options.errorPath ?? temp);
  const second = failure('ENOENT', temp);
  let tempStats = 0, finalStats = 0;
  const file = (data, extra = {}) => ({data, size: data.length, uid: 1000,
    gid: 1000, mode: 0o100600, nlink: 1, dev: 7, ino: 15, kind: 'file', ...extra});
  const finalFile = () => file(bytes, {ino: 16, ...options.finalInfo});
  const rename = () => {
    files.delete(temp);
    if (!options.missingFinal) files.set(FINAL, finalFile());
    if (options.recreated || options.secondRace) files.set(temp, file(Buffer.from('new-owned-stage'), {ino: 17}));
  };
  if (options.oldFinal) files.set(FINAL, finalFile());
  if (options.stable) files.set(FINAL, finalFile());
  else files.set(temp, file(bytes));
  for (const [name, size] of options.extraFiles ?? [])
    files.set(OUT + '/' + name, file(Buffer.from('public'), {size}));
  if (options.chrome) files.set(CHROME_LEAF, file(Buffer.from('cache')));

  const directories = () => {
    const result = new Set([OUT, MEDIA, CACHE]);
    for (const name of files.keys()) {
      for (let parent = path.dirname(name); parent.startsWith(OUT); parent = path.dirname(parent)) {
        result.add(parent);
        if (parent === OUT) break;
      }
    }
    return result;
  };
  const info = (row, opts = {}) => {
    const result = {...row};
    for (const key of ['mode', 'uid', 'gid', 'nlink', 'dev', 'ino', 'size']) {
      const value = row[key] ?? 0;
      result[key] = opts.bigint ? BigInt(value) : value;
    }
    result.isFile = () => row.kind === 'file';
    result.isDirectory = () => row.kind === 'directory';
    result.isSymbolicLink = () => row.kind === 'symlink';
    return result;
  };
  const lookup = (name, opts = {}) => {
    if (files.has(name)) return info(files.get(name), opts);
    if (directories().has(name)) return info({kind: 'directory', uid: 1000,
      gid: 1000, dev: 7, ino: 2, mode: 0o40700, nlink: 2, size: 0}, opts);
    throw failure('ENOENT', name);
  };
  const readdir = async (directory, opts = {}) => {
    calls.readdir.push(directory);
    if (directory === MEDIA) return [];
    assert.ok(directories().has(directory), `Undeclared mock directory: ${directory}`);
    const rows = new Map();
    for (const name of [...directories(), ...files.keys()]) {
      if (path.dirname(name) !== directory) continue;
      const leaf = path.basename(name), row = files.get(name);
      rows.set(leaf, {name: leaf, isDirectory: () => !row,
        isFile: () => row?.kind === 'file', isSymbolicLink: () => row?.kind === 'symlink'});
    }
    return opts.withFileTypes ? [...rows.values()] : [...rows.keys()];
  };
  const stat = async (name, opts) => {
    calls.stat.push(name);
    if (name === temp && !options.stable) {
      tempStats++;
      if (tempStats === 1) { rename(); throw initial; }
      if (options.secondRace && tempStats === 2) { rename(); throw second; }
    }
    if (options.chrome && name === CHROME_LEAF) {
      files.delete(name);
      throw failure('ENOENT', name);
    }
    if (name === FINAL) finalStats++;
    return lookup(name, opts);
  };
  const lstat = async (name, opts) => {
    calls.lstat.push(name);
    if (name === FINAL && options.finalPermission) throw options.finalPermission;
    return lookup(name, opts);
  };
  const readFile = async name => {
    calls.read.push(name);
    if (/^\/proc\/\d+\/stat$/.test(name)) {
      const fields = Array(23).fill('0'); fields[19] = '4010';
      return `401 (inert) ${fields.join(' ')}`;
    }
    assert.ok(files.has(name), 'Mock reads may not escape declared leaves');
    if (files.get(name).kind === 'symlink') {
      calls.forbidden.push('follow-final-symlink');
      throw failure('ELOOP', name);
    }
    return files.get(name).data;
  };
  const children = options.noProducer ? [] : [{label: 'backend', pid: PID,
    startTicks: 3010, exitCode: null, signalCode: null}];
  if (options.chrome) children.push({label: 'chromium', pid: 401,
    exitCode: null, signalCode: null,
    budgetIdentity: {pid: 401, startTicks: '4010', exe: '/protocol/chrome'}});
  const context = vm.createContext({assert, path, Buffer, digest: hash,
    readdir, stat, lstat, readFile,
    realpath: async name => name === '/proc/401/exe' ? '/protocol/chrome'
      : options.redirectRoot && name === OUT ? '/foreign' : name,
    writeFile: async (name, data) => {
      calls.write.push(name); assert.ok(name.startsWith(OUT + '/'));
      files.set(name, file(Buffer.from(data)));
    },
    storageInventory: async () => ({bytes: options.storageBytes ?? 0}),
    process: {getuid: () => 1000, pid: 201,
      kill: (...args) => calls.signals.push(args)},
    children});
  const declarations = `const root=${JSON.stringify(ROOT)},out=${JSON.stringify(OUT)},db=${JSON.stringify(DB)};
    const ownerLock=db+'.capacity-owner.lock';
    const ownerEpochs=new Map(),closedBackupHashes=new Map();
    let lockIdentity,shuttingDown=false,backendReady=true;
    let backend=children.find(child=>child.label==='backend');`;
  const code = declarations + '\n' + methods.map(functionText).join('\n') +
    '\nglobalThis.subject={outputBudget,storageReceipts};';
  new vm.Script(code, {filename: 'actual-pinned-budget-functions.mjs'}).runInContext(context);
  return {run: () => context.subject.outputBudget(), context, calls, initial, second,
    files, bytes, temp, get tempStats() { return tempStats; },
    get finalStats() { return finalStats; },
    expectedBytes: () => [...files.values()].reduce((sum, row) => sum + row.size, 0)};
}
