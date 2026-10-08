import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { build } from 'esbuild';
import { openBrowser } from './browser-driver.mjs';

const evidence = process.env.MTG_BROWSER_TEST_EVIDENCE;
assert.ok(evidence && path.isAbsolute(evidence), 'Declare fresh owned evidence');
assert.ok(process.env.MTG_BROWSER_ORIGIN, 'Declare owned Chromium debugger');
await mkdir(evidence, { recursive: false });
const paid = JSON.parse(await readFile(new URL('./fixtures/spree-public/paid-views.json', import.meta.url)));
const pending = JSON.parse(await readFile(new URL('./fixtures/spree-public/continuations.json', import.meta.url)));
await build({ stdin: { contents: `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {Battlefield} from './Battlefield';
import {Controls} from './Controls';
import {parseMatchState,parseLegalMoves} from '../api/match-contract';
const paid=${JSON.stringify(paid)},pending=${JSON.stringify(pending)};
const root=createRoot(document.getElementById('root'));
window.sent=[];
window.showSpree=(kind,index)=>{
 const row=kind==='cast'?paid.rows[index]:kind==='pending'?pending.pending_rows[index]:pending.no_alternative_rows[index];
 const actor=row.casting_player;
 const match={...row.actual_public_serialized_match,revision:row.protocol_envelope.revision,controllers:row.protocol_envelope.controllers};
 const moves=kind==='cast'?[row.actual_offered_move]:row.actual_legal_moves;
 parseMatchState(match);parseLegalMoves({player_id:actor,revision:0,moves});
 window.current={row,actor,match,moves};
 root.render(<React.Fragment key={kind+':'+index}>
  <div data-testid="row">{kind+':'+index}</div>
  {kind==='cast'?<Battlefield match={match} legalMoves={moves} actingPlayerId={actor}
   onCardAction={(seat,action)=>window.sent.push({seat,action})}/>:<Controls
   match={match} legalMoves={moves} actingPlayerId={actor} decks={[]} selectedA={null} selectedB={null}
   bestOf={1} startMode="human_vs_human" humanSeat={actor} difficulty="normal"
   autoplayDelayMs={1000} responseCountdown={null} autoResponsePaused={false}
   onChooseMechanic={(seat,action)=>window.sent.push({seat,action})}/>}
 </React.Fragment>);
};
window.showSpree('cast',0);
`, resolveDir: new URL('../src/components/', import.meta.url).pathname, loader: 'tsx' },
  bundle: true, platform: 'browser', outfile: path.join(evidence, 'app.js'), jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''", 'process.env.NODE_ENV': '"production"' } });
await writeFile(path.join(evidence, 'index.html'), '<!doctype html><html lang="en"><meta charset="utf-8"><title>Spree controls</title><div id="root"></div><script src="app.js"></script></html>');
const requests = [];
const server = createServer(async (request, response) => {
  requests.push({ method: request.method, path: request.url });
  const name = request.url === '/' ? 'index.html' : request.url === '/app.js' ? 'app.js' : null;
  if (request.method !== 'GET' || !name) { response.writeHead(404).end(); return; }
  response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : 'text/html');
  response.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'none'");
  try { response.end(await readFile(path.join(evidence, name))); }
  catch { response.writeHead(500).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
const receipts = [];
try {
  browser = await openBrowser(`http://127.0.0.1:${server.address().port}/`);
  const show = async (kind, index) => {
    const before = await browser.evaluate('window.sent.length');
    await browser.evaluate(`window.showSpree(${JSON.stringify(kind)},${index})`);
    await browser.waitFor(`document.querySelector('[data-testid=row]')?.textContent===${JSON.stringify(kind+':'+index)}`);
    assert.equal(await browser.evaluate('window.sent.length'), before, 'Rendering must not select');
  };
  const disabled = () => browser.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Cast Return the Favor')).disabled");
  for (const [index, row] of paid.rows.entries()) {
    await show('cast', index);
    assert.equal(await disabled(), true);
    const modes = row.actual_offered_move.target_hints.modes;
    const selected = row.selection === 2 ? modes : [modes[row.selection]];
    await browser.evaluate(`(()=>{const el=document.querySelector('select[aria-label="Spell modes"]');
      for(const option of el.options)option.selected=${JSON.stringify(selected)}.includes(option.value);
      el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    await browser.waitFor(`document.querySelectorAll('select[aria-label^="Target for "]').length===${selected.length}`);
    assert.equal(await disabled(), true);
    const modeTargets = {};
    for (const mode of selected) {
      const id = row.actual_checked_action.targets.mode_targets?.[mode]?.target_stack_id
        ?? row.actual_checked_action.targets.target_stack_id;
      modeTargets[mode] = { target_stack_id: id };
      await browser.evaluate(`(()=>{const el=[...document.querySelectorAll('select')].find(x=>x.getAttribute('aria-label')===${JSON.stringify('Target for '+mode)});
        el.value=${JSON.stringify(id)};el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    }
    await browser.waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Cast Return the Favor')&&!b.disabled)");
    const label = await browser.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Cast Return the Favor')).textContent");
    const hints = row.actual_offered_move.target_hints;
    assert.ok(label.includes(`(${hints.mode_base_mana_costs.base+selected.map(m=>hints.mode_additional_mana_costs[m]).join('')})`));
    await browser.click(label);
    const callback = await browser.evaluate('window.sent.at(-1)');
    assert.deepEqual(callback, { seat: row.casting_player, action: { type: 'cast_spell',
      card_id: row.actual_offered_move.card_id, targets: { mode_texts: selected, mode_targets: modeTargets },
      cost_choice: { id: 'base' }, from_graveyard: row.actual_offered_move.from_graveyard } });
    receipts.push({ kind: 'cast', index, callback });
    if (index === 5) {
      const shot = await browser.command('Page.captureScreenshot', { format: 'png' });
      await writeFile(path.join(evidence, 'cast-modes.png'), Buffer.from(shot.data, 'base64'));
    }
  }
  for (const [index, row] of pending.pending_rows.entries()) {
    await show('pending', index);
    const move = row.actual_legal_moves.find(m=>m.type==='choose_mechanic');
    assert.equal(move.options.includes('keep'), row.phase==='optional');
    if (index === 0) {
      const shot = await browser.command('Page.captureScreenshot', { format: 'png' });
      await writeFile(path.join(evidence, 'pending-choice.png'), Buffer.from(shot.data, 'base64'));
    }
    for (const option of move.options) {
      await browser.click(move.option_labels?.[option] ?? option);
      const callback = await browser.evaluate('window.sent.at(-1)');
      assert.deepEqual(callback, { seat: row.casting_player, action: { type: 'choose_mechanic', card_ids: [option] } });
      receipts.push({ kind: 'pending', index, option, callback });
    }
  }
  for (const [index] of pending.no_alternative_rows.entries()) await show('none', index);
  const shot = await browser.command('Page.captureScreenshot', { format: 'png' });
  await writeFile(path.join(evidence, 'controls.png'), Buffer.from(shot.data, 'base64'));
  assert.ok(requests.every(r=>r.method==='GET'), 'Component server cannot mutate game state');
  await writeFile(path.join(evidence, 'result.json'), JSON.stringify({ passed: true, views: 16,
    scope: 'Actual React/Chromium captured-view component callbacks, not App/API/SQLite or full browser release',
    receipts, requests }, null, 2));
  console.log('PASS Chromium Spree 16 actual views, explicit modes/targets/prices and copy/retarget callbacks');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => {
    server.close(resolve);
    server.closeAllConnections();
  });
}
