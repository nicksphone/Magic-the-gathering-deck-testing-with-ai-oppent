import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

export async function runDelverRepairAudit({api,frontend,runtime,fixtureRequest,restartBackend,caseNames}) {
  const results=[], actions=[];
  const get=async route=>{const r=await fetch(api+route);assert.equal(r.status,200);return r.json();};
  for(const seat of [1,2]) for(const scenario of caseNames??['cathar-natural','delver-reveal','delver-decline','delver-ineligible','delver-empty','delver-stale']) {
    const row={seat,scenario,checks:[]}; const b=await openBrowser(frontend);let fixture,id;
    const check=(name,condition,detail)=>{row.checks.push({name,status:condition?'PASS':'RED',detail});console.log(`${condition?'PASS':'RED'} P${seat} ${scenario}: ${name}`);};
    async function loaded(){await b.waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session') && !document.body.innerText.includes('Match operation pending')");}
    async function checkpoint(stage){const value={audit:await fixtureRequest(`/${id}/audit`),state:await get(`/matches/${id}`),legal:await get(`/matches/${id}/legal-moves`)};await writeFile(path.join(runtime,`evidence/${seat}-${scenario}-${stage}.json`),JSON.stringify(value,null,2));return value;}
    async function restart(stage){const before=await checkpoint(stage+'-before');await restartBackend();const after=await checkpoint(stage+'-restored');check('real process restart preserves exact snapshot',before.audit.pid!==after.audit.pid&&before.audit.snapshot_sha256===after.audit.snapshot_sha256&&before.state.revision===after.state.revision);await b.reload();await loaded();check('actual App reload is read-only',(await fixtureRequest(`/${id}/audit`)).snapshot_sha256===before.audit.snapshot_sha256);}
    async function privacy(stage){const c=await checkpoint(stage);const actor=c.legal.player_id;const ids=[...c.audit.snapshot.players[String(3-actor)].hand,...c.audit.snapshot.players[String(3-actor)].library];check('opponent private IDs absent from DOM/legal choice',!ids.some(cid=>JSON.stringify(c.legal).includes(cid))&&await b.evaluate(ids.map(cid=>`!document.body.innerHTML.includes(${JSON.stringify(cid)})`).join('&&')));check('view reads preserve root',(await fixtureRequest(`/${id}/audit`)).snapshot_sha256===c.audit.snapshot_sha256);}
    async function clickAction(label){const before=await get(`/matches/${id}`);await b.click(label);await waitForApiState(`${api}/matches/${id}`,s=>s.revision>before.revision);await b.waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(String(before.revision))}`);await loaded();}
    async function step(){const c=await checkpoint('latest');let label;
      if(c.legal.moves.some(m=>m.type==='pass_priority')) label='Pass Priority';
      else if(c.legal.moves.some(m=>m.type==='declare_attackers')) label='Declare attackers (';
      else if(c.legal.moves.some(m=>m.type==='declare_blockers')) label='Declare blockers (';
      else throw new Error(`No ordinary offered turn control: ${JSON.stringify(c.legal.moves)}`);
      await clickAction(label);
    }
    async function until(predicate,max=100){for(let i=0;i<max;i++){const c=await checkpoint('latest');if(predicate(c))return c;await step();}throw new Error('Bounded actual turn controls did not reach expected phase');}
    try{
      await b.waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");await b.evaluate("localStorage.removeItem('mtg.activeMatch');localStorage.removeItem('mtg.pendingStart')");await b.reload();await b.waitFor("document.querySelector('.saved-games') && !document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");
      const name=scenario.startsWith('cathar')?'Brutal Cathar // Moonrage Brute':'Delver of Secrets // Insectile Aberration';
      const r=await fetch(`${api}/decks/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:`Human transform audit ${seat} ${scenario} ${randomUUID()}`,deck_text:`2 ${name}\n1 Grizzly Bears\n1 Shock\n56 Island`,source:'owned-transform-audit'})});assert.equal(r.status,200);const imported=await r.json();await writeFile(path.join(runtime,`evidence/${seat}-${scenario}-import.json`),JSON.stringify(imported,null,2));check('real HTTP import retains exact name/quantity',!imported.errors.length&&imported.mainboard.find(x=>x.card_name===name)?.quantity===2);
      fixture=await fixtureRequest(`?seat=${seat}&scenario=${scenario}&deck_id=${imported.deck_id}`,'POST');id=fixture.match.id;row.match_id=id;await b.evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(id)})`);await b.reload();await loaded();
      const initial=await checkpoint('initial');const source=initial.state.players[String(seat)].hand.find(c=>c.id===fixture.source_id);const fields=['name','mana_cost','type_line','oracle_text','power','toughness','colors'];check('hydration retains both canonical faces',fixture.canonical_faces.every((face,i)=>fields.every(k=>JSON.stringify(face[k]??null)===JSON.stringify(source.card_faces[i][k]??null))));await privacy('initial-private');check('controlled own top stays opaque before legitimate look',(scenario==='delver-empty'||!JSON.stringify(initial.legal).includes(fixture.top_id))&&await b.evaluate(`!document.body.innerHTML.includes(${JSON.stringify(fixture.top_id)})`));
      const before=initial.state.revision;await b.evaluate(`(()=>{const button=[...document.querySelector('[data-hand-card-id="${fixture.source_id}"]').querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('Cast')&&!b.disabled);if(!button)throw new Error('Actual cast control missing');button.click();})()`);await waitForApiState(`${api}/matches/${id}`,s=>s.revision>before);await loaded();
      const queued=await checkpoint('queued-cast');const wire=(await fixtureRequest(`/actions?match_id=${id}`)).at(-1);check('actual cast uses front face only',queued.state.stack.at(-1)?.label===fixture.canonical_faces[0].name&&wire.body.player_id===seat&&wire.body.action.type==='cast_spell'&&wire.body.action.card_id===fixture.source_id&&(wire.body.action.selected_face_index??0)===0&&Number(wire.revision_header)===initial.state.revision);await restart('queued-cast');
      if(scenario==='cathar-natural'){
        const pending=await until(c=>c.legal.moves.some(m=>m.type==='choose_trigger_target'));check('legitimate cast ETB offers opposing target',pending.legal.moves.some(m=>m.type==='choose_trigger_target'&&m.target_card_id===fixture.target_id));await restart('pending-etb');
        const index=pending.legal.moves.filter(m=>m.type==='choose_trigger_target').findIndex(m=>m.target_card_id===fixture.target_id);await b.waitFor("document.querySelector('.trigger-target-panel')");const rev=(await get(`/matches/${id}`)).revision;await b.evaluate(`document.querySelectorAll('.trigger-target-panel button')[${index}].click()`);await waitForApiState(`${api}/matches/${id}`,s=>s.revision>rev);await loaded();
        const entered=await until(c=>!c.state.stack.length);const front=entered.state.players[String(seat)].battlefield.find(c=>c.id===fixture.source_id);check('day front effective facts and actual exile',front?.type_line===fixture.canonical_faces[0].type_line&&front?.name==='Brutal Cathar'&&front.power===2&&front.toughness===2&&front.types.includes('Creature')&&JSON.stringify(front.colors)==='["W"]'&&entered.audit.snapshot.day_night==='day'&&entered.audit.snapshot.players[String(3-seat)].exile.includes(fixture.target_id));const ledger=JSON.stringify(entered.audit.snapshot.linked_exiles);
        const next=await until(c=>c.audit.snapshot.turn===2&&c.audit.snapshot.step==='upkeep');check('one active-player cast keeps day next upkeep',next.audit.snapshot.day_night==='day');
        const night=await until(c=>c.audit.snapshot.turn===3&&c.audit.snapshot.step==='upkeep');const back=night.state.players[String(seat)].battlefield.find(c=>c.id===fixture.source_id);check('zero-spell opposing turn naturally transforms at next upkeep',night.audit.snapshot.day_night==='night'&&back?.name==='Moonrage Brute'&&back.selected_face_index===1&&back.power===3&&back.toughness===3&&back.types.includes('Creature')&&JSON.stringify(back.colors)==='["R"]'&&back.oracle_text===fixture.canonical_faces[1].oracle_text&&back.type_line===fixture.canonical_faces[1].type_line&&back.keywords.includes('first strike')&&back.keywords.includes('ward pay 3 life'));
        check('same source and linked exile survive natural transform',JSON.stringify(night.audit.snapshot.linked_exiles)===ledger&&night.audit.snapshot.players[String(3-seat)].exile.includes(fixture.target_id));check('actual App renders effective back stats',await b.evaluate(`document.querySelector('[data-card-id="${fixture.source_id}"] .card-stats')?.textContent.includes('3/3')`));await restart('night');await privacy('night-private');
      }else{
        const entered=await until(c=>!c.state.stack.length);const front=entered.state.players[String(seat)].battlefield.find(c=>c.id===fixture.source_id);check('front enters as canonical blue 1/1',front?.name==='Delver of Secrets'&&front.power===1&&front.toughness===1&&JSON.stringify(front.colors)==='["U"]');
        const otherUpkeep=await until(c=>c.audit.snapshot.turn===2&&c.audit.snapshot.step==='upkeep');check('unrelated transform does not create day/night',otherUpkeep.audit.snapshot.day_night==='none');check('no Delver trigger on opponent upkeep',!otherUpkeep.audit.snapshot.stack.some(s=>s.source_card_id===fixture.source_id));
        const ownUpkeep=await until(c=>c.audit.snapshot.turn===3&&c.audit.snapshot.step==='upkeep');check('neither designation remains neither after zero-spell turn',ownUpkeep.audit.snapshot.day_night==='none');check('legitimate controller upkeep creates actual trigger',ownUpkeep.audit.snapshot.stack.some(s=>s.source_card_id===fixture.source_id));await restart('own-upkeep');
        const choice=await until(c=>c.legal.moves.some(m=>['choose_optional_effect','choose_mechanic'].includes(m.type))||!c.state.stack.length,10);const offered=choice.legal.moves.filter(m=>['choose_optional_effect','choose_mechanic'].includes(m.type));row.offered_reveal_choices=offered;
        check(scenario==='delver-empty'?'empty top finishes without a fabricated inspection choice':'human receives private look and optional reveal/decline',scenario==='delver-empty'?offered.length===0:offered.length>0,{offered,day_night:choice.audit.snapshot.day_night});
        if(!offered.length){
          const effective=choice.state.players[String(seat)].battlefield.find(c=>c.id===fixture.source_id);row.observed={name:effective?.name,power:effective?.power,toughness:effective?.toughness,colors:effective?.colors,oracle_text:effective?.oracle_text,log:choice.audit.snapshot.log.slice(-8)};
          if(scenario==='delver-decline')check('declining reveal leaves front and does not publish top name',effective?.name==='Delver of Secrets'&&!choice.audit.snapshot.log.slice(-8).some(s=>s.includes('reveals')));
          else if(scenario==='delver-reveal')check('automatic back materialization retains canonical blue flying 3/2 (not choice certification)',effective?.name==='Insectile Aberration'&&effective.power===3&&effective.toughness===2&&JSON.stringify(effective.colors)==='["U"]'&&effective.type_line===fixture.canonical_faces[1].type_line&&effective.oracle_text===fixture.canonical_faces[1].oracle_text&&effective.keywords.includes('flying'));
          else check('ineligible top does not transform',effective?.name==='Delver of Secrets'&&effective.power===1&&effective.toughness===1);
          check('no fabricated reveal/decline POST',!(await fixtureRequest(`/actions?match_id=${id}`)).some(p=>['choose_optional_effect','choose_mechanic'].includes(p.body.action.type)));
        }else{
          check('owner legal view privately inspects exactly current canonical top',offered.length===1&&offered[0].kind==='optional_reveal'&&offered[0].player_id===seat&&offered[0].inspected_cards.length===1&&offered[0].inspected_cards[0].id===fixture.top_id);
          const foreign=await get(`/matches/${id}/legal-moves?player_id=${3-seat}`);
          check('other seat cannot inspect or answer owned choice',foreign.moves.length===0&&!JSON.stringify(foreign).includes(fixture.top_id));
          check('public pending status contains no top/reference/continuation',!JSON.stringify(choice.state.pending_mechanic_choice).includes(fixture.top_id)&&!('effect_payload' in choice.state.pending_mechanic_choice));
          check('actual App provides private inspection and two explicit buttons',await b.evaluate("document.querySelector('[aria-label=\"Privately inspected cards\"]') && [...document.querySelectorAll('button')].some(b=>b.textContent==='Reveal inspected card'&&!b.disabled) && [...document.querySelectorAll('button')].some(b=>b.textContent==='Decline reveal'&&!b.disabled)"));
          check('inspection copy does not prohibit revealing ineligible cards',await b.evaluate("document.querySelector('[aria-label=\"Privately inspected cards\"]').textContent.includes('even if it will not transform') && !document.querySelector('[aria-label=\"Privately inspected cards\"]').textContent.includes('(not selectable)')"));
          await restart('pending-private-look');await privacy('pending-choice-private');
          if(scenario==='delver-stale'){
            const initialChoice=await checkpoint('before-other-human-decline');
            const r=await fetch(`${api}/matches/${id}/action`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':randomUUID(),'X-Match-Revision':String(initialChoice.state.revision)},body:JSON.stringify({player_id:seat,action:{type:'choose_mechanic',card_ids:['decline']}})});assert.equal(r.status,200);
            const once=await checkpoint('other-human-declined');await restartBackend();
            await b.click('Reveal inspected card');
            await b.waitFor("[...document.querySelectorAll('[role=alert]')].some(e=>/Match changed|reload authoritative/i.test(e.textContent)) && !document.body.innerText.includes('Match operation pending')");
            const after=await checkpoint('stale-ui-rejected');const posts=await fixtureRequest(`/actions?match_id=${id}`);
            check('actual stale reveal after restart rejects without mutation',posts.at(-1).status===409&&JSON.stringify(posts.at(-1).body.action.card_ids)==='["reveal"]'&&after.audit.snapshot_sha256===once.audit.snapshot_sha256&&after.audit.pid!==once.audit.pid);
            check('stale inspected controls reconcile away',await b.evaluate("document.querySelector('[aria-label=\"Privately inspected cards\"]')===null"));
          }else{
            const choiceId=scenario==='delver-decline'?'decline':'reveal';await clickAction(choiceId==='decline'?'Decline reveal':'Reveal inspected card');
            const posts=await fixtureRequest(`/actions?match_id=${id}`);const posted=posts.at(-1);
            check('actual checked choice wire is explicit and owner-scoped',posted.status===200&&posted.body.player_id===seat&&posted.body.action.type==='choose_mechanic'&&JSON.stringify(posted.body.action.card_ids)===JSON.stringify([choiceId]));
          }
          const done=await checkpoint('choice-resolved');const effective=done.state.players[String(seat)].battlefield.find(c=>c.id===fixture.source_id);
          check('private reveal continuation resolves once without moving top',done.audit.snapshot.players[String(seat)].library.at(-1)===fixture.top_id&&!done.state.pending_mechanic_choice&&!done.state.stack.length&&done.audit.snapshot.step==='upkeep');
          if(scenario==='delver-decline'||scenario==='delver-stale')check('declining reveal leaves front and does not publish top name',effective?.name==='Delver of Secrets'&&!done.audit.snapshot.log.slice(-8).some(s=>s.includes('reveals')));
          else if(scenario==='delver-reveal')check('automatic back materialization retains canonical blue flying 3/2 (not choice certification)',effective?.name==='Insectile Aberration'&&effective.power===3&&effective.toughness===2&&JSON.stringify(effective.colors)==='["U"]'&&effective.type_line===fixture.canonical_faces[1].type_line&&effective.oracle_text===fixture.canonical_faces[1].oracle_text&&effective.keywords.includes('flying'));
          else check('ineligible top does not transform',effective?.name==='Delver of Secrets'&&effective.power===1&&effective.toughness===1);
          check('no fabricated reveal/decline POST',done.state.revision>choice.state.revision);
        }
        await restart('after-upkeep-effect');await privacy('after-upkeep-private');
      }
      const posts=await fixtureRequest(`/actions?match_id=${id}`);check('all natural progression actions use checked HTTP successfully',posts.length>5&&posts.every(p=>p.status===200||(scenario==='delver-stale'&&p.status===409)));row.path='Actual App cast/target/priority/combat-confirmation events; no transformation helper invoked.';
    }catch(error){check('bounded actual event path completes without fabricated control',false,error.stack);}
    finally{if(id){row.actions=await fixtureRequest(`/actions?match_id=${id}`);actions.push(...row.actions);await writeFile(path.join(runtime,`evidence/${seat}-${scenario}-body.txt`),await b.evaluate('document.body.innerText'));}const s=await b.command('Page.captureScreenshot',{format:'png'});await writeFile(path.join(runtime,`evidence/${seat}-${scenario}.png`),Buffer.from(s.data,'base64'));await b.close();results.push(row);}
  }
  return {results,actions};
}
