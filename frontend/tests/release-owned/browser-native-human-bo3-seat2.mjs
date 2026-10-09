import assert from 'node:assert/strict';
import { appendFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { openBrowser, closeBrowsersPreservingError } from './browser-driver.mjs';

const DECKS = [
  [[4,'Monastery Swiftspear'],[4,'Soul-Scar Mage'],[4,'Kumano Faces Kakkazan'],[4,'Lightning Bolt'],
    [4,'Lava Spike'],[4,'Rift Bolt'],[4,'Skewer the Critics'],[4,'Shock'],[4,'Light Up the Stage'],[4,'Skullcrack'],[20,'Mountain']],
  [[4,'Goblin Guide'],[4,'Eidolon of the Great Revel'],[4,'Monastery Swiftspear'],[4,'Lightning Bolt'],
    [4,'Lava Spike'],[4,'Rift Bolt'],[4,'Boros Charm'],[4,'Skullcrack'],[4,'Shock'],[16,'Mountain'],[4,'Plains'],[4,'Plateau']],
];
const SWAPS = [['Soul-Scar Mage','Goblin Guide'], ['Goblin Guide','Soul-Scar Mage']];
// NEW additional episode: reverse the same complete deck/sideboard pair by seat.
DECKS.reverse();
SWAPS.reverse();
const json = value => JSON.stringify(value);

// Explicit public projection before the selector can receive an API state.
function actorView(raw, pid) {
  const players = {};
  for (const [key, p] of Object.entries(raw.players)) players[key] = {
    life:p.life, mana_pool:p.mana_pool, hand_count:p.hand_count, library_count:p.library_count,
    battlefield:p.battlefield, graveyard:p.graveyard,
    exile:(p.exile ?? []).filter(c => !c.face_down), hand:Number(key) === pid ? p.hand : [],
  };
  return { id:raw.id, revision:raw.revision, game_number:raw.game_number, step:raw.step,
    turn:raw.turn, active_player:raw.active_player, priority_player:raw.priority_player,
    winner:raw.winner, match_complete:raw.match_complete, score:raw.score,
    controllers:raw.controllers, pregame_pending:raw.pregame_pending, players,
    stack:raw.stack.map(item=>({id:item.id,label:item.label,controller:item.controller,source_card_id:item.source_card_id})),
    mulligan_count:raw.mulligan_count, mulligan_bottomed:raw.mulligan_bottomed };
}
function inventory(view) {
  return Object.fromEntries(Object.entries(view.sideboarding??{}).map(([pid, row]) => {
    const sum = {};
    for (const item of [...row.mainboard,...row.sideboard]) sum[item.card_name] = (sum[item.card_name] ?? 0) + item.quantity;
    return [pid,Object.fromEntries(Object.entries(sum).sort())];
  }));
}
function retained(view) {
  return { id:view.id, score:view.score, revision:view.revision, game_number:view.game_number,
    next_play_draw_chooser:view.next_play_draw_chooser, sideboarding:view.sideboarding,
    controllers:view.controllers, match_complete:view.match_complete };
}

export async function runNativeHumanBo3Seat2({mode,api,frontend,out,restartBackend,maxMilliseconds,assertAlive}) {
  assert.equal(mode, 'player_vs_ai');
  const dir = path.join(out,'player_vs_ai-seat2'); await mkdir(dir,{mode:0o700});
  const browser = await openBrowser(frontend);
  const {evaluate,waitFor,click,command} = browser;
  let raw, legal, fatal, writes=0, starts=0, createdId, actualStartDifficulty;
  const importedIds=[];
  const begin=Date.now(), counts={}, games=new Set(), naturalKinds=new Set();
  const projectionLog=path.join(dir,'actor-decisions.jsonl');
  const apiOrigin=new URL(api).origin, frontendOrigin=new URL(frontend).origin;
  const bounded=()=>{assertAlive();if(fatal)throw fatal;assert.ok(Date.now()-begin<maxMilliseconds,'Episode wall bound');assert.ok(writes<6000,'Episode action bound');};
  const readPath=p=>p==='/health'||p.startsWith('/decks')||p==='/cards/completeness'||p==='/matches'||/^\/matches\/[a-z0-9-]+(?:\/legal-moves)?$/.test(p);
  function permitted(req) {
    const u=new URL(req.url);
    if (u.origin===frontendOrigin) return req.method==='GET';
    if (u.origin!==apiOrigin) return false;
    if(req.method==='GET')return readPath(u.pathname)||u.pathname.startsWith('/card-images/')
      ||u.pathname==='/diagnostics/runs'&&u.search==='?limit=20';
    if(req.method==='OPTIONS')return true;
    if(req.method!=='POST')return false;
    return ['/decks/import','/simulate/batch/preflight','/matches/start'].includes(u.pathname)
      || /^\/matches\/[a-z0-9-]+\/(action|sideboard|next-game)$/.test(u.pathname)
      || /^\/matches\/[a-z0-9-]+\/autoplay$/.test(u.pathname)&&u.search==='?ticks=1';
  }
  browser.onIntercept(async event=>{
    const paused={requestId:event.requestId,method:event.request.method,url:event.request.url,
      stage:event.responseStatusCode?'Response':'Request',status:event.responseStatusCode};
    let operation='paused-event-record';
    try {
      await appendFile(path.join(dir,'private-paused-requests.jsonl'),json(paused)+'\n');
      if (!event.responseStatusCode) {
        if (!permitted(event.request)) {
          // Remote art is deliberately unavailable offline; real CardArt owns its fallback.
          if(event.resourceType==='Image') { operation='Fetch.failRequest';await command('Fetch.failRequest',{requestId:event.requestId,errorReason:'BlockedByClient'}); return; }
          throw new Error(`Outside native browser protocol: ${event.request.method} ${event.request.url}`);
        }
        if(event.request.method==='POST') {
          writes++;
          if(new URL(event.request.url).pathname==='/matches/start') {
            starts++; const body=JSON.parse(event.request.postData);
            assert.ok(!('seed'in body),'No seed injection');assert.equal(body.mode,mode);assert.equal(body.best_of,3);
            assert.equal(body.controller_a, 'ai'); assert.equal(body.controller_b, 'human');
            assert.equal(String(body.deck_a_id), importedIds[0]); assert.equal(String(body.deck_b_id), importedIds[1]);
            assert.equal(body.ai_difficulty, 'master_plus'); actualStartDifficulty=body.ai_difficulty;
          }
          await appendFile(path.join(dir,'private-requests.jsonl'),json(event.request)+'\n');
        }
        operation='Fetch.continueRequest';await command(operation,{requestId:event.requestId,interceptResponse:true});
      } else {
        const url=new URL(event.request.url);
        if(url.origin===apiOrigin&&!url.pathname.startsWith('/card-images/')) {
          operation='Fetch.getResponseBody';const response=await command(operation,{requestId:event.requestId});
          const text=response.base64Encoded?Buffer.from(response.body,'base64').toString():response.body;
          await appendFile(path.join(dir,'private-responses.jsonl'),json({path:url.pathname,status:event.responseStatusCode,body:text})+'\n');
          assert.ok(event.responseStatusCode>=200&&event.responseStatusCode<300,`HTTP ${event.responseStatusCode}: ${url.pathname} ${text}`);
          if(event.request.method!=='OPTIONS') {
            const d=JSON.parse(text);
            if(url.pathname==='/matches/start')createdId=d.id;
            if(url.pathname==='/decks/import') {assert.deepEqual(d.errors,[]);importedIds.push(String(d.deck_id));}
            if(d.id&&d.players)raw=d;
            if(url.pathname.endsWith('/legal-moves'))legal=d;
            if(url.pathname==='/simulate/batch/preflight')assert.deepEqual(d.known_unsupported_cards,[],'Native current deck gaps');
          }
        }
        operation='Fetch.continueResponse';await command(operation,{requestId:event.requestId});
      }
    } catch(error) {
      fatal??=error;
      try {await appendFile(path.join(dir,'private-interception-errors.jsonl'),json({...paused,operation,error:error.stack})+'\n');}
      catch {/* Preserve original terminal error if evidence writing also fails. */}
      try {await command('Fetch.failRequest',{requestId:event.requestId,errorReason:'Aborted'});}catch{/* Closed request; failure remains terminal. */}
    }
  });
  await command('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  async function consistent() {
    bounded();
    await waitFor(`!!document.querySelector('.battlefield') && !document.querySelector('fieldset')?.disabled && !document.body.innerText.includes('Restoring saved session') && !document.querySelector('.saved-games [role="status"]')`,30000);
    const end=Date.now()+30000;
    while(Date.now()<end) {
      bounded();
      const rendered=await evaluate("Number(document.querySelector('.battlefield')?.dataset.matchRevision)");
      if(raw&&(!createdId||raw.id===createdId)&&rendered===raw.revision&&(raw.winner!==null||legal?.revision===raw.revision))return;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw new Error('Rendered/observed legal revision did not converge');
  }
  async function changed(label,revision) {
    const end=Date.now()+30000;
    while(Date.now()<end) {bounded();if(raw&&raw.revision>revision){await consistent();counts[label]=(counts[label]??0)+1;return;}await new Promise(resolve=>setTimeout(resolve,100));}
    throw new Error(`No revision after ${label}; no uncertain mutation retry`);
  }
  async function button(label,scope='document') {
    bounded();
    await waitFor(`${scope} && [...${scope}.querySelectorAll('button')].some(b=>b.textContent.trim()===${json(label)}&&!b.disabled)`);
    await evaluate(`(()=>{const b=[...${scope}.querySelectorAll('button')].find(b=>b.textContent.trim()===${json(label)}&&!b.disabled);if(!b)throw Error('Missing exact button');b.click();})()`);
  }
  async function pacingSnapshot(phase) {
    const dom=await evaluate(`(()=>{const e=document.querySelector('input[aria-label="AI playback delay"]');return e?{value:e.value,min:e.min,max:e.max,step:e.step,disabled:e.disabled}:null;})()`);
    await appendFile(path.join(dir,'pacing-dom.jsonl'),json({utc:new Date().toISOString(),elapsedMilliseconds:Date.now()-begin,phase,revision:raw?.revision,game:raw?.game_number,dom})+'\n');
  }
  async function input(selector,value) {
    const pacing=selector==='input[aria-label="AI playback delay"]';
    if(pacing)await pacingSnapshot('before-original600-setting');
    await waitFor(`document.querySelector(${json(selector)}) && !document.querySelector(${json(selector)}).disabled`);
    await evaluate(`(()=>{const e=document.querySelector(${json(selector)});if(!e||e.disabled)throw Error('Missing input');const setter=Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;setter.call(e,${json(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await waitFor(`document.querySelector(${json(selector)})?.value===${json(String(value))}`);
    if(pacing)await pacingSnapshot('after-original600-setting');
  }
  async function select(selector,values,index=0) {
    await waitFor(`(() => { const e = document.querySelectorAll(${json(selector)})[${index}]; return e && !e.disabled && ${json(values)}.every(v => [...e.options].some(o => o.value === v && !o.disabled)); })()`);
    await evaluate(`(()=>{const e=document.querySelectorAll(${json(selector)})[${index}];if(!e||e.disabled)throw Error('Missing select');const wanted=${json(values)};if(wanted.some(v=>![...e.options].some(o=>o.value===v&&!o.disabled)))throw Error('Choice not offered');for(const o of e.options)o.selected=wanted.includes(o.value);e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    await waitFor(`JSON.stringify([...document.querySelectorAll(${json(selector)})[${index}].selectedOptions].map(o=>o.value))===${json(json(values))}`);
  }
  async function selections(selector) {return evaluate(`[...document.querySelectorAll(${json(selector)})].map((s,i)=>({i,label:s.getAttribute('aria-label'),multiple:s.multiple,disabled:s.disabled,options:[...s.options].filter(o=>o.value&&!o.disabled).map(o=>({value:o.value,text:o.textContent.trim()})),first:s.options[0]?.textContent.trim()}))`);}
  async function action(label,operation) {const revision=raw.revision;await operation();await changed(label,revision);}
  async function cold(label) {
    const before=retained(raw);await writeFile(path.join(dir,`${label}-before.json`),json(before));
    const ledger=await restartBackend(raw.id);
    for(const pid of [1,2]) {
      const sum={};for(const c of [...ledger.mainboards[String(pid)],...ledger.sideboards[String(pid)]])sum[c.card_name]=(sum[c.card_name]??0)+c.quantity;
      assert.deepEqual(Object.fromEntries(Object.entries(sum).sort()),fixedInventory[String(pid)]);
      assert.equal(ledger.mainboards[String(pid)].reduce((n,c)=>n+c.quantity,0),60);
    }
    await command('Page.reload');await consistent();
    if(mode==='player_vs_ai')await input('input[aria-label="AI playback delay"]','600');
    assert.deepEqual(retained(raw),before,'Native cold restored public controller');
    await writeFile(path.join(dir,`${label}-after.json`),json(retained(raw)));
  }
  async function spell(move,pid,view) {
    const box=`[data-hand-card-id="${move.card_id}"]`;
    await waitFor(`!!document.querySelector(${json(box)})`);
    const rows=await selections(`${box} select`);
    const costs=move.cost_options??[];
    const chosen=[...costs].sort((a,b)=>String(a.mana_cost??'').length-String(b.mana_cost??'').length||String(a.id).localeCompare(String(b.id)))[0];
    const costRow=rows.find(r=>r.first==='Cost Option');
    // Use DOM indices through querySelectorAll, not CSS nth-of-type across nested labels.
    async function rowChoice(index,values){await select(`${box} select`,values,index);}
    if(costRow){assert.ok(chosen);await rowChoice(costRow.i,[chosen.id]);}
    const mode=(await selections(`${box} select`)).find(r=>r.label==='Spell mode');
    let selectedMode;
    if(mode){const option=mode.options.find(o=>/deals \d+ damage/i.test(o.text))??mode.options[0];assert.ok(option);
      assert.ok((move.target_hints?.available_modes??move.target_hints?.modes??[]).includes(option.value),'Selected mode must be publicly offered');
      await rowChoice(mode.i,[option.value]);selectedMode=option.value;}
    const card=view.players[String(pid)].hand.find(c=>c.id===move.card_id)??move.card_view;
    assert.ok(card&&card.id===move.card_id,'Spell target policy requires actor-visible source');
    const targetText=selectedMode??card.card_faces?.[move.selected_face_index??0]?.oracle_text??card.oracle_text??'';
    const exclusive=Boolean(!selectedMode&&move.target_hints?.single_target_alternative||(/\b(?:any target|target player or planeswalker)\b/i.test(targetText)&&(targetText.match(/\btarget\b/gi)?.length??0)===1));
    const publicBoard=new Set(Object.values(view.players).flatMap(p=>p.battlefield).map(c=>c.id));
    const opposingBoard=new Set(view.players[String(3-pid)].battlefield.map(c=>c.id));
    let playerChosen=false;
    const targetRows=await selections(`${box} select`);
    if(exclusive&&targetRows.some(r=>r.first==='Choose Target'||r.label==='Player target')) {
      // Clear the unused alternative before choosing the player: its onChange can clear that player.
      for(const row of targetRows.filter(r=>['Target Creature','Target Permanent'].includes(r.first)&&!r.multiple)) {
        const value=await evaluate(`document.querySelectorAll(${json(`${box} select`)})[${row.i}].value`);
        if(value!=='')await rowChoice(row.i,['']);
      }
    }
    for(const row of await selections(`${box} select`)) {
      if(row.disabled||row.first==='Cost Option'||row.label==='Spell mode')continue;
      if(row.first==='Choose Target'||row.label==='Player target') {
        const preferred=row.options.find(o=>o.value===String(3-pid)||o.value===`player:${3-pid}`);
        assert.ok(preferred,'Finite burn target is not offered');await rowChoice(row.i,[preferred.value]);playerChosen=true;
      } else if(['Target Creature','Target Permanent'].includes(row.first)&&!row.multiple) {
        if(exclusive&&playerChosen) {
          const value=await evaluate(`document.querySelectorAll(${json(`${box} select`)})[${row.i}].value`);
          assert.equal(value,'','Native exclusive player choice must leave companion card slot empty');
        } else {
          const offered=row.options.filter(o=>publicBoard.has(o.value));
          const chosenTarget=offered.find(o=>opposingBoard.has(o.value))??offered[0];
          assert.ok(chosenTarget,'No actual offered public battlefield target; no private/default fallback');
          await rowChoice(row.i,[chosenTarget.value]);
        }
      } else if(row.label?.startsWith('Pay ')) {assert.ok(row.options[0]);await rowChoice(row.i,[row.options[0].value]);}
      else if(row.label?.startsWith('Discard for cost')||row.label?.startsWith('Sacrifice for cost')) {
        const discard=row.label.startsWith('Discard');const count=discard?chosen?.discard_cards:chosen?.sacrifice_creatures;
        assert.ok(Number.isInteger(count));assert.ok(row.options.length>=count);await rowChoice(row.i,row.options.slice(0,count).map(o=>o.value));
      } else if(row.first?.startsWith('Face 1:')) {assert.ok(row.options.some(o=>o.value==='0'));await rowChoice(row.i,['0']);}
      else if(row.options.length&&row.first!=='Cost Option')throw new Error(`Unmapped finite spell control: ${json(row)}`);
    }
    const automatic=await evaluate(`[...document.querySelector(${json(box)}).querySelectorAll('input[aria-label^="Automatic resources"]')].map(e=>e.checked)`);
    assert.ok(automatic.every(Boolean),'Native automatic casting resources not silently overwritten');
    const scope=`document.querySelector(${json(box)})`;
    const label=await evaluate(`[...${scope}.querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('Cast ')&&!b.disabled)?.textContent.trim()`);
    assert.ok(label,'Missing or incomplete actual spell UI');await button(label,scope);
  }
  async function mechanic(move,view) {
    const kind=move.kind;naturalKinds.add(kind);
    const panel="document.querySelector('.block-panel:has(h3)')";
    if(kind==='suspend_cast') {
      const m=legal.moves.find(m=>m.type==='cast_spell'&&m.from_exile);
      if(m){await spell(m,legal.player_id,view);return;}
      assert.ok(move.options.includes('decline'));await button('Decline suspended casting');return;
    }
    if(['cleanup_discard','mulligan_bottom','scry','surveil'].includes(kind)) {
      const count=['scry','surveil'].includes(kind)?0:move.count;assert.ok(Number.isInteger(count));
      await evaluate(`(()=>{const p=${panel};const boxes=[...p.querySelectorAll('input[type=checkbox]')];if(boxes.length!==${move.options.length})throw Error('Options/control mismatch');boxes.forEach((b,i)=>{if(b.checked!==(i<${count}))b.click();});})()`);
      await button('Confirm Selection',panel);return;
    }
    if(['effect_cast','optional_search','draw','land_entry','saga_entry'].includes(kind)) {
      assert.ok(move.options.length);const choice=move.options[0];await button(move.option_labels?.[choice]??choice,panel);return;
    }
    if(kind==='combat_damage') {
      const cards=Object.values(view.players).flatMap(p=>p.battlefield);
      let remaining=move.count;assert.ok(Number.isInteger(remaining));
      for(const [index,target] of move.options.entries()) {
        const card=cards.find(c=>c.id===target);
        const amount=card&&index<move.options.length-1?Math.min(remaining,Math.max(0,Number(card.toughness)-(Number(card.damage_marked)||0))):remaining;
        const label=`Damage to ${move.option_labels?.[target]??target} ${target}`;
        await input(`input[aria-label=${json(label)}]`,String(amount));remaining-=amount;
      }
      assert.equal(remaining,0,'Unrepresentable complete public combat assignment');await button('Assign Damage',panel);return;
    }
    throw new Error(`Unmapped required mechanic ${kind}; no fallback pass`);
  }
  async function policy(view,moves,pid) {
    const pick=type=>moves.find(m=>m.type===type);
    if(pick('choose_mechanic'))return action('mechanic',()=>mechanic(pick('choose_mechanic'),view));
    if(pick('choose_trigger_order'))return action('order',()=>button((pick('choose_trigger_order').trigger_labels??pick('choose_trigger_order').trigger_order).join(' -> '),"document.querySelector('.trigger-order-panel')"));
    if(pick('choose_optional_effect')) {const m=moves.find(m=>m.type==='choose_optional_effect'&&m.accept===true)??pick('choose_optional_effect');return action('optional',()=>button(m.accept?'Apply effect':'Decline effect',"document.querySelector('.optional-effect-panel')"));}
    if(pick('choose_trigger_target')) {const m=moves.find(m=>m.type==='choose_trigger_target'&&m.target_player===3-pid)??pick('choose_trigger_target');return action('trigger-target',()=>button(m.target_name??m.target_card_id??`Player ${m.target_player}`,"document.querySelector('.trigger-target-panel')"));}
    if(pick('choose_replacement'))return action('replacement',()=>button(pick('choose_replacement').replacement_name??pick('choose_replacement').replacement_source_id,"document.querySelector('.replacement-choice-panel')"));
    if(view.pregame_pending) {
      const hand=view.players[String(pid)].hand,lands=hand.filter(c=>c.types.includes('Land')).length;
      if((lands<2||lands>5)&&(view.mulligan_count[String(pid)]??0)<2&&pick('mulligan'))return action('mulligan',()=>button('Mulligan'));
      const bottom=(view.mulligan_count[String(pid)]??0)-(view.mulligan_bottomed?.[String(pid)]??0);
      for(const c of [...hand].sort((a,b)=>Number(a.types.includes('Land'))-Number(b.types.includes('Land'))).slice(0,bottom)) {
        const label=`Bottom ${c.name} ${c.id}`;await evaluate(`document.querySelector('input[aria-label='+CSS.escape(${json(label)})+']').click()`);
      }
      return action('keep',()=>button('Keep Hand'));
    }
    if(pick('block')) {
      const m=pick('block'),publicCards=Object.values(view.players).flatMap(p=>p.battlefield),used=new Set();
      const incoming=m.attackers.reduce((n,a)=>n+(Number(publicCards.find(c=>c.id===a.id)?.power)||0),0);
      for(const [index,a] of m.attackers.entries()) {
        const card=publicCards.find(c=>c.id===a.id);assert.ok(card);
        const b=m.blockers.find(b=>!used.has(b.id)&&m.legal_blocks[b.id].includes(a.id)&&
          (Number(publicCards.find(c=>c.id===b.id)?.power)>=Number(card.toughness)||incoming>=view.players[String(pid)].life));
        await select('#block-declaration select[multiple]',b?[b.id]:[],index);if(b)used.add(b.id);
      }
      for(const row of await selections('select[aria-label^="Block payment"]')){assert.ok(row.options[0]);await select(`select[aria-label=${json(row.label)}]`,[row.options[0].value]);}
      return action('block',()=>button('Submit Blocks'));
    }
    if(pick('attack')) {
      await button('Select all',"document.querySelector('#attack-declaration')");
      for(const row of await selections('select[aria-label^="Attack payment"]')){assert.ok(row.options[0]);await select(`select[aria-label=${json(row.label)}]`,[row.options[0].value]);}
      return action('attack',()=>button('Submit Attackers'));
    }
    if(pick('play_land')) {
      const move=pick('play_land');
      const card=view.players[String(pid)].hand.find(c=>c.id===move.card_id)??move.card_view;
      assert.ok(card&&card.id===move.card_id,'Offered land must bind an actor-visible card');
      const name=move.card_name??card.card_faces?.[move.selected_face_index??0]?.name??card.name;
      assert.ok(typeof name==='string'&&name.length,'Missing offered land label');
      const label=`Play Land ${name}${move.entry_choice==='pay_two_life'?' (pay 2 life, untapped)':move.entry_choice==='tapped'?' (tapped)':''}${move.graveyard_permission_name?` via ${move.graveyard_permission_name}`:''}`;
      const scope=`document.querySelector('[data-hand-card-id='+CSS.escape(${json(move.card_id)})+']')`;
      return action('land',()=>button(label,scope));
    }
    if(pick('suspend')) {
      const m=pick('suspend');const label=await evaluate(`[...document.querySelectorAll('[data-hand-card-id="${m.card_id}"] button')].find(b=>b.textContent.trim().startsWith('Suspend ')&&!b.disabled)?.textContent.trim()`);
      assert.ok(label,'Missing finite suspend UI');return action('suspend',()=>button(label));
    }
    const casts=moves.filter(m=>m.type==='cast_spell');
    if(casts.length) {const m=casts.find(m=>view.players[String(pid)].hand.find(c=>c.id===m.card_id)?.types.includes('Creature'))??casts[0];return action(m.from_exile?'exile-cast':'cast',()=>spell(m,pid,view));}
    assert.ok(pick('pass_priority'),'No native public advance/control; stop');
    return action('pass',()=>button('Pass Priority'));
  }
  const fixedInventory=Object.fromEntries(DECKS.map((deck,i)=>[String(i+1),Object.fromEntries([...deck,[4,SWAPS[i][1]]].map(([quantity,name])=>[name,quantity]).sort((a,b)=>a[0].localeCompare(b[0])))]));
  function assertVisibleInventory(){for(const [pid,sum] of Object.entries(inventory(raw)))assert.deepEqual(sum,fixedInventory[pid]);}
  let primaryError;
  try {
    // openBrowser already navigated: reloading here can cancel paused startup reads.
    await waitFor("!!document.querySelector('a[href=\"#lab-tools\"]')",30000);
    await waitFor("document.querySelector('.saved-games') && !document.querySelector('.saved-games [role=\"status\"]')");
    await evaluate("document.querySelector('a[href=\"#lab-tools\"]').click()");
    await waitFor("!!document.querySelector('input[aria-label=\"Deck name\"]') && !!document.querySelector('textarea[aria-label=\"Deck list\"]')",30000);
    for(let i=0;i<2;i++) {
      await input('input[aria-label="Deck name"]',`Native browser ${mode} seat${i+1}`);
      await input('textarea[aria-label="Deck list"]',[...DECKS[i].map(([n,c])=>`${n} ${c}`),'Sideboard',`4 ${SWAPS[i][1]}`].join('\n'));
      await button('Save Deck');
      const deadline=Date.now()+30000;
      while(importedIds.length<i+1){bounded();assert.ok(Date.now()<deadline,'UI deck import receipt');await new Promise(resolve=>setTimeout(resolve,100));}
      await waitFor(`document.querySelector('select[aria-label="Deck A"]')?.querySelector('option[value="${importedIds[i]}"]')`);
    }
    const ids=importedIds;assert.equal(ids.length,2);
    await waitFor("document.querySelector('details.match-setup summary')");
    await evaluate("(()=>{const d=document.querySelector('details.match-setup');if(!d.open)d.querySelector('summary').click();})()");
    await select('select[aria-label="Deck A"]',[ids[0]]);await select('select[aria-label="Deck B"]',[ids[1]]);
    await select('select[aria-label="Match mode"]',[mode]);await select('select[aria-label="Match length"]',['3']);await select('select[aria-label="AI difficulty"]',['master_plus']);
    assert.equal(await evaluate("document.querySelector('select[aria-label=\"AI difficulty\"]').selectedOptions[0].textContent.trim()"),'Master+');
    await waitFor("!!document.querySelector('select[aria-label=\"Human seat\"]')");
    await select('select[aria-label="Human seat"]',['2']);
    assert.equal(await evaluate("document.querySelector('select[aria-label=\"Human seat\"]').selectedOptions[0].textContent.trim()"),'Seat 2 (Deck B)');
    await button('Start Best-of-3 Match');await waitFor("!!document.querySelector('input[aria-label=\"Acknowledge exploratory interactive match\"]')");
    assert.equal(starts,0,'No unreviewed creation');
    await evaluate("document.querySelector('input[aria-label=\"Acknowledge exploratory interactive match\"]').click()");
    await button('Start Best-of-3 Match');await consistent();assert.equal(starts,1);
    const mid=raw.id;assert.equal(mid,createdId);
    assert.equal(raw.mode,mode);
    assert.equal(raw.controllers['1'], 'ai'); assert.equal(raw.controllers['2'], 'human');
    if(mode==='player_vs_ai')await input('input[aria-label="AI playback delay"]','600');
    const hold=await evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Hold Priority Timer'&&!b.disabled)");
    if(hold)await button('Hold Priority Timer');
    while(!raw.match_complete) {
      bounded();await consistent();games.add(raw.game_number);
      if(raw.winner!==null) {
        const number=raw.game_number, humans=[1,2].filter(p=>raw.controllers[String(p)]==='human');
        assertVisibleInventory();
        for(let i=0;i<humans.length;i++) {
          const pid=humans[i];await select('select[aria-label="Sideboarding player"]',[String(pid)]);
          assert.equal(await evaluate("[...document.querySelectorAll('.sideboard-panel button')].filter(b=>/Play First|Draw First|Start Next Game/.test(b.textContent)).every(b=>b.disabled)"),true);
          if(number===1) {await input('textarea[aria-label="Cards out"]',`1 ${SWAPS[pid-1][0]}`);await input('textarea[aria-label="Cards in"]',`1 ${SWAPS[pid-1][1]}`);await action('swap',()=>button('Apply Sideboard Swaps'));}
          else await action('no-swaps',()=>button('Confirm No Swaps'));
          assert.equal(raw.sideboarding[String(pid)].applied,true);assertVisibleInventory();
          assert.equal(raw.sideboarding[String(pid)].mainboard.reduce((s,c)=>s+c.quantity,0),60);
          assert.equal(raw.sideboarding[String(pid)].sideboard.reduce((s,c)=>s+c.quantity,0),4);
          if(number===1) {
            const row=raw.sideboarding[String(pid)], [old,newCard]=SWAPS[pid-1];
            const quantity=(list,name)=>list.filter(c=>c.card_name===name).reduce((n,c)=>n+c.quantity,0);
            assert.equal(quantity(row.mainboard,old),3);assert.equal(quantity(row.mainboard,newCard),1);
            assert.equal(quantity(row.sideboard,old),1);assert.equal(quantity(row.sideboard,newCard),3);
          }
          if(i===0){const saved=retained(raw);await command('Page.reload');await consistent();if(mode==='player_vs_ai')await input('input[aria-label="AI playback delay"]','600');assert.deepEqual(retained(raw),saved);}
        }
        await cold(`between-${number}`);
        const chooser=raw.next_play_draw_chooser;assert.equal(chooser,3-raw.winner);
        const playFirst=number%2===0;
        await action('next-game',()=>button(raw.controllers[String(chooser)]==='human'?`P${chooser} ${playFirst?'Play First':'Draw First'}`:'Start Next Game (AI chooses play)'));
        assert.equal(raw.game_number,number+1);assert.equal(raw.pregame_pending,true);
        if(raw.controllers[String(chooser)]==='human')assert.equal(raw.active_player,playFirst?chooser:3-chooser);
        if(mode==='player_vs_ai') {
          assert.equal(await evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Resume automatic play'&&!b.disabled)"),true,'Cold restore must pause automatic play');
          await button('Resume automatic play');
        }
        continue;
      }
      assert.equal(raw.id,mid);
      if(raw.controllers[String(legal.player_id)]==='ai') {await changed('native-ai',raw.revision);continue;}
      const pid=legal.player_id, publicView=actorView(raw,pid);
      assert.deepEqual(publicView.players[String(3-pid)].hand,[]);
      const visibleIds=await evaluate("[...document.querySelectorAll('[data-hand-card-id]')].map(e=>e.dataset.handCardId)");
      const allowedIds=new Set([...publicView.players[String(pid)].hand.map(c=>c.id),...legal.moves.filter(m=>['cast_spell','play_land','suspend'].includes(m.type)).map(m=>m.card_id)]);
      assert.ok(visibleIds.every(id=>allowedIds.has(id)),'Rendered hand is not actor/permitted-play projection');
      await appendFile(path.join(dir,'progress.jsonl'),json({utc:new Date().toISOString(),elapsedMilliseconds:Date.now()-begin,revision:publicView.revision,game:raw.game_number,turn:raw.turn,step:raw.step,actor:pid,writes,score:raw.score})+'\n');
      await appendFile(projectionLog,json({revision:publicView.revision,actor:pid,publicView,legal:legal.moves})+'\n');
      await policy(publicView,legal.moves,pid);
    }
    assert.equal(Math.max(...Object.values(raw.score)),2);assert.ok([2,3].includes(games.size));assert.equal(starts,1);
    await cold('complete');
    assert.ok(counts.land&&counts.cast&&counts.attack&&counts.swap);
    const result={mode,humanSeat:2,reversedWholeDeckPair:true,difficulty:actualStartDifficulty,
      difficultyEvidence:'Actual UI Master+ and captured start payload; public match response has no difficulty field; closed controller difficulty asserted separately by supervisor',
      matchId:mid,score:raw.score,games:[...games],writes,counts,naturalKinds:[...naturalKinds],
      elapsedMilliseconds:Date.now()-begin,rootSeedAfterCompletion:raw.root_seed,
      claim:'Actual UI natural BO3; only encountered branches; no incoming singleton cast or manual browser expertise certificate'};
    await writeFile(path.join(dir,'RESULT.json'),json(result));return result;
  } catch (error) { primaryError = error; throw error; } finally {await closeBrowsersPreservingError(primaryError, browser);}
}
