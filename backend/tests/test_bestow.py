"""Canonical bestow casting, attachment, payment and restart regressions."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_card_view, serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.attachments import attach_if_legal, is_aura, attachment_target_is_legal
from rules_engine.bestow import bestow_cost, begin_bestow, end_bestow, bestow_cast_view, is_bestowed
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_combat_domain_temporary_costs import add
from tests.test_api_input_contracts import game

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/bestow.json').read_text())}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,cost', [('Leafcrown Dryad', '{3}{G}'), ('Noble Quarry', '{5}{G}')])
def test_bestow_view_preserves_canonical_identity_without_mutating_physical_card(seat, name, cost):
    state = fixture()
    card = raw_add(state, name, seat, Zone.HAND, cards=ROWS)
    before = serialize_match_snapshot(state)
    view = bestow_cast_view(card)
    assert bestow_cost(card) == cost
    assert is_aura(view) and is_bestowed(view)
    assert view.types == ['Enchantment'] and view.type_line.endswith('Aura')
    assert view.oracle_text == card.oracle_text == ROWS[name]['oracle_text']
    assert view.mana_cost == card.mana_cost and view.colors == card.colors
    assert serialize_match_snapshot(state) == before
    end_bestow(view)
    assert view.types == card.types and view.type_line == card.type_line
    assert not is_aura(view)


@pytest.mark.parametrize('seat', [1, 2])
def test_bestowed_buff_keyword_attachment_and_snapshot_revert_on_host_departure(seat):
    state = fixture()
    host = add(state, 'Grizzly Bears', seat)
    source = raw_add(state, 'Leafcrown Dryad', seat, cards=ROWS)
    source.summoning_sick = False
    begin_bestow(source)
    assert attach_if_legal(state, source.id, host.id)
    assert effective_power(state, host.id) == effective_toughness(state, host.id) == 4
    assert 'reach' in effective_keywords(state, host.id)
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_card_view(resumed, source.id)['bestowed']
    assert is_bestowed(resumed.cards[source.id]) and is_aura(resumed.cards[source.id])
    resumed.players[seat].battlefield.remove(host.id)
    resumed.cards[host.id].move_to_zone(Zone.GRAVEYARD)
    resumed.players[seat].graveyard.append(host.id)
    apply_state_based_actions(resumed)
    returned = resumed.cards[source.id]
    assert returned.zone == Zone.BATTLEFIELD and 'Creature' in returned.types
    assert not is_bestowed(returned) and returned.attached_to is None
    assert not returned.summoning_sick
    assert returned.oracle_text == ROWS['Leafcrown Dryad']['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
def test_losing_creature_type_on_host_reverts_bestow_instead_of_destroying_aura(seat):
    state = fixture()
    host = add(state, 'Grizzly Bears', seat)
    source = raw_add(state, 'Noble Quarry', seat, cards=ROWS)
    begin_bestow(source)
    assert attach_if_legal(state, source.id, host.id)
    host.types = ['Enchantment']  # Explicit characteristic transition fixture.
    apply_state_based_actions(state)
    assert source.zone == Zone.BATTLEFIELD and 'Creature' in source.types
    assert source.attached_to is None and not is_bestowed(source)


@pytest.mark.parametrize('destination', [Zone.HAND, Zone.GRAVEYARD, Zone.EXILE, Zone.LIBRARY])
def test_bestow_ends_on_zone_departure_and_plain_aura_behavior_is_unchanged(destination):
    state = fixture()
    source = raw_add(state, 'Noble Quarry', cards=ROWS)
    begin_bestow(source)
    source.move_to_zone(destination)
    assert source.types == ['Enchantment', 'Creature']
    assert source.type_line == ROWS[source.name]['type_line']
    assert not is_bestowed(source)


def test_reverted_zero_toughness_creature_is_checked_in_same_sba_fixed_point():
    state = fixture()
    source = raw_add(state, 'Noble Quarry', cards=ROWS)
    source.counters['-1/-1'] = 1
    begin_bestow(source)
    apply_state_based_actions(state)
    assert source.zone == Zone.GRAVEYARD
    assert not is_bestowed(source)


def test_bestow_grants_enchant_creature_without_inventing_printed_oracle_and_keeps_gap():
    state = fixture()
    source = raw_add(state, 'Noble Quarry', cards=ROWS)
    host = add(state, 'Grizzly Bears', 2)
    land = add(state, 'Forest')
    begin_bestow(source)
    assert attachment_target_is_legal(state, source, host.id)
    assert not attachment_target_is_legal(state, source, land.id)
    assert source.oracle_text == ROWS[source.name]['oracle_text']
    # Until announcement, cost, resolution and UI/AI integration land, do not
    # quietly turn groundwork into a claim that bestow cards are supported.
    assert 'bestow' in known_unsupported_mechanics(source.oracle_text)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['none', 'depart', 'return', 'shroud'])
def test_bestowed_stack_characteristics_resolve_legally_or_continue_as_creature(seat, change):
    from rules_engine.cast_choice import build_cast_hints
    from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
    state = fixture()
    host = add(state, 'Grizzly Bears', 3-seat)
    source = raw_add(state, 'Leafcrown Dryad', seat, Zone.HAND, cards=ROWS)
    state.players[seat].hand.remove(source.id)
    source.move_to_zone(Zone.STACK)
    begin_bestow(source)
    hints = build_cast_hints(state, source, seat)
    assert host.id in {target['id'] for target in hints['aura_targets']}
    add_to_stack(state, source.id, seat, source.name, 'noop',
        {'target_card_id': host.id, '__announced_targets': {'target_card_id': host.id}})
    if change in {'depart', 'return'}:
        state.players[3-seat].battlefield.remove(host.id)
        host.move_to_zone(Zone.EXILE)
        if change == 'return':
            host.move_to_zone(Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.append(host.id)
    elif change == 'shroud':
        host.keywords.append('Shroud')
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(resumed)
    result = resumed.cards[source.id]
    assert result.zone == Zone.BATTLEFIELD
    assert is_bestowed(result) == (change == 'none')
    assert result.attached_to == (host.id if change == 'none' else None)
    assert ('Creature' in result.types) == (change != 'none')


def test_resolving_later_ability_of_bestowed_permanent_does_not_end_bestow():
    from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
    state = fixture()
    host = add(state, 'Grizzly Bears')
    source = raw_add(state, 'Leafcrown Dryad', cards=ROWS)
    begin_bestow(source)
    assert attach_if_legal(state, source.id, host.id)
    add_to_stack(state, source.id, 1, 'Ability classification boundary', 'noop', {}, is_spell=False)
    assert resolve_top_of_stack(state)
    assert is_bestowed(source) and source.attached_to == host.id


def cast_board(seat=1, mana=4, host_seat=None):
    from tests.test_combat_domain_temporary_costs import zero_mana
    state = fixture()
    zero_mana(state)
    state.active_player = state.priority_player = seat
    state.players[seat].mana_pool['G'] = mana
    source = raw_add(state, 'Leafcrown Dryad', seat, Zone.HAND, cards=ROWS)
    host = add(state, 'Grizzly Bears', host_seat or seat)
    return state, source, host


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant,spent', [('base', 2), ('bestow', 4)])
def test_checked_cast_announces_variant_pays_correct_cost_and_resolves(seat, variant, spent):
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    from tests.test_ai_recurring_engines import resolve
    state, source, host = cast_board(seat)
    before = serialize_match_snapshot(state)
    action = {'type': 'cast_spell', 'card_id': source.id, 'cost_choice': {'id': variant},
              'targets': {'target_card_id': host.id} if variant == 'bestow' else {}}
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert result.players[seat].mana_pool['G'] == 4-spent
    assert is_bestowed(result.cards[source.id]) == (variant == 'bestow')
    assert result.cards[source.id].zone == Zone.STACK
    assert result.cards[source.id].mana_cost == ROWS[source.name]['mana_cost']
    resumed = deserialize_match_snapshot(serialize_match_snapshot(result))
    resolved = resolve(resumed)
    assert resolved.cards[source.id].zone == Zone.BATTLEFIELD
    assert resolved.cards[source.id].attached_to == (host.id if variant == 'bestow' else None)


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_missing_target_and_underpayment_are_rejected_without_mutation(seat):
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action, ActionRejected
    state, source, host = cast_board(seat, 3)
    action = {'type': 'cast_spell', 'card_id': source.id, 'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool['G'] = 4
    action['targets'] = {}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_ai_materializes_payable_bestow_variant_with_real_target_and_cost(seat, difficulty):
    from ai.agent import AIAgent, _card_for_move
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    state, source, host = cast_board(seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('cast_variant') == 'bestow')
    assert is_aura(_card_for_move(state, move))
    action = AIAgent(difficulty)._materialize_action(state, move, seat)
    assert not action.get('_invalid_ai_choice'), action
    assert action['cost_choice']['id'] == 'bestow'
    assert action['targets']['target_card_id'] == host.id
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.players[seat].mana_pool['G'] == 0
    assert is_bestowed(result.cards[source.id])


@pytest.mark.parametrize('seat', [1, 2])
def test_http_bestow_cost_target_and_snapshot_resume(game, seat):
    import main
    from tests.test_api_input_contracts import persist, rejected, snapshot
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, source, host = cast_board(seat, 3)
    state.id = match.state.id
    match.state = state
    persist(match)
    action = {'type': 'cast_spell', 'card_id': source.id, 'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}}
    rejected(client, match, action, seat)
    match.state.players[seat].mana_pool['G'] = 4
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert match.state.players[seat].mana_pool['G'] == 0
    assert is_bestowed(match.state.cards[source.id])
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed


@pytest.mark.parametrize('remove_target', [False, True])
def test_bestowed_spell_copy_keeps_characteristics_after_original_is_countered(remove_target):
    from effects.handlers import copy_spell, counter_spell
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    from rules_engine.stack_engine import resolve_top_of_stack
    state, source, host = cast_board()
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id,
        'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}})
    original = state.stack[-1]
    copy_spell(state, 1, {'target_stack_id': original.id})
    counter_spell(state, 2, {'target_stack_id': original.id})
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    if remove_target:
        state.players[1].battlefield.remove(host.id)
        state.cards[host.id].move_to_zone(Zone.EXILE)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    token = next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert is_bestowed(token) == (not remove_target)
    assert ('Creature' in token.types) == remove_target
    if not remove_target:
        assert token.attached_to == host.id
        state.players[1].battlefield.remove(host.id)
        state.cards[host.id].move_to_zone(Zone.EXILE)
        apply_state_based_actions(state)
        assert token.zone == Zone.BATTLEFIELD and 'Creature' in token.types


def test_bestow_copy_retarget_binds_new_host_identity_and_preserves_original_target():
    from effects.handlers import copy_spell
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    from rules_engine.stack_engine import resolve_top_of_stack
    state, source, host = cast_board()
    replacement = add(state, 'Grizzly Bears', 2)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id,
        'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}})
    original = state.stack[-1]
    copy_spell(state, 1, {'target_stack_id': original.id, 'may_choose_new_targets': True})
    option = f'target_card_id:{replacement.id}'
    assert option in state.pending_mechanic_choice['options']
    state = checked_action(state, RulesEngine(), 1, {'type': 'choose_mechanic', 'card_ids': [option]})
    assert state.stack[0].payload['target_card_id'] == host.id
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    token = next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert is_bestowed(token) and token.attached_to == replacement.id


def test_bestow_uses_aura_target_discount_not_creature_spell_characteristics():
    from tests.test_aura_costs import add as aura_add
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    state, source, host = cast_board(1, 1)
    discount = aura_add(state, 'Strong Back')
    discount.attached_to = host.id
    result = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id,
        'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}})
    assert result.players[1].mana_pool['G'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mana', [2, 4])
def test_actual_ai_choice_is_payable_and_does_not_mutate_announcement_state(seat, mana):
    from ai.agent import AIAgent
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action
    state, source, host = cast_board(seat, mana)
    before = serialize_match_snapshot(state)
    decision = AIAgent('master', archetype='Tempo').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == source.id
    if mana == 2:
        assert decision.action['cost_choice']['id'] == 'base'
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.cards[source.id].zone == Zone.STACK
    assert result.players[seat].mana_pool['G'] >= 0


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_respects_exile_permission_and_expiry(seat):
    from rules_engine.engine import RulesEngine
    from rules_engine.action_validation import checked_action, ActionRejected
    state, source, host = cast_board(seat)
    player = state.players[seat]
    player.hand.remove(source.id)
    source.move_to_zone(Zone.EXILE)
    player.exile.append(source.id)
    action = {'type': 'cast_spell', 'card_id': source.id, 'from_exile': True,
              'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': host.id}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    player.exile_play_until[source.id] = state.turn + 1
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move.get('cast_variant') == 'bestow' and move.get('from_exile') for move in moves)
    result = checked_action(state, RulesEngine(), seat, action)
    assert is_bestowed(result.cards[source.id]) and source.id not in result.players[seat].exile
    player.exile_play_until[source.id] = state.turn - 1
    assert not any(move.get('card_id') == source.id for move in RulesEngine().legal_moves(state, seat))
