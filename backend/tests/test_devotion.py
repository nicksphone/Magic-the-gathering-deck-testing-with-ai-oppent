"""Canonical devotion payoff families and their shared live resource count."""
import json
from copy import copy
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.continuous import effective_combat_stats
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_ai_recurring_engines import fixture, add
from tests.test_api_input_contracts import game, persist

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/devotion.json').read_text())}


@pytest.mark.parametrize('seat', [1, 2])
def test_aspect_resolves_using_live_devotion_not_announced_x(seat):
    state = fixture()
    recipient = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    spell = add(state, 'Aspect of Hydra', seat, Zone.HAND, cards=ROWS)
    state.players[seat].hand.remove(spell.id)
    spell.move_to_zone(Zone.STACK)
    key, payload = infer_effect_from_oracle(state, spell, seat,
                                           {'target_card_id': recipient.id, 'x_value': 99})
    assert key == 'devotion_effect'
    add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    resolve_effect(state, seat, key, {**payload, '__source_card_id': spell.id})
    assert effective_combat_stats(state, recipient.id) == (6, 6)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,family', [
    ('Fanatic of Mogis', 'damage'), ('Gray Merchant of Asphodel', 'drain'),
    ('Setessan Petitioner', 'gain'), ('Reverent Hunter', 'counters'),
    ('Evangel of Heliod', 'tokens'), ('Abhorrent Overlord', 'tokens'),
])
def test_canonical_devotion_entry_instructions_resolve(seat, name, family):
    state = fixture()
    source = add(state, name, seat, cards=ROWS)
    surface = copy(source)
    surface.types = []
    surface.oracle_text = next(line.split(', ', 1)[1] for line in source.oracle_text.splitlines()
                              if line.startswith('When this creature enters,'))
    key, payload = infer_effect_from_oracle(state, surface, seat)
    assert key == 'devotion_effect'
    resolve_effect(state, seat, key, {**payload, '__source_card_id': source.id})
    amount = 1 if name in {'Fanatic of Mogis', 'Reverent Hunter'} else 2
    if family == 'damage':
        assert state.players[3 - seat].life == 20 - amount
    elif family == 'drain':
        assert (state.players[seat].life, state.players[3 - seat].life) == (22, 18)
    elif family == 'gain':
        assert state.players[seat].life == 22
    elif family == 'counters':
        assert source.counters['+1/+1'] == 1
    else:
        tokens = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
        assert len(tokens) == amount
        assert all(effective_combat_stats(state, card.id) == (1, 1) for card in tokens)
        if name == 'Abhorrent Overlord':
            from rules_engine.continuous import has_keyword
            assert all(has_keyword(state, card.id, 'flying') for card in tokens)


@pytest.mark.parametrize('seat', [1, 2])
def test_hybrid_count_is_controller_scoped_and_combined_colors_count_once(seat):
    from rules_engine.devotion import devotion_count
    state = fixture()
    source = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    add(state, 'Burning-Tree Emissary', 3 - seat, cards=ROWS)
    add(state, 'Burning-Tree Emissary', seat, Zone.HAND, cards=ROWS)
    before = serialize_match_snapshot(state)
    assert devotion_count(state, seat, ['R']) == 2
    assert devotion_count(state, seat, ['G']) == 2
    assert devotion_count(state, seat, ['R', 'G']) == 2
    assert devotion_count(state, seat, ['B']) == 0
    assert serialize_match_snapshot(state) == before
    restored = deserialize_match_snapshot(before)
    assert devotion_count(restored, seat, ['G', 'R']) == 2
    restored.cards[source.id].mana_cost = ''
    assert devotion_count(restored, seat, ['G']) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Gray Merchant of Asphodel', 'Fanatic of Mogis',
                                'Reverent Hunter', 'Setessan Petitioner',
                                'Evangel of Heliod', 'Abhorrent Overlord'])
def test_real_entry_trigger_uses_resolution_resources_and_survives_snapshot(seat, name):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    state = fixture()
    source = add(state, name, seat, cards=ROWS)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    assert len(state.stack) == 1
    assert state.stack[0].effect_key == 'devotion_effect'
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(restored)
    assert not restored.stack
    assert not any('noop' in line.lower() or 'missing effect' in line.lower() for line in restored.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restriction', ['locked_life', 'double_gain'])
def test_drain_gain_is_actual_loss_and_uses_existing_gain_replacements(seat, restriction):
    state = fixture()
    source = add(state, 'Gray Merchant of Asphodel', seat, cards=ROWS)
    add(state, 'Platinum Emperion' if restriction == 'locked_life' else 'Boon Reflection',
        3 - seat if restriction == 'locked_life' else seat, cards=ROWS)
    from rules_engine.devotion import devotion_instruction
    instruction = next(line.split(', ', 1)[1] for line in source.oracle_text.splitlines()
                       if line.startswith('When this creature enters,'))
    resolve_effect(state, seat, 'devotion_effect', {
        'devotion': devotion_instruction(instruction, source.name), '__source_card_id': source.id})
    assert (state.players[seat].life, state.players[3 - seat].life) == (
        (20, 20) if restriction == 'locked_life' else (24, 18))


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_tokens_keep_mana_cost_but_ordinary_tokens_do_not_add_devotion(seat):
    from effects.handlers import create_token_copy, create_token
    from rules_engine.devotion import devotion_count
    state = fixture()
    source = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    create_token_copy(state, seat, {'target_card_id': source.id})
    create_token(state, seat, {'name': 'Soldier', 'types': ['Creature', 'Token'],
                             'power': 1, 'toughness': 1, 'colors': ['G']})
    assert devotion_count(state, seat, ['G']) == 4
    state.players[seat].battlefield.remove(source.id)
    state.players[3 - seat].battlefield.append(source.id)
    source.controller = 3 - seat
    assert devotion_count(state, seat, ['G']) == 2
    assert devotion_count(state, 3 - seat, ['G']) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_devotion_pump_chooses_own_creature_not_opponents(seat, difficulty):
    from ai.agent import AIAgent
    from rules_engine.engine import RulesEngine
    state = fixture()
    state.active_player = state.priority_player = seat
    own = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    opposing = add(state, 'Burning-Tree Emissary', 3 - seat, cards=ROWS)
    opposing.counters['+1/+1'] = 8
    spell = add(state, 'Aspect of Hydra', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool['G'] = 1
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == spell.id)
    action = AIAgent(difficulty)._materialize_action(state, move, seat)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == own.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color,expected', [
    ('Reaper King', ['W', 'U', 'B', 'R', 'G'], 5),
    ('Reaper King', ['G'], 1), ('Phyrexian Metamorph', ['U'], 1),
    ('Myr Superion', ['G'], 0), ('Dryad Arbor', ['G'], 0),
])
def test_canonical_symbol_costs_not_mana_value_or_permanent_colors(seat, name, color, expected):
    from rules_engine.devotion import devotion_count
    state = fixture()
    card = add(state, name, seat, cards=ROWS)
    card.tapped = True
    assert devotion_count(state, seat, color) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,extra,color,family', [
    ('Fanatic of Mogis', 'Burning-Tree Emissary', 'R', 'damage'),
    ('Gray Merchant of Asphodel', 'Gray Merchant of Asphodel', 'B', 'drain'),
    ('Setessan Petitioner', 'Burning-Tree Emissary', 'G', 'gain'),
    ('Reverent Hunter', 'Burning-Tree Emissary', 'G', 'counters'),
    ('Evangel of Heliod', 'Evangel of Heliod', 'W', 'tokens'),
    ('Abhorrent Overlord', 'Gray Merchant of Asphodel', 'B', 'tokens'),
])
def test_queued_entry_uses_live_devotion_after_source_departure(seat, name, extra, color, family):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    from effects.handlers import return_permanent_to_hand
    state = fixture()
    source = add(state, name, seat, cards=ROWS)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    add(state, extra, seat, cards=ROWS)
    return_permanent_to_hand(state, seat, {'target_card_id': source.id})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(restored)
    assert not restored.stack
    if family in {'damage', 'drain'}:
        assert restored.players[3 - seat].life == 18
    if family in {'gain', 'drain'}:
        assert restored.players[seat].life == 22
    if family == 'counters':
        assert '+1/+1' not in restored.cards[source.id].counters
    if family == 'tokens':
        assert len([cid for cid in restored.players[seat].battlefield if restored.cards[cid].is_token]) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_reentered_counter_source_is_not_the_queued_trigger_object(seat):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    from effects.handlers import return_permanent_to_hand
    from game_state.state import assign_static_order_on_battlefield_entry
    state = fixture()
    source = add(state, 'Reverent Hunter', seat, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, source.id)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    return_permanent_to_hand(state, seat, {'target_card_id': source.id})
    state.players[seat].hand.remove(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(source.id)
    assign_static_order_on_battlefield_entry(state, source.id)
    resolve_top_of_stack(state)
    assert '+1/+1' not in source.counters


def test_devotion_compilation_isolated_from_mutable_action_payloads_and_admission():
    from rules_engine.devotion import devotion_instruction
    from rules_engine.coverage import known_unsupported_mechanics
    text = ROWS['Aspect of Hydra']['oracle_text']
    devotion_instruction(text)['colors'].append('B')
    assert devotion_instruction(text)['colors'] == ['G']
    for name in ['Aspect of Hydra', 'Gray Merchant of Asphodel', 'Abhorrent Overlord']:
        assert known_unsupported_mechanics(ROWS[name]['oracle_text'], card_name=name) == []
    assert 'unsupported devotion instruction' not in known_unsupported_mechanics(
        ROWS['Nylea, God of the Hunt']['oracle_text'], card_name='Nylea, God of the Hunt')
    assert known_unsupported_mechanics('', [ROWS['Gray Merchant of Asphodel']], card_name='face fixture') == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Aspect of Hydra', 'Reverent Hunter'])
def test_http_cast_resolution_and_database_restore_use_devotion(game, seat, name):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    state = controller.state
    state.active_player = state.priority_player = seat
    recipient = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    spell = add(state, name, seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool['G'] = 1 if name == 'Aspect of Hydra' else 3
    persist(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {
        'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_card_id': recipient.id} if name == 'Aspect of Hydra' else {}}})
    assert response.status_code == 200, response.text
    for _ in range(12):
        current = main.ACTIVE_MATCHES[state.id].state
        if not current.stack:
            break
        response = client.post(f'/matches/{state.id}/action', json={
            'player_id': current.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert not current.stack
    result = current.cards[recipient.id if name == 'Aspect of Hydra' else spell.id]
    assert effective_combat_stats(current, result.id) == (4, 4)
    expected = client.get(f'/matches/{state.id}').json()
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').json() == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_drain_replacement_choice_latches_actual_loss_and_does_not_repeat_it(seat):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    from rules_engine.engine import RulesEngine
    from effects.handlers import return_permanent_to_hand
    state = fixture()
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    source = add(state, 'Gray Merchant of Asphodel', seat, cards=ROWS)
    add(state, 'Boon Reflection', seat, cards=ROWS)
    add(state, 'Boon Reflection', seat, cards=ROWS)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    resolve_top_of_stack(state)
    assert state.pending_replacement_choice and state.players[3 - seat].life == 18
    return_permanent_to_hand(state, seat, {'target_card_id': source.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    for _ in range(4):
        pending = state.pending_replacement_choice
        if not pending:
            break
        RulesEngine().take_action(state, seat, {'type': 'choose_replacement',
            'replacement_source_id': pending['options'][0]['source_id']})
    assert not state.pending_replacement_choice and not state.stack
    assert (state.players[seat].life, state.players[3 - seat].life) == (28, 18)
    assert len([line for line in state.log if line.endswith('loses 2 life.')]) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_devotion_counter_amount_uses_shared_counter_replacement(seat):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    state = fixture()
    source = add(state, 'Reverent Hunter', seat, cards=ROWS)
    add(state, 'Corpsejack Menace', seat, cards=ROWS)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    resolve_top_of_stack(state)
    assert source.counters['+1/+1'] == 4
    assert effective_combat_stats(state, source.id) == (5, 5)


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_controller_not_source_current_controller_owns_devotion(seat):
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import resolve_top_of_stack
    state = fixture()
    source = add(state, 'Gray Merchant of Asphodel', seat, cards=ROWS)
    emit_event(state, 'enters_battlefield', {'card_id': source.id, 'controller': seat})
    state.players[seat].battlefield.remove(source.id)
    state.players[3 - seat].battlefield.append(source.id)
    source.controller = 3 - seat
    add(state, 'Gray Merchant of Asphodel', seat, cards=ROWS)
    add(state, 'Gray Merchant of Asphodel', seat, cards=ROWS)
    resolve_top_of_stack(state)
    assert (state.players[seat].life, state.players[3 - seat].life) == (24, 16)


@pytest.mark.parametrize('seat', [1, 2])
def test_devotion_follows_current_face_not_front_or_combined_card_cost(seat):
    from rules_engine.devotion import devotion_count
    from rules_engine.card_faces import apply_transform_face
    from tests.test_type_effect_lifecycle import permanent
    state = fixture()
    card = permanent(state, 'Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun', seat)
    assert devotion_count(state, seat, ['G']) == 1
    apply_transform_face(card, 1)
    assert devotion_count(state, seat, ['G']) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_current_face_instruction_proxy_is_not_overwritten_with_whole_printed_face(seat):
    from rules_engine.card_faces import apply_transform_face
    from tests.test_type_effect_lifecycle import permanent
    state = fixture()
    card = permanent(state, 'Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun', seat)
    apply_transform_face(card, 1)
    surface = copy(card)
    surface.types = []
    surface.oracle_text = next(line.split(':', 1)[1].strip() for line in card.oracle_text.splitlines()
                              if line.startswith('{T}: Add {G}.'))
    key, payload = infer_effect_from_oracle(state, surface, seat)
    assert key == 'add_mana' and payload['amount'] == 1
    before = state.players[seat].mana_pool['G']
    resolve_effect(state, seat, key, payload)
    assert state.players[seat].mana_pool['G'] == before + 1
