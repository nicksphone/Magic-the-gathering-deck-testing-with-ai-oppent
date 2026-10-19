import assert from 'node:assert/strict';
import {appendFile, mkdir, writeFile, stat, readFile, readdir} from 'node:fs/promises';
import {request as httpRequest} from 'node:http';
import path from 'node:path';
import {openBrowser, closeBrowsersPreservingError} from './browser-driver.mjs';
import {reviewStart} from '../review-start.mjs';

const json = JSON.stringify;
const postData = capture => JSON.parse(capture.base64Encoded
  ? Buffer.from(capture.postData, 'base64').toString() : capture.postData);
const sum = pool => Object.values(pool).reduce((n, v) => n + v, 0);
export async function waitForStartDropACKs(readState, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const {acknowledged, fatal} = readState();
    if (fatal) throw fatal;
    if (acknowledged === 2) return;
    if (Date.now() >= deadline) throw new Error('Two actual start-response drop ACKs did not arrive before reload');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}
function currentCastLabel(move, choice, card) {
  const selectedCost = move.cost_options.find(c => c.id === choice);
  assert.ok(selectedCost, 'Actual offered cast cost');
  const displayedCost = selectedCost.mana_cost ?? move.mana_cost;
  return 'Cast ' + (move.card_name ?? card.name) + (displayedCost ? ' (' + displayedCost + ')' : '');
}
async function journal(file, row) {
  const value = json(row) + '\n';
  assert.ok(Buffer.byteLength(value) < 4 * 1024 * 1024, 'Single journal record bound');
  const bytes = await stat(file).then(s => s.size, () => 0);
  assert.ok(bytes + Buffer.byteLength(value) <= 256 * 1024 * 1024, 'Journal byte bound');
  await appendFile(file, value);
}

async function validateColdOwnerChange(after, before, out) {
  const names = await readdir(out);
  const bind = async snapshot => {
    const rows = snapshot.SQL.filter(row => row.startsWith('INSERT INTO "resourcecapacity" VALUES('));
    assert.equal(rows.length, 1, 'Exactly one capacity singleton');
    const match = /^INSERT INTO "resourcecapacity" VALUES\((1,1,\d+,\d+,\d+,\d+,)'([a-f0-9]{32})'\);$/.exec(rows[0]);
    assert.ok(match, 'Exact capacity schema and UUID32 epoch');
    const epoch = match[2];
    const proofs = [];
    for (const name of names.filter(name => name.startsWith('snapshot-owner-' + epoch + '-'))) {
      const proof = JSON.parse(await readFile(path.join(out, name), 'utf8'));
      if (json(proof.snapshot) === json(snapshot)) proofs.push(proof);
    }
    assert.equal(proofs.length, 1, 'Snapshot bound to actual live owner and SQL row');
    const proof = proofs[0], owner = proof.owner;
    assert.equal(owner.epoch, epoch);
    assert.equal(owner.stage, 'ready');
    assert.equal(owner.ready, true); assert.equal(owner.registered, true);
    assert.equal(owner.admissions_open, true); assert.ok(Number.isInteger(owner.owner_fd));
    assert.ok(Number.isInteger(owner.pid) && owner.pid > 0);
    assert.ok(Number.isInteger(owner.start_ticks) && owner.start_ticks > 0);
    assert.equal(proof.database, path.resolve(out, '../../runtime/sql/api.db'));
    assert.equal(owner.lock.path, proof.database + '.capacity-owner.lock');
    assert.equal(owner.lock.bytes, 0);
    assert.deepEqual(proof.columns, ['id', 'version', 'durable_bytes', 'snapshot_rows', 'reserved_bytes', 'reserved_snapshot_rows', 'owner_epoch']);
    assert.deepEqual(proof.capacity_row, match[1].slice(0, -1).split(',').map(Number).concat(epoch));
    const current = JSON.parse(await readFile(path.join(out, `storage-owner-${owner.pid}-${epoch}.json`), 'utf8'));
    assert.equal(current.pid, owner.pid); assert.equal(current.start_ticks, owner.start_ticks);
    assert.equal(current.epoch, epoch); assert.deepEqual(current.lock, owner.lock);
    assert.equal(current.backups.length, 1); assert.equal(owner.backups.length, 1);
    const retainedBackup = {...current.backups[0]};
    if (!Object.hasOwn(owner.backups[0], 'ready_sha256')) {
      if (current.stage === 'closed') assert.equal(retainedBackup.ready_sha256, owner.backups[0].sha256);
      delete retainedBackup.ready_sha256;
    }
    assert.deepEqual(retainedBackup, owner.backups[0], 'Verified backup unchanged through owner closure');
    return {epoch, row: rows[0], owner, current};
  };
  const old = await bind(before), fresh = await bind(after);
  assert.notEqual(old.epoch, fresh.epoch, 'Genuine restart has a new owner epoch');
  assert.notEqual(old.owner.pid, fresh.owner.pid, 'Genuine OS backend replacement');
  assert.equal(old.current.stage, 'closed');
  assert.equal(old.current.registered, false); assert.equal(old.current.ready, false);
  assert.equal(old.current.owner_fd, null); assert.equal(old.current.admissions_open, false);
  assert.equal(old.current.producers, 0);
  assert.equal(fresh.current.stage, 'ready');
  assert.deepEqual(fresh.current, fresh.owner);
  assert.deepEqual(fresh.owner.lock, old.owner.lock, 'Same retained lock identity');
  const expected = structuredClone(before);
  const index = expected.SQL.indexOf(old.row);
  expected.SQL[index] = old.row.replace("'" + old.epoch + "'", "'" + fresh.epoch + "'");
  assert.deepEqual(after, expected, 'All controller/state/SQL exact except proven capacity epoch cell');
  await journal(path.join(out, 'cold-owner-validation.jsonl'), {old, fresh, all_other_snapshot_fields_exact: true});
  // Only the already-proven administrative cell changes in the comparison copy.
  before.SQL[index] = expected.SQL[index];
}

export async function runPaidBuiltCases({cases, api, frontend, out, token, restartBackend, assertAlive}) {
  const completed = [];
  const end = Date.now() + 1500000;
  for (const row of cases) {
    assertAlive(); assert.ok(Date.now() < end, 'Controlled cohort aggregate deadline');
    const directory = path.join(out, row.id); await mkdir(directory);
    const requestFile = path.join(directory, 'requests.jsonl');
    const calls = [];
    const headers = {'X-Owned-Test-Token': token};
    const get = async route => {
      const response = await fetch(api + route, {headers, signal: AbortSignal.timeout(15000)});
      assert.equal(response.status, 200, await response.clone().text());
      return response.json();
    };
    const setup = await fetch(api + '/__built__/setup/' + row.id,
      {method: 'POST', headers, signal: AbortSignal.timeout(90000)});
    assert.equal(setup.status, 200, await setup.clone().text());
    const meta = await setup.json();
    const browser = await openBrowser(frontend);
    const {evaluate, waitFor, click, command} = browser;
    let dropped = 0, fatal;
    const snapshot = () => get('/__built__/snapshot/' + meta.id);
    const view = () => get('/matches/' + meta.id);
    const legal = async seat => (await get('/matches/' + meta.id + '/legal-moves?player_id=' + seat)).moves;
    const check = () => { assertAlive(); assert.ok(Date.now() < end); if (fatal) throw fatal; };
    await command('Network.enable');
    browser.onIntercept(async event => {
      try {
        const url = new URL(event.request.url);
        const isAPI = url.origin === new URL(api).origin;
        const isPage = url.origin === new URL(frontend).origin;
        assert.ok(isAPI || isPage || event.resourceType === 'Image', 'External request');
        if (!isAPI && !isPage) {
          await command('Fetch.failRequest', {requestId: event.requestId, errorReason: 'BlockedByClient'});
          dropped++;
          return;
        }
        if (event.request.method === 'POST' && event.responseStatusCode) {
          assert.match(url.pathname, /^\/matches\/[a-z0-9-]+\/action$/);
          assert.ok(event.networkId);
          const captured = await command('Network.getRequestPostData', {requestId: event.networkId});
          const raw = captured.base64Encoded ? Buffer.from(captured.postData, 'base64').toString() : captured.postData;
          const body = JSON.parse(raw);
          const normalized = Object.fromEntries(Object.entries(event.request.headers).map(([k, v]) => [k.toLowerCase(), v]));
          assert.equal(normalized.origin, new URL(frontend).origin, 'Real browser Origin');
          assert.match(normalized['idempotency-key'], /^[0-9a-f]{32}$/);
          assert.match(normalized['x-match-revision'], /^\d+$/);
          const receipt = {body, status: event.responseStatusCode,
            key: normalized['idempotency-key'], revision: normalized['x-match-revision']};
          calls.push(receipt); await journal(requestFile, receipt);
        }
        await command(event.responseStatusCode ? 'Fetch.continueResponse' : 'Fetch.continueRequest',
          {requestId: event.requestId});
      } catch (error) { fatal = error; }
    });
    await command('Fetch.enable', {patterns: [{urlPattern: '*', requestStage: 'Request'},
      {urlPattern: api + '/matches/*/action', requestStage: 'Response'}]});
    const consistent = async () => {
      check(); const current = await view();
      await waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision===${json(String(current.revision))} && !document.body.innerText.includes('Match operation pending')`, 30000);
      return current;
    };
    const action = async (label, scope = 'document') => {
      check(); const before = await view(); const start = calls.length;
      await waitFor(`[...${scope}.querySelectorAll('button')].some(b=>b.textContent.trim()===${json(label)}&&!b.disabled)`);
      await evaluate(`(()=>{const b=[...${scope}.querySelectorAll('button')].find(b=>b.textContent.trim()===${json(label)}&&!b.disabled);if(!b)throw Error('Missing actual control');b.click();})()`);
      await waitFor(`(async()=>{const r=await fetch(${json(api + '/matches/' + meta.id)});return r.ok&&(await r.json()).revision>${before.revision};})()`, 30000);
      const current = await consistent();
      assert.equal(current.revision, before.revision + 1, 'Exactly one accepted mutation');
      assert.equal(calls.length, start + 1, 'Exactly one browser write');
      assert.equal(calls.at(-1).status, 200);
      return current;
    };
    const select = async (selector, values) => {
      await evaluate(`(()=>{const s=document.querySelector(${json(selector)});if(!s)throw Error('Missing actual select');const requested=${json(values)};for(const v of requested)if(![...s.options].some(o=>o.value===v&&!o.disabled))throw Error('Unoffered option');if(s.multiple){for(const o of s.options)o.selected=requested.includes(o.value);}else{s.value=requested[0]??'';}s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    };
    const cast = async (source, choice, target = null, pitch = null, x = null) => {
      const current = await view(); const offered = await legal(current.priority_player);
      const move = offered.find(m => m.type === 'cast_spell' && m.card_id === source);
      assert.ok(move, 'Actual actor legal cast');
      assert.ok(move.cost_options.some(c => c.id === choice));
      const box = `[data-hand-card-id="${source}"]`;
      await waitFor(`Boolean(document.querySelector(${json(box)}))`);
      await evaluate(`(()=>{const b=document.querySelector(${json(box)});const s=[...b.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.textContent==='Cost Option'));if(!s)throw Error('Cost control absent');s.value=${json(choice)};s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      if (x !== null) {
        await evaluate(`(()=>{const i=document.querySelector(${json(box)}).querySelector('input[placeholder="X value"]');if(!i)throw Error('X absent');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(i,${json(String(x))});i.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      }
      let DOMPitch = null;
      if (pitch !== null) {
        const selector = box + ' select[aria-label="Exile from hand for cost March of Otherworldly Light"]';
        await waitFor(`Boolean(document.querySelector(${json(selector)}))`);
        // Deliberate reverse selection still emits native DOM option order.
        for (let i = 0; i < pitch.length; i++) await select(selector, pitch.slice(0, i + 1));
        if (!pitch.length) await select(selector, []);
        DOMPitch = await evaluate(`[...document.querySelector(${json(selector)}).selectedOptions].map(o=>o.value)`);
        assert.deepEqual([...DOMPitch].sort(), [...pitch].sort());
      }
      if (target) {
        await evaluate(`(()=>{const b=document.querySelector(${json(box)});const candidates=${json([target, 'card:' + target])};const s=[...b.querySelectorAll('select')].find(s=>!s.multiple&&[...s.options].some(o=>candidates.includes(o.value)));if(!s)throw Error('Target absent');s.value=candidates.find(v=>[...s.options].some(o=>o.value===v));s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      }
      const before = await snapshot();
      const label = currentCastLabel(move, choice, before.state.cards[source]);
      await waitFor(`[...document.querySelector(${json(box)}).querySelectorAll('button')].filter(b=>b.textContent.trim()===${json(label)}&&!b.disabled).length===1`);
      await action(label, `document.querySelector(${json(box)})`);
      const receipt = calls.at(-1).body;
      assert.equal(receipt.action.type, 'cast_spell'); assert.equal(receipt.action.card_id, source);
      assert.equal(receipt.action.cost_choice.id, choice);
      if (DOMPitch) assert.deepEqual(receipt.action.cost_choice.exile_card_ids, DOMPitch);
      if (x !== null) assert.equal(receipt.action.targets.x_value, x);
      const paid = await snapshot();
      const item = paid.state.stack.find(i => i.source_card_id === source && i.kind === 'spell')
        ?? paid.state.stack.find(i => i.source_card_id === source);
      assert.ok(item); assert.equal(paid.state.cards[source].zone, 'stack');
      assert.ok(sum(before.state.players[String(row.seat)].mana_pool) > sum(paid.state.players[String(row.seat)].mana_pool));
      return {before, paid, item, DOMPitch};
    };
    const advance = async predicate => {
      for (let i = 0; i < 128; i++) {
        const current = await view();
        if (predicate(current)) return current;
        assert.ok(!current.pending_mechanic_choice && !current.pending_replacement_choice, 'Unexpected decision: stop');
        const moves = await legal(current.pending_trigger_order?.current_controller ?? current.priority_player);
        if (current.pending_trigger_order) {
          const move = moves.find(m => m.type === 'choose_trigger_target' && m.target_player === 3 - row.seat)
            ?? moves.find(m => m.type === 'choose_trigger_order');
          assert.ok(move, 'Actual owned trigger offer');
          const label = move.type === 'choose_trigger_order'
            ? (move.trigger_labels ?? move.trigger_order ?? []).join(' -> ') || 'Use trigger order'
            : move.target_name ?? move.target_card_id ?? `Player ${move.target_player}`;
          await action(label);
        } else if (moves.some(m => m.type === 'attack')) await action('Submit Attackers');
        else if (moves.some(m => m.type === 'block')) await action('Submit Blocks');
        else await action('Pass Priority');
      }
      throw Error('128 real UI priority actions exceeded');
    };
    const cold = async () => {
      const before = await snapshot();
      await restartBackend(meta.id);
      await command('Page.reload'); await consistent();
      const after = await snapshot();
      await validateColdOwnerChange(after, before, out);
      assert.deepEqual(after, before, 'Actual OS restore exact controller/state/SQL');
    };
    let primaryError;
    try {
      await waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('.saved-games [role=\"status\"]')");
      await evaluate(`localStorage.setItem('mtg.activeMatch',${json(meta.id)})`);
      await command('Page.reload'); await consistent();
      assert.equal(calls.length, 0, 'Rendering cannot submit default action');
      if (row.kind === 'sunc') {
        const paid = await cast(meta.source, 'base'); assert.equal(paid.item.payload.mana_spent, 2);
        await advance(v => v.pending_mechanic_choice?.kind === 'entry_mode');
        if (row.cold) await cold();
        const offered = (await legal(row.seat)).find(m => m.kind === 'entry_mode');
        assert.ok(offered && offered.options.length);
        const choice = offered.options.find(id => offered.option_labels[id].includes(row.mode === 'creature' ? 'creature' : 'opponent'));
        assert.ok(choice); const beforeMode = calls.length;
        await action(offered.option_labels[choice]);
        assert.equal(calls.length, beforeMode + 1);
        assert.deepEqual(calls.at(-1).body.action, {type: 'choose_mechanic', choice_id: choice});
        const targetMove = (await legal(row.seat)).find(m => m.type === 'choose_trigger_target' &&
          (row.mode === 'creature' ? m.target_card_id === meta.target : m.target_player === meta.target));
        assert.ok(targetMove); await action(targetMove.target_name ?? targetMove.target_card_id ?? `Player ${targetMove.target_player}`);
        await advance(v => !v.stack.length);
        let proof = await snapshot();
        const count = state => row.mode === 'creature'
          ? state.cards[meta.target].counters['+1/+1'] ?? 0
          : state.players[String(meta.target)].counters?.experience ?? 0;
        assert.equal(count(proof.state), 0);
        if (row.mode === 'creature') await cast(meta.followup, 'base', meta.target);
        else {
          await advance(v => v.active_player === meta.target && v.step === 'precombat_main' && !v.stack.length && v.priority_player === meta.target);
          const land = (await legal(meta.target)).find(m => m.type === 'play_land'); assert.ok(land);
          const actor = (await view()).players[String(meta.target)];
          const card = actor.hand.find(c => c.id === land.card_id); assert.ok(card);
          await action('Play Land ' + card.name, `document.querySelector('[data-hand-card-id="${card.id}"]')`);
        }
        await advance(v => !v.stack.length); proof = await snapshot();
        assert.equal(count(proof.state), 0); assert.equal(proof.state.cards[meta.source].zone, 'battlefield');
      } else if (row.kind === 'brain') {
        await cast(meta.source, 'base');
        await advance(v => v.pending_mechanic_choice?.kind === 'hand_top_order');
        if (row.cold) await cold();
        const offered = (await legal(row.seat)).find(m => m.kind === 'hand_top_order');
        assert.ok(offered && offered.count === 2);
        const chosen = offered.options.slice(0, 2); if (row.reverse) chosen.reverse();
        const before = await snapshot();
        assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Confirm Order').disabled"), true);
        const pick = async cid => {
          const index = offered.options.indexOf(cid); assert.ok(index >= 0);
          await evaluate(`(()=>{const p=[...document.querySelectorAll('.block-panel')].find(p=>p.querySelector('button')&&p.textContent.includes('Reset Order'));const b=[...p.querySelectorAll('button')][${index}];if(!b||b.disabled||b.textContent.trim()!==${json(offered.option_labels?.[cid] ?? cid)})throw Error('Order control mismatch');b.click();})()`);
        };
        await pick(chosen[0]); await click('Reset Order');
        for (const cid of chosen) await pick(cid);
        await action('Confirm Order');
        assert.deepEqual(calls.at(-1).body.action, {type: 'choose_mechanic', card_ids: chosen});
        const after = await snapshot();
        assert.deepEqual(after.state.players[String(row.seat)].library,
          [...before.state.players[String(row.seat)].library, ...[...chosen].reverse()]);
        assert.equal(after.state.cards[meta.source].zone, 'graveyard');
        assert.equal(after.state.pending_mechanic_choice, null);
      } else if (row.kind === 'march') {
        if (row.cold) await cold();
        const pitch = meta.whites.slice(0, meta.pitch_count); if (pitch.length === 2) pitch.reverse();
        const paid = await cast(meta.source, 'base', meta.target, pitch, 4);
        assert.equal(paid.item.payload.mana_spent, meta.mana_spent);
        for (const cid of paid.DOMPitch) assert.equal(paid.paid.state.cards[cid].zone, 'exile');
        for (const cid of meta.whites.filter(cid => !pitch.includes(cid))) assert.equal(paid.paid.state.cards[cid].zone, 'hand');
        await advance(v => !v.stack.length);
        assert.equal((await snapshot()).state.cards[meta.target].zone, 'exile');
      } else if (row.kind === 'pair') {
        const paid = await cast(meta.source, row.choice);
        assert.equal(paid.item.payload.__kicker_count, meta.count);
        const before = paid.before.state.players;
        await advance(v => !v.stack.length && !v.pending_trigger_order);
        const after = await snapshot();
        assert.equal(after.state.cards[meta.source].zone, 'battlefield');
        assert.equal(after.state.cards[meta.source].kicker_count, meta.count);
        assert.equal(after.state.players[String(3-row.seat)].life, before[String(3-row.seat)].life - 2*meta.count);
        assert.equal(after.state.players[String(row.seat)].life, before[String(row.seat)].life + 2*meta.count);
      } else {
        const paid = await cast(meta.source, row.choice, meta.target);
        assert.equal(paid.item.payload.mana_spent, meta.mana_spent);
        await advance(v => !v.stack.length);
        assert.equal((await snapshot()).state.cards[meta.target].zone, row.choice === 'kicker' ? 'graveyard' : 'battlefield');
      }
      check(); assert.equal(dropped, 0);
      const shot = await command('Page.captureScreenshot', {format: 'png'});
      await writeFile(path.join(directory, 'terminal.png'), Buffer.from(shot.data, 'base64'));
      const receipt = {id: row.id, success: true, fullApp: true, writes: calls.length, fixture: meta,
        terminal: await snapshot(), public: await view()};
      await writeFile(path.join(directory, 'RESULT.json'), json(receipt, null, 2));
      completed.push({id: row.id, writes: calls.length});
    } catch (error) { primaryError = error; throw error; } finally { await closeBrowsersPreservingError(primaryError, browser); }
  }
  assert.equal(completed.length, 40);
  return completed;
}

export async function runBuiltRecovery({api, frontend, out, token, restartBackend, assertAlive}) {
  const headers = {'X-Owned-Test-Token': token};
  const get = async route => {
    const response = await fetch(api + route, {headers, signal: AbortSignal.timeout(15000)});
    assert.equal(response.status, 200, await response.clone().text()); return response.json();
  };
  const results = [];
  for (const name of ['lost-response', 'overlap-stale']) {
    assertAlive(); const begin = Date.now();
    const setup = await fetch(api + '/__built__/setup/recovery-' + name, {method: 'POST', headers});
    assert.equal(setup.status, 200); const meta = await setup.json();
    const browser = await openBrowser(frontend); let other, otherCastLabel;
    const before = await get('/__built__/snapshot/' + meta.id);
    const writes = [], staleWrites = []; let dropped = 0, fatal;
    const load = async b => {
      await b.waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('.saved-games [role=\"status\"]')");
      await b.evaluate(`localStorage.setItem('mtg.activeMatch',${json(meta.id)})`);
      await b.command('Page.reload');
      await b.waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision===${json(String(before.controller.revision))}`);
      const selector = `[data-hand-card-id="${meta.source}"]`;
      await b.waitFor(`(() => { const boxes = [...document.querySelectorAll(${json(selector)})]; return boxes.length === 1 && [...boxes[0].querySelectorAll('select')].filter(s => !s.disabled && [...s.options].some(o => o.value === 'base' && !o.disabled)).length === 1; })()`);
      await b.evaluate(`(()=>{const box=document.querySelector(${json(selector)});const s=[...box.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.value==='base'));s.value='base';s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await b.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
      await b.waitFor(`(() => { const box = document.querySelector(${json(selector)}); const nodes = box && [...box.querySelectorAll('select')].filter(s => [...s.options].some(o => o.value === 'base')); return nodes && nodes.length === 1 && nodes[0].value === 'base' && nodes[0].selectedOptions.length === 1 && nodes[0].selectedOptions[0].value === 'base'; })()`);
      const offered = await get('/matches/' + meta.id + '/legal-moves?player_id=1');
      const move = offered.moves.find(m => m.type === 'cast_spell' && m.card_id === meta.source);
      assert.ok(move, 'Actual recovery actor legal cast');
      const label = currentCastLabel(move, 'base', before.state.cards[meta.source]);
      await b.waitFor(`[...document.querySelector(${json(selector)}).querySelectorAll('button')].filter(b=>b.textContent.trim()===${json(label)}&&!b.disabled).length===1`);
      return label;
    };
    let primaryError;
    try {
      const castLabel = await load(browser); await browser.command('Network.enable');
      browser.onIntercept(async event => {
        try {
          if (event.request.method === 'POST') {
            assert.ok(event.networkId); const captured = await browser.command('Network.getRequestPostData', {requestId: event.networkId});
            writes.push({status: event.responseStatusCode, body: postData(captured)});
          }
          if (name === 'lost-response' && event.request.method === 'POST' && event.responseStatusCode === 200 && !dropped) {
            dropped++; await browser.command('Fetch.failRequest', {requestId: event.requestId, errorReason: 'Failed'});
          } else await browser.command('Fetch.continueResponse', {requestId: event.requestId});
        } catch (error) { fatal = error; }
      });
      await browser.command('Fetch.enable', {patterns: [{urlPattern: api + '/matches/*/action', requestStage: 'Response'}]});
      if (name === 'overlap-stale') {
        other = await openBrowser(frontend); otherCastLabel = await load(other);
        await other.command('Network.enable');
        other.onIntercept(async event => {
          try {
            if (event.request.method === 'POST') {
              assert.ok(event.networkId);
              const captured = await other.command('Network.getRequestPostData', {requestId: event.networkId});
              staleWrites.push({status: event.responseStatusCode, body: postData(captured)});
            }
            await other.command('Fetch.continueResponse', {requestId: event.requestId});
          } catch (error) { fatal = error; }
        });
        await other.command('Fetch.enable', {patterns: [{urlPattern: api + '/matches/*/action', requestStage: 'Response'}]});
      }
      await browser.evaluate(`(()=>{const buttons=[...document.querySelector(${json(`[data-hand-card-id="${meta.source}"]`)}).querySelectorAll('button')].filter(b=>b.textContent.trim()===${json(castLabel)}&&!b.disabled);if(buttons.length!==1)throw Error('Actual recovery cast cardinality');const b=buttons[0];b.click();${name === 'overlap-stale' ? 'b.click();' : ''}})()`);
      await browser.waitFor(`(async()=>{const r=await fetch(${json(api + '/matches/' + meta.id)});return r.ok&&(await r.json()).revision===${before.controller.revision + 1};})()`);
      await browser.waitFor("!document.body.innerText.includes('Match operation pending')");
      if (fatal) throw fatal;
      const paid = await get('/__built__/snapshot/' + meta.id);
      assert.equal(paid.state.cards[meta.source].zone, 'stack');
      assert.equal(paid.state.players['1'].mana_pool.U ?? 0, 0);
      assert.equal(writes.length, 1, 'One actual write, never replay');
      if (name === 'lost-response') {
        assert.equal(dropped, 1);
        await browser.waitFor("document.querySelector('[role=alert]') && [...document.querySelectorAll('button')].some(b=>b.textContent==='Resume automatic play')");
        await restartBackend(meta.id); await browser.command('Page.reload');
        await browser.waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision===${json(String(paid.controller.revision))}`);
        await validateColdOwnerChange(await get('/__built__/snapshot/' + meta.id), paid, out);
        assert.deepEqual(await get('/__built__/snapshot/' + meta.id), paid);
      } else {
        await other.evaluate(`(()=>{const buttons=[...document.querySelector(${json(`[data-hand-card-id="${meta.source}"]`)}).querySelectorAll('button')].filter(b=>b.textContent.trim()===${json(otherCastLabel)}&&!b.disabled);if(buttons.length!==1)throw Error('Actual stale-tab cast cardinality');buttons[0].click();})()`);
        await other.waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending')");
        if (fatal) throw fatal;
        assert.equal(staleWrites.length, 1, 'One actual stale-tab submission');
        assert.equal(staleWrites[0].status, 409, 'Actual stale revision rejection');
        assert.deepEqual(await get('/__built__/snapshot/' + meta.id), paid, 'Stale rejected root/controller/all SQL unchanged');
      }
      assert.ok(Date.now() - begin < 60000);
      results.push({name, writes, staleWrites, dropped, success: true});
    } catch (error) { primaryError = error; throw error; } finally { await closeBrowsersPreservingError(primaryError, other, browser); }
  }
  // Normal deck controls and real start receipts, not a fixture start response.
  const browser = await openBrowser(frontend);
  const attempts = []; let dropped = 0, fatal, dropAcknowledgments = 0;
  const idsBefore = new Set((await get('/matches')).map(m => m.id));
  let primaryError;
  try {
    await browser.waitFor("!!document.querySelector('a[href=\"#lab-tools\"]')");
    await browser.waitFor("document.querySelector('.saved-games') && !document.querySelector('.saved-games [role=\"status\"]')");
    await browser.evaluate("localStorage.removeItem('mtg.activeMatch');localStorage.removeItem('mtg.pendingStart')");
    await browser.command('Page.reload');
    await browser.waitFor("document.querySelector('a[href=\"#lab-tools\"]') && document.querySelector('details.match-setup') && !document.querySelector('.saved-games [role=\"status\"]')");
    await browser.evaluate("document.querySelector('a[href=\"#lab-tools\"]').click();document.querySelector('details.match-setup').open=true");
    const decks = await get('/decks'); assert.ok(decks.length >= 2);
    for (const [label, value] of [['Deck A', decks[0].id], ['Deck B', decks[1].id], ['Match mode', 'human_vs_human']]) {
      const selector = `select[aria-label="${label}"]`, expected = String(value);
      const readSelection = () => browser.evaluate(`(() => { const nodes = [...document.querySelectorAll(${json(selector)})]; return {readyState: document.readyState, cardinality: nodes.length, restoring: !!document.querySelector('.saved-games [role="status"]'), selects: nodes.map(s => ({value: s.value, disabled: s.disabled, options: [...s.options].map(o => ({value: o.value, selected: o.selected, disabled: o.disabled}))}))}; })()`);
      await journal(path.join(out, 'recovery-selection-readiness.jsonl'), {phase: 'before-option-wait', label, expected, actual: await readSelection()});
      await browser.waitFor(`(() => { const nodes = [...document.querySelectorAll(${json(selector)})]; return nodes.length === 1 && !nodes[0].disabled && [...nodes[0].options].filter(o => o.value === ${json(expected)} && !o.disabled).length === 1; })()`);
      await browser.evaluate(`(()=>{const s=document.querySelector('select[aria-label="${label}"]');s.value=${json(String(value))};s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await browser.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
      await browser.waitFor(`(() => { const nodes = [...document.querySelectorAll(${json(selector)})]; return nodes.length === 1 && nodes[0].value === ${json(expected)} && nodes[0].selectedOptions.length === 1 && nodes[0].selectedOptions[0].value === ${json(expected)}; })()`);
      await journal(path.join(out, 'recovery-selection-readiness.jsonl'), {phase: 'after-controlled-selection-retained', label, expected, actual: await readSelection()});
    }
    await reviewStart(browser); await browser.command('Network.enable');
    browser.onIntercept(async event => {
      try {
        if (event.request.method === 'POST') {
          assert.ok(event.networkId); const data = await browser.command('Network.getRequestPostData', {requestId: event.networkId});
          const normalized = Object.fromEntries(Object.entries(event.request.headers).map(([k, v]) => [k.toLowerCase(), v]));
          attempts.push({key: normalized['idempotency-key'], body: postData(data), status: event.responseStatusCode});
        }
        if (event.request.method === 'POST' && event.responseStatusCode === 200 && dropped < 2) {
          dropped++; await browser.command('Fetch.failRequest', {requestId: event.requestId, errorReason: 'Failed'});
          dropAcknowledgments++;
          await journal(path.join(out, 'pending-start-drop-acks.jsonl'), {requestId: event.requestId, networkId: event.networkId, responseStatusCode: event.responseStatusCode, dropped, acknowledged: dropAcknowledgments});
        } else await browser.command('Fetch.continueResponse', {requestId: event.requestId});
      } catch (error) { fatal = error; }
    });
    await browser.command('Fetch.enable', {patterns: [{urlPattern: api + '/matches/start', requestStage: 'Response'}]});
    await browser.click('Start Best-of-3 Match');
    await browser.waitFor("Boolean(localStorage.getItem('mtg.pendingStart'))", 30000);
    await waitForStartDropACKs(() => ({acknowledged: dropAcknowledgments, fatal}));
    await browser.waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Recover pending match start' && !b.disabled)");
    await browser.command('Page.reload');
    await browser.waitFor("document.querySelector('.battlefield') && !localStorage.getItem('mtg.pendingStart')", 75000);
    if (fatal) throw fatal;
    assert.equal(dropped, 2); assert.ok(attempts.length >= 3);
    for (const receipt of attempts) { assert.equal(receipt.key, attempts[0].key); assert.deepEqual(receipt.body, attempts[0].body); }
    const idsAfter = new Set((await get('/matches')).map(m => m.id));
    assert.equal(idsAfter.size, idsBefore.size + 1);
    results.push({name: 'pending-start', dropped, attempts, success: true});
  } catch (error) { primaryError = error; throw error; } finally { await closeBrowsersPreservingError(primaryError, browser); }
  await writeFile(path.join(out, 'recovery.json'), json(results, null, 2));
  assert.equal(results.length, 3); return results;
}

export async function runBuiltOrigins({api, frontend, hostile, out, token, mid, assertAlive}) {
  const body = json({player_id: 1, action: {type: 'pass_priority'}});
  const snapshot = async () => {
    const response = await fetch(api + '/__built__/snapshot/' + mid, {headers: {'X-Owned-Test-Token': token}});
    assert.equal(response.status, 200); return response.json();
  };
  const before = await snapshot(); const results = [];
  const preflight = await fetch(api + '/matches/' + mid + '/action', {method: 'OPTIONS', headers: {
    Origin: new URL(frontend).origin, 'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'Content-Type,Idempotency-Key,X-Match-Revision'}});
  assert.equal(preflight.status, 200); assert.equal(preflight.headers.get('access-control-allow-origin'), new URL(frontend).origin);
  // Trusted valid browser writes are witnessed by all40 paid episodes; this control is preflight-only.
  results.push({name: 'trusted', preflight: 200, valid_writes_scope: 'actual40 paid episodes'});
  for (const [name, page] of [['hostile', hostile], ['null', hostile + '/null']]) {
    assertAlive(); const browser = await openBrowser(page); const statuses = []; let fatal;
    let primaryError;
    try {
      browser.onIntercept(async event => {
        try {
          if (event.request.method === 'POST') statuses.push(event.responseStatusCode);
          await browser.command('Fetch.continueResponse', {requestId: event.requestId}, event.sessionId);
        } catch (error) { fatal = error; }
      });
      await browser.command('Fetch.enable', {patterns: [{urlPattern: api + '/matches/*/action', requestStage: 'Response'}]});
      await browser.enableOwnedIframeInterception([{urlPattern: api + '/matches/*/action', requestStage: 'Response'}]);
      const script = `fetch(${json(api + '/matches/' + mid + '/action')},{method:'POST',headers:{'Content-Type':'text/plain'},body:${json(body)}}).catch(()=>{});`;
      if (name === 'null') {
        const readyScript = `addEventListener('message',e=>{if(e.source===parent&&e.data==='owned-origin-go'){${script}}},{once:true});parent.postMessage('owned-origin-ready','*');`;
        await browser.evaluate(`(()=>{const f=document.createElement('iframe');f.dataset.ownedOriginProbe='true';f.sandbox='allow-scripts';addEventListener('message',e=>{if(e.source===f.contentWindow&&e.data==='owned-origin-ready')f.dataset.ready='true';});f.srcdoc=${json('<script>' + readyScript + '</script>')};document.body.append(f);})()`);
        await browser.waitFor(`document.querySelector('iframe[data-owned-origin-probe]')?.dataset.ready === 'true'`);
        await browser.waitForInterceptions(1);
        await browser.evaluate(`document.querySelector('iframe[data-owned-origin-probe]').contentWindow.postMessage('owned-origin-go','*')`);
      } else await browser.evaluate(script);
      const end = Date.now() + 15000;
      while (!statuses.length) { browser.assertInterceptionHealthy(); if (fatal) throw fatal; assert.ok(Date.now() < end); await new Promise(r => setTimeout(r, 50)); }
      await browser.waitForInterceptions(); if (fatal) throw fatal;
      assert.deepEqual(statuses, [403]); assert.deepEqual(await snapshot(), before);
      const protocol = await fetch(api + '/matches/' + mid + '/action', {method: 'POST', headers: {
        Origin: name === 'null' ? 'null' : new URL(hostile).origin, 'Content-Type': 'application/json'}, body});
      assert.equal(protocol.status, 403); assert.equal((await protocol.json()).detail.code, 'untrusted_browser_origin');
      results.push({name, browser_status: 403, protocol_status: 403, semantic_SQL_unchanged: true});
    } catch (error) { primaryError = error; throw error; } finally { await closeBrowsersPreservingError(primaryError, browser); }
  }
  const duplicated = await new Promise((resolve, reject) => {
    const request = httpRequest(api + '/matches/' + mid + '/action', {method: 'POST', headers: {
      Origin: [new URL(frontend).origin, new URL(frontend).origin], 'Content-Type': 'application/json'}}, response => {
      let data = ''; response.on('data', chunk => data += chunk); response.on('end', () => resolve({status: response.statusCode, body: JSON.parse(data)}));
    }); request.on('error', reject); request.setTimeout(15000, () => request.destroy(Error('Duplicate Origin bound'))); request.end(body);
  });
  assert.equal(duplicated.status, 403); assert.equal(duplicated.body.detail.code, 'untrusted_browser_origin');
  assert.deepEqual(await snapshot(), before); results.push({name: 'duplicate', ...duplicated, native_protocol_only: true});
  await writeFile(path.join(out, 'origins.json'), json(results, null, 2));
  assert.equal(results.length, 4); return results;
}
