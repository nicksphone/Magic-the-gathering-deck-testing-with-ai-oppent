"""Full canonical grammar boundaries and generic haste, not named protection."""
import json
import pickle
from pathlib import Path

import pytest

from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.continuous import _iter_keyword_grants, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.static_global_keyword_support import add, cast
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card

FIXTURE = Path(__file__).parent / 'fixtures/static_global_keyword_fix'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,expected', [
    ('Mass Hysteria', [('all', False, 'creatures', ('haste',))]),
    ('Levitation', [('you control', False, 'creatures', ('flying',))]),
    ('Wonder', []),
    ('Bedlam', []),
])
def test_full_canonical_clause_boundaries_and_cached_parser_parity(seat, name, expected):
    state = position(seat)
    source = raw_card(state, RAW[name], seat, Zone.BATTLEFIELD)
    before = pickle.dumps(state)
    assert list(_iter_keyword_grants(source)) == expected
    assert list(_iter_keyword_grants.uncached(source)) == expected
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('source_seat', [1, 2])
@pytest.mark.parametrize('actor', [1, 2])
def test_paid_generic_haste_dynamic_both_players_real_attack_and_source_departure(source_seat, actor):
    state = position(source_seat)
    source = raw_card(state, RAW['Mass Hysteria'], source_seat, Zone.HAND)
    state.players[source_seat].mana_pool = {'R': 1}
    state = checked_action(state, RulesEngine(), source_seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert resolve_top_of_stack(state)
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    engine = RulesEngine()
    for _ in range(2*len(Step)):
        if state.active_player == actor and state.step == Step.PRECOMBAT_MAIN:
            break
        engine.next_step(state)
    assert state.active_player == actor and state.step == Step.PRECOMBAT_MAIN
    late = [add(state, 'Grizzly Bears', owner).id for owner in (1, 2)]
    for cid in late:
        state.cards[cid].entered_turn = state.turn
        state.cards[cid].summoning_sick = True
        assert has_keyword(state, cid, 'haste')
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    while state.step != Step.DECLARE_ATTACKERS:
        engine.next_step(state)
    attacker = late[actor-1]
    before = pickle.dumps(state)
    moved = checked_action(state, engine, actor, {'type': 'attack', 'attackers': [attacker],
                           'attack_targets': {attacker: f'player:{3-actor}'}})
    assert attacker in moved.attackers
    assert pickle.dumps(state) == before
    state, _ = cast(moved, 'Disenchant', actor, {'target_card_id': source.id})
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert all(not has_keyword(state, cid, 'haste') for cid in late)
