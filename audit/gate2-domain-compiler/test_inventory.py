from copy import deepcopy
import json
from pathlib import Path
import _socket
import _sqlite3
import subprocess

import pytest

import inventory as inv
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack

EVIDENCE = inv.ROOT.parent / 'evidence'
import os
SUFFIX = os.environ.get('GATE2_OUTPUT_SUFFIX', '')
EXECUTIONS = []

@pytest.fixture(scope='session')
def inputs():
    return inv.load_inputs()

@pytest.mark.parametrize('operation', [lambda: _sqlite3.connect(':memory:'),
    _socket.socket, lambda: subprocess.run(['true'])], ids=['native_sql', 'native_socket', 'child'])
def test_native_denial_is_active(operation):
    with pytest.raises(PermissionError):
        operation()

def test_exhaustive_deterministic_lossless_inventory(inputs):
    seed, raws, provenance = inputs
    before = deepcopy((seed, raws))
    one = inv.report(*inputs)
    assert inv.report(*inputs) == one
    assert (seed, raws) == before
    with (EVIDENCE / ('inventory' + SUFFIX + '.json')).open('x') as stream:
        json.dump(one, stream, indent=2, sort_keys=True)
    assert one['counts']['seed_names'] == 155
    assert one['counts']['exact_printing_joins'] + one['counts']['representative_oracle_joins'] == 155
    assert all(not c['canonical_fact_gaps'] for c in one['cards'])
    assert all(c['complete_card_semantics'] == 'unverified' for c in one['cards'])
    for card in one['cards']:
        raw = raws[card['runtime_printing_id']]
        assert [s['oracle_text'] for s in card['surfaces']] == [
            s.get('oracle_text') for s in [raw, *raw.get('card_faces', [])]]
        for surface in card['surfaces']:
            assert [line['printed_text'] for line in surface['lines']] == [
                line for line in (surface['oracle_text'] or '').splitlines() if line.strip()]

def test_missing_join_and_unrecognized_clause_never_promoted(inputs):
    seed, raws, _ = inputs
    runtime = seed['Lightning Bolt']
    missing = inv.inspect_card('Lightning Bolt', runtime, None)
    assert missing['canonical_join'] == 'missing_exact_printing'
    raw = deepcopy(raws[runtime['scryfall_id']])
    # Adversarial parser input only, never canonical data or a gameplay fixture.
    raw['oracle_text'] += '\nUnknown audit instruction.'
    damaged = inv.inspect_card('Lightning Bolt', runtime, raw)
    assert all(line['contract'] is None for line in damaged['surfaces'][0]['lines'])
    assert damaged['complete_card_semantics'] == 'unverified'
    assert damaged['runtime_fact_mismatches'] == ['oracle_text']

@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_paid_damage_execution_and_restore(inputs, seat):
    seed, raws, _ = inputs
    raw = raws[seed['Lightning Bolt']['scryfall_id']]
    land = raws[seed['Mountain']['scryfall_id']]
    deck = [{**land, 'card_name': land['name'], 'quantity': 20},
            {**raw, 'card_name': raw['name'], 'quantity': 1}]
    state = MatchFactory.from_decks(deck, deck, seed=2331)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    source = next(c for c in state.cards.values() if c.name == raw['name'] and c.owner == seat)
    state.players[seat].library.remove(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source.id)
    state.players[seat].mana_pool = {'R': 1}
    before = serialize_match_snapshot(state)
    paid = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
        'card_id': source.id, 'targets': {'target_player': 3-seat}})
    assert len(paid.stack) == 1
    assert paid.players[seat].mana_pool.get('R', 0) == 0
    assert paid.players[3-seat].life == 20
    restored = deserialize_match_snapshot(serialize_match_snapshot(paid))
    assert serialize_match_snapshot(restored) == serialize_match_snapshot(paid)
    assert resolve_top_of_stack(restored)
    assert restored.players[3-seat].life == 17
    assert restored.cards[source.id].zone == Zone.GRAVEYARD
    assert not restored.stack
    EXECUTIONS.append({'name': raw['name'], 'printing_id': raw['id'],
        'raw_sha256': inv.canonical_hash(raw), 'seat': seat, 'target_player': 3-seat,
        'test': 'test_canonical_paid_damage_execution_and_restore',
        'paid_R': 1, 'life_before': 20, 'life_after': 17,
        'source_after': 'graveyard', 'snapshot_roundtrip': True,
        'scope': 'complete printed stack body; player target only; no response/prevention/HTTP'})

def test_publish_execution_receipts():
    with (EVIDENCE / ('execution' + SUFFIX + '.json')).open('x') as stream:
        json.dump(EXECUTIONS, stream, indent=2, sort_keys=True)
    assert {e['seat'] for e in EXECUTIONS} == {1, 2}
