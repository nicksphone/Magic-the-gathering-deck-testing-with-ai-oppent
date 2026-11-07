import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {openBrowser} from './browser-driver.mjs';

const origin = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15177';
const browser = await openBrowser(origin + '/tests/ui-clarity.html');
const {evaluate, waitFor, click, command, close, uiInput} = browser;
const dock = '#turn-commands', pass = `${dock} button:not([form]):not(#automatic-play-toggle)`;
const submit = `${dock} button[type="submit"]`;
const labels = {creature: 'Creature target', attack: 'Attack draft', block: 'Block draft'};
async function key(name, code, modifiers = 0) {
  if (uiInput) return uiInput.pressKey(name);
  await command('Input.dispatchKeyEvent', {type: 'keyDown', key: name, code: name, windowsVirtualKeyCode: code, modifiers,
    ...(name === 'Enter' ? {text: '\r', unmodifiedText: '\r'} : {})});
  await command('Input.dispatchKeyEvent', {type: 'keyUp', key: name, code: name, windowsVirtualKeyCode: code, modifiers});
}
async function pointer(selector) {
  const point = await evaluate(`(() => {const e = document.querySelector(${JSON.stringify(selector)});
    if (!e || e.matches(':disabled')) throw Error('Missing/enabled control: ' + ${JSON.stringify(selector)});
    e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
    const hit = document.elementFromPoint(x, y);
    if (!e.contains(hit)) {
      const describe = n => {if (!n) return null; const b=n.getBoundingClientRect(); return {tag:n.tagName,id:n.id,class:n.className,
        rect:{x:b.x,y:b.y,width:b.width,height:b.height},position:getComputedStyle(n).position,zIndex:getComputedStyle(n).zIndex};};
      const ancestors=[]; for(let n=hit;n && ancestors.length<8;n=n.parentElement) ancestors.push(describe(n));
      throw Error('Control is obscured '+JSON.stringify({selector:${JSON.stringify(selector)},point:{x,y},target:describe(e),hit:describe(hit),ancestors,
        focus:describe(document.activeElement),dock:describe(document.querySelector('#turn-commands')),scrollY,viewport:{width:innerWidth,height:innerHeight},
        rootZoom:getComputedStyle(document.documentElement).zoom,preview:describe(document.querySelector('.card-hover-preview')),
        previewPinned:document.querySelector('.card-hover-preview')?.getAttribute('data-pinned') ?? null}));
    } return {x, y};})()`);
  if (uiInput) return uiInput.clickAt(point.x, point.y);
  await command('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
  await command('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
}
async function reset(scenario, seat) {
  await click('Fixture seat ' + seat); await click('Reset ' + labels[scenario]);
  await waitFor(`window.fixtureScenario === '${scenario}' && window.fixtureSeat === ${seat} && !window.fixtureActions.length && document.querySelector('${dock}')`);
  await evaluate('window.dockSubmitEvents = []');
}
async function geometry() {
  await waitFor(`(() => {const e = document.querySelector('${dock}'); return e && parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--turn-command-space')) === e.offsetHeight + 24;})()`);
  const result = await evaluate(`(() => {const e = document.querySelector('${dock}'), r = e.getBoundingClientRect(), root = getComputedStyle(document.documentElement);
    return {fixed: getComputedStyle(e).position, top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height,
      width: innerWidth, viewport: innerHeight, zoom: Number(root.zoom) || 1, scroll: scrollY,
      overflow: document.documentElement.scrollWidth > innerWidth + 1, reserve: parseFloat(root.getPropertyValue('--turn-command-space')),
      padding: parseFloat(getComputedStyle(document.querySelector('main.layout')).paddingBottom),
      targets: [...e.querySelectorAll('button,a')].map(n => {const b=n.getBoundingClientRect(); return [b.width,b.height];})};})()`);
  assert.equal(result.fixed, 'fixed'); assert.equal(result.overflow, false);
  assert.ok(result.top >= 0 && result.left >= 0 && result.right <= result.width + 1, JSON.stringify(result));
  assert.ok(result.bottom <= result.viewport + 1 && result.viewport - result.bottom <= 32 * result.zoom, JSON.stringify(result));
  assert.ok(result.padding >= result.reserve - 1 && result.reserve * result.zoom >= result.height + 23 * result.zoom, 'Layout-unit reservation provides physical dock clearance at actual zoom');
  assert.ok(result.targets.length >= 2 && result.targets.every(([w,h]) => w >= 44 && h >= 44), 'Dock targets are at least 44px');
  return result;
}
async function focusVisible(selector) {
  await waitFor(`document.activeElement === document.querySelector(${JSON.stringify(selector)})`);
  assert.equal(await evaluate(`(() => {const r=document.activeElement.getBoundingClientRect(), d=document.querySelector('${dock}').getBoundingClientRect();
    return r.top >= 0 && r.bottom <= d.top && r.left >= 0 && r.right <= innerWidth + 1;})()`), true, 'Focused target/payment must clear the dock');
}
async function committed(type, fields, form) {
  await waitFor('window.fixtureActions.length === 1');
  assert.deepEqual(await evaluate('window.fixtureActions'), [{type, ...fields}]);
  assert.deepEqual(await evaluate('window.dockSubmitEvents'), form ? [form] : []);
}
try {
  await waitFor(`window.fixtureState && document.querySelector('${dock}') && document.querySelector('#match-controls > fieldset')`);
  await evaluate("window.dockSubmitEvents=[];document.addEventListener('submit',e=>window.dockSubmitEvents.push(e.target.id))");
  for (const [width,height,zoom] of [[1440,900,1], [390,844,1], [720,400,1], [1440,900,2]]) {
    await command('Emulation.setDeviceMetricsOverride', {width,height,deviceScaleFactor:1,mobile:false});
    await evaluate(`document.documentElement.style.zoom='${zoom}'`);
    await reset('creature', 1); await evaluate('scrollTo(0,0)'); const before = await geometry();
    await evaluate('scrollTo(0,document.documentElement.scrollHeight)');
    await waitFor('scrollY > 100'); const after = await geometry();
    assert.ok(Math.abs(before.top-after.top) <= 1 && Math.abs(before.bottom-after.bottom) <= 1, 'Dock remains viewport-anchored after real scrolling');
    await pointer('[data-hand-card-id="spell"] button[aria-describedby="cast-target-help-spell"]'); await focusVisible('#cast-target-spell');
    await pointer('#cast-target-spell'); await key('Escape',27); await focusVisible('#cast-target-spell');
    await reset('attack', 1); await click('Toggle attack payment');
    await pointer('[data-card-id="attacker"]');
    const payment = '#attack-declaration select[aria-label^="Attack payment 1"]';
    await waitFor(`document.querySelector(${JSON.stringify(payment)}) && document.querySelector('${submit}').matches(':disabled')`);
    await pointer(payment); await key('Escape',27); await focusVisible(payment);
    assert.equal(await evaluate('window.fixtureActions.length'), 0);
    await geometry();
    if (process.env.MTG_UI_EVIDENCE) {
      await mkdir(process.env.MTG_UI_EVIDENCE,{recursive:true});
      const shot=await command('Page.captureScreenshot',{format:'png'});
      await writeFile(`${process.env.MTG_UI_EVIDENCE}/command-dock-${width}x${height}-zoom${zoom}.png`,Buffer.from(shot.data,'base64'));
    }
  }
  await evaluate("document.documentElement.style.zoom='1'");
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  for (const seat of [1,2]) {
    await reset('creature',seat);
    assert.equal(await evaluate("document.querySelectorAll('#automatic-play-toggle').length"),1);
    assert.equal(await evaluate("[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='Pass Priority').length"),1);
    await pointer(pass); await committed('pass_priority',{});
    await reset('creature',seat); await pointer('#automatic-play-toggle'); await committed('toggle_auto',{});
    for (const flag of ['busy','AI actor','required choice']) {
      await reset('attack',seat); await click('Toggle '+flag);
      await waitFor(`document.querySelector('${pass}').matches(':disabled')`);
      assert.equal(await evaluate('window.fixtureActions.length'),0);
      if (flag === 'busy') assert.equal(await evaluate(`document.querySelector('${dock}').closest('fieldset').disabled && [...document.querySelectorAll('${dock} button')].every(e=>e.matches(':disabled'))`),true);
      else assert.equal(await evaluate(`document.querySelector('${submit}') === null`),true);
      if (flag === 'required choice') {
        assert.equal(await evaluate(`document.querySelector('${dock} .turn-command-primary').getAttribute('href')`),'#match-controls');
        await pointer(`${dock} a`); await waitFor("location.hash === '#match-controls'");
        assert.equal(await evaluate('window.fixtureActions.length'),0);
      }
    }
    await reset('attack',seat); await pointer(submit); await committed('attack',{attackers:[],attackTargets:{},bands:[]},'attack-declaration');
    await reset('attack',seat); await click('Toggle attack payment'); await pointer('[data-card-id="attacker"]');
    await waitFor(`document.querySelector('${submit}').matches(':disabled')`);
    const payment='#attack-declaration select[aria-label^="Attack payment 1"]';
    await pointer(payment); await key('Escape',27); await key('ArrowDown',40); await key('Enter',13);
    await waitFor(`document.querySelector(${JSON.stringify(payment)}).value === 'W' && !document.querySelector('${submit}').matches(':disabled')`);
    assert.equal(await evaluate(`document.querySelector('${submit}').form.id`),'attack-declaration');
    await pointer(submit); await committed('attack',{attackers:['attacker'],attackTargets:{},bands:[]},'attack-declaration');
    await reset('block',seat); await pointer('[data-card-id="blocker"]');
    assert.deepEqual(await evaluate('window.fixtureDraft.blocks'),{});
    await pointer(submit); await committed('block',{blocks:{}},'block-declaration');
    assert.deepEqual(await evaluate('window.fixtureDraft.blocks'),{},'Missing assignment never auto-selects an attacker');
    await reset('block',seat); await pointer('[data-card-id="blocker"]'); await pointer('[data-card-id="incoming"]');
    await waitFor("window.fixtureDraft.blocks.incoming?.includes('blocker')");
    assert.equal(await evaluate(`document.querySelector('${submit}').form.id`),'block-declaration');
    await pointer(submit); await committed('block',{blocks:{incoming:['blocker']}},'block-declaration');
    await reset('creature',seat); await pointer(pass);
    const focused=[];
    for(let i=0;i<4;i++){await key('Tab',9);focused.push(await evaluate(`({id:document.activeElement.id,dock:!!document.activeElement.closest('${dock}'),tag:document.activeElement.tagName})`));}
    assert.ok(focused.some(value=>!value.dock),'Tab exits the dock rather than trapping focus');
    assert.equal(await evaluate('window.fixtureActions.length'),1,'Tab does not dispatch an action');
    assert.equal(await evaluate('window.fixtureState.priority_player'),seat);
    assert.equal(await evaluate('window.fixtureState.revision'),7);
  }
  assert.deepEqual(await evaluate("performance.getEntriesByType('resource').filter(e=>new URL(e.name).pathname.startsWith('/api/')).map(e=>e.name)"),[]);
  console.log('PASS synthetic command dock: viewport/scroll/zoom, reserved height, native submits/payments, both seats, busy/AI/required choice, focus and tab exit; no engine/API/gameplay qualification');
} finally {
  await close();
}
