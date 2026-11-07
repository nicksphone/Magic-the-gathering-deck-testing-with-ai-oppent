import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {openBrowser} from './browser-driver.mjs';
const origin=process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15175';
const evidence=process.env.MTG_UI_EVIDENCE;
const browser=await openBrowser(origin+'/tests/interactive-preflight.html');
const {evaluate,waitFor,click,command,close}=browser;
async function select(label,value){await evaluate(`(() => {const e=document.querySelector('select[aria-label="'+${JSON.stringify(label)}+'"]');if(!e||e.disabled)throw Error('missing selector');e.value=${JSON.stringify(String(value))};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);}
async function enter(){await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',unmodifiedText:'\r',windowsVirtualKeyCode:13});await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});}
async function shot(name){if(!evidence)return;await mkdir(evidence,{recursive:true});const r=await command('Page.captureScreenshot',{format:'png'});await writeFile(evidence+'/'+name+'.png',Buffer.from(r.data,'base64'));}
try{
 await waitFor("window.interactiveFixture && document.querySelector('select[aria-label=\"Deck A\"]')?.options.length===4 && !document.querySelector('fieldset')?.disabled");
 assert.match(await evaluate("document.querySelector('[aria-label=\"Play guide\"]').innerText"),/What to do next/);
 assert.equal(await evaluate("document.querySelector('[aria-label=\"Interactive match support preflight\"] details').open"),false,'Support diagnostic stays folded until needed');
 assert.equal(await evaluate("document.querySelector('.setup-options').open"),false);
 assert.equal(await evaluate("document.querySelector('.advanced-turn-controls').open"),false);
 assert.match(await evaluate("document.querySelector('select[aria-label=\"Deck A\"]').closest('label').innerText"),/Your deck/);
 await evaluate("document.querySelector('.setup-options summary').focus()");await enter();
 await waitFor("document.querySelector('.setup-options').open");
 await select('Human seat',2);await waitFor("document.querySelector('select[aria-label=\"Deck B\"]').closest('label').innerText.includes('Your deck')");
 await select('Match mode','ai_vs_ai');await waitFor("document.querySelector('select[aria-label=\"Deck A\"]').closest('label').innerText.includes('Player 1')");
 await select('Match mode','player_vs_ai');await select('Human seat',1);
 await select('Deck A',1);await select('Deck B',2);await click('Start Best-of-3 Match');
 await waitFor("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"Interactive match support preflight\"] details').open"),true,'Required review opens automatically');
 assert.equal(await evaluate('window.interactiveFixture.requests.length'),0,'Start still checks support before creating anything');
 assert.equal(await evaluate('window.interactiveFixture.blockedFetches'),0);
 await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await evaluate('scrollTo(0,0)');
 assert.equal(await evaluate("document.querySelector('#match-controls').getBoundingClientRect().top < document.querySelector('#table').getBoundingClientRect().top"),true,'Mobile setup appears before the decorative welcome panel');
 assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),true);await shot('beginner-lobby-mobile390');
 await evaluate("document.querySelector('.guide-link').click()");await waitFor("document.activeElement?.id==='match-controls'");
 await command('Page.navigate',{url:origin+'/tests/ui-clarity.html'});await waitFor('window.fixtureState');
 await click('Reset Block draft');await waitFor("document.querySelector('.play-guide h2')?.textContent.toLowerCase().includes('block')");
 await evaluate("document.querySelector('.quick-glossary summary').focus()");await enter();await waitFor("document.querySelector('.quick-glossary').open");
 assert.match(await evaluate("document.querySelector('.quick-glossary').innerText"),/Priority[\s\S]*Stack[\s\S]*Mana[\s\S]*Tapped/);
 assert.equal(await evaluate('window.fixtureActions.length'),0);
 await evaluate("document.querySelector('.play-guide > details summary').focus()");await enter();
 assert.equal(await evaluate("document.querySelector('.play-guide > details').open"),false,'Experienced players can fold guidance');
 await click('Reset Attack draft');assert.equal(await evaluate("document.querySelector('.play-guide > details').open"),false,'Renders preserve manual collapse');
 assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),true);assert.equal(await evaluate('window.fixtureActions.length'),0);
 await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await evaluate("document.querySelector('.play-guide > details summary').click();scrollTo(0,0)");await shot('beginner-combat-desktop');
 console.log('PASS actual App beginner setup, keyboard advanced settings, seat labels, automatic support review, mobile390, action navigation, collapsible guide/glossary; synthetic fixtures, no backend writes');
}finally{await close();}
