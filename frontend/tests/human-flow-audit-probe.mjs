import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

export async function runHumanFlowAudit({ api, frontend, runtime, fixtureRequest, restartBackend }) {
  const results = [], actions = [];
  const scenarios = ['shark-cycle-only', 'shark-castable', 'renewed-accept', 'renewed-decline',
    'renewed-cast', 'hangarback', 'stale-shark', 'creature-control'];
  await mkdir(path.join(runtime, 'evidence'), { recursive: true });
  const get = async route => {
    const response = await fetch(api + route, { signal: AbortSignal.timeout(15000) });
    assert.equal(response.status, 200, route); return response.json();
  };
  for (const seat of [1, 2]) for (const scenario of scenarios) {
    const row = { seat, scenario, checks: [] };
    const b = await openBrowser(frontend);
    let fixture, id;
    function check(name, category, condition, detail) {
      const status = condition ? 'PASS' : 'RED';
      row.checks.push({ name, category, status, detail });
      console.log(`${status} P${seat} ${scenario}: ${name}`);
    }
    async function checkpoint(stage) {
      const audit = await fixtureRequest(`/${id}/audit`);
      const state = await get(`/matches/${id}`);
      const legal = await get(`/matches/${id}/legal-moves`);
      await writeFile(path.join(runtime, `evidence/${seat}-${scenario}-${stage}.json`), JSON.stringify({ audit, state, legal }, null, 2));
      return { audit, state, legal };
    }
    async function loaded() {
      await b.waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session') && !document.body.innerText.includes('Match operation pending')");
    }
    async function refreshed() {
      const before = (await checkpoint('pre-refresh')).audit;
      await b.reload(); await loaded();
      const after = (await checkpoint('post-refresh')).audit;
      check('refresh is read-only', 'safety', before.snapshot_sha256 === after.snapshot_sha256 && before.revision === after.revision);
    }
    async function privacy() {
      const before = (await fixtureRequest(`/${id}/audit`)).snapshot_sha256;
      const legal = await get(`/matches/${id}/legal-moves`);
      const state = await get(`/matches/${id}`);
      const viewer = legal.player_id;
      check('actual acting seat displayed', 'ui-control', await b.evaluate(`document.querySelector('.player .seat-label').textContent.includes('P${viewer}')`));
      let privateHand = await b.evaluate("document.querySelectorAll('.opponent .hand-card').length===0");
      for (const card of state.players[String(3-viewer)].hand) {
        privateHand &&= !await b.evaluate(`document.body.innerHTML.includes(${JSON.stringify(card.id)})`);
        privateHand &&= !JSON.stringify(legal).includes(card.id);
      }
      check('opponent hand absent from DOM and actor legal moves', 'privacy', privateHand);
      check('public view reads preserve root', 'safety', (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === before);
    }
    async function passUntilChoiceOrEmpty() {
      for (let i = 0; i < 8; i++) {
        const state = await get(`/matches/${id}`), legal = await get(`/matches/${id}/legal-moves`);
        if (!state.stack.length || legal.moves.some(m => m.type === 'choose_optional_effect' || m.type === 'choose_mechanic')) return { state, legal };
        assert.ok(legal.moves.some(m => m.type === 'pass_priority'), 'Use only an actual offered pass');
        await b.click('Pass Priority');
        await waitForApiState(`${api}/matches/${id}`, next => next.revision > state.revision);
        await b.waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(String(state.revision))}`);
        await loaded();
      }
      throw new Error('Canonical stack did not reach an actual choice or empty state within eight passes');
    }
    async function chooseCycleX(value) {
      const box = `[data-hand-card-id="${fixture.source_id}"]`;
      const selector = await b.evaluate(`(() => {const box=document.querySelector(${JSON.stringify(box)});return [...box.querySelectorAll('select')].some(s=>[...s.options].some(o=>o.textContent==='X=${value}'));})()`);
      check('human can explicitly choose affordable cycling X', 'ui-blocker', selector, { wanted: value });
      if (!selector) return false;
      const before = (await fixtureRequest(`/${id}/audit`)).snapshot_sha256;
      await b.evaluate(`(() => {const s=[...document.querySelector(${JSON.stringify(box)}).querySelectorAll('select')].find(s=>[...s.options].some(o=>o.textContent==='X=${value}'));Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,${JSON.stringify(String(value))});s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      check('cycling X draft preserves root', 'safety', (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === before);
      return true;
    }
    async function cycle() {
      const before = await get(`/matches/${id}`);
      await b.evaluate(`(() => {const button=[...document.querySelector('[data-hand-card-id="${fixture.source_id}"]').querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('Cycle')&&!b.matches(':disabled'));if(!button)throw new Error('Missing actual cycling button');button.click();})()`);
      await waitForApiState(`${api}/matches/${id}`, state => state.revision > before.revision);
      await loaded();
      return checkpoint('cycled');
    }
    try {
      await b.waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");
      await b.evaluate("localStorage.removeItem('mtg.activeMatch');localStorage.removeItem('mtg.pendingStart')");
      await b.reload();
      await b.waitFor("document.querySelector('.saved-games') && !document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");
      fixture = await fixtureRequest(`?seat=${seat}&scenario=${scenario}`, 'POST'); id = fixture.match.id;
      row.match_id = id;
      await b.evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(id)})`);
      await b.reload(); await loaded();
      const initial = await checkpoint('initial'); await privacy();
      check('unseen library IDs absent from DOM and legal choices', 'privacy', fixture.initial_library_ids.every(cid => !JSON.stringify(initial.legal).includes(cid))
        && await b.evaluate(fixture.initial_library_ids.map(cid => `!document.body.innerHTML.includes(${JSON.stringify(cid)})`).join('&&')));
      if (scenario.startsWith('shark') || scenario === 'stale-shark') {
        const cycles = initial.legal.moves.filter(m => m.type === 'cycle_card' && m.card_id === fixture.source_id);
        assert.ok(cycles.some(m => m.x_value === 2), 'Expected X=2 is actually affordable and offered');
        row.offered_cycling_x = cycles.map(m => m.x_value);
        if (!await chooseCycleX(2)) {
          check('missing-choice inspection sends no action', 'safety', (await fixtureRequest(`/actions?match_id=${id}`)).length === 0
            && (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === initial.audit.snapshot_sha256);
          await refreshed();
          continue;
        }
        if (scenario === 'stale-shark') {
          // A second human HTTP action changes the state while this actual App
          // keeps its old legal control. No DOM or frontend state is fabricated.
          const changed = await fetch(`${api}/matches/${id}/action`, { method: 'POST', headers: {
            'Content-Type': 'application/json', 'Idempotency-Key': randomUUID(), 'X-Match-Revision': String(initial.state.revision),
          }, body: JSON.stringify({ player_id: seat, action: { type: 'cycle_card', card_id: fixture.source_id, x_value: 2 } }) });
          assert.equal(changed.status, 200);
          const paid = await checkpoint('other-human-paid');
          await restartBackend();
          const resumed = await checkpoint('restarted-stale-ui');
          check('restart restores exact paid snapshot', 'restart', resumed.audit.snapshot_sha256 === paid.audit.snapshot_sha256 && resumed.audit.pid !== paid.audit.pid);
          await b.evaluate(`(() => {const button=[...document.querySelector('[data-hand-card-id="${fixture.source_id}"]').querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('Cycle')&&!b.matches(':disabled'));if(!button)throw new Error('Missing actual stale cycle control');button.click();})()`);
          await b.waitFor("[...document.querySelectorAll('[role=alert]')].some(e=>/Match changed|reload authoritative/i.test(e.textContent)) && !document.body.innerText.includes('Match operation pending')");
          const attempted = await fixtureRequest(`/actions?match_id=${id}`);
          const after = await checkpoint('stale-rejected');
          check('actual stale UI dispatch rejected before second mutation', 'safety', attempted.length === 2 && attempted[1].status === 409
            && attempted[1].revision_header === String(initial.state.revision) && after.audit.snapshot_sha256 === paid.audit.snapshot_sha256, attempted);
          check('stale cycling button reconciled away', 'ui-control', await b.evaluate(`document.querySelector('[data-hand-card-id="${fixture.source_id}"]')===null`));
          await refreshed(); await privacy();
          continue;
        }
        const paid = await cycle();
        const posted = await fixtureRequest(`/actions?match_id=${id}`);
        check('actual UI sends selected X and pays four mana', 'ui-control', posted[0].body.action.x_value === 2
          && Object.values(paid.state.players[String(seat)].mana_pool).reduce((a,n)=>a+n,0) === Object.values(initial.state.players[String(seat)].mana_pool).reduce((a,n)=>a+n,0)-4);
        check('self-cycling trigger above actual draw ability', 'engine-known', paid.state.stack.length === 2, paid.state.stack);
        await passUntilChoiceOrEmpty();
        const done = await checkpoint('resolved');
        const tokens = done.state.players[String(seat)].battlefield.filter(c => c.is_token);
        check('chosen X creates actual 2/2 flying Shark', 'engine-known', tokens.length === 1 && tokens[0].name === 'Shark'
          && tokens[0].power === 2 && tokens[0].toughness === 2 && tokens[0].keywords.some(k=>k.toLowerCase()==='flying'), tokens);
        check('cycling draw resolves once', 'ui-control', done.audit.snapshot.draws_this_turn[String(seat)] === 1);
        await refreshed(); await privacy();
      } else if (scenario.startsWith('renewed')) {
        if (scenario === 'renewed-cast') {
          await b.click('Cast Renewed Faith');
          await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
          await loaded(); await passUntilChoiceOrEmpty();
          const done = await checkpoint('normal-cast-resolved');
          const posts = await fixtureRequest(`/actions?match_id=${id}`);
          check('normal cast action and cost are canonical', 'control', posts[0].body.action.type === 'cast_spell'
            && done.state.players[String(seat)].mana_pool.W === 0 && done.state.players[String(seat)].mana_pool.C === 0);
          check('canonical normal spell gains six life', 'engine-baseline', done.state.players[String(seat)].life === initial.state.players[String(seat)].life+6,
            { before: initial.state.players[String(seat)].life, after: done.state.players[String(seat)].life });
        } else {
          const paid = await cycle();
          check('Renewed self-cycling trigger materializes', 'engine-known', paid.state.stack.length === 2, paid.state.stack);
          const atChoice = await passUntilChoiceOrEmpty();
          const offered = atChoice.legal.moves.some(m => m.type === 'choose_optional_effect');
          check('actual human optional life choice offered', 'engine-known', offered, atChoice.legal);
          if (offered) {
            check('public choice belongs to cycling human', 'privacy', atChoice.legal.player_id === seat);
            const foreign = await get(`/matches/${id}/legal-moves?player_id=${3-seat}`);
            check('foreign seat cannot dispatch the choice', 'privacy', foreign.moves.length === 0);
            await b.click(scenario === 'renewed-accept' ? 'Apply effect' : 'Decline effect');
            await loaded(); await passUntilChoiceOrEmpty();
          }
          const done = await checkpoint('resolved');
          check('actual selected optional result (not a synthetic choice)', 'engine-known', offered
            && done.state.players[String(seat)].life === initial.state.players[String(seat)].life+(scenario==='renewed-accept'?2:0));
          check('fixed cycling draws exactly once', 'control', done.audit.snapshot.draws_this_turn[String(seat)] === 1);
        }
        await refreshed(); await privacy();
      } else if (scenario === 'creature-control') {
        await b.click('Cast Grizzly Bears');
        await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
        await loaded(); await passUntilChoiceOrEmpty();
        const done = await checkpoint('creature-control-resolved');
        const bear = done.state.players[String(seat)].battlefield.find(c => c.id === fixture.source_id);
        check('independent canonical creature casts and resolves', 'control', bear?.power === 2 && bear?.toughness === 2
          && done.state.players[String(seat)].mana_pool.G === 0 && done.state.players[String(seat)].mana_pool.C === 0);
        await refreshed(); await privacy();
      } else {
        const move = initial.legal.moves.find(m => m.type === 'activate_mana_ability' && m.card_id === fixture.source_id && m.cost_text.includes('Sacrifice'));
        assert.ok(move);
        const selector = `[data-mana-source="${fixture.source_id}"][data-mana-index="${move.ability_index}"]`;
        await b.evaluate(`document.querySelector(${JSON.stringify(selector)}).closest('details').open=true`);
        const index = move.output_options.findIndex(o => o.color === 'B' && o.output_bundle.B === 2);
        assert.ok(index >= 0);
        await b.evaluate(`(() => {const box=document.querySelector(${JSON.stringify(selector)});const select=box.querySelector('select[aria-label^="Base mana output"]');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(select,${JSON.stringify(String(index))});select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
        await b.evaluate(`(() => {const box=document.querySelector(${JSON.stringify(selector)});const input=[...box.querySelectorAll('input[type=checkbox]')].find(e=>e.getAttribute('aria-label').includes(${JSON.stringify(fixture.victim_id)}));if(!input||input.matches(':disabled'))throw new Error('Missing offered sacrifice victim');input.click();})()`);
        check('chosen sacrifice draft preserves root', 'safety', (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === initial.audit.snapshot_sha256);
        await b.evaluate(`document.querySelector(${JSON.stringify(selector+' fieldset button')}).click()`);
        await waitForApiState(`${api}/matches/${id}`, state => state.revision > initial.state.revision);
        await loaded();
        const departed = await checkpoint('departed');
        check('actual chosen sacrifice pays BB and queues death trigger', 'control', departed.state.players[String(seat)].mana_pool.B === 2
          && departed.state.stack.length === 1 && departed.state.players[String(seat)].graveyard.some(c=>c.id===fixture.victim_id));
        check('death LKI retains actual two counters', 'engine-baseline',
          departed.audit.snapshot.cards[fixture.victim_id].last_known_battlefield.counters['+1/+1'] === 2,
          departed.audit.snapshot.cards[fixture.victim_id].last_known_battlefield);
        await restartBackend();
        check('death stack survives real restart', 'restart', (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === departed.audit.snapshot_sha256);
        await b.reload(); await loaded(); await passUntilChoiceOrEmpty();
        const done = await checkpoint('death-resolved');
        const tokens = done.state.players[String(seat)].battlefield.filter(c => c.is_token);
        check('two counters create exactly two tokens', 'engine-known', tokens.length === 2, tokens);
        check('canonical token artifact type represented', 'engine-known', tokens.length > 0 && tokens.every(c=>c.types.includes('Artifact')), tokens);
        let effective = tokens.length > 0;
        for (const token of tokens) {
          effective &&= token.power === 2 && token.toughness === 2 && token.keywords.some(k=>k.toLowerCase()==='flying');
          effective &&= await b.evaluate(`document.querySelector('[data-card-id="${token.id}"] .card-stats').textContent.trim()==='2/2'`);
        }
        check('actual effective 2/2 flying token views match public HTTP', 'effective-view', effective, tokens);
        await refreshed();
        const beforeRestart = (await fixtureRequest(`/${id}/audit`)).snapshot_sha256;
        await restartBackend(); await b.reload(); await loaded();
        check('resolved token snapshot survives restart', 'restart', (await fixtureRequest(`/${id}/audit`)).snapshot_sha256 === beforeRestart);
        for (const token of tokens) check('refreshed/restarted DOM retains effective token stats', 'effective-view',
          await b.evaluate(`document.querySelector('[data-card-id="${token.id}"] .card-stats').textContent.trim()==='2/2'`));
        await privacy();
      }
    } catch (error) {
      check('flow execution', 'infrastructure-or-control', false, error.stack);
    } finally {
      if (id) {
        await checkpoint('final').catch(error => { row.final_capture_error = error.stack; });
        const captured = await fixtureRequest(`/actions?match_id=${id}`).catch(() => []);
        actions.push(...captured); row.action_statuses = captured.map(action => action.status);
      }
      await writeFile(path.join(runtime, `evidence/${seat}-${scenario}-body.txt`), await b.evaluate('document.body.innerText').catch(()=>'Browser context unavailable'));
      const screenshot = await b.command('Page.captureScreenshot', {format:'png'}).catch(()=>null);
      if (screenshot) await writeFile(path.join(runtime, `evidence/${seat}-${scenario}.png`), Buffer.from(screenshot.data,'base64'));
      await b.close(); results.push(row);
      await writeFile(path.join(runtime, 'evidence/progress.json'), JSON.stringify(results,null,2));
    }
  }
  return { results, actions };
}
