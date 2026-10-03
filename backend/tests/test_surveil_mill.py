"""Canonical surveil, payoff triggers and milling; fixtures are not match decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.events import emit_event
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_legendary_channels import resolve_to_choice, choice
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/surveil_mill.json').read_text())}


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    card = raw_add(state, name, seat, zone, cards=ROWS)
    card.summoning_sick = False
    return card


def cast(state, source, **targets):
    return checked_action(state, RulesEngine(), source.controller, {
        'type': 'cast_spell', 'card_id': source.id, 'targets': targets})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bin_count', [0, 1, 3])
def test_private_surveil_partition_and_order_commit_once_after_restart(seat, bin_count):
    state = board(seat)
    bug = add(state, 'Dimir Spybug', seat)
    library = list(state.players[seat].library)
    resolve_effect(state, seat, 'surveil', {'amount': 3})
    options = state.pending_mechanic_choice['options']
    binned = list(reversed(options[:bin_count]))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choice(state, 3-seat, binned)
    assert serialize_match_snapshot(state) == before
    assert RulesEngine().legal_moves(state, 3-seat) == []
    state = choice(state, seat, binned)
    retained = [cid for cid in options if cid not in binned]
    if len(retained) > 1:
        assert state.players[seat].library == library
        assert not state.stack and not state.players[seat].graveyard
        assert state.pending_mechanic_choice['kind'] == 'surveil_top_order'
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        retained.reverse()
        state = choice(state, seat, retained)
    assert state.players[seat].library == library[:-3] + list(reversed(retained))
    assert state.players[seat].graveyard == binned
    assert sum(item.payload.get('__trigger_event') == 'surveilled' for item in state.stack) == 1
    state = resolve(state)
    assert state.cards[bug.id].counters['+1/+1'] == 1
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_empty_and_short_surveil_have_distinct_event_semantics(seat):
    state = board(seat)
    bug = add(state, 'Thoughtbound Phantasm', seat)
    original = serialize_match_snapshot(state)
    resolve_effect(state, seat, 'surveil', {'amount': 0})
    assert serialize_match_snapshot(state) == original
    state.players[seat].library = state.players[seat].library[-1:]
    resolve_effect(state, seat, 'surveil', {'amount': 4})
    assert state.pending_mechanic_choice['count'] == 1
    state = resolve(choice(state, seat, state.pending_mechanic_choice['options']))
    assert not state.players[seat].library and state.winner is None
    resolve_effect(state, seat, 'surveil', {'amount': 1})
    state = resolve(state)
    assert state.cards[bug.id].counters['+1/+1'] == 2 and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Consider', 'Notion Rain'])
def test_surveillance_spell_resumes_all_later_instructions_once(seat, name):
    state = board(seat)
    source = add(state, name, seat, Zone.HAND)
    state.players[seat].mana_pool.update(U=3, B=1, C=4)
    original = list(state.players[seat].library)
    state = resolve_to_choice(cast(state, source))
    assert state.pending_mechanic_choice['kind'] == 'surveil'
    binned = state.pending_mechanic_choice['options']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(choice(state, seat, binned))
    draws = 1 if name == 'Consider' else 2
    assert len(state.players[seat].hand) == draws
    assert len(state.players[seat].library) == len(original)-len(binned)-draws
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in binned)
    assert state.players[seat].life == (18 if name == 'Notion Rain' else 20)
    assert sum(' surveils ' in line for line in state.log) == 1
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_then_surveil_and_illegal_target_fizzle(seat):
    state = board(3-seat)
    target = add(state, 'Grizzly Bears', 3-seat, Zone.HAND)
    counter = add(state, 'Sinister Sabotage', seat, Zone.HAND)
    state.players[3-seat].mana_pool.update(C=1, G=1)
    state.players[seat].mana_pool.update(C=1, U=2)
    state = cast(state, target)
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    state = cast(state, counter, target_stack_id=state.stack[-1].id)
    doomed = deserialize_match_snapshot(serialize_match_snapshot(state))
    doomed.stack = [item for item in doomed.stack if item.source_card_id != target.id]
    doomed = resolve(doomed)
    assert not any(' surveils ' in line for line in doomed.log) and not doomed.pending_mechanic_choice
    state = resolve_to_choice(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice['kind'] == 'surveil'
    state = resolve(choice(state, seat, []))
    assert state.cards[counter.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_replacement_does_not_cancel_surveil_event(seat):
    state = board(seat)
    add(state, 'Leyline of the Void', 3-seat)
    bug = add(state, 'Dimir Spybug', seat)
    resolve_effect(state, seat, 'surveil', {'amount': 2})
    options = state.pending_mechanic_choice['options']
    state = resolve(choice(state, seat, options))
    assert state.players[seat].exile == options and not state.players[seat].graveyard
    assert state.cards[bug.id].counters['+1/+1'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_payoff_references_original_object_and_respects_suppression(seat):
    state = board(seat)
    bug = add(state, 'Dimir Spybug', seat)
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': bug.id})
    state.players[seat].hand.remove(bug.id)
    state.players[seat].battlefield.append(bug.id)
    state.cards[bug.id].move_to_zone(Zone.BATTLEFIELD)
    from game_state.state import assign_static_order_on_battlefield_entry
    assign_static_order_on_battlefield_entry(state, bug.id)
    state = resolve(state)
    assert not state.cards[bug.id].counters.get('+1/+1')
    resolve_effect(state, 3-seat, 'temporary_ability_loss', {'target_card_id': bug.id})
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_first_surveillance_drain_is_counterable_and_resets_next_turn(seat):
    state = board(seat)
    source = add(state, 'Whispering Snitch', seat)
    for _ in range(2):
        emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    assert len(state.stack) == 1
    state.stack.clear()  # Simulate the payoff being countered; first occurrence remains spent.
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    assert not state.stack and state.players[3-seat].life == 20
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    state = resolve(state)
    assert state.players[3-seat].life == 19 and state.players[seat].life == 21
    assert state.cards[source.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Glimpse the Unthinkable', 'Thought Scour'])
def test_targeted_mill_hits_announced_player_and_is_not_a_draw(seat, name):
    state = board(seat)
    source = add(state, name, seat, Zone.HAND)
    state.players[seat].mana_pool.update(U=1, B=1)
    before = len(state.players[3-seat].library)
    state = resolve(cast(state, source, target_player=3-seat))
    count = 10 if name == 'Glimpse the Unthinkable' else 2
    assert len(state.players[3-seat].library) == before-count
    assert len(state.players[seat].hand) == (1 if name == 'Thought Scour' else 0)
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_draw_mill_payoff_triggers_for_each_draw_but_not_mill(seat):
    state = board(seat)
    add(state, 'Psychic Corrosion', seat)
    before = len(state.players[3-seat].library)
    resolve_effect(state, seat, 'draw_cards', {'amount': 2})
    assert len(state.stack) == 2
    state = resolve(state)
    assert len(state.players[3-seat].library) == before-4
    resolve_effect(state, seat, 'mill_cards', {'amount': 2})
    assert not state.stack


def test_unknown_surveillance_clauses_are_visible_gaps():
    assert 'surveil modification/replacement fidelity' in known_unsupported_mechanics(ROWS['Enhanced Surveillance']['oracle_text'])
    assert not known_unsupported_mechanics(ROWS['Whispering Snitch']['oracle_text'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Tempo', 'Control', 'Ramp', 'Reanimator'])
@pytest.mark.parametrize('flooded', [False, True])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_all_ai_styles_keep_needed_lands_and_bin_surplus_without_peeking(seat, style, flooded, difficulty):
    state = board(seat)
    for _ in range(6 if flooded else 1):
        add(state, 'Island', seat)
    state.players[seat].library.clear()
    inspected = add(state, 'Island', seat, Zone.LIBRARY)
    resolve_effect(state, seat, 'surveil', {'amount': 1})
    ai = AIAgent(archetype=style, difficulty=difficulty)
    for hidden_name in ['Mind Stone', 'Grizzly Bears']:
        sim = deserialize_match_snapshot(serialize_match_snapshot(state))
        add(sim, hidden_name, 3-seat, Zone.HAND)
        hidden = add(sim, hidden_name, seat, Zone.LIBRARY)
        sim.players[seat].library.remove(hidden.id)
        sim.players[seat].library.insert(0, hidden.id)
        before = serialize_match_snapshot(sim)
        decision = ai.choose_action(sim, RulesEngine().legal_moves(sim, seat), seat)
        assert decision.action['card_ids'] == ([inspected.id] if flooded else [])
        assert serialize_match_snapshot(sim) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_known_payable_reanimation_not_archetype_or_exile_enables_graveyard_choice(seat):
    state = board(seat)
    add(state, 'Zombify', seat, Zone.HAND)
    state.players[seat].mana_pool.update(C=3, B=1)
    threat = add(state, 'Griselbrand', seat, Zone.LIBRARY)
    resolve_effect(state, seat, 'surveil', {'amount': 1})
    ai = AIAgent(archetype='Tempo', difficulty='master')
    assert ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['card_ids'] == [threat.id]
    add(state, 'Leyline of the Void', 3-seat)
    assert ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['card_ids'] == []


@pytest.mark.parametrize('seat', [1, 2])
def test_first_surveillance_is_player_history_not_new_source_history(seat):
    state = board(seat)
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    add(state, 'Whispering Snitch', seat)
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    assert not state.stack and state.surveils_this_turn[seat] == 2
    state.surveils_this_turn[seat] = 0
    resolve_effect(state, 3-seat, 'temporary_ability_loss', {'target_card_id': state.players[seat].battlefield[-1]})
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    assert not state.stack and state.surveils_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reenter', [False, True])
def test_self_return_payoff_keeps_original_identity_after_snapshot(seat, reenter):
    state = board(seat)
    source = add(state, 'Disinformation Campaign', seat)
    emit_event(state, 'surveilled', {'player_id': seat, 'amount': 1})
    if reenter:
        resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source.id})
        state.players[seat].hand.remove(source.id)
        state.players[seat].battlefield.append(source.id)
        state.cards[source.id].move_to_zone(Zone.BATTLEFIELD)
        from game_state.state import assign_static_order_on_battlefield_entry
        assign_static_order_on_battlefield_entry(state, source.id)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[source.id].zone == (Zone.BATTLEFIELD if reenter else Zone.HAND)


@pytest.mark.parametrize('seat', [1, 2])
def test_sqlite_resumes_surveil_top_order_without_repeating_draw(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    state = board(seat)
    state.id = controller.state.id
    source = add(state, 'Otherworldly Gaze', seat, Zone.HAND)
    for name in ['Mind Stone', 'Grizzly Bears', 'Island']:
        add(state, name, seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(U=1)
    controller.state = resolve_to_choice(cast(state, source))
    options = list(controller.state.pending_mechanic_choice['options'])
    controller.state = choice(controller.state, seat, [options[0]])
    assert controller.state.pending_mechanic_choice['kind'] == 'surveil_top_order'
    persist(controller)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    retained = list(restored.state.pending_mechanic_choice['options'])
    rejected(client, restored, {'type': 'choose_mechanic', 'card_ids': retained}, 3-seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat,
        'action': {'type': 'choose_mechanic', 'card_ids': list(reversed(retained))}})
    assert response.status_code == 200, response.text
    result = main.ACTIVE_MATCHES[state.id].state
    assert result.cards[options[0]].zone == Zone.GRAVEYARD
    assert result.cards[source.id].zone == Zone.GRAVEYARD
    assert result.surveils_this_turn[seat] == 1
    assert not result.stack and not result.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_flashback_surveillance_exiles_only_after_owned_choice_finishes(seat):
    state = board(seat)
    source = add(state, 'Otherworldly Gaze', seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool.update(C=1, U=1)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': source.id, 'from_graveyard': True,
        'cost_choice': {'id': 'flashback'}, 'targets': {},
    })
    state = resolve_to_choice(state)
    assert state.cards[source.id].zone == Zone.STACK
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choice(state, seat, state.pending_mechanic_choice['options'])
    assert state.cards[source.id].zone == Zone.EXILE
    assert state.surveils_this_turn[seat] == 1 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_library_mill_does_not_lose_until_failed_draw(seat):
    from rules_engine.state_based_actions import apply_state_based_actions
    state = board(seat)
    state.players[3-seat].library.clear()
    resolve_effect(state, seat, 'mill_cards', {'target_player': 3-seat, 'amount': 10})
    apply_state_based_actions(state)
    assert state.winner is None
    resolve_effect(state, 3-seat, 'draw_cards', {'amount': 1})
    apply_state_based_actions(state)
    assert state.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ids', [None, ['invalid'], ['repeat', 'repeat']])
def test_invalid_surveillance_partition_is_atomic(seat, ids):
    state = board(seat)
    resolve_effect(state, seat, 'surveil', {'amount': 2})
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choice(state, seat, ids)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_surveil_preserves_needed_fixing_even_with_many_wrong_color_lands(seat):
    state = board(seat)
    for _ in range(7):
        add(state, 'Swamp', seat)
    add(state, 'Consider', seat, Zone.HAND)
    fixing = add(state, 'Island', seat, Zone.LIBRARY)
    resolve_effect(state, seat, 'surveil', {'amount': 1})
    decision = AIAgent(archetype='Aggro', difficulty='strong').choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['card_ids'] == []
    state = choice(state, seat, [])
    assert state.players[seat].library[-1] == fixing.id
