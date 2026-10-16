"""Completed native activations, real optional payment and genuine ability copies."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_object_kind
from tests.rings_activation_native_support_5763 import add, act, activate, board, optional, position, raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_real_completed_activation_publishes_one_trigger_above_its_actual_item(seat, foreign_owner):
    state = activate(board(seat, foreign_owner=foreign_owner), seat)
    assert len(state.stack) == 2
    original, trigger = state.stack
    assert original.source_card_id == 'pyromancer' and stack_object_kind(state, original) == 'activated'
    assert trigger.source_card_id == 'rings' and stack_object_kind(state, trigger) == 'triggered'
    assert trigger.controller == original.controller == seat
    assert state.cards['pyromancer'].tapped and state.players[seat].mana_pool == {'C': 2}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', [False, True])
def test_real_optional_two_payment_then_one_copy_keeps_or_changes_target(seat, keep):
    state = activate(board(seat), seat)
    assert len(state.stack) == 2
    original_id = state.stack[0].id
    original_payload = deepcopy(state.stack[0].payload)
    state = optional(state, seat)
    assert not any(state.players[seat].mana_pool.values())
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    assert len(state.stack) == 2 and state.stack[-1].id != original_id
    choice = 'keep' if keep else f'target_player:{seat}'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, 'choose_mechanic', card_ids=[choice])
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = act(state, seat, 'choose_mechanic', card_ids=[choice])
    assert len(state.stack) == 2 and not state.pending_mechanic_choice
    copy = state.stack[-1]
    assert copy.controller == seat and copy.payload['__copied_from_stack_id'] == original_id
    assert copy.payload['target_player'] == (3-seat if keep else seat)
    assert state.stack[0].payload == original_payload
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.players[seat].life == (20 if keep else 19)
    assert state.players[3-seat].life == (18 if keep else 19)
    assert not state.stack and not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_decline_and_unaffordable_accept_leave_original_and_pay_nothing(seat):
    state = activate(board(seat), seat)
    assert len(state.stack) == 2
    state.players[seat].mana_pool = {}
    assert not resolve_top_of_stack(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, 'choose_optional_effect', stack_id=state.stack[-1].id, accept=True)
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, 'choose_optional_effect', stack_id=state.stack[-1].id, accept=False)
    assert len(state.stack) == 1 and state.stack[0].source_card_id == 'pyromancer'
    assert resolve_top_of_stack(state) and state.players[3-seat].life == 19


@pytest.mark.parametrize('seat', [1, 2])
def test_countered_original_still_copies_genuine_last_known_ability(seat):
    state = activate(board(seat), seat)
    assert len(state.stack) == 2
    original_id = state.stack[0].id
    add(state, 'Stifle', 'stifle', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = act(state, seat, 'pass_priority')
    state = act(state, 3-seat, 'cast_spell', card_id='stifle', targets={'target_stack_id': original_id})
    assert resolve_top_of_stack(state)
    assert all(item.id != original_id for item in state.stack)
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert len(state.stack) == 1 and state.stack[0].payload['__copied_from_stack_id'] == original_id
    assert resolve_top_of_stack(state) and state.players[3-seat].life == 19
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_real_mana_activation_and_opponent_nonmana_activation_do_not_trigger(seat):
    state = board(seat)
    add(state, 'Sol Ring', 'mana', seat)
    state = act(state, seat, 'tap_nonland_for_mana', card_id='mana', color='C')
    assert not state.stack and state.players[seat].mana_pool['C'] == 4
    add(state, 'Prodigal Pyromancer', 'opponent', 3-seat)
    state = act(state, seat, 'pass_priority')
    state = act(state, 3-seat, 'activate_ability', card_id='opponent', ability_index=0,
                targets={'target_player': seat})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == 'opponent'


@pytest.mark.parametrize('seat', [1, 2])
def test_failed_activation_does_not_emit_a_completion_or_change_state(seat):
    state = board(seat)
    state.cards['pyromancer'].tapped = True
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        activate(state, seat)
    assert serialize_match_snapshot(state) == before and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['cycle', 'crew', 'equip', 'loyalty', 'ninjutsu'])
def test_all_native_nonmana_producer_families_publish_completed_item_once(seat, family):
    state = position(seat)
    add(state, 'Rings of Brighthearth', 'rings', seat)
    state.players[seat].mana_pool = {'C': 10, 'U': 1, 'W': 1}
    if family == 'cycle':
        add(state, 'Renewed Faith', 'source', seat, Zone.HAND)
        state = act(state, seat, 'cycle_card', card_id='source')
        assert state.cards['source'].zone == Zone.GRAVEYARD
    elif family == 'crew':
        add(state, "Smuggler's Copter", 'source', seat)
        add(state, 'Grizzly Bears', 'bear', seat)
        state = act(state, seat, 'crew', card_id='source', crew_card_ids=['bear'])
        assert state.cards['bear'].tapped
    elif family == 'equip':
        add(state, 'Shuko', 'source', seat)
        add(state, 'Grizzly Bears', 'bear', seat)
        state = act(state, seat, 'equip', card_id='source', target_card_id='bear')
    elif family == 'loyalty':
        add(state, "Elspeth, Sun's Champion", 'source', seat)
        state = act(state, seat, 'activate_loyalty', card_id='source', ability_index=0)
        assert state.cards['source'].loyalty == 5
    else:
        add(state, 'Ninja of the Deep Hours', 'source', seat, Zone.HAND)
        add(state, 'Grizzly Bears', 'bear', seat)
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        state.attackers = ['bear']
        state.attack_targets = {'bear': f'player:{3-seat}'}
        state = act(state, seat, 'ninjutsu', card_id='source', return_card_id='bear')
        assert state.cards['bear'].zone == Zone.HAND
    frames = [item for item in state.stack if item.source_card_id == 'source'
              and stack_object_kind(state, item) == 'activated']
    triggers = [item for item in state.stack if item.source_card_id == 'rings']
    assert len(frames) == len(triggers) == 1
    assert stack_object_kind(state, frames[0]) == 'activated'
    assert state.stack.index(triggers[0]) > state.stack.index(frames[0])


@pytest.mark.parametrize('seat', [1, 2])
def test_rings_sacrificed_as_real_activation_cost_does_not_trigger(seat):
    state = position(seat)
    add(state, 'Rings of Brighthearth', 'rings', seat)
    add(state, 'Trading Post', 'post', seat)
    state.players[seat].mana_pool = {'C': 1}
    state = act(state, seat, 'activate_ability', card_id='post', ability_index=3,
                payment_choices={'sacrifice_card_ids': ['rings']})
    assert state.cards['rings'].zone == Zone.GRAVEYARD
    assert len(state.stack) == 1 and state.stack[0].source_card_id == 'post'


@pytest.mark.parametrize('seat', [1, 2])
def test_suppressed_full_rings_does_not_observe_real_cycling(seat):
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.keyword_effects import add_keyword_effect

    state = position(seat)
    add(state, 'Rings of Brighthearth', 'rings', seat)
    # Explicit runtime suppression protocol, not a claim that March is implemented.
    add_keyword_effect(state, 'rings', ['all abilities'], operation='remove')
    assert printed_abilities_suppressed(state, 'rings')
    add(state, 'Renewed Faith', 'cycle', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = act(state, seat, 'cycle_card', card_id='cycle')
    assert state.cards['cycle'].zone == Zone.GRAVEYARD
    assert len(state.stack) == 2 and all(item.source_card_id == 'cycle' for item in state.stack)
    assert [stack_object_kind(state, item) for item in state.stack] == ['activated', 'triggered']


@pytest.mark.parametrize('seat', [1, 2])
def test_positive_loyalty_cost_waits_for_all_native_replacement_choices(seat):
    state = position(seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    add(state, 'Rings of Brighthearth', 'rings', seat)
    add(state, "Elspeth, Sun's Champion", 'walker', seat)
    for i, name in enumerate(('Doubling Season', 'Vorinclex, Monstrous Raider', "Lae'zel, Vlaakith's Champion")):
        add(state, name, f'replacement-{i}', seat)
    state = act(state, seat, 'activate_loyalty', card_id='walker', ability_index=0)
    original_id = state.stack[0].id
    assert state.pending_replacement_choice and state.cards['walker'].loyalty == 4
    assert len(state.stack) == 1 and not any(t['source_card_id'] == 'rings' for t in state.staged_triggers)
    for _ in range(4):
        if not state.pending_replacement_choice:
            break
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        pending = state.pending_replacement_choice
        option = next((o for o in pending['options'] if o.get('operation') == 'add'), pending['options'][0])
        state = act(state, seat, 'choose_replacement', replacement_source_id=option['source_id'])
        if state.pending_replacement_choice:
            assert len(state.stack) == 1 and not any(t['source_card_id'] == 'rings' for t in state.staged_triggers)
    assert not state.pending_replacement_choice
    assert state.cards['walker'].loyalty > 4 and state.stack[0].id == original_id
    assert len([item for item in state.stack if item.source_card_id == 'rings']) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_real_retarget_then_counter_uses_last_actual_target_not_activation_snapshot(seat):
    from rules_engine.spree import parse

    state = activate(board(seat), seat)
    assert len(state.stack) == 2
    original_id = state.stack[0].id
    add(state, 'Return the Favor', 'favor', 3-seat, Zone.HAND)
    add(state, 'Stifle', 'stifle', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C': 1, 'R': 2, 'U': 1}
    state = act(state, seat, 'pass_priority')
    mode = parse(raw_card('Return the Favor')['oracle_text'])[1]
    state = act(state, 3-seat, 'cast_spell', card_id='favor', cost_choice={'id': 'base'},
                targets={'mode_texts': [mode.text], 'mode_targets': {mode.text: {'target_stack_id': original_id}}})
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'spree_target_change'
    state = act(state, 3-seat, 'choose_mechanic', card_ids=[f'target_player:{seat}'])
    assert next(item for item in state.stack if item.id == original_id).payload['target_player'] == seat
    if state.priority_player != 3-seat:
        state = act(state, state.priority_player, 'pass_priority')
    state = act(state, 3-seat, 'cast_spell', card_id='stifle', targets={'target_stack_id': original_id})
    assert resolve_top_of_stack(state)
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert state.stack[-1].payload['target_player'] == seat
    assert resolve_top_of_stack(state) and state.players[seat].life == 19
    assert state.players[3-seat].life == 20 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_original_source_bounce_does_not_cancel_already_published_copy_trigger(seat):
    state = activate(board(seat, foreign_owner=True), seat)
    assert len(state.stack) == 2
    add(state, 'Unsummon', 'bounce', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = act(state, seat, 'pass_priority')
    state = act(state, 3-seat, 'cast_spell', card_id='bounce', targets={'target_card_id': 'pyromancer'})
    assert resolve_top_of_stack(state) and state.cards['pyromancer'].zone == Zone.HAND
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert state.stack[-1].controller == seat
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.players[3-seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_remains_its_controller_after_foreign_owned_rings_is_destroyed(seat):
    state = activate(board(seat, foreign_owner=True), seat)
    add(state, 'Vindicate', 'vindicate', 3-seat, Zone.HAND)
    # Vindicate is a sorcery: this deliberate native resolver seam does not claim
    # that the spell could be cast while responding to the trigger.
    from rules_engine.ability_model import build_spell_spec
    from effects.registry import resolve_effect
    spell = state.cards['vindicate']
    spec = build_spell_spec(state, spell, 3-seat, {'target_card_id': 'rings'})
    resolve_effect(state, 3-seat, spec.effect.key, spec.effect.payload)
    assert state.cards['rings'].zone == Zone.GRAVEYARD
    assert state.stack[-1].controller == seat
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert state.stack[-1].controller == seat
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.players[3-seat].life == 18


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', [False, True])
def test_real_bounce_preserves_stale_target_or_allows_legal_new_copy_target(seat, keep):
    state = board(seat)
    add(state, 'Grizzly Bears', 'victim', 3-seat)
    state = act(state, seat, 'activate_ability', card_id='pyromancer', ability_index=0,
                targets={'target_card_id': 'victim'})
    add(state, 'Unsummon', 'bounce', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = act(state, seat, 'pass_priority')
    state = act(state, 3-seat, 'cast_spell', card_id='bounce', targets={'target_card_id': 'victim'})
    assert resolve_top_of_stack(state) and state.cards['victim'].zone == Zone.HAND
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep' if keep else f'target_player:{3-seat}'])
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.cards['victim'].zone == Zone.HAND and not state.stack
    assert state.players[3-seat].life == (20 if keep else 19)


@pytest.mark.parametrize('seat', [1, 2])
def test_completed_actual_item_is_idempotent_and_equal_id_clone_is_not_a_producer(seat):
    from rules_engine.activation_copy import record_activation_complete

    state = activate(board(seat), seat)
    original = state.stack[0]
    before = serialize_match_snapshot(state)
    record_activation_complete(state, original)
    assert serialize_match_snapshot(state) == before
    with pytest.raises(ValueError, match='actual announced item'):
        record_activation_complete(state, deepcopy(original))
    assert serialize_match_snapshot(state) == before and len(state.stack) == 2


@pytest.mark.parametrize('suffix', [' Extra instruction.', ' (Extra instruction.)', '\nUnknown effect.'])
def test_complete_clause_never_admits_unknown_trailing_instruction(suffix):
    from rules_engine.activation_copy import compile_clause

    clause = raw_card('Rings of Brighthearth')['oracle_text']
    assert compile_clause(clause) is not None
    assert compile_clause(clause + suffix) is None


def test_complete_activation_copy_grammar_does_not_depend_on_card_name():
    from rules_engine.activation_copy import compile_clause

    clause = raw_card('Rings of Brighthearth')['oracle_text']
    assert compile_clause(clause.replace('{2}', '{3}')).startswith('you may pay {3}')
    assert compile_clause(clause.replace('you activate', 'an opponent activates')) is None
    assert compile_clause(clause.replace("if it isn't a mana ability, ", '')) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_optional_payment_uses_real_mana_ability_without_triggering_again(seat):
    state = board(seat)
    state.players[seat].mana_pool = {}
    add(state, 'Sol Ring', 'mana', seat)
    state = activate(state, seat)
    state = optional(state, seat)
    assert state.cards['mana'].tapped and not any(state.players[seat].mana_pool.values())
    assert len(state.stack) == 2
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, 'choose_optional_effect', stack_id=state.stack[-1].id, accept=True)
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.players[3-seat].life == 18 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_real_opposite_controller_copy_of_trigger_pays_and_controls_its_own_copy(seat):
    from rules_engine.spree import parse

    state = activate(board(seat, foreign_owner=True), seat)
    trigger_id = state.stack[-1].id
    add(state, 'Return the Favor', 'favor', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C': 3, 'R': 2}
    state = act(state, seat, 'pass_priority')
    mode = parse(raw_card('Return the Favor')['oracle_text'])[0]
    state = act(state, 3-seat, 'cast_spell', card_id='favor', cost_choice={'id': 'base'},
                targets={'mode_texts': [mode.text], 'mode_targets': {mode.text: {'target_stack_id': trigger_id}}})
    assert resolve_top_of_stack(state) and len(state.stack) == 3
    assert state.stack[-1].controller == 3-seat
    state = optional(state, 3-seat)
    state = act(state, 3-seat, 'choose_mechanic', card_ids=[f'target_player:{seat}'])
    assert state.stack[-1].controller == 3-seat and state.stack[-1].source_card_id == 'pyromancer'
    assert state.players[seat].mana_pool == {'C': 2}
    assert not any(state.players[3-seat].mana_pool.values())
    assert resolve_top_of_stack(state) and state.players[seat].life == 19
    assert state.stack[-1].id == trigger_id and state.stack[-1].controller == seat
    state = optional(state, seat)
    state = act(state, seat, 'choose_mechanic', card_ids=['keep'])
    assert resolve_top_of_stack(state) and resolve_top_of_stack(state)
    assert state.players[3-seat].life == 18 and not state.stack
