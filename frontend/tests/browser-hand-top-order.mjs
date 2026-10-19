import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { openBrowser } from './browser-driver.mjs';

// Real browser component checks; no simulated HTTP or claimed database restore.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = process.env.MTG_BROWSER_TEST_EVIDENCE;
assert.ok(evidence && path.isAbsolute(evidence), 'declare a fresh local evidence directory');
await mkdir(evidence, {recursive: false});
const rows = JSON.parse(execFileSync(process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python'), ['-c', `
import json,sys
def deny(event,args):
 if event.startswith(('sqlite3.','socket.')) or event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn'):
  raise AssertionError('pure paid fixture denied '+event)
sys.addaudithook(deny)
sys.path.insert(0,'../audit/brainstorm')
from test_brainstorm_desired import position,brainstorm,add,act,RULES
from game_state.state import Zone
from game_state.serializers import serialize_match
rows=[]
for seat in (1,2):
 state=position(seat)
 for player in state.players.values(): player.snow_mana_pool.clear()
 add(state,'Counterspell',seat,Zone.HAND)
 state,_=brainstorm(state,seat)
 moves=RULES.legal_moves(state,seat)
 move=next(m for m in moves if m.get('kind')=='hand_top_order')
 chosen=[move['options'][1],move['options'][0]]
 resolved=act(state,seat,{'type':'choose_mechanic','card_ids':chosen})
 assert resolved.players[seat].library[-2:]==list(reversed(chosen))
 view=serialize_match(state,look_players={seat})
 view.update(controllers={'1':'human','2':'human'},revision=0)
 rows.append(dict(seat=seat,state=view,moves=moves,chosen=chosen))
print(json.dumps(rows))
`], {cwd: path.join(root, 'backend'), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
await writeFile(path.join(evidence, 'actual-paid-views.json'), JSON.stringify(rows, null, 2));
await build({stdin: {contents: `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {Controls} from './Controls';
import {parseMatchState,parseLegalMoves} from '../api/match-contract';
const rows=${JSON.stringify(rows)};
const root=createRoot(document.getElementById('root'));
window.sent=[];
window.showSeat=seat=>{
 const row=rows.find(row=>row.seat===seat);
 parseMatchState(row.state); parseLegalMoves({player_id:seat,revision:0,moves:row.moves});
 window.current=row;
 root.render(<React.Fragment key={seat}><div data-testid="fixture-seat">{seat}</div><Controls match={row.state} legalMoves={row.moves}
  actingPlayerId={seat} decks={[]} selectedA={null} selectedB={null} bestOf={1}
  startMode="human_vs_human" difficulty="normal" autoplayDelayMs={1000}
  responseCountdown={null} autoResponsePaused={false}
  onChooseMechanic={(seat,action)=>window.sent.push({seat,action})}/></React.Fragment>);
};
window.showSeat(1);
`, resolveDir: path.join(root, 'frontend/src/components'), loader: 'tsx'},
bundle: true, platform: 'browser', outfile: path.join(evidence, 'app.js'), jsx: 'automatic',
define: {'import.meta.env.VITE_API_BASE_URL': "''", 'process.env.NODE_ENV': '"production"'}});
const html = path.join(evidence, 'index.html');
await writeFile(html, '<!doctype html><html lang="en"><meta charset="utf-8"><title>Ordered hand control</title><div id="root"></div><script src="app.js"></script></html>');
const server = createServer(async (request, response) => {
  const filename = request.url === '/' ? 'index.html' : request.url === '/app.js' ? 'app.js' : null;
  if (request.method !== 'GET' || !filename) { response.writeHead(404).end(); return; }
  try {
    response.setHeader('Content-Type', filename.endsWith('.js') ? 'text/javascript' : 'text/html');
    response.end(await readFile(path.join(evidence, filename)));
  } catch { response.writeHead(500).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await openBrowser(`http://127.0.0.1:${server.address().port}/`);
  for (const row of rows) {
    await browser.evaluate(`window.showSeat(${row.seat})`);
    await browser.waitFor(`document.querySelector('[data-testid=fixture-seat]')?.textContent === '${row.seat}' && document.body.innerText.includes('topmost first')`);
    assert.equal(await browser.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirm Order').disabled"), true);
    const move = row.moves.find(move => move.kind === 'hand_top_order');
    for (const id of row.chosen) {
      await browser.click(move.option_labels[id]);
      assert.equal(await browser.evaluate(`([...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(move.option_labels[id])})).disabled`), true);
    }
    await browser.click('Confirm Order');
    assert.deepEqual(await browser.evaluate('window.sent.at(-1)'), {seat: row.seat, action: {type: 'choose_mechanic', card_ids: row.chosen}});
    await browser.click('Reset Order');
    assert.equal(await browser.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirm Order').disabled"), true);
    const shot = await browser.command('Page.captureScreenshot', {format: 'png'});
    await writeFile(path.join(evidence, `seat-${row.seat}.png`), Buffer.from(shot.data, 'base64'));
  }
  await writeFile(path.join(evidence, 'browser-result.json'), JSON.stringify({passed: true, seats: [1,2], scope: 'real browser component; backend paid pure fixture; no API/SQLite'}, null, 2));
  console.log('PASS real browser: both-seat paid views, deliberate order, exact action, disabled/cardinality and reset');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
