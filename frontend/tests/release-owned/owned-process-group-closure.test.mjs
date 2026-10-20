import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

// PROTOCOL ONLY: actual source bodies, inert processes, filesystem and clock.
// No application, browser, real process, signal, listener, SQL or procfs access.
const launcher = readFileSync(new URL('./run-current-built-acceptance.mjs', import.meta.url), 'utf8');
const roles = ['build', 'preview', 'chromium', 'firefox', 'backend', 'ledger',
  'restart-fuser', 'closure-fuser'];
const deadSignals = [null, 'SIGTERM'];
const plain = value => JSON.parse(JSON.stringify(value));

function actualFunction(name, optional = false) {
  const found = launcher.match(new RegExp(`^(?:async )?function ${name}\\([^\\n]*\\) \\{\\n[\\s\\S]*?^\\}`, 'm'));
  if (!found && optional) return '';
  assert.ok(found, `Existing actual ${name} source must remain available`);
  return found[0];
}

function protocol(options = {}) {
  const context = vm.createContext({assert, path});
  const fixture = `
    const options = ${JSON.stringify(options)};
    const root='/owned/source', out='/owned/evidence/native-browser';
    const db='/owned/runtime/sql/api.db', allocations=new Set(), ports={};
    const model={now:0, groupAlive:options.groupAlive !== false,
      violations:[], signals:[], queries:[], writes:[], timers:new Map(),
      nextTimer:0, termExitAt:null, groupGoneAt:options.groupGoneAt ?? null,
      closureProven:false, deadlineCalls:[]};
    function violation(message) {
      model.violations.push(message);
      throw new Error('Inert fixture rejected an undeclared operation');
    }
    let resolveDone;
    const child={pid:701,label:options.role ?? 'firefox',
      exitCode:options.live || options.deadSignal ? null : 0,
      signalCode:options.live ? null : options.deadSignal ?? null,
      done:new Promise(resolve=>{resolveDone=resolve;})};
    const children=[child];
    if(!options.live) resolveDone();
    function refresh() {
      if(model.termExitAt !== null && model.now >= model.termExitAt) {
        model.termExitAt=null; child.exitCode=0; resolveDone();
        if(!options.survivor) model.groupAlive=false;
      }
      if(model.groupGoneAt !== null && model.now >= model.groupGoneAt) {
        model.groupGoneAt=null; model.groupAlive=false;
      }
    }
    const Date=class extends globalThis.Date {
      constructor(...args) { super(...(args.length ? args : [model.now])); }
      static now() { return model.now; }
    };
    function setTimeout(callback, milliseconds) {
      if(typeof callback !== 'function' || !Number.isSafeInteger(milliseconds)
          || milliseconds < 0 || milliseconds > 5000) violation('timer');
      const id=++model.nextTimer;
      model.timers.set(id,{at:model.now+milliseconds,callback}); return id;
    }
    function clearTimeout(id) { model.timers.delete(id); }
    const process={pid:100,kill(pid,signum) {
      if(pid !== -child.pid) violation('foreign process group');
      refresh();
      if(signum === 0) {
        model.queries.push({pid,at:model.now});
        if(options.queryCode) throw Object.assign(new Error('Inert observation unavailable'),
          {code:options.queryCode});
        if(!model.groupAlive) throw Object.assign(new Error('Inert absent group'),{code:'ESRCH'});
        return;
      }
      if(!['SIGTERM','SIGKILL'].includes(signum)) violation('signal kind');
      model.signals.push({pid,signum,at:model.now});
      if(child.exitCode !== null || child.signalCode !== null) {
        violation('nonzero signal after leader death');
      }
      if(signum === 'SIGTERM' && !options.ignoreTerm) {
        model.termExitAt=model.now+(options.termExitAfter ?? 0); refresh();
      }
      if(signum === 'SIGKILL') {
        child.signalCode='SIGKILL'; model.groupAlive=false; resolveDone();
      }
    }};
    async function deadline(promise,milliseconds,label) {
      if(milliseconds !== 2000 || label !== 'Owned KILL exit '+child.label)
        violation('changed original KILL deadline');
      model.deadlineCalls.push({milliseconds,label});
      let timer;
      try {
        return await Promise.race([promise,new Promise((_,reject)=>{
          timer=setTimeout(()=>reject(new Error('Inert deadline expired')),milliseconds);
        })]);
      } finally { clearTimeout(timer); }
    }
    async function storageInventory({closed}) {
      if(closed !== true) violation('storage mode');
      return {allowed:[],actual:[],receipts:child.label === 'backend' ? [{}] : []};
    }
    async function readdir(file) {
      if(file === '/proc' || file === path.dirname(db)) return [];
      if(file === out) return child.label === 'backend' ? ['server-closure-701.json'] : [];
      return violation('filesystem directory');
    }
    async function readFile(file) {
      if(file !== path.join(out,'server-closure-701.json') || child.label !== 'backend')
        violation('filesystem read');
      return JSON.stringify({denials:[],jobs:{},ordinary_pool_disposed:true,
        zero_checkouts:true,workers_empty:true,shutdown_admission_closed:true,
        no_emergency_dispose:true,canaries:[1,2,3],shutdown_complete:true});
    }
    async function writeFile(file,data) {
      if(!['CLOSURE.json','OUTPUT-BOUNDS.json'].some(name=>file === path.join(out,name)))
        violation('filesystem write');
      model.writes.push({name:path.basename(file),body:JSON.parse(data)});
    }
    async function checkFuser(label) {
      if(label !== 'closure-fuser') violation('fuser role');
      return {exit:1,stdout:'',stderr:''};
    }
    async function checkPins() {}
    async function outputBudget() { return {}; }
    function createServer() { return violation('unexpected listener'); }
    async function realpath() { return violation('unexpected realpath'); }
    async function readlink() { return violation('unexpected descriptor'); }
    async function stat() { return violation('unexpected stat'); }
    ${actualFunction('ownedGroupAbsent', true)}
    ${actualFunction('stop')}
    ${actualFunction('closedReceipt')}
    globalThis.subject={stop,closedReceipt};
    globalThis.model=model;
    globalThis.child=child;
    globalThis.advance=function() {
      const events=[...model.timers].map(([id,row])=>({id,at:row.at}));
      if(model.termExitAt !== null) events.push({id:null,at:model.termExitAt});
      events.sort((a,b)=>a.at-b.at);
      const next=events[0];
      if(!next) return false;
      model.now=next.at; refresh();
      if(next.id !== null) {
        const timer=model.timers.get(next.id); model.timers.delete(next.id);
        if(timer) timer.callback();
      }
      return true;
    };
  `;
  new vm.Script(fixture, {filename: 'owned-group-protocol-fixture.mjs'})
    .runInContext(context, {timeout: 1000});
  return {
    context,
    async run(operation) {
      let settled = false, error, value;
      Promise.resolve().then(operation).then(result => { value = result; settled = true; },
        failure => { error = failure; settled = true; });
      for (let turns = 0; turns < 8192 && !settled; turns++) {
        // Finish current Promise work before advancing a purely fake timer.
        for (let jobs = 0; jobs < 64; jobs++) await Promise.resolve();
        if (!settled) assert.equal(context.advance(), true, 'Protocol has unmodeled pending work');
      }
      assert.equal(settled, true, 'Protocol must settle within its finite fake-clock steps');
      assert.deepEqual(plain(context.model.violations), [], 'No foreign operation or post-death signal');
      assert.equal(context.model.timers.size, 0, 'Actual stop must clear its own fake timers');
      assert.ok(!error || !['ReferenceError', 'SyntaxError', 'TypeError'].includes(error.name),
        'Missing fixture bindings are not meaningful product rejection');
      return {error, value};
    },
    stop() { return this.run(() => context.subject.stop(context.child)); },
    close(requireOwnedIdentity = true) {
      return this.run(async () => {
        await context.subject.closedReceipt({requireOwnedIdentity});
        context.model.closureProven = true;
      });
    },
  };
}

test('[protocol] exited leaders with surviving groups reject stop for every declared child role', async () => {
  for (const role of roles) for (const deadSignal of deadSignals) {
    const p = protocol({role, deadSignal});
    const result = await p.stop();
    assert.ok(result.error, role + ': leader exit is not group closure');
    assert.equal(p.context.model.groupAlive, true);
    assert.deepEqual(plain(p.context.model.signals), []);
    assert.ok(p.context.model.now <= 5000, 'No extended group-drain budget');
  }
});

test('[protocol] already absent dead-leader groups pass stop without new nonzero signals', async () => {
  for (const role of roles) for (const deadSignal of deadSignals) {
    const p = protocol({role, deadSignal, groupAlive: false});
    const result = await p.stop();
    assert.equal(result.error, undefined);
    assert.deepEqual(plain(p.context.model.signals), []);
    assert.equal(p.context.model.now, 0);
  }
});

test('[protocol] a dead-leader group may drain naturally within the existing five seconds', async () => {
  const p = protocol({groupGoneAt: 750});
  const result = await p.stop();
  assert.equal(result.error, undefined);
  assert.equal(p.context.model.groupAlive, false, 'Do not return before genuine mocked absence');
  assert.ok(p.context.model.now >= 750 && p.context.model.now <= 5000);
  assert.ok(p.context.model.queries.length >= 2);
  assert.deepEqual(plain(p.context.model.signals), []);
});

test('[protocol] TERM leader exit still waits for its group without additional destructive signals', async () => {
  const p = protocol({live: true, survivor: true, groupGoneAt: 750});
  const result = await p.stop();
  assert.equal(result.error, undefined);
  assert.equal(p.context.child.exitCode, 0);
  assert.equal(p.context.model.groupAlive, false);
  assert.ok(p.context.model.now >= 750 && p.context.model.now <= 5000);
  assert.deepEqual(plain(p.context.model.signals).map(row => row.signum), ['SIGTERM']);
});

test('[protocol] leader wait and descendant drain share the original five-second window', async () => {
  const p = protocol({live: true, survivor: true, termExitAfter: 4500, groupGoneAt: 5500});
  const result = await p.stop();
  assert.ok(result.error, 'A fresh descendant timeout would extend the existing shutdown budget');
  assert.equal(p.context.child.exitCode, 0);
  assert.equal(p.context.model.groupAlive, true);
  assert.ok(p.context.model.now >= 4500 && p.context.model.now <= 5000);
  assert.deepEqual(plain(p.context.model.signals).map(row => row.signum), ['SIGTERM']);
});

test('[protocol] denied or unknown group observations reject stop without post-death signals', async () => {
  for (const queryCode of ['EPERM', 'EACCES', 'EIO']) {
    const p = protocol({queryCode});
    const result = await p.stop();
    assert.ok(result.error, queryCode + ': unknown is not absent');
    assert.deepEqual(plain(p.context.model.signals), []);
  }
});

test('[protocol] surviving groups cannot produce closedReceipt success for any role or vendor strictness', async () => {
  for (const role of roles) for (const deadSignal of deadSignals) for (const strict of [false, true]) {
    const p = protocol({role, deadSignal});
    const result = await p.close(strict);
    assert.ok(result.error, role + ': no leader-only closure qualification');
    assert.equal(p.context.model.closureProven, false);
    assert.deepEqual(plain(p.context.model.signals), []);
  }
});

test('[protocol] absent groups retain ordinary closedReceipt success for all roles and both vendor modes', async () => {
  for (const role of roles) for (const deadSignal of deadSignals) for (const strict of [false, true]) {
    const p = protocol({role, deadSignal, groupAlive: false});
    const result = await p.close(strict);
    assert.equal(result.error, undefined);
    assert.equal(p.context.model.closureProven, true);
    assert.deepEqual(plain(p.context.model.signals), []);
    assert.ok(p.context.model.writes.some(row => row.name === 'OUTPUT-BOUNDS.json'));
  }
});

test('[protocol] unknown group status cannot qualify closedReceipt in either vendor mode', async () => {
  for (const queryCode of ['EPERM', 'EACCES', 'EIO']) for (const strict of [false, true]) {
    const p = protocol({queryCode});
    const result = await p.close(strict);
    assert.ok(result.error, queryCode + ': closure must remain unproven');
    assert.equal(p.context.model.closureProven, false);
    assert.deepEqual(plain(p.context.model.signals), []);
  }
});

test('[protocol] live leaders retain one original TERM and normal successful shutdown for all roles', async () => {
  for (const role of roles) {
    const p = protocol({role, live: true});
    const result = await p.stop();
    assert.equal(result.error, undefined);
    assert.equal(p.context.child.exitCode, 0);
    assert.equal(p.context.model.groupAlive, false);
    assert.deepEqual(plain(p.context.model.signals).map(row => row.signum), ['SIGTERM']);
    assert.equal(p.context.model.now, 0);
  }
});

test('[protocol] live leaders ignoring TERM retain original KILL deadline and forced-failure result', async () => {
  for (const role of roles) {
    const p = protocol({role, live: true, ignoreTerm: true});
    const result = await p.stop();
    assert.ok(result.error);
    assert.match(result.error.message, /^Forced kill required:/);
    assert.equal(p.context.child.signalCode, 'SIGKILL');
    assert.equal(p.context.model.groupAlive, false);
    assert.deepEqual(plain(p.context.model.signals).map(row => row.signum), ['SIGTERM', 'SIGKILL']);
    assert.equal(p.context.model.now, 5000);
    assert.deepEqual(plain(p.context.model.deadlineCalls),
      [{milliseconds: 2000, label: 'Owned KILL exit ' + role}]);
  }
});
