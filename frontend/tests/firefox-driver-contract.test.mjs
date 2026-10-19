import assert from 'node:assert/strict';
import {mkdir, mkdtemp, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {test} from 'node:test';

let sequence = 0;
async function loadDriver(name) {
  return import(new URL(`${name}?firefox-contract=${++sequence}`, import.meta.url));
}

async function ownTrace(t) {
  const previous = process.env.MTG_CDP_DIAGNOSTIC_DIR;
  const directory = await mkdtemp(path.join(tmpdir(), 'mtg-firefox-driver-'));
  process.env.MTG_CDP_DIAGNOSTIC_DIR = directory;
  t.after(async () => {
    if (previous === undefined) delete process.env.MTG_CDP_DIAGNOSTIC_DIR;
    else process.env.MTG_CDP_DIAGNOSTIC_DIR = previous;
    await rm(directory, {recursive: true});
  });
  return directory;
}

function fixture() {
  const commands = [], opened = [], known = new WeakSet();
  let initialized, destroyed, closed = 0, failure, closureFailure, arming;
  const socket = {
    send(text) {
      const message = JSON.parse(text);
      commands.push(message);
      const result = message.method === 'Runtime.evaluate' ? {result: {value: true}} : {};
      queueMicrotask(() => socket.onmessage({data: JSON.stringify({id: message.id, result})}));
    },
    close() { throw new Error('Native page must use native closure'); },
    assertHealthy() { if (failure) throw failure; },
  };
  const page = {
    id: 'owned-firefox-top', socket,
    uiInput: {async pressKey() {}, async clickAt() {}},
    async close() { closed++; if (closureFailure) throw closureFailure; },
    onChildInitialized(callback, onDestroyed) { initialized = callback; destroyed = onDestroyed; },
    validateChildInitialized(receipt) {
      assert.ok(known.has(receipt), 'Unrecognized native child receipt');
      return receipt;
    },
    async armFutureChildren(patterns) { commands.push({method: 'native-arm', params: patterns}); await arming; },
  };
  return {
    commands, opened,
    transport: {async open(url) { opened.push(url); return page; }, async close() {}},
    child(receipt, authentic = true) { if (authentic) known.add(receipt); initialized(receipt); },
    destroy(context) { destroyed(context); },
    fail(error) { failure = error; },
    failClosure(error) { closureFailure = error; },
    armWith(promise) { arming = promise; },
    get closed() { return closed; },
  };
}

for (const name of ['./browser-driver.mjs', './release-owned/browser-driver.mjs']) {
  test(`${name}: native Firefox uses its transport and closes the actual page`, async t => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    assert.deepEqual(f.opened, ['http://127.0.0.1:15173/']);
    assert.equal(await page.evaluate('true'), true);
    await page.close();
    assert.equal(f.closed, 1);
  });

  test(`${name}: binding rejects invalid or repeated transports`, async () => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    for (const value of [null, {}, {open() {}}, {close() {}}, {open: true, close() {}}]) {
      assert.throws(() => driver.configureFirefoxTransport(value), /once-bound Firefox transport/);
    }
    driver.configureFirefoxTransport(fixture().transport);
    assert.throws(() => driver.configureFirefoxTransport(fixture().transport), /once-bound Firefox transport/);
  });

  test(`${name}: native transport failure remains visible`, async t => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    const error = new Error('Native transport failed');
    f.fail(error);
    assert.throws(() => page.command('Network.enable'), value => value === error);
    await page.close();
  });

  test(`${name}: failed initialization closes only its native page`, async t => {
    const driver = await loadDriver(name);
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    f.fail(new Error('Native transport failed'));
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), /Native transport failed|Browser evaluation failed/);
    assert.equal(f.closed, 1);
  });

  test(`${name}: malformed native results never fall back to Chromium`, async t => {
    const driver = await loadDriver(name);
    const fetcher = t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport({async open() { return null; }, async close() {}});
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'));
    assert.equal(fetcher.mock.callCount(), 0);
  });

  test(`${name}: initialization and cleanup failures are both retained`, async t => {
    const driver = await loadDriver(name);
    const f = fixture();
    await ownTrace(t);
    driver.configureFirefoxTransport(f.transport);
    const opening = new Error('Native initialization failed');
    const closing = new Error('Native closure failed');
    f.fail(opening);
    f.failClosure(closing);
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), error => {
      assert.ok(error instanceof AggregateError);
      assert.equal(error.errors[0].cause ?? error.errors[0], opening);
      assert.equal(error.errors[1], closing);
      return true;
    });
    assert.equal(f.closed, 1);
  });
}

test('release driver arms native descendants before accepting genuine child receipts', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const f = fixture();
  await ownTrace(t);
  t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const patterns = [{urlPattern: '*', requestStage: 'Request'}];
  await page.enableOwnedIframeInterception(patterns);
  assert.deepEqual(f.commands.find(command => command.method === 'native-arm').params, patterns);
  assert.equal(f.commands.some(command => command.method === 'Target.setAutoAttach'), false);
  f.child({context: 'owned-child', parent: 'owned-firefox-top', generation: 1});
  await page.waitForInterceptions(1);
  f.destroy('owned-child');
  await page.waitForInterceptions();
  await page.close();
});

test('release driver rejects an unrecognized native child without fabricating initialization', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const f = fixture();
  await ownTrace(t);
  t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  await page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]);
  f.child({context: 'forged-child'}, false);
  assert.throws(() => page.assertInterceptionHealthy(), /Unrecognized native child receipt/);
  await page.close();
});

test('shared driver rejects unsupported passive CDP evidence instead of silently dropping it', async t => {
  const driver = await loadDriver('./browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const previous = process.env.MTG_PASSIVE_CDP_EVIDENCE;
  process.env.MTG_PASSIVE_CDP_EVIDENCE = '/not-a-native-firefox-evidence-directory';
  t.after(() => {
    if (previous === undefined) delete process.env.MTG_PASSIVE_CDP_EVIDENCE;
    else process.env.MTG_PASSIVE_CDP_EVIDENCE = previous;
  });
  const f = fixture();
  driver.configureFirefoxTransport(f.transport);
  await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), /Firefox.*passive CDP/);
  assert.deepEqual(f.opened, []);
});

for (const failClosure of [false, true]) {
  test(`release driver closes its native page when trace finalization fails (closure failure: ${failClosure})`, async t => {
    const driver = await loadDriver('./release-owned/browser-driver.mjs');
    const f = fixture();
    const directory = await ownTrace(t);
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    await rm(path.join(directory, 'cdp.jsonl'));
    await mkdir(path.join(directory, 'cdp.jsonl'));
    const closing = new Error('Native closure failed');
    if (failClosure) f.failClosure(closing);
    await assert.rejects(page.close(), error => {
      if (failClosure) {
        assert.ok(error instanceof AggregateError);
        assert.equal(error.errors[0].code, 'EISDIR');
        assert.equal(error.errors[1], closing);
      } else assert.equal(error.code, 'EISDIR');
      return true;
    });
    assert.equal(f.closed, 1);
  });
}

test('release driver closes a native page if diagnostic creation fails', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  const directory = await ownTrace(t);
  const occupied = path.join(directory, 'occupied');
  await writeFile(occupied, 'owned fixture');
  process.env.MTG_CDP_DIAGNOSTIC_DIR = occupied;
  driver.configureFirefoxTransport(f.transport);
  await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), {code: 'EEXIST'});
  assert.equal(f.closed, 1);
});

test('release driver awaits native arming acknowledgment', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  await ownTrace(t);
  let acknowledge, armed = false;
  f.armWith(new Promise(resolve => { acknowledge = resolve; }));
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const pending = page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]).then(() => { armed = true; });
  await Promise.resolve();
  assert.equal(armed, false);
  acknowledge();
  await pending;
  assert.equal(armed, true);
  await page.close();
});

test('release driver remains fail-closed after native arming rejects', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  await ownTrace(t);
  let reject;
  f.armWith(new Promise((resolve, fail) => { reject = fail; }));
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const pending = page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]);
  const error = new Error('Native registration failed');
  reject(error);
  await assert.rejects(pending, value => value === error);
  assert.throws(() => page.command('Runtime.evaluate'), value => value === error);
  await page.close();
});

test('shared driver exposes native uiInput without translating its result or error',async t=>{
 const driver=await loadDriver('./browser-driver.mjs'),f=fixture(),calls=[];
 const original=new Error('Native input failure'),result={native:'opaque'};
 const uiInput={async pressKey(key){calls.push(['key',key]);return result;},async clickAt(point){calls.push(['click',point]);throw original;}};
 const open=f.transport.open;f.transport.open=async url=>({...await open(url),uiInput});
 const fetcher=t.mock.method(globalThis,'fetch',()=>{throw Error('Unexpected Chromium discovery');});
 driver.configureFirefoxTransport(f.transport);const page=await driver.openBrowser('http://127.0.0.1:15173/');
 assert.equal(page.uiInput,uiInput);
 assert.equal(await page.uiInput.pressKey('Enter'),result);
 await assert.rejects(page.uiInput.clickAt({x:1.25,y:2.75}),error=>error===original);
 assert.deepEqual(calls,[['key','Enter'],['click',{x:1.25,y:2.75}]]);
 assert.equal(f.commands.some(m=>m.method.startsWith('Input.')),false);
 assert.equal(fetcher.mock.callCount(),0);await page.close();
});
for(const uiInput of [undefined,null,{}, {pressKey(){},clickAt:1}, {pressKey:1,clickAt(){}}]){
 test('shared driver rejects missing or malformed uiInput and closes its page: '+JSON.stringify(uiInput),async t=>{
  const driver=await loadDriver('./browser-driver.mjs'),f=fixture();
  const open=f.transport.open;f.transport.open=async url=>({...await open(url),uiInput});
  const fetcher=t.mock.method(globalThis,'fetch',()=>{throw Error('Unexpected Chromium discovery');});
  driver.configureFirefoxTransport(f.transport);
  await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'),/Firefox.*uiInput/);
  assert.equal(f.closed,1);assert.equal(fetcher.mock.callCount(),0);
 });
}

// Compile only the existing helper declarations as an inert ES module. No VM,
// browser startup, top-level scenario, application fetch, or DOM is executed.
async function callerHelpers(name,uiInput,command,evaluate){
 const {readFile}=await import('node:fs/promises');
 const source=await readFile(new URL(name,import.meta.url),'utf8');
 const take=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
 const declarations=name.includes('direct-combat')?
  take('  async function pointerClick(id)', '  // Exercise the native HTML drag'):
  name.includes('redesign')?
   take('async function capture(name)', 'async function viewport')+
   take('async function key(key','try {'):
   take('async function key(key','async function fit')+
   take('async function pointer(selector)','async function recoverDroppedResponse');
 const exports=name.includes('direct-combat')?'pointerClick':name.includes('redesign')?'key,pointerClick,capture':'key,pointer';
 const module=await import('data:text/javascript,'+encodeURIComponent(
  `export function bind(uiInput,command,evaluate){const evidence='inert';const card=id=>id;const writeFile=async()=>{};${declarations}\nreturn {${exports}};}`));
 return module.bind(uiInput,command,evaluate);
}
for(const name of ['./browser-ui-v2.mjs','./browser-ui-redesign.mjs','./browser-direct-combat.mjs']){
 test(name+': original Chromium keyboard and pointer command tuples are preserved',async()=>{
  const calls=[],point={x:10.125,y:20.875};
  const helpers=await callerHelpers(name,undefined,async(method,params)=>{calls.push({method,params});return {data:''};},async()=>point);
  if(helpers.key)for(const key of ['Enter','Escape','Tab']){
   calls.length=0;await helpers.key(key);
   assert.deepEqual(calls,['keyDown','keyUp'].map(type=>({method:'Input.dispatchKeyEvent',params:{type,key,code:key,
    ...(name.includes('v2')?{windowsVirtualKeyCode:({Enter:13,Escape:27,Tab:9})[key],...(key==='Enter'&&type==='keyDown'?{text:'\r'}:{})}:{})}})));
  }
  calls.length=0;await (helpers.pointer??helpers.pointerClick)('inert-selector');
  const move={method:'Input.dispatchMouseEvent',params:{type:'mouseMoved',...point}};
  const click=['mousePressed','mouseReleased'].map(type=>({method:'Input.dispatchMouseEvent',params:{type,...point,button:'left',clickCount:1}}));
  assert.deepEqual(calls,name.includes('direct-combat')?click:[move,...click]);
  if(helpers.capture){calls.length=0;await helpers.capture('inert');assert.deepEqual(calls.slice(0,2),[
   {method:'Input.dispatchKeyEvent',params:{type:'keyDown',key:'Escape',code:'Escape'}},
   {method:'Input.dispatchKeyEvent',params:{type:'keyUp',key:'Escape',code:'Escape'}}]);}
 });
 test(name+': Firefox takes only the explicit native gesture branch at unchanged geometry',async()=>{
  const calls=[],point={x:10.125,y:20.875};
  const uiInput={async pressKey(...args){if(args.length!==1)throw Error('Unsupported key options');calls.push(['key',args[0]]);},async clickAt(p){assert.equal(p,point);calls.push(['click',p]);}};
  const helpers=await callerHelpers(name,uiInput,async(method)=>{assert.equal(method,'Page.captureScreenshot');return {data:''};},async()=>point);
  if(helpers.key)for(const key of ['Enter','Escape','Tab'])await helpers.key(key);
  await (helpers.pointer??helpers.pointerClick)('inert-selector');
  assert.deepEqual(calls,[...(helpers.key?[['key','Enter'],['key','Escape'],['key','Tab']]:[]),['click',point]]);
  if(helpers.capture){await helpers.capture('inert');assert.deepEqual(calls.at(-1),['key','Escape']);}
  if(helpers.key){
   const before=calls.length;
   await assert.rejects(helpers.key('Enter','NumpadEnter'),/Unsupported key options/);
   await assert.rejects(helpers.key('Enter',undefined),/Unsupported key options/);
   assert.equal(calls.length,before,'Explicit key metadata must not be silently dropped');
  }
 });
}

// Use the actual driver return objects, never a source projection of the getter.
for (const name of ['./browser-driver.mjs', './release-owned/browser-driver.mjs']) {
  test(`${name}: actual CDP page exposes a readonly true filter capability bound to that page`, async t => {
    const driver = await loadDriver(name);
    await ownTrace(t);
    const previousOrigin = process.env.MTG_BROWSER_ORIGIN;
    process.env.MTG_BROWSER_ORIGIN = 'http://runtime.invalid';
    t.after(() => {
      if (previousOrigin === undefined) delete process.env.MTG_BROWSER_ORIGIN;
      else process.env.MTG_BROWSER_ORIGIN = previousOrigin;
    });
    const commands = [], requests = [];
    let closed = 0;
    class Socket {
      constructor(url) {
        assert.equal(url, 'ws://runtime.invalid');
        queueMicrotask(() => this.onopen?.());
      }
      send(raw) {
        const message = JSON.parse(raw); commands.push(message);
        const result = message.method === 'Runtime.evaluate' ? {result: {value: true}} : {};
        queueMicrotask(() => this.onmessage({data: JSON.stringify({id: message.id, result})}));
      }
      close() { closed++; }
    }
    const previousSocket = globalThis.WebSocket;
    globalThis.WebSocket = Socket;
    t.after(() => { globalThis.WebSocket = previousSocket; });
    t.mock.method(globalThis, 'fetch', async (url, options) => {
      requests.push([url, options]);
      if (url === 'http://runtime.invalid/json/new?http://ui.invalid') {
        assert.equal(options.method, 'PUT');
        return {json: async () => ({id: 'owned-cdp-capability', webSocketDebuggerUrl: 'ws://runtime.invalid'})};
      }
      assert.equal(url, 'http://runtime.invalid/json/close/owned-cdp-capability');
      return {};
    });
    const page = await driver.openBrowser('http://ui.invalid');
    try {
      const descriptor = Object.getOwnPropertyDescriptor(page, 'supportsFetchResourceTypeFilter');
      assert.equal(typeof descriptor?.get, 'function', 'Capability must be an own readonly getter');
      assert.equal(descriptor.set, undefined);
      const before = [commands.length, requests.length];
      assert.equal(page.supportsFetchResourceTypeFilter, true);
      assert.equal(descriptor.get.call({}), true);
      assert.throws(() => { page.supportsFetchResourceTypeFilter = false; }, TypeError);
      const laterTransport = fixture();
      driver.configureFirefoxTransport(laterTransport.transport);
      assert.equal(page.supportsFetchResourceTypeFilter, true, 'A later global binding cannot change this CDP page');
      assert.deepEqual(laterTransport.opened, []);
      assert.deepEqual([commands.length, requests.length], before, 'Reading capability must not issue a command or probe');
    } finally {
      await page.close();
    }
    assert.equal(closed, 1);
    assert.equal(requests.length, 2);
  });

  test(`${name}: actual bound Firefox page exposes a readonly false filter capability without CDP fallback`, async t => {
    const driver = await loadDriver(name), f = fixture();
    await ownTrace(t);
    const fetcher = t.mock.method(globalThis, 'fetch', () => { throw Error('No CDP discovery for a bound Firefox page'); });
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://ui.invalid');
    try {
      const descriptor = Object.getOwnPropertyDescriptor(page, 'supportsFetchResourceTypeFilter');
      assert.equal(typeof descriptor?.get, 'function', 'Capability must be an own readonly getter');
      assert.equal(descriptor.set, undefined);
      const before = f.commands.length;
      assert.equal(page.supportsFetchResourceTypeFilter, false);
      assert.equal(descriptor.get.call({supportsFetchResourceTypeFilter: true}), false);
      assert.throws(() => { page.supportsFetchResourceTypeFilter = true; }, TypeError);
      assert.equal(f.commands.length, before);
      assert.equal(fetcher.mock.callCount(), 0);
    } finally {
      await page.close();
    }
    assert.deepEqual(f.opened, ['http://ui.invalid']);
    assert.equal(f.closed, 1);
  });
}
