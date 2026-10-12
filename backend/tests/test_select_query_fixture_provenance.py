"""Paid flashback, actual scan work, and exact offline-profile provenance."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from card_data.fallback_cards import fallback_card_payload
from effects.handlers import counter_spell
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine import basic_land_layer
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.test_basic_land_layer_goldens import add, position
from tests.test_replacement_query_batches import reference, rows


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_flashback_and_counter_keep_native_announcement_after_snapshot(seat):
    state = MatchFactory.from_decks([{'quantity': 60, 'card_name': 'Island'}],
                                   [{'quantity': 60, 'card_name': 'Island'}], seed=29)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.DRAW
    for name, identifier, owner, zone in [('Memory Deluge', 'deluge', seat, Zone.GRAVEYARD),
                                          ('Negate', 'counter', 3-seat, Zone.HAND)]:
        raw = fallback_card_payload(name)
        card = CardInstance(identifier, name, owner, owner, zone, ['Instant'],
                            mana_cost=raw['mana_cost'], oracle_text=raw['oracle_text'])
        state.cards[identifier] = card
        (state.players[owner].graveyard if zone == Zone.GRAVEYARD else state.players[owner].hand).append(identifier)
    state.players[seat].mana_pool['U'] = 7
    state.players[3-seat].mana_pool['U'] = 2
    before = serialize_match_snapshot(state)
    cast = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': 'deluge',
                           'from_graveyard': True, 'cost_choice': {'id': 'flashback'}})
    assert serialize_match_snapshot(state) == before
    original = cast.stack[-1]
    assert original.payload['mana_spent'] == original.payload['mana_spent_to_cast'] == 7
    assert original.payload['__flashback'] is True and stack_object_kind(cast, original) == 'spell'
    cast = deserialize_match_snapshot(serialize_match_snapshot(cast))
    assert stack_object_kind(cast, cast.stack[-1]) == 'spell'
    cast = checked_action(cast, RulesEngine(), seat, {'type': 'pass_priority'})
    response = checked_action(cast, RulesEngine(), 3-seat, {'type': 'cast_spell', 'card_id': 'counter',
                              'targets': {'target_stack_id': original.id}})
    assert response.stack[-1].payload['mana_spent'] == 2
    assert stack_object_kind(response, response.stack[-1]) == 'spell'
    assert resolve_top_of_stack(response)
    assert response.stack == [] and response.pending_mechanic_choice is None
    assert response.cards['deluge'].zone == Zone.EXILE
    assert 'deluge' in response.players[seat].exile and 'deluge' not in response.players[seat].graveyard
    assert response.cards['counter'].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_flashback_flag_alone_never_classifies_unknown_frame_or_forces_counter(seat):
    state = position(seat)
    raw = fallback_card_payload('Memory Deluge')
    card = CardInstance('legacy-deluge', 'Memory Deluge', seat, seat, Zone.STACK, ['Instant'],
                        mana_cost=raw['mana_cost'], oracle_text=raw['oracle_text'])
    state.cards[card.id] = card
    item = StackItem('legacy', card.id, seat, card.name, 'look_top_select_hand',
                     {'__flashback': True, 'mana_spent_to_cast': 7, 'hand_count': 2})
    state.stack.append(item)
    before = serialize_match_snapshot(state)
    assert stack_object_kind(state, item) == 'legacy_unknown'
    counter_spell(state, 3-seat, {'target_stack_id': item.id})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('warm', [False, True])
def test_live_layer_precheck_scan_reduction_survives_warm_parser_cache(seat, warm):
    state = position(seat)
    for index in range(8):
        add(state, 'Llanowar Elves', seat if index % 2 else 3-seat)
    if warm:
        rows(state)
    before = serialize_match_snapshot(state)
    original = basic_land_layer._printed_layer_four_effect
    with patch.object(basic_land_layer, '_printed_layer_four_effect', wraps=original) as query:
        expected = reference(state)
        baseline = query.call_count
    with patch.object(basic_land_layer, '_printed_layer_four_effect', wraps=original) as query:
        assert rows(state) == expected
        assert 0 < query.call_count < baseline / 2
        assert query.call_count == 8 and baseline == 64
    assert len(expected) == 8 and serialize_match_snapshot(state) == before


def test_qualified_seed_refresh_keeps_exact_profiles_and_previous_source_evidence():
    directory = Path(__file__).parent / 'fixtures/optional_land_from_hand'
    provenance = json.loads((directory / 'provenance.json').read_bytes())
    assert {'source_revision', 'qualified_previous_source_sha256'} <= provenance.keys()
    assert provenance['qualified_previous_source_sha256'] == 'a07caf7e2faa72ba860a44930e5d0df2f6f79eb858044564befa1434bfc4d0e6'
    assert provenance['previous_source_sha256'] == '257e0276f8c4f4526dbabddd662a2cb1c2098295085b348441a09b0334b0c1d4'
    assert provenance['source_revision'] == '21db2554cce47eebc4de48dd606a76ee415edc36'
    data = (Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == provenance['source_sha256']
    seed = json.loads(data)['cards']
    assert json.loads((directory / 'canonical.json').read_bytes()) == {
        name: seed[name] for name in provenance['card_names']}
