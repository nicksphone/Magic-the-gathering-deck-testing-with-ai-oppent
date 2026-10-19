"""Exact Saga fixture and checked browser action sequence, without HTTP/SQL."""
import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from effects.registry import resolve_effect
from game_state.state import MatchFactory, Step, Zone
from rules_engine.state_based_actions import apply_state_based_actions


def projected_saga_fixture():
    path = Path(__file__).parent / 'browser_fixture_server.py'
    tree = ast.parse(path.read_text())
    route = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'fixture')
    route.decorator_list = []
    def publish(state, deck):
        assert deck == [{'quantity': 60, 'card_name': 'Island'}]
        serialize_match_snapshot(state)
        return state
    namespace = {'publish': publish, 'RulesEngine': RulesEngine}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['fixture'](face_kind='saga_counter_order')


def test_exact_saga_browser_sequence_survives_knight_token_snapshot(tmp_path):
    state = projected_saga_fixture()
    saga = next(card for card in state.cards.values() if card.name == 'History of Benalia')
    assert saga.counters['__lore'] == 5
    pending = state.pending_trigger_order
    assert pending['current_controller'] == 2
    group = pending['groups']['2']
    assert [item['payload']['__chapter_number'] for item in group] == [2, 3]
    ids = [item['_choice_id'] for item in sorted(group, key=lambda row: row['payload']['__chapter_number'], reverse=True)]
    rules = RulesEngine()
    state = checked_action(state, rules, 2, {'type': 'choose_trigger_order', 'trigger_order': ids})
    assert not state.pending_trigger_order and len(state.stack) == 2
    assert [item.payload['__chapter_number'] for item in state.stack] == [3, 2]
    state = checked_action(state, rules, 2, {'type': 'pass_priority'})
    assert state.priority_player == 1
    state = checked_action(state, rules, 1, {'type': 'pass_priority'})
    assert len(state.stack) == 1
    tokens = [state.cards[cid] for cid in state.players[2].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2 and all(token.power == token.toughness == 2 for token in tokens)
    from rules_engine.card_types import CARD_TYPES
    bits = []
    for token in tokens:
        source = state.sideboard_facts['seats']['1']['observed_creature_sources'][token.id]
        record = state.card_observations[1][token.id]
        bits.append({
            'native_token_true': token.is_token is True,
            'original_stock_absent': token.id not in state.sideboard_facts['inventory'],
            'witness_shape_exact': set(source) == {'cid', 'owner', 'controller', 'zone_change_sequence', 'effective_types'},
            'cid_matches': source['cid'] == token.id,
            'owner_matches': type(source['owner']) is int and source['owner'] == token.owner,
            'controller_matches': type(source['controller']) is int and source['controller'] == 2,
            'sequence_valid': type(source['zone_change_sequence']) is int and 0 <= source['zone_change_sequence'] <= token.zone_change_sequence,
            'types_list': type(source['effective_types']) is list,
            'types_unique': len(set(source['effective_types'])) == len(source['effective_types']),
            'creature_type_present': 'Creature' in source['effective_types'],
            'all_types_declared': all(type(kind) is str and kind in CARD_TYPES for kind in source['effective_types']),
            'legacy_token_marker_present': 'Token' in source['effective_types'],
            'public_id_owner_match': record['id'] == token.id and record['owner'] == source['owner'],
            'public_sequence_valid': type(record['zone_change_sequence']) is int and source['zone_change_sequence'] <= record['zone_change_sequence'] <= token.zone_change_sequence,
        })
    (tmp_path / 'saga-witness-condition-bits.json').write_text(json.dumps(bits, sort_keys=True))
    # This is the real persistence serializer, not an inferred browser token problem.
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, rules, 2, {'type': 'pass_priority'})
    assert state.priority_player == 1
    state = checked_action(state, rules, 1, {'type': 'pass_priority'})
    assert not state.stack and state.cards[saga.id].zone.value == 'graveyard'
    from rules_engine.continuous import effective_combat_stats
    assert all(effective_combat_stats(state, token.id) == (4, 3) for token in tokens)


def token_state(seat, types=None):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=71)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    payload = {'power': 2, 'toughness': 2, 'amount': 1}
    if types is not None:
        payload['types'] = types
    before = set(state.cards)
    # Trusted native resolver instruction, not a paid token-spell certificate.
    resolve_effect(state, seat, 'create_token', payload)
    cid, = set(state.cards)-before
    return state, cid


def roundtrip(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('types,expected', [(None, {'Creature'}),
    (['Creature', 'Artifact', 'Token'], {'Creature', 'Artifact'}),
    (['Creature', 'Land', 'Token'], {'Creature', 'Land'})])
def test_native_token_marker_projects_only_private_witness(seat, types, expected):
    state, cid = token_state(seat, types)
    token = state.cards[cid]
    original_types = list(token.types)
    witness = state.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid]
    assert token.is_token is True and 'Token' in original_types
    assert set(witness['effective_types']) == expected
    assert token.types == original_types
    assert 'Token' in state.card_observations[3-seat][cid]['types']
    restored = roundtrip(state)
    assert restored.cards[cid].types == original_types
    assert restored.sideboard_facts == state.sideboard_facts


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_saga_checked_chapters_create_then_buff_tokens(seat):
    from tests.test_restricted_mana import clean
    from tests.test_saga_counter_events import saga
    from tests.test_counter_replacements import source
    from rules_engine.continuous import effective_combat_stats
    state = clean(seat)
    card = saga(state, player=seat)  # Existing complete canonical public Oracle row.
    card.counters['__lore'] = 1
    source(state, 'Doubling Season', seat)
    source(state, 'Vorinclex, Monstrous Raider', seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    rules = RulesEngine()
    rules._advance_sagas(state)
    group = state.pending_trigger_order['groups'][str(seat)]
    ids = [row['_choice_id'] for row in sorted(group,
        key=lambda row: row['payload']['__chapter_number'], reverse=True)]
    state = checked_action(state, rules, seat, {'type': 'choose_trigger_order', 'trigger_order': ids})
    state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    assert len(state.stack) == 1
    tokens = [cid for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2 and all(effective_combat_stats(state, cid) == (2, 2) for cid in tokens)
    state = roundtrip(state)
    state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    assert not state.stack and state.cards[card.id].zone == Zone.GRAVEYARD
    assert all(effective_combat_stats(state, cid) == (4, 3) for cid in tokens)
    roundtrip(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_future_token_type_is_not_filtered_or_blessed(seat):
    state, cid = token_state(seat, ['Creature', 'Token', 'FutureType'])
    witness = state.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid]
    assert 'FutureType' in witness['effective_types']
    with pytest.raises(ValueError, match='Invalid retained public creature source'):
        serialize_match_snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_nontoken_legacy_marker_still_rejects(seat):
    from rules_engine.events import emit_event
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=71)
    cid = state.players[seat].hand.pop()
    card = state.cards[cid]
    state.players[seat].battlefield.append(cid)
    card.move_to_zone(Zone.BATTLEFIELD)
    card.types = ['Creature', 'Token']  # Deliberate malformed non-token, not paid animation.
    assert card.is_token is False
    emit_event(state, 'enters_battlefield', {'card_id': cid})
    assert 'Token' in state.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid]['effective_types']
    with pytest.raises(ValueError, match='Invalid retained public creature source'):
        serialize_match_snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('transition', ['destroy', 'sacrifice', 'exile'])
def test_departed_token_retains_history_through_ceasing(seat, transition):
    from rules_engine.zone_actions import sacrifice_selected
    state, cid = token_state(seat)
    state = roundtrip(state)
    witness = deepcopy(state.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid])
    if transition == 'sacrifice':
        assert sacrifice_selected(state, seat, [cid])
    else:
        resolve_effect(state, 3-seat, 'exile' if transition == 'exile' else 'destroy_permanent', {'target_card_id': cid})
    assert state.cards[cid].zone == (Zone.EXILE if transition == 'exile' else Zone.GRAVEYARD)
    state = roundtrip(state)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.CEASED
    assert all(cid not in getattr(state.players[seat], zone) for zone in ['battlefield', 'graveyard', 'exile'])
    restored = roundtrip(state)
    assert restored.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid] == witness
    assert cid in restored.sideboard_facts['seats'][str(3-seat)]['observed_creatures']


@pytest.mark.parametrize('seat', [1, 2])
def test_token_normal_lethal_sba_preserves_historical_witness(seat):
    state, cid = token_state(seat)
    state = roundtrip(state)
    state.cards[cid].counters['__damage_marked'] = 2  # Declared lethal-damage physical seam.
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.CEASED
    restored = roundtrip(state)
    assert cid in restored.sideboard_facts['seats'][str(3-seat)]['observed_creatures']


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_token_combat_then_ceasing_roundtrips(seat):
    state, cid = token_state(seat)
    before = set(state.cards)
    resolve_effect(state, 3-seat, 'create_token', {'power': 2, 'toughness': 2})
    blocker, = set(state.cards)-before
    state = roundtrip(state)
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    state.cards[cid].summoning_sick = False  # Trusted combat position, not a played-turn certificate.
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'attack', 'attackers': [cid]})
    for _ in range(4):
        if state.step == Step.DECLARE_BLOCKERS:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS
    state = checked_action(state, rules, 3-seat, {'type': 'block', 'blocks': {cid: [blocker]}})
    for _ in range(4):
        if state.cards[cid].zone == Zone.CEASED:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[cid].zone == state.cards[blocker].zone == Zone.CEASED
    restored = roundtrip(state)
    assert cid in restored.sideboard_facts['seats'][str(3-seat)]['observed_creatures']
    assert blocker in restored.sideboard_facts['seats'][str(seat)]['observed_creatures']
