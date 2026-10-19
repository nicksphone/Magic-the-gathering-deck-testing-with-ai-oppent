import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { build } from 'esbuild';
import { openBrowser } from './browser-driver.mjs';

// Real DOM checks with captured paid views; no simulated API or SQLite claims.
const evidence = process.env.MTG_BROWSER_TEST_EVIDENCE;
assert.ok(evidence && path.isAbsolute(evidence), 'Declare fresh local evidence');
assert.ok(process.env.MTG_BROWSER_ORIGIN, 'Declare the owned Chromium debugger');
await mkdir(evidence, { recursive: false });
const rows = JSON.parse(await readFile(new URL('./fixtures/entry-mode-public/paid-views.json', import.meta.url)));
await build({ stdin: { contents: `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {Controls} from './Controls';
import {parseMatchState,parseLegalMoves} from '../api/match-contract';
const rows=${JSON.stringify(rows)};
const root=createRoot(document.getElementById('root'));
window.sent=[];
window.showRow=(index,unknown=false)=>{
 const row=rows[index];
 const move={...row.move,kind:unknown?'__unknown_entry_mode__':row.move.kind};
 parseMatchState(row.state);
 parseLegalMoves({player_id:row.seat,revision:0,moves:[move]});
 window.current=row;
 root.render(<React.Fragment key={index+':'+unknown}>
  <div data-testid="row">{index+':'+unknown}</div>
  <Controls match={row.state} legalMoves={[move]} actingPlayerId={row.seat}
   decks={[]} selectedA={null} selectedB={null} bestOf={1} startMode="human_vs_human"
   difficulty="normal" autoplayDelayMs={1000} responseCountdown={null} autoResponsePaused={false}
   onChooseMechanic={(seat,action)=>window.sent.push({seat,action})}/>
 </React.Fragment>);
};
window.showRow(0);
`, resolveDir: new URL('../src/components/', import.meta.url).pathname, loader: 'tsx' },
  bundle: true, platform: 'browser', outfile: path.join(evidence, 'app.js'), jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''", 'process.env.NODE_ENV': '"production"' } });
await writeFile(path.join(evidence, 'index.html'), '<!doctype html><html lang="en"><meta charset="utf-8"><title>Entry mode</title><div id="root"></div><script src="app.js"></script></html>');
const requests = [];
const server = createServer(async (request, response) => {
  requests.push({ method: request.method, path: request.url });
  const name = request.url === '/' ? 'index.html' : request.url === '/app.js' ? 'app.js' : null;
  if (request.method !== 'GET' || !name) { response.writeHead(404).end(); return; }
  try {
    response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : 'text/html');
    response.end(await readFile(path.join(evidence, name)));
  } catch { response.writeHead(500).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await openBrowser(`http://127.0.0.1:${server.address().port}/`);
  for (const [index, row] of rows.entries()) {
    await browser.evaluate(`window.showRow(${index})`);
    await browser.waitFor(`document.querySelector('[data-testid=row]')?.textContent==='${index}:false'`);
    assert.equal(await browser.evaluate('window.sent.length'), index, 'Rendering must not infer a choice');
    for (const id of row.move.options) {
      assert.equal(await browser.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent===${JSON.stringify(row.move.option_labels[id])}&&!b.disabled)`), true);
    }
    await browser.click(row.move.option_labels[row.chosen]);
    assert.deepEqual(await browser.evaluate('window.sent.at(-1)'), { seat: row.seat, action: { type: 'choose_mechanic', choice_id: row.chosen } });
    const shot = await browser.command('Page.captureScreenshot', { format: 'png' });
    await writeFile(path.join(evidence, `seat-${row.seat}-${row.mode}.png`), Buffer.from(shot.data, 'base64'));
    await browser.evaluate(`window.showRow(${index},true)`);
    await browser.waitFor("document.body.innerText.includes('Unsupported mechanic choice:')");
    assert.equal(await browser.evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent===${JSON.stringify(row.move.option_labels[row.chosen])})`), false);
  }
  assert.ok(requests.every(request => request.method === 'GET'), 'No pretend backend mutations');
  await writeFile(path.join(evidence, 'result.json'), JSON.stringify({ passed: true, rows: 4,
    scope: 'real Chromium component, captured paid views, exact callback; no application API/SQLite', requests }, null, 2));
  console.log('PASS Chromium entry modes: both seats/modes, offered buttons, explicit exact callback, no default, unknown warning');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
