export const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
export function fixture() {
  const face = {name: 'SYNTHETIC Island', type: 'Basic Land', mana_cost: '', oracle_text: '', power: 0, toughness: 0};
  const card = {card_id: 42, owner_id: 8, controller_id: 8, tapped: false, face_down: false, face};
  const zones = () => Object.fromEntries(['Hand','Library','Battlefield','Graveyard','Exile','Command','Sideboard']
    .map(name => [name, {count: name === 'Library' ? 53 : 0, visible_cards: []}]));
  const own = zones(); own.Hand = {count: 1, visible_cards: [card]};
  return {engine: 'forge', session_id: uuid(9), sequence: 3, status: 'running', actor_id: 8,
    state: {actor_id: 8, turn: 1, phase: 'MAIN1', players: [
      {player_id: 8, name: 'Human', life: 20, zones: own},
      {player_id: 19, name: 'Native AI', life: 20, zones: zones()}], stack: [{stack_id: 2, source: card}]},
    question: {actor_id: 8, request_id: uuid(1), kind: 'input:InputPassPriority', min: 1, max: 1,
      choices: [{token: uuid(2), display: card}, {token: uuid(3), display: 'button_ok'}]},
    info: {prompt: 'Choose a native action', ok_label: 'Pass'}, last_answer: null, result: null, error: null};
}
