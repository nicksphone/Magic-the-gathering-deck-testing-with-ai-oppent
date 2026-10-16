"""Cross-controller continuation and explicit legacy/stale record protocols."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, place
from tests.test_entry_copy_native_936 import cast, position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_actual_ai_vaults_choice_uses_entry_owner_not_original_spell_controller(seat, difficulty):
    names = ['Sculpting Steel', 'Open the Vaults', 'Liquimetal Coating', 'Rancor', 'Grizzly Bears']
    state = position(names, names, 3-seat)
    state, creature = cast(state, seat, 'Grizzly Bears')
    assert resolve_top_of_stack(state)
    state, aura = cast(state, seat, 'Rancor', target_card_id=creature)
    assert resolve_top_of_stack(state)
    state, coating = cast(state, seat, 'Liquimetal Coating')
    assert resolve_top_of_stack(state)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': coating, 'ability_index': 0,
        'targets': {'target_card_id': aura}})
    assert resolve_top_of_stack(state)
    steel = place(state, 'Sculpting Steel', Zone.GRAVEYARD, seat)
    state.active_player = state.priority_player = 3-seat
    state, _ = cast_vaults(state, 3-seat)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['player_id'] == seat
    assert state.pending_mechanic_choice['resolving_item']['controller'] == 3-seat
    assert aura in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Midrange', difficulty=difficulty).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, decision.action)
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[steel].zone == Zone.BATTLEFIELD
    assert state.cards[steel].owner == state.cards[steel].controller == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_explicitly_declines_when_only_eligible_target_has_unavailable_legacy_values(seat):
    names = ['Sculpting Steel', 'Liquimetal Coating']
    state = position(names, names, seat)
    state, coating = cast(state, seat, 'Liquimetal Coating')
    assert resolve_top_of_stack(state)
    # An opaque legacy snapshot is a protocol control, not a fabricated game effect.
    state.cards[coating].characteristic_record = {}
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['options'] == [coating]
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Midrange', difficulty='strong').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action == {'type': 'choose_mechanic', 'card_ids': []}
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, decision.action)
    assert state.cards[steel].name == 'Sculpting Steel'
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_retained_frame_is_not_masked_as_a_valid_ai_decline(seat):
    names = ['Sculpting Steel', 'Liquimetal Coating']
    state = position(names, names, seat)
    state, coating = cast(state, seat, 'Liquimetal Coating')
    assert resolve_top_of_stack(state)
    state, _ = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state.pending_mechanic_choice['effect_payload']['__entry_copy_plan']['frame']['source_card_id'] = coating
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        AIAgent(archetype='Midrange', difficulty='strong').choose_action(
            state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
