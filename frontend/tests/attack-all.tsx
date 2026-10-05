import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '../src/App';

// All API traffic is handled in-browser; this fixture never contacts a backend.
const params = new URLSearchParams(location.search);
const [seatText, kind = 'normal'] = (params.get('case') || '1-normal').split('-');
const seat = Number(seatText);
const card = (id: string, tapped = false) => ({ id, name: id, types: ['Creature'], type_line: 'Creature', tapped,
  power: 2, toughness: 2, summoning_sick: id === 'sick', keywords: id === 'hero' ? ['banding'] : [] });
const player = () => ({ life: 20, hand: [], battlefield: [], graveyard: [], exile: [], graveyard_count: 0,
  exile_count: 0, library_count: 40, hand_count: 0, mana_pool: {} });
const state = { id: 'attack-all-fixture', revision: 1, game_number: 1, turn: 2, step: 'declare_attackers',
  active_player: seat, priority_player: seat, mode: 'player_vs_ai', controllers: { [seat]: 'human', [3 - seat]: 'ai' },
  players: { '1': player(), '2': player() }, score: { '1': 0, '2': 0 }, stack: [], log: [], winner: null,
  attackers: [], attack_bands: [], blocks: {}, attack_targets: {} };
Object.assign(state.players[String(seat) as '1' | '2'], { battlefield: [card('hero'), card('bear'), card('tapped', true), card('sick')] });
const move = { type: 'attack', options: kind === 'empty' ? [] : ['hero', 'bear'], banding_attackers: kind === 'empty' ? [] : ['hero'],
  defenders: [{ id: `player:${3-seat}`, label: 'Opponent', kind: 'player' }, { id: 'walker', label: 'Planeswalker', kind: 'planeswalker' }],
  attack_costs: kind === 'generic' || kind === 'hybrid' ? { hero: { [`player:${3-seat}`]: {
    mana_cost: kind === 'generic' ? '{2}' : '{W/U}', hybrid_symbols: kind === 'hybrid' ? [{ symbol: 'W/U', choices: ['W', 'U'] }] : []
  } } } : {} };
const writes: unknown[] = [];
Object.assign(window, { attackEvidence: { writes, state, move } });
localStorage.removeItem('mtg.pendingStart');
localStorage.setItem('mtg.activeMatch', state.id);
window.fetch = async (input, init) => {
  const path = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.origin).pathname.replace(/^\/api(?=\/)/, '');
  let body: unknown = [];
  if (init?.method === 'POST') {
    writes.push({ path, body: JSON.parse(String(init.body || '{}')) });
    await new Promise(resolve => setTimeout(resolve, 300));
    state.revision++;
    state.step = 'begin_combat';
    body = state;
  } else if (path.endsWith('/legal-moves')) body = { player_id: seat, revision: state.revision, can_auto_pass: false,
    moves: state.step === 'declare_attackers' ? [move, ...(kind === 'restriction' ? [{ type: 'attack_restricted', card_id: 'sick', reason: 'Summoning sickness' }] : [])] : [] };
  else if (path.endsWith(`/matches/${state.id}`)) body = state;
  else if (path.endsWith('/health')) body = { ok: true };
  else if (!['/decks', '/decks/builtin', '/decks/expansion-top', '/matches'].includes(path)) {
    return new Response(JSON.stringify({ detail: 'Not needed by attack fixture' }), { status: 503 });
  }
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
};
createRoot(document.getElementById('root')!).render(<App />);
