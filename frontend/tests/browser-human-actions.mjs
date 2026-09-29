import assert from "node:assert/strict";
import { openBrowser } from "./browser-driver.mjs";
const { evaluate, waitFor, click, close } = await openBrowser("http://127.0.0.1:15173/tests/human-actions.html");
async function reset() {
  await click("Reset Fixture");
  await waitFor("window.fixtureActions?.length === 0 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
}
async function assignDamage(amounts) {
  for (const [label, value] of Object.entries(amounts)) {
    await evaluate(`(() => { const input = document.querySelector(${JSON.stringify(`[aria-label="Damage to ${label}"]`)}); if (!input) throw new Error('Missing damage input: ${label}'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(String(value))}); input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  }
  await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent === 'Assign Damage' && !b.disabled)");
  await click("Assign Damage");
}
try {
  await waitFor("window.fixtureState && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("[...document.querySelectorAll('.hand-row button')].some(button => button.textContent.includes('Island'))"), false);
  await click("Play Land Forest");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'forest')");
  assert.equal(await evaluate("window.fixtureActions[0].player_id"), 2);
  console.log("PASS seat-2 land uses seat 2 and reaches battlefield");

  await click("Nonland Mana Fixture");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'mana-treasure') && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Add G");
  await waitFor("window.fixtureState.players['2'].mana_pool.G === 1 && window.fixtureState.players['2'].battlefield.find(c => c.id === 'mana-creature').tapped");
  await click("Add U");
  await waitFor("window.fixtureState.players['2'].mana_pool.U === 1 && !window.fixtureState.players['2'].battlefield.some(c => c.id === 'mana-treasure')");
  await click("Add 2 C");
  await waitFor("window.fixtureState.players['2'].mana_pool.C === 2 && window.fixtureState.players['2'].battlefield.find(c => c.id === 'mana-ring').tapped");
  await click("Add 3 R");
  await waitFor("window.fixtureState.players['2'].mana_pool.R === 3 && window.fixtureState.players['2'].battlefield.find(c => c.id === 'mana-lotus').tapped");
  assert.equal(await evaluate("window.fixtureActions.at(-1).player_id"), 2);
  console.log("PASS manual creature and Treasure mana activation uses printed costs");

  await click("Draw Cap Fixture");
  await waitFor("window.fixtureState.players['2'].hand.some(c => c.id === 'draw-divination') && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  const libraryBeforeCap = await evaluate("window.fixtureState.players['2'].library_count");
  await click("Cast Divination");
  await waitFor("window.fixtureState.stack.some(item => item.label === 'Divination')");
  await click("Resolve Stack");
  await waitFor(`window.fixtureState.players['2'].library_count === ${libraryBeforeCap - 1} && window.fixtureState.stack.length === 0`);
  assert.equal(await evaluate("window.fixtureState.players['2'].hand_count"), 8);
  console.log("PASS Spirit limits a Divination draw to one card through UI and API");

  await reset();
  await evaluate("(() => { const select = document.querySelector('[aria-label=\"Ability target player\"]'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Activate Prodigal Pyromancer");
  await waitFor("window.fixtureState.stack.length === 1");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 19");
  console.log("PASS targeted permanent ability resolves against player 1");

  await reset();
  await evaluate("(() => { const label = [...document.querySelectorAll('label')].find(l => l.textContent.includes('Grizzly Bears (2 power)')); label.querySelector('input').click(); })()");
  await click("Crew Smuggler's Copter");
  await waitFor("window.fixtureState.stack.some(item => item.effect_key === 'crew_vehicle')");
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.find(c => c.id === 'copter').types.includes('Creature')"), false);
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.find(c => c.id === 'bear').tapped"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'copter' && c.types.includes('Creature'))");
  console.log("PASS explicit crew taps as cost and animates only after its response stack resolves");

  await reset();
  await evaluate("(() => { const box = [...document.querySelectorAll('.cast-card-box')].find(b => b.querySelector('button')?.textContent.includes('Shock')); const select = [...box.querySelectorAll('select')].find(s => s.options[0].text === 'Target Player'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Cast Shock");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.from_exile"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 18");
  console.log("PASS permitted exile spell preserves source zone and resolves");

  await click("Alternative Target Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('.cast-card-box button')].some(b => b.textContent.includes('Cast Lava Spike'))");
  await evaluate("(() => { const select = [...document.querySelectorAll('.cast-card-box select')].find(s => s.options[0].text === 'Choose Target'); if (!select) throw new Error('Missing combined target selector'); select.value = 'player:1'; select.dispatchEvent(new Event('change', { bubbles: true })); select.value = 'card:teferi'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Cast Lava Spike");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.targets.target_card_id"), "teferi");
  assert.equal(await evaluate("window.fixtureActions[0].action.targets.target_player"), undefined);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].battlefield.some(c => c.id === 'teferi' && c.loyalty === 1)");
  console.log("PASS player-or-planeswalker choice uses one selector and damages loyalty");

  await click("Variable Life X Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('.cast-card-box button')].some(b => b.textContent.includes('Cast Toxic Deluge'))");
  assert.equal(await evaluate("document.querySelector('.cast-card-box input[type=number]')?.max"), "20");
  await evaluate("(() => { const input = document.querySelector('.cast-card-box input[type=number]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '2'); input.dispatchEvent(new Event('input', { bubbles: true })); })()");
  await click("Cast Toxic Deluge");
  await waitFor("window.fixtureState.players['2'].life === 18 && window.fixtureState.stack.some(item => item.label === 'Toxic Deluge')");
  assert.equal(await evaluate("window.fixtureActions[0].action.targets.x_value"), 2);
  await click("Resolve Stack");
  await waitFor("!window.fixtureState.players['1'].battlefield.some(c => c.id === 'their-two') && window.fixtureState.players['2'].battlefield.some(c => c.id === 'own-four' && c.toughness === 2)");
  console.log("PASS human chooses variable life X and global debuff resolves through UI/API");

  await click("First Strike Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && window.fixtureState.step === 'declare_blockers'");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.combat_damage_stage === 'first' && window.fixtureState.players['2'].life === 19 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("document.querySelector('.battlefield header')?.innerText.includes('First-strike damage')"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.combat_damage_stage === 'regular' && window.fixtureState.players['2'].life === 18 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("document.querySelector('.battlefield header')?.innerText.includes('Regular damage')"), true);
  console.log("PASS first-strike and regular damage have separate UI priority windows");

  await click("Damage Assignment Fixture");
  await waitFor("window.fixtureState.step === 'declare_blockers' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_mechanic_choice?.kind === 'combat_damage' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.some(c => c.id === 'giant')"), true);
  await evaluate("(() => { const input = document.querySelector('[aria-label=\"Damage to Hill Giant giant\"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '3'); input.dispatchEvent(new Event('input', { bubbles: true })); })()");
  await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent === 'Assign Damage' && !b.disabled)");
  await click("Assign Damage");
  await waitFor("window.fixtureState.pending_mechanic_choice === null && !window.fixtureState.players['2'].battlefield.some(c => c.id === 'giant')");
  assert.deepEqual(await evaluate("window.fixtureActions.at(-1).action.damage_assignment"), { bears: 0, giant: 3 });
  console.log("PASS human assigns all combat damage to the later blocker through UI and API");

  await click("Shared Trample Fixture");
  await waitFor("window.fixtureState.step === 'declare_blockers' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'first' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await assignDamage({ "Player B player:2": 5 });
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'second' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 20);
  await click("Restart Damage Assignments");
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'first' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await assignDamage({ "Palace Guard guard": 1, "Player B player:2": 4 });
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'second' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await assignDamage({ "Palace Guard guard": 3, "Player B player:2": 2 });
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'guard' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 20);
  await assignDamage({ "Charging Monstrosaur first": 1 });
  await waitFor("window.fixtureState.pending_mechanic_choice === null && window.fixtureState.players['2'].life === 14");
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.some(c => c.id === 'guard')"), false);
  console.log("PASS shared trample assignment can restart and resolves only after both players assign damage");

  await click("Banding Damage Fixture");
  await waitFor("window.fixtureState.step === 'declare_blockers' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_mechanic_choice?.source_id === 'courser' && window.fixtureState.pending_mechanic_choice?.player_id === 2 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await assignDamage({ "Benalish Hero hero": 3 });
  await waitFor("window.fixtureState.pending_mechanic_choice === null && !window.fixtureState.players['2'].battlefield.some(c => c.id === 'hero')");
  assert.equal(await evaluate("window.fixtureActions.at(-1).player_id"), 2);
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.some(c => c.id === 'bears')"), true);
  console.log("PASS banding blocker transfers attacker's damage choice to defending human seat");

  await click("Attacking Band Fixture");
  await waitFor("window.fixtureState.step === 'declare_attackers' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await evaluate("document.querySelector('[aria-label=\"Attack with Llanowar Elves\"]').click()");
  await evaluate("(() => { for (const name of ['Benalish Hero', 'Serra Angel']) { const input = document.querySelector(`[aria-label=\"Band number for ${name}\"]`); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '1'); input.dispatchEvent(new Event('input', { bubbles: true })); } })()");
  await click("Submit Attackers");
  await waitFor("window.fixtureState.attack_bands?.length === 1 && window.fixtureState.attackers?.length === 2 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.deepEqual(await evaluate("window.fixtureActions.at(-1).action.bands"), [["hero", "angel"]]);
  assert.deepEqual(await evaluate("window.fixtureState.attack_bands"), [["hero", "angel"]]);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.step === 'declare_blockers' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Pass Priority");
  await waitFor("window.fixtureState.priority_player === 2 && [...document.querySelectorAll('.block-panel .row')].some(row => row.textContent.includes('Benalish Hero')) && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await evaluate("(() => { const row = [...document.querySelectorAll('.block-panel .row')].find(row => row.textContent.includes('Benalish Hero')); const select = row.querySelector('select'); select.options[0].selected = true; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Submit Blocks");
  await waitFor("window.fixtureState.blocks?.hero?.includes('bears') && window.fixtureState.blocks?.angel?.includes('bears') && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.deepEqual(await evaluate("window.fixtureState.blocks"), { hero: ["bears"], angel: ["bears"] });
  console.log("PASS human attacking-band block propagates to flying member through UI and API");

  await reset();
  await click("Cast Llanowar Elves");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.from_library"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'elf')");
  console.log("PASS permitted top-library spell reaches battlefield");

  await click("Pregame Fixture");
  await waitFor("document.querySelector('legend')?.textContent.includes('Choose 1 cards to bottom') && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(button => button.textContent === 'Keep Hand').disabled"), true);
  await evaluate("document.querySelector('fieldset input[type=checkbox]').click()");
  await click("Keep Hand");
  await waitFor("!window.fixtureState.pregame_pending && window.fixtureState.players['2'].hand_count === 6");
  assert.equal(await evaluate("window.fixtureActions[0].player_id"), 2);
  assert.equal(await evaluate("window.fixtureActions[0].action.bottom_card_ids.length"), 1);
  console.log("PASS seat-2 human mulligan bottom selection is required and applied");

  await click("Modal Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Cast Explore the Vastlands'))");
  assert.equal(await evaluate("[...document.querySelector('.cast-card-box select').options].some(o => o.value === '0' && o.disabled)"), true);
  await click("Cast Explore the Vastlands");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.selected_face_index"), 1);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].graveyard_count === 1 && window.fixtureState.stack.length === 0");
  console.log("PASS affordable modal sorcery face reaches stack and resolves to graveyard");

  await click("Modal Choice Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Cast Wandering Archaic'))");
  await evaluate("(() => { const select = document.querySelector('.cast-card-box select'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await waitFor("document.querySelector('.cast-card-box button').textContent.includes('Cast Explore the Vastlands ({3})')");
  await click("Cast Explore the Vastlands");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureState.players['2'].mana_pool.C"), 2);
  console.log("PASS human modal choice switches the action and pays only the selected face cost");

  await click("Land Face Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Play Land Bala Ged Sanctuary'))");
  await click("Play Land Bala Ged Sanctuary");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Bala Ged Sanctuary' && c.tapped)");
  assert.equal(await evaluate("window.fixtureState.stack.length"), 0);
  assert.equal(await evaluate("window.fixtureActions[0].action.selected_face_index"), 1);
  console.log("PASS human land face bypasses stack and enters tapped");

  await click("Conditional Land Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('.hand-row button')].some(b => b.textContent.includes('Sacred Foundry (pay 2 life, untapped)'))");
  await click("Play Land Sacred Foundry (pay 2 life, untapped)");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Sacred Foundry' && !c.tapped)");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 18);
  assert.equal(await evaluate("window.fixtureActions[0].action.entry_choice"), "pay_two_life");
  await click("Conditional Land Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Play Land Sacred Foundry (tapped)");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Sacred Foundry' && c.tapped)");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 20);
  console.log("PASS human conditional land play sends paid and tapped choices through HTTP");

  await click("Conditional Land Effect Fixture");
  await waitFor("window.fixtureState.pending_mechanic_choice?.kind === 'land_entry'");
  await click("Pay 2 life to enter untapped");
  await waitFor("window.fixtureState.pending_mechanic_choice === null && window.fixtureState.players['2'].battlefield.some(c => c.name === 'Sacred Foundry' && !c.tapped)");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 18);
  console.log("PASS human effect-driven entry choice resumes through HTTP");

  await click("Adventure Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && !!document.querySelector('.cast-card-box select')");
  await evaluate("(() => { const select = document.querySelector('.cast-card-box select'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await waitFor("document.querySelector('.cast-card-box button').textContent.includes('Cast Stomp')");
  await evaluate("(() => { const box = document.querySelector('.cast-card-box'); const select = [...box.querySelectorAll('select')].find(s => s.options[0].text === 'Target Player'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Cast Stomp");
  await waitFor("window.fixtureState.stack.length === 1");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 18 && window.fixtureState.players['2'].exile_count === 1 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Cast Bonecrusher Giant");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions.find(a => a.action.from_exile)?.action.selected_face_index ?? 0"), 0);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Bonecrusher Giant')");
  console.log("PASS human Adventure resolves into exile then normal face casts to battlefield");

  await click("Trigger Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Cast Reclamation Sage'))");
  await click("Cast Reclamation Sage");
  await waitFor("window.fixtureState.stack.length === 1");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'targets' && [...document.querySelectorAll('.trigger-target-panel button')].some(b => b.textContent.includes('Sol Ring'))");
  assert.equal(await evaluate("[...document.querySelectorAll('.trigger-target-panel button')].some(b => b.textContent.includes(\"Smuggler's Copter\"))"), true);
  await click("Sol Ring");
  await waitFor("window.fixtureState.pending_trigger_order === null && window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions.at(-1).action.type"), "choose_trigger_target");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'optional' && [...document.querySelectorAll('.optional-effect-panel button')].some(b => b.textContent.includes('Apply effect'))");
  await click("Apply effect");
  await waitFor("window.fixtureState.players['2'].graveyard_count === 1 && window.fixtureState.players['1'].battlefield.some(c => c.name === \"Smuggler's Copter\")");
  console.log("PASS human ETB trigger chooses friendly legal artifact and accepts effect at resolution");

  await click("Damage Trigger Fixture");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'targets' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("[...document.querySelectorAll('.trigger-target-panel button')].some(b => b.textContent.includes('Llanowar Elves'))"), true);
  await click("Llanowar Elves");
  await waitFor("window.fixtureState.pending_trigger_order === null && window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions.at(-1).action.target_card_id"), "elf");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].graveyard_count === 1 && window.fixtureState.stack.length === 0");
  assert.equal(await evaluate("window.fixtureState.players['2'].life"), 20);

  await click("Damage Trigger Fixture");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'targets' && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  await click("Player A");
  await waitFor("window.fixtureState.pending_trigger_order === null && window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions.at(-1).action.target_player"), 1);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 19 && window.fixtureState.stack.length === 0");
  console.log("PASS damage trigger offers creature and player targets through UI and API");

  await click("Trigger Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Cast Reclamation Sage'))");
  await click("Cast Reclamation Sage");
  await waitFor("window.fixtureState.stack.length === 1");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'targets'");
  await click("Smuggler's Copter");
  await waitFor("window.fixtureState.pending_trigger_order === null");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'optional'");
  await click("Decline effect");
  await waitFor("window.fixtureState.stack.length === 0 && window.fixtureState.players['1'].battlefield.some(c => c.name === \"Smuggler's Copter\")");
  console.log("PASS human optional ETB effect can be declined after its target was announced");

  await click("Cast Trigger Fixture");
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready' && [...document.querySelectorAll('button')].some(b => b.textContent.includes('Cast Ulamog, the Infinite Gyre'))");
  await click("Cast Ulamog, the Infinite Gyre");
  await waitFor("window.fixtureState.pending_trigger_order?.phase === 'targets' && window.fixtureState.stack.length === 2");
  await click("Sol Ring");
  await waitFor("window.fixtureState.pending_trigger_order === null");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].graveyard_count === 1 && window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Ulamog, the Infinite Gyre')"), false);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.name === 'Ulamog, the Infinite Gyre')");
  console.log("PASS cast-trigger target resolves before its creature spell through the production UI/API");

  await click("Iteration Fixture");
  await waitFor("window.fixtureState?.pending_mechanic_choice?.kind === 'look_top_choose'");
  const iterationOptions = await evaluate("window.fixtureState.pending_mechanic_choice.options");
  await click("Counterspell");
  await click("Lightning Bolt");
  await click("Llanowar Elves");
  await click("Confirm Order");
  await waitFor("window.fixtureState?.pending_mechanic_choice === null && window.fixtureState?.players['2'].hand.some(c => c.name === 'Counterspell')");
  assert.deepEqual(await evaluate("window.fixtureActions.at(-1).action.card_ids"), [iterationOptions[1], iterationOptions[2], iterationOptions[0]]);
  assert.equal(await evaluate("window.fixtureState.players['2'].exile_count"), 1);
  console.log("PASS ordered top-card hand/exile/bottom choice through Controls and API");

  await click("Company Fixture");
  await waitFor("window.fixtureState?.pending_mechanic_choice?.kind === 'topdeck_put'");
  await evaluate("(() => { const label = [...document.querySelectorAll('.block-panel label')].find(l => l.textContent.includes('Grizzly Bears')); label.querySelector('input').click(); })()");
  await click("Confirm Selection");
  await waitFor("window.fixtureState?.pending_mechanic_choice?.kind === 'topdeck_bottom_order'");
  assert.equal(await evaluate("window.fixtureState.players['2'].graveyard_count"), 0);
  for (const name of ["Island", "Plains", "Swamp", "Mountain", "Llanowar Elves"]) await click(name);
  await click("Confirm Order");
  await waitFor("window.fixtureState?.pending_mechanic_choice === null && window.fixtureState?.players['2'].battlefield.some(c => c.name === 'Grizzly Bears')");
  assert.equal(await evaluate("window.fixtureState.players['2'].graveyard_count"), 1);
  assert.equal(await evaluate("window.fixtureActions.at(-1).action.card_ids.length"), 5);
  console.log("PASS two-step Collected Company choice orders bottom cards before spell completion");

  await click("Search Fixture");
  await waitFor("window.fixtureState?.pending_mechanic_choice?.kind === 'search_library'");
  await evaluate("(() => { const label = [...document.querySelectorAll('.block-panel label')].find(l => l.textContent.includes('Grizzly Bears')); label.querySelector('input').click(); })()");
  await click("Confirm Selection");
  await waitFor("window.fixtureState?.pending_mechanic_choice === null && window.fixtureState?.players['2'].hand.some(c => c.name === 'Grizzly Bears')");
  assert.equal(await evaluate("window.fixtureActions.at(-1).action.card_ids.length"), 1);
  console.log("PASS resolution-time library search choice through Controls and API");

  await click("Draw Replacement Fixture");
  await waitFor("window.fixtureState?.pending_replacement_choice?.event === 'card_draw'");
  const drawHandBefore = await evaluate("window.fixtureState.players['2'].hand_count");
  await click("Thought Reflection");
  for (let index = 0; index < 2; index++) {
    await waitFor("window.fixtureState?.pending_mechanic_choice?.kind === 'draw'");
    await click("Draw normally");
  }
  await waitFor("window.fixtureState?.pending_replacement_choice === null && window.fixtureState?.pending_mechanic_choice === null");
  assert.equal(await evaluate("window.fixtureState.players['2'].hand_count"), drawHandBefore + 2);
  assert.equal(await evaluate("window.fixtureActions[0].action.replacement_source_id"), "reflection");
  console.log("PASS draw replacement and nested dredge choices through Controls and API");

  await click("BO3 Fixture");
  await waitFor("window.fixtureState?.next_play_draw_chooser === 2 && [...document.querySelectorAll('button')].some(b => b.textContent === 'P2 Draw First')");
  await click("P2 Draw First");
  await waitFor("window.fixtureState?.game_number === 2 && window.fixtureState?.active_player === 1 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("window.fixtureState.root_seed"), null);
  console.log("PASS human loser chooses draw through Controls and the production next-game API");

  await click("BO3 Fixture");
  await waitFor("window.fixtureState?.next_play_draw_chooser === 2 && [...document.querySelectorAll('button')].some(b => b.textContent === 'P2 Play First')");
  await click("P2 Play First");
  await waitFor("window.fixtureState?.game_number === 2 && window.fixtureState?.active_player === 2 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("window.fixtureState.root_seed"), null);
  console.log("PASS human loser chooses play through Controls and the production next-game API");
} finally {
  await close();
}
