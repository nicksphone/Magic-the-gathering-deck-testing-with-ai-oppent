"""Actual damage/effect outcomes; numeric grants are resolution-level controls."""
from copy import deepcopy

import pytest

from effects.handlers import return_permanent_to_hand, transform_card
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.card_faces import select_cast_face
from rules_engine.combat import _deal_unblocked_damage
from rules_engine.continuous import effective_keyword_counts, printed_abilities_suppressed
from rules_engine.query_context import rule_query_scope
from tests.test_expanded_keyword_mechanics import card
from tests.test_keyword_zone4f86_fidelity import raw_card
from tests.test_zone_object_reset import _state


def pose(seat, name='Skrelv, Defector Mite'):
    state = _state()
    state.active_player = state.priority_player = seat
    source = card(state, 'source', name, controller=seat, summoning_sick=False)
    return state, source


def grant_instances(state, source, keywords):
    resolve_effect(state, source.controller, 'grant_keyword',
                   {'target_card_id': source.id, 'keywords': keywords})


def lose_abilities(state, source):
    resolve_effect(state, source.controller, 'temporary_ability_loss',
                   {'target_card_id': source.id})
    assert printed_abilities_suppressed(state, source.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('damage', [1, 3])
def test_full_canonical_self_toxic_is_not_granted_clause_or_damage_amount(seat, damage):
    state, source = pose(seat)
    assert source.oracle_text == raw_card(source.name)['oracle_text']
    assert _deal_unblocked_damage(state, f'player:{3-seat}', damage, source.id) == damage
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (20-damage, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_noncombat_full_canonical_source_does_not_add_toxic(seat):
    state, source = pose(seat)
    resolve_effect(state, seat, 'deal_damage',
                   {'target_player': 3-seat, 'amount': 3, '__source_card_id': source.id})
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (17, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_resolved_ability_loss_suppresses_printed_toxic(seat):
    state, source = pose(seat)
    lose_abilities(state, source)
    assert _deal_unblocked_damage(state, f'player:{3-seat}', 1, source.id) == 1
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (19, 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,printed', [('Skrelv, Defector Mite', 1), ('Grizzly Bears', 0)])
def test_resolved_multiple_numeric_instances_retain_multiplicity(seat, name, printed):
    state, source = pose(seat, name)
    grant_instances(state, source, ['toxic 1', 'toxic 1', 'toxic 2'])
    assert effective_keyword_counts(state, source.id)['toxic 1'] == 2 + printed
    assert effective_keyword_counts(state, source.id)['toxic 2'] == 1
    assert _deal_unblocked_damage(state, f'player:{3-seat}', 1, source.id) == 1
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (19, 4+printed)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('grant_after_loss,poison', [(False, 0), (True, 4)])
def test_real_loss_grant_resolution_order_controls_effective_instances(
        seat, grant_after_loss, poison):
    state, source = pose(seat)
    if not grant_after_loss:
        grant_instances(state, source, ['toxic 1', 'toxic 1', 'toxic 2'])
    lose_abilities(state, source)
    if grant_after_loss:
        grant_instances(state, source, ['toxic 1', 'toxic 1', 'toxic 2'])
    assert _deal_unblocked_damage(state, f'player:{3-seat}', 1, source.id) == 1
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (19, poison)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_leave_captured_lki_remains_noncombat_only(seat):
    state, source = pose(seat)
    return_permanent_to_hand(state, 3-seat, {'target_card_id': source.id})
    assert source.zone == Zone.HAND
    lki = deepcopy(source.last_known_battlefield)
    assert lki['oracle_text'] == raw_card(source.name)['oracle_text']
    assert lki['controller'] == seat and 'keyword_counts' in lki
    resolve_effect(state, seat, 'deal_damage',
                   {'target_player': 3-seat, 'amount': 3, '__source_card_id': source.id,
                    '__source_lki': lki})
    assert (state.players[3-seat].life, state.players[3-seat].poison) == (17, 0)
    assert source.last_known_battlefield == lki


@pytest.mark.parametrize('seat', [1, 2])
def test_toxic_count_does_not_mutate_existing_scoped_keyword_result(seat):
    state, source = pose(seat)
    printed = source.oracle_text
    with rule_query_scope(state):
        cached = effective_keyword_counts(state, source.id)
        before = deepcopy(cached)
        assert _deal_unblocked_damage(state, f'player:{3-seat}', 1, source.id) == 1
        assert cached == before
        assert effective_keyword_counts(state, source.id) == before
    assert source.oracle_text == printed
    assert state.players[3-seat].poison == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_factory_delver_none_restores_real_front_not_back_characteristics(seat):
    state, source = pose(seat, 'Delver of Secrets')
    raw = raw_card('Delver of Secrets')
    front = raw['card_faces'][0]
    assert source.selected_face_index is None
    assert source.printed_characteristics['selected_face_index'] is None
    transform_card(state, seat, {'target_card_id': source.id, 'face_index': 1})
    assert source.name == raw['card_faces'][1]['name'] and source.selected_face_index == 1
    return_permanent_to_hand(state, 3-seat, {'target_card_id': source.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    restored = state.cards[source.id]
    assert restored.selected_face_index is None
    assert (restored.name, restored.oracle_text, restored.mana_cost, restored.type_line,
            restored.power, restored.toughness) == (
        front['name'], front['oracle_text'], front['mana_cost'], front['type_line'],
        int(front['power']), int(front['toughness']))
    assert restored.card_faces[0]['name'] == front['name']
    preview = select_cast_face(restored)
    assert preview.selected_face_index == 0 and preview.name == front['name']
