"""Paid flashback, actual scan work, and exact offline-profile provenance."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from card_data.seed_cards import seed_card_payload
from card_data.sync import ScryfallSyncService
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


def _paid_input_card(name, *, id, owner, zone):
    sources = {
        'Memory Deluge': (62, 63, 'ca78551defc92aef72551b4b03060d3e86bd7f81fa8820c283fe8f9b518f4ac7',
                          'edcd3802-ddb3-4eb6-9b6e-a26d76557662', 'e6fd55f2-7e26-469c-a44a-ea2eb90e19a9'),
        'Negate': (66, 66, 'a6e0857a1fc161e46106b89cf0adb8d271d0ead6717da123a7a4093dcc5c5ba2',
                   '52d58fe4-6070-4022-9cd7-c35a11b44525', '3407fe41-fdd3-4119-8f70-4bc4590a379f'),
    }
    encoded = (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    if hashlib.sha256(encoded).hexdigest() != '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732':
        raise ValueError('Full paid-input source changed')
    line, fields, object_sha, identifier, oracle_id = sources[name]
    raw = json.loads(encoded.splitlines()[line - 1])
    if (raw.get('object'), raw.get('name'), raw.get('id'), raw.get('oracle_id'), len(raw)) != (
            'card', name, identifier, oracle_id, fields):
        raise ValueError('Full paid-input identity changed')
    if hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=False).encode()).hexdigest() != object_sha:
        raise ValueError('Full paid-input object changed')
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:task13-paid-input-display')
    entry = {**raw, **normalized, 'card_name': raw['name'], 'quantity': 8,
             'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
             'card_faces': deepcopy(raw.get('card_faces', []))}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id=id, owner=owner, controller=owner, zone=zone,
                   instance_order=0, summoning_sick=True)


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
        raw = seed_card_payload(name)
        card = _paid_input_card(name, id=identifier, owner=owner, zone=zone)
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
    raw = seed_card_payload('Memory Deluge')
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
