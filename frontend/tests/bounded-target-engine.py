"""Real canonical public views and execution of component-submitted actions."""
import json
import hashlib
import os
from pathlib import Path
import sys


def deny(event, _args):
    if event.startswith(('sqlite3.', 'socket.')) or event in {
            'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn'}:
        raise AssertionError('Pure bounded-target fixture denied ' + event)


sys.addaudithook(deny)
root = Path(__file__).resolve().parents[2]
for relative in ('backend', 'audit/bounded-spells', 'audit/gate2-domain-compiler'):
    sys.path.insert(0, str(root / relative))
os.environ.setdefault('GAP6_EVIDENCE', str(root.parent / 'evidence'))
from game_state.serializers import (serialize_match, serialize_match_snapshot,
                                    deserialize_match_snapshot)
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from card_data.hydration import hydrate_deck_cards, is_playable_deck_card
import test_paid_preflight as original
import domain_paid_support as paid

if len(sys.argv) > 1 and sys.argv[1] == 'execute':
    results = []
    for packet in json.load(sys.stdin):
        state = deserialize_match_snapshot(packet['snapshot'])
        action = packet['action']
        try:
            state = paid.act(state, packet['seat'], action['type'], **{
                key: value for key, value in action.items() if key != 'type'})
        except Exception as error:
            raise AssertionError({'submitted_action': action}) from error
        assert sum(state.players[packet['seat']].mana_pool.values()) == 0
        assert state.cards[action['card_id']].zone == Zone.STACK
        state = paid.resolve(paid.restore(state))
        selected = action['targets'].get('target_card_ids', [])
        assert state.cards[action['card_id']].zone == Zone.GRAVEYARD
        assert all(state.cards[cid].zone == (
            Zone.GRAVEYARD if cid in selected else Zone.BATTLEFIELD)
            for cid in packet['offered'])
        results.append({'seat': packet['seat'], 'selected': selected, 'resolved': True})
    print(json.dumps(results))
else:
    fixture = root / 'audit/gate2-granted-target'
    assert hashlib.sha256((fixture / 'canonical-raw.json').read_bytes()).hexdigest() == \
        'fea9d4f8057b2d85ffb09e96f62639dbcd12fed9993c679b483540d2db12b494'
    assert hashlib.sha256((fixture / 'raw-provenance.json').read_bytes()).hexdigest() == \
        'fe9846ff4c7edb1c6db0b057b375e8c2efe3f562549fced58b830b12b022e6c2'
    raw = json.loads((fixture / 'canonical-raw.json').read_text())
    proof = json.loads((fixture / 'raw-provenance.json').read_text())
    seed = json.loads((root / 'backend/card_data/builtin_oracle_seed.json').read_text())['cards']
    source_proof = json.loads((root / 'backend/tests/fixtures/builtin_face_colors/provenance.json').read_text())
    assert proof['bulk_sha256'] == source_proof['source_bulk_sha256']
    facts = {}
    # Only these five canonical rows feed the unchanged Force of Vigor setup.
    # Forest uses the inventory's documented unique playable-English representative.
    for name in ('Force of Vigor', 'Forest', 'Llanowar Elves', "Witch's Oven", 'Intangible Virtue'):
        card = raw[name]
        assert card['name'] == name and card['lang'] == 'en' and is_playable_deck_card(card)
        row = hydrate_deck_cards(None, [{'card_name': name, 'quantity': 1}])[0]
        assert row['scryfall_id'] == seed[name]['scryfall_id']
        assert row['oracle_text'] == card['oracle_text'] == seed[name]['oracle_text']
        facts[name] = {**row, 'name': name}
    rows = []
    for seat in (1, 2):
        state, source, _, _, _ = original.setup(facts, seat, 'Force of Vigor')
        paid.add(state, facts, "Witch's Oven", seat)
        for player in state.players.values():
            player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
        public = serialize_match(state, look_players={seat})
        public.update(controllers={'1': 'human', '2': 'human'}, revision=0,
                      mode='human_vs_human')
        moves = RulesEngine().legal_moves(state, seat)
        move = next(move for move in moves if move['type'] == 'cast_spell'
                    and move['card_id'] == source)
        assert move['target_hints']['up_to_target_count'] == 2
        rows.append({'seat': seat, 'source': source, 'state': public,
                     'snapshot': serialize_match_snapshot(state),
                     'legal': {'player_id': seat, 'revision': 0, 'moves': moves}})
    print(json.dumps(rows))
