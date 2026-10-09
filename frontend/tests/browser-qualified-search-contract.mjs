import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const packets = JSON.parse(execFileSync(process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python'), ['-c', `
import sys,json
def deny(event,args):
 if event.startswith(('sqlite3.','socket.')) or event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn'):
  raise AssertionError('pure search fixture denied '+event)
sys.addaudithook(deny)
from game_state.serializers import serialize_match,serialize_match_snapshot,deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_qualified_spell_costs import setup,announcement,SPELLS
from tests.test_legendary_channels import resolve_to_choice
from tests.test_ai_recurring_engines import resolve
rules=RulesEngine()
rows=[]
for seat in (1,2):
 for name in SPELLS:
  state,spell,payer,target=setup(name,seat)
  state.mechanic_choice_players={1,2}
  initial=serialize_match(state,look_players={seat})
  state=checked_action(state,rules,seat,announcement(state,spell,payer,target,seat))
  paid=serialize_match(state,look_players={seat})
  state=resolve_to_choice(state)
  pending=serialize_match(state,look_players={seat})
  legal=None
  if name=='Natural Order':
   state=deserialize_match_snapshot(serialize_match_snapshot(state))
   before=serialize_match_snapshot(state)
   moves=rules.legal_moves(state,seat)
   choice=next(move for move in moves if move.get('kind')=='search_library')
   assert choice['player_id']==seat and len(choice['options'])==1
   assert state.cards[choice['options'][0]].name=='Baloth Gorger'
   assert serialize_match_snapshot(state)==before
   assert 'options' not in pending['pending_mechanic_choice']
   assert not any(move.get('kind')=='search_library' for move in rules.legal_moves(state,3-seat))
   legal=dict(player_id=seat,moves=moves)
   state=checked_action(state,rules,seat,dict(type='choose_mechanic',card_ids=choice['options']))
  state=resolve(state)
  rows.append(dict(seat=seat,name=name,initial=initial,paid=paid,pending=pending,legal=legal,final=serialize_match(state,look_players={seat})))
print(json.dumps(rows))
`], { cwd: path.join(root, 'backend'), env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8', timeout: 60000 }));
const source = (await readFile(new URL('./browser-qualified-costs.mjs', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '');
const run = new (Object.getPrototypeOf(async function () {}).constructor)('assert', 'openBrowser', 'fetch', 'console', source);

async function execute({ wrongSeat = false, badOptions = false, rejected = false } = {}) {
  let packet, phase, passes;
  const choices = [], requests = [], messages = [];
  const fetch = async (url, options) => {
    if (url.includes('/fixture?')) {
      assert.equal(options.method, 'POST');
      const [, index, seat] = url.match(/qualified_cost_(\d)_(\d)$/);
      packet = packets.find(row => row.seat === Number(seat) && row.name === Object.keys({ 'Goblin Grenade': 0, 'Fodder Launch': 1, 'Natural Order': 2, Abjure: 3 })[index]);
      assert.ok(packet);
      phase = 'initial';
      passes = 0;
      return { status: 200, json: async () => packet.initial };
    }
    assert.equal(options, undefined, 'Choice inspection must not mutate or retry a request');
    if (url.includes('/legal-moves?')) {
      requests.push(url);
      assert.equal(url, `http://127.0.0.1:10199/matches/${packet.initial.id}/legal-moves?player_id=${packet.seat}`);
      const legal = structuredClone(packet.legal);
      if (wrongSeat) legal.player_id = 3 - packet.seat;
      if (badOptions) legal.moves.find(move => move.kind === 'search_library').options = [];
      return { ok: !rejected, status: rejected ? 403 : 200, json: async () => legal };
    }
    assert.equal(url, `http://127.0.0.1:10199/matches/${packet.initial.id}`);
    return { ok: true, status: 200, json: async () => packet[phase] };
  };
  const openBrowser = async () => ({
    evaluate: async expression => expression.startsWith('[...document.querySelectorAll') ? false : undefined,
    waitFor: async () => {}, command: async () => {}, close: async () => {},
    click: async label => {
      if (label.startsWith('Cast ')) phase = 'paid';
      else if (label === 'Pass Priority') {
        if (++passes === 2) phase = packet.name === 'Natural Order' ? 'pending' : 'final';
      } else {
        assert.equal(label, 'Confirm Selection');
        assert.equal(phase, 'pending');
        choices.push(packet.seat);
        phase = 'final';
      }
    },
  });
  await run(assert, openBrowser, fetch, { log: (...args) => messages.push(args) });
  assert.deepEqual(choices, [1, 2]);
  assert.equal(requests.length, 2);
  assert.equal(messages.length, 8);
}

await execute();
await assert.rejects(execute({ wrongSeat: true }), { code: 'ERR_ASSERTION' });
await assert.rejects(execute({ badOptions: true }), { code: 'ERR_ASSERTION' });
await assert.rejects(execute({ rejected: true }), { code: 'ERR_ASSERTION' });
console.log('PASS actual qualified-cost automation: redacted match, actor-only legal search, both seats, strict candidate/HTTP contracts, and all original paid-resolution assertions');
