import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture/direct-combat?seat=${seat}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const {evaluate, command, waitFor, click, reload, close} = browser;
  const card = id => `.card[data-combat-role][aria-label^="${({hero:'Benalish Hero',angel:'Serra Angel',elf:'Llanowar Elves',bears:'Grizzly Bears'})[id]};"]`;
  async function pointerClick(id) {
    const point = await evaluate(`(() => { const node=document.querySelector(${JSON.stringify(card(id))}); node.scrollIntoView({block:'center'}); const box=node.getBoundingClientRect(); return {x:box.x+box.width/2,y:box.y+15}; })()`);
    await command('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
    await command('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
  }
  // Exercise the native HTML drag handlers with explicit browser DragEvents.
  // This is not a claim of OS-level pointer-drag automation.
  async function drop(source, target) {
    await evaluate(`(() => {const data=new DataTransfer(); const source=document.querySelector(${JSON.stringify(card(source))}); const target=document.querySelector(${JSON.stringify(card(target))}); source.dispatchEvent(new DragEvent('dragstart',{bubbles:true,cancelable:true,dataTransfer:data})); target.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:data})); target.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data})); })()`);
  }
  async function state() { return (await fetch(`${backend}/matches/${fixture.id}`)).json(); }
  try {
    await waitFor("!document.body.innerText.includes('Restoring saved session') && document.querySelector('.saved-games')");
    await evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor("document.body.innerText.includes('Declare attackers (0)')");
    const revision = (await state()).revision;
    await pointerClick('elf');
    await waitFor("document.body.innerText.includes('Declare attackers (1)')");
    await pointerClick('elf');
    await waitFor("document.body.innerText.includes('Declare attackers (0)')");
    await drop('elf','angel');
    await waitFor("document.body.innerText.includes('A band needs banding')");
    assert.equal((await state()).revision, revision, 'draft changes must not mutate the game');
    await drop('hero','angel');
    await waitFor("document.body.innerText.includes('Declare attackers (2)') && document.querySelectorAll('.combat-band').length === 2");
    await click('Declare attackers (2)');
    await waitFor("!document.querySelector('#attack-declaration')");
    let current = await state();
    assert.deepEqual(current.attackers, ['hero','angel']);
    assert.deepEqual(current.attack_bands, [['hero','angel']]);
    for (let i=0; i<4 && current.step !== 'declare_blockers'; i++) {
      await click('Pass Priority');
      await waitFor(`!document.querySelector('fieldset:disabled')`);
      current = await state();
    }
    await waitFor("document.body.innerText.includes('Declare blockers (0)')");
    await pointerClick('bears');
    await pointerClick('angel');
    await waitFor("document.body.innerText.includes('That creature cannot block this attacker')");
    await pointerClick('hero');
    await waitFor("document.body.innerText.includes('Declare blockers (1)')");
    await click('Clear blocks');
    await drop('bears','hero');
    await waitFor("document.body.innerText.includes('Declare blockers (1)')");
    await click('Declare blockers (1)');
    await waitFor("!document.querySelector('#block-declaration')");
    current = await state();
    assert.deepEqual(current.blocks, {hero:['bears'],angel:['bears']});
    console.log(`PASS seat ${seat}: real pointer card selection; browser drag/drop handlers; legal band; flying rejection; click/drag block assignment; remote form submission and authoritative band propagation`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
