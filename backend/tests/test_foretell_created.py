"""Effect-created Foretell permissions use canonical cards and ordinary events."""
import json
from pathlib import Path
from copy import deepcopy
import pytest

from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.foretell import record, can_look, cast_costs
from tests.test_foretell import setup, add
from tests.test_ai_recurring_engines import resolve
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_api_input_contracts import game, persist, snapshot

EXTRA = {row['name']: row for file in ['ability_suppression', 'draw_forecast', 'foretell_created']
         for row in json.loads((Path(__file__).parent / f'fixtures/{file}.json').read_text())}


def position(seat=1, name='Ethereal Valkyrie'):
    state, _ = setup(seat=seat)
    source = add(state, name, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 12, 'W': 4, 'U': 4, 'G': 4}
    return state, source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('event', ['enters_battlefield', 'attack_declared'])
def test_draw_then_private_hand_selection_creates_owner_permission(seat, event):
    state, source = position(seat)
    held = next(cid for cid in state.players[seat].hand
                if state.cards[cid].name == 'Behold the Multiverse')
    before = len(state.players[seat].hand)
    emit_event(state, event, {'card_id': source.id, 'controller': seat})
    assert len(state.stack) == 1
    state = resolve(state)
    assert len(state.players[seat].hand) == before + 1
    assert state.pending_mechanic_choice['kind'] == 'foretell_from_hand'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [held]})
    assert record(state.cards[held])['origin'] == 'effect'
    assert can_look(state.cards[held], seat) and not can_look(state.cards[held], 3-seat)
    assert not state.foretells_this_turn.get(seat, 0)
    assert not any('Behold the Multiverse' in line for line in state.log)
    assert not cast_costs(state, state.cards[held], seat)
    state.turn += 1
    assert cast_costs(state, state.cards[held], seat) == ['{1}{U}']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('combat', [False, True])
def test_damage_self_exile_is_a_trigger_and_gives_the_owner_access(seat, combat):
    state, source = position(seat, 'The Foretold Soldier')
    owner = 3-seat
    source.owner = owner
    emit_event(state, 'combat_damage_dealt' if combat else 'damage_dealt',
               {'source_card_id': source.id, 'target_player': owner, 'amount': 1})
    assert len(state.stack) == 1 and source.id in state.players[seat].battlefield
    state = resolve(state)
    assert source.id in state.players[owner].exile
    assert can_look(state.cards[source.id], owner) and not can_look(state.cards[source.id], seat)
    assert not state.foretells_this_turn.get(seat, 0)
    state.turn += 1
    assert cast_costs(state, state.cards[source.id], owner) == ['{1}{G}']
    assert cast_costs(state, state.cards[source.id], seat) == []
    assert serialize_match(state, look_players=[owner])['players'][owner]['exile'][0]['name'] == source.name


@pytest.mark.parametrize('seat', [1, 2])
def test_damage_trigger_does_not_follow_the_source_through_reentry(seat):
    state, source = position(seat, 'The Foretold Soldier')
    emit_event(state, 'damage_dealt', {'source_card_id': source.id, 'amount': 1})
    source.move_to_zone(Zone.EXILE)
    source.move_to_zone(Zone.BATTLEFIELD)
    state = resolve(state)
    assert source.id in state.players[seat].battlefield and not state.players[seat].exile


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_creature_cast_draws_only_through_the_counterable_entry_trigger(seat):
    state, cid = setup('Ethereal Valkyrie', seat)
    state.players[seat].mana_pool = {'C': 4, 'W': 1, 'U': 1}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cid})
    assert not state.players[seat].hand
    state = resolve(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert len(state.players[seat].hand) == 1
    assert state.pending_mechanic_choice['kind'] == 'foretell_from_hand'


@pytest.mark.parametrize('seat', [1, 2])
def test_colored_symbols_survive_reduction_and_both_foretell_costs_are_available(seat):
    state, source = position(seat)
    spell = add(state, 'Poison the Cup', seat)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [spell.id]})
    state.turn += 1
    assert set(cast_costs(state, state.cards[spell.id], seat)) == {'{1}{B}', '{B}{B}'}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert set(cast_costs(state, state.cards[spell.id], seat)) == {'{1}{B}', '{B}{B}'}


@pytest.mark.parametrize('seat', [1, 2])
def test_foretold_land_cannot_be_played_without_an_independent_permission(seat):
    from rules_engine.card_faces import exile_permission
    state, source = position(seat)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    land = next(cid for cid in state.players[seat].hand if 'Land' in state.cards[cid].types)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [land]})
    state.turn += 1
    assert can_look(state.cards[land], seat) and not exile_permission(state, seat, land)
    assert not any(move.get('card_id') == land for move in RulesEngine().legal_moves(state, seat))
    state.players[seat].exile_play_until[land] = state.turn
    assert exile_permission(state, seat, land)
    assert any(move['type'] == 'play_land' and move.get('card_id') == land
               for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selection', [None, [], ['missing'], ['source'], ['duplicate']])
def test_invalid_effect_selection_is_atomic(seat, selection):
    state, source = position(seat)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    held = state.players[seat].hand[0]
    ids = [source.id] if selection == ['source'] else [held, held] if selection == ['duplicate'] else selection
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ids})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('prevented', [False, True])
def test_actual_noncombat_damage_notifies_only_damage_that_was_dealt(seat, prevented):
    from effects.handlers import deal_damage, prevent_damage
    state, source = position(seat, 'The Foretold Soldier')
    other = 3-seat
    if prevented:
        prevent_damage(state, seat, {'target_player': other, 'amount': 2})
    dealt = deal_damage(state, seat, {'__source_card_id': source.id, 'target_player': other, 'amount': 2})
    assert dealt == (0 if prevented else 2)
    assert len(state.stack) == (0 if prevented else 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,event', [('Ethereal Valkyrie', 'enters_battlefield'),
                                      ('The Foretold Soldier', 'damage_dealt')])
def test_suppression_prevents_effect_created_triggers(seat, name, event):
    state, source = position(seat, name)
    raw_add(state, 'Humility', 3-seat, cards=EXTRA)
    emit_event(state, event, {'card_id': source.id, 'source_card_id': source.id, 'amount': 2})
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_countering_the_trigger_does_not_exile_the_source(seat):
    from effects.handlers import counter_ability
    state, source = position(seat, 'The Foretold Soldier')
    emit_event(state, 'damage_dealt', {'source_card_id': source.id, 'amount': 2})
    counter_ability(state, 3-seat, {'target_stack_id': state.stack[-1].id})
    assert not state.stack and source.id in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_loses_battlefield_only_foretell_cost_before_becoming_foretold(seat):
    from rules_engine.card_faces import FACE_FIELDS
    state, source = position(seat, 'Dream Devourer')
    model = add(state, 'The Foretold Soldier', 3-seat, Zone.HAND)
    source.printed_characteristics = {field: deepcopy(getattr(source, field)) for field in FACE_FIELDS}
    for field in FACE_FIELDS:
        setattr(source, field, deepcopy(getattr(model, field)))
    emit_event(state, 'damage_dealt', {'source_card_id': source.id, 'amount': 1})
    state = resolve(state)
    assert state.cards[source.id].name == 'Dream Devourer' and record(state.cards[source.id])
    state.turn += 1
    assert not cast_costs(state, state.cards[source.id], seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_effect_does_not_consume_ranar_free_action_or_trigger_foretelling_rewards(seat):
    state, source = position(seat)
    add(state, 'Ranar the Ever-Watchful', seat, Zone.BATTLEFIELD)
    add(state, 'Dream Devourer', seat, Zone.BATTLEFIELD)
    another = add(state, 'Behold the Multiverse', seat)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [another.id]})
    assert not state.stack and not state.foretells_this_turn.get(seat, 0)
    before = deepcopy(state.players[seat].mana_pool)
    held = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Behold the Multiverse')
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': held})
    assert state.players[seat].mana_pool == before and state.foretells_this_turn[seat] == 1
    assert len(state.stack) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp', 'Drain',
                                  'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite',
                                  'Counter-heavy', 'Removal-heavy'])
def test_ai_effect_choice_keeps_lands_and_affordable_interaction(seat, difficulty, style):
    from ai.agent import AIAgent
    state, source = position(seat)
    answer = add(state, 'Saw It Coming', seat)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty=difficulty, archetype=style).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat).action
    assert serialize_match_snapshot(state) == before
    assert action['type'] == 'choose_mechanic' and answer.id not in action['card_ids']
    assert all('Land' not in state.cards[cid].types for cid in action['card_ids'])
    state = checked_action(state, RulesEngine(), seat, action)
    assert record(state.cards[action['card_ids'][0]])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,costs', [('Lotus Bloom', []), ('Memnite', ['{0}'])])
@pytest.mark.parametrize('by_effect', [False, True])
def test_no_mana_cost_is_not_zero_even_after_a_foretell_reduction(seat, name, costs, by_effect):
    state, source = position(seat)
    spell = raw_add(state, name, seat, Zone.HAND, cards=EXTRA)
    if by_effect:
        emit_event(state, 'enters_battlefield', {'card_id': source.id})
        state = resolve(state)
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': [spell.id]})
    else:
        add(state, 'Dream Devourer', seat, Zone.BATTLEFIELD)
        state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': spell.id})
        state = resolve(state)
    state.turn += 1
    assert cast_costs(state, state.cards[spell.id], seat) == costs
    assert bool([move for move in RulesEngine().legal_moves(state, seat)
                 if move['type'] == 'cast_spell' and move.get('card_id') == spell.id]) == bool(costs)


@pytest.mark.parametrize('seat', [1, 2])
def test_each_modal_spell_face_derives_its_own_foretell_cost(seat):
    from rules_engine.card_faces import select_cast_face
    state, source = position(seat)
    spell = raw_add(state, 'Kolvori, God of Kinship', seat, Zone.HAND, cards=EXTRA)
    spell.card_faces = EXTRA[spell.name]['card_faces']
    spell.layout = EXTRA[spell.name]['layout']
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [spell.id]})
    state.turn += 1
    before = serialize_match_snapshot(state)
    assert cast_costs(state, select_cast_face(state.cards[spell.id], 0), seat) == ['{G}{G}']
    assert cast_costs(state, select_cast_face(state.cards[spell.id], 1), seat) == ['{G}']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_replacement_aware_draw_completes_before_hand_selection(seat):
    state, source = position(seat)
    raw_add(state, "Teferi's Ageless Insight", seat, cards=EXTRA)
    before = len(state.players[seat].hand)
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    assert len(state.players[seat].hand) == before + 2
    assert set(state.pending_mechanic_choice['options']) == set(state.players[seat].hand)


@pytest.mark.parametrize('seat', [1, 2])
def test_failed_draw_waits_for_the_resolving_ability_to_finish(seat):
    state, source = position(seat)
    state.players[seat].library.clear()
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    assert state.winner is None
    assert state.pending_mechanic_choice['kind'] == 'foretell_from_hand'
    held = state.players[seat].hand[0]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [held]})
    assert state.winner == 3-seat and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,ordinary', [('Lotus Bloom', False), ('Memnite', True)])
def test_absent_mana_cost_is_not_a_zero_mana_cost(seat, name, ordinary):
    from rules_engine.costs import collect_cost_options
    state, _ = position(seat)
    spell = raw_add(state, name, seat, Zone.HAND, cards=EXTRA)
    assert bool(collect_cost_options(state, seat, spell)) == ordinary
    assert bool([move for move in RulesEngine().legal_moves(state, seat)
                 if move['type'] == 'cast_spell' and move.get('card_id') == spell.id]) == ordinary
    assert collect_cost_options(state, seat, spell, without_mana=True)


@pytest.mark.parametrize('seat', [1, 2])
def test_http_pending_choice_and_effect_permission_survive_database_restart(game, seat):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    client, match = game
    state, source = position(seat)
    held = next(cid for cid in state.players[seat].hand
                if state.cards[cid].name == 'Behold the Multiverse')
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    state = resolve(state)
    state.id = match.state.id
    match.state = state
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    match = main.ACTIVE_MATCHES[state.id]
    before = snapshot(match)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': 3-seat, 'action': {'type': 'choose_mechanic', 'card_ids': [held]}})
    assert response.status_code == 422, response.text
    assert snapshot(match) == before
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [held]}})
    assert response.status_code == 200, response.text
    assert record(match.state.cards[held])['origin'] == 'effect'
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    match = main.ACTIVE_MATCHES[state.id]
    assert not match.state.pending_mechanic_choice
    assert record(match.state.cards[held])['origin'] == 'effect'
    match.state.turn += 1
    match.state.priority_player = seat
    match.state.active_player = seat
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': held,
                                   'from_exile': True, 'cost_choice': {'id': 'foretell_0'}}})
    assert response.status_code == 200, response.text
    assert match.state.stack[-1].payload['__was_foretold']


@pytest.mark.parametrize('seat', [1, 2])
def test_entry_trigger_survives_source_removal_and_its_permission_is_independent(seat):
    from effects.handlers import exile_permanent
    state, source = position(seat)
    held = state.players[seat].hand[0]
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    exile_permanent(state, 3-seat, {'target_card_id': source.id})
    state = resolve(state)
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [held]})
    state.turn += 1
    assert cast_costs(state, state.cards[held], seat) == ['{1}{U}']


@pytest.mark.parametrize('seat', [1, 2])
def test_token_damage_trigger_exiles_but_does_not_make_a_castable_card(seat):
    state, source = position(seat, 'The Foretold Soldier')
    source.is_token = True
    emit_event(state, 'damage_dealt', {'source_card_id': source.id, 'amount': 1})
    state = resolve(state)
    assert source.id not in state.players[seat].battlefield and source.id not in state.players[seat].exile
