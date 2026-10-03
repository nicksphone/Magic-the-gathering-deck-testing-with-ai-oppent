"""Canonical subtype/color payments and their actual downstream instructions."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone, StackItem
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import collect_cost_options, additional_cost_candidates
from rules_engine.engine import RulesEngine
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.oracle_effects import infer_effect_from_oracle, search_card_matches
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_kicker import ROWS as KICKER
from tests.test_permanent_kicker import ROWS as PERMANENTS
from tests.test_surveil_mill import add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/qualified_spell_costs.json').read_text())}
SPELLS = {'Goblin Grenade': 'subtype_goblin', 'Fodder Launch': 'subtype_goblin',
          'Natural Order': 'green_creature', 'Abjure': 'blue_permanent'}


def setup(name, seat=1):
    state = board(seat)
    spell = raw_add(state, name, seat, Zone.HAND, cards=ROWS)
    payer = raw_add(state, {'Goblin Grenade':'Goblin Instigator','Fodder Launch':'Goblin Instigator',
                           'Natural Order':'Woodland Changeling','Abjure':'Hapless Researcher'}[name], seat, cards=ROWS)
    target = raw_add(state, 'Baloth Gorger', 3-seat, cards=PERMANENTS)
    state.players[seat].mana_pool.update(R=10,B=10,G=10,U=10,C=20)
    if name == 'Natural Order':
        raw_add(state,'Myr Superion',seat,Zone.LIBRARY,cards=ROWS)
        raw_add(state,'Baloth Gorger',seat,Zone.LIBRARY,cards=PERMANENTS)
    if name == 'Abjure':
        other = raw_add(state,'Burst Lightning',3-seat,Zone.HAND,cards=KICKER)
        state.players[3-seat].hand.remove(other.id)
        other.move_to_zone(Zone.STACK)
        state.stack.append(StackItem(id=state.allocate_object_id(),controller=3-seat,label=other.name,
            source_card_id=other.id,effect_key='deal_damage',payload={'amount':2,'target_player':seat}))
    return state, spell, payer, target


def announcement(state, spell, payer, target, seat):
    targets = ({'target_stack_id':state.stack[-1].id} if spell.name == 'Abjure' else
               {'target_card_id':target.id} if spell.name == 'Fodder Launch' else
               {'target_player':3-seat} if spell.name == 'Goblin Grenade' else {})
    return {'type':'cast_spell','card_id':spell.id,'targets':targets,
            'cost_choice':{'id':'base','sacrifice_card_ids':[payer.id]}}


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_real_qualified_cost_and_snapshot_resolution(seat,name):
    state,spell,payer,target = setup(name,seat)
    option, = collect_cost_options(state,seat,spell)
    assert option.sacrifice_kind == SPELLS[name]
    assert 'unsupported spell additional cost' not in known_unsupported_mechanics(spell.oracle_text,card_name=spell.name)
    before = sum(state.players[seat].mana_pool.values())
    state = checked_action(state,RulesEngine(),seat,announcement(state,spell,payer,target,seat))
    assert state.cards[payer.id].zone == Zone.GRAVEYARD
    assert before-sum(state.players[seat].mana_pool.values()) == {'Goblin Grenade':1,'Fodder Launch':4,'Natural Order':4,'Abjure':1}[name]
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    if name in {'Goblin Grenade','Fodder Launch'}:
        assert state.players[3-seat].life == 15
        if name == 'Fodder Launch': assert state.cards[target.id].zone == Zone.GRAVEYARD
    elif name == 'Abjure':
        assert state.players[seat].life == 20
        assert any(state.cards[i].name == 'Burst Lightning' for i in state.players[3-seat].graveyard)
    else:
        assert any(state.cards[i].name == 'Baloth Gorger' for i in state.players[seat].battlefield)
        assert not any(state.cards[i].name == 'Myr Superion' for i in state.players[seat].battlefield)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_candidates_are_owned_controlled_present_and_exact(seat,name):
    state,spell,payer,_ = setup(name,seat)
    option, = collect_cost_options(state,seat,spell)
    opponent = raw_add(state,payer.name,3-seat,cards=ROWS)
    wrong = raw_add(state,'Goblin Warrens',seat,cards=ROWS)
    island = add(state,'Island',seat)
    ghost = raw_add(state,payer.name,seat,cards=ROWS)
    ghost.move_to_zone(Zone.GRAVEYARD)  # Stale list entry is not a permanent.
    controlled_elsewhere = raw_add(state,payer.name,seat,cards=ROWS)
    controlled_elsewhere.controller = 3-seat
    eligible = set(additional_cost_candidates(state,seat,spell.id,option)['sacrifice_card_ids'])
    assert payer.id in eligible
    assert not eligible.intersection({opponent.id,wrong.id,island.id,ghost.id,controlled_elsewhere.id})
    for invalid in [opponent,wrong,island,ghost,controlled_elsewhere]:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state,RulesEngine(),seat,announcement(state,spell,invalid,state.cards[next(
                i for i in state.players[3-seat].battlefield if state.cards[i].name == 'Baloth Gorger')],seat))
        assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat',[1,2])
def test_subtype_cost_includes_changeling_and_kindred_permanents_not_nonpermanent_cards(seat):
    state,spell,payer,_ = setup('Goblin Grenade',seat)
    changeling = raw_add(state,'Mothdust Changeling',seat,cards=ROWS)
    kindred = raw_add(state,'Boggart Shenanigans',seat,cards=ROWS)
    instant = raw_add(state,'Crib Swap',seat,Zone.HAND,cards=ROWS)
    # Even corrupted/stale battlefield indexes cannot make an instant permanent.
    state.players[seat].battlefield.append(instant.id)
    option, = collect_cost_options(state,seat,spell)
    assert set(additional_cost_candidates(state,seat,spell.id,option)['sacrifice_card_ids']) == {payer.id,changeling.id,kindred.id}


@pytest.mark.parametrize('seat',[1,2])
def test_color_cost_uses_actual_colors_not_mana_abilities_or_identity(seat):
    state,spell,payer,_ = setup('Abjure',seat)
    dual = raw_add(state,'Mistvein Borderpost',seat,cards=ROWS)
    devoid = raw_add(state,'Benthic Infiltrator',seat,cards=ROWS)
    add(state,'Island',seat)
    option, = collect_cost_options(state,seat,spell)
    eligible = set(additional_cost_candidates(state,seat,spell.id,option)['sacrifice_card_ids'])
    assert eligible == {payer.id,dual.id}
    assert devoid.id not in eligible


@pytest.mark.parametrize('seat',[1,2])
def test_referenced_controller_damage_uses_resolution_controller_not_cast_controller(seat):
    state,spell,payer,target = setup('Fodder Launch',seat)
    state = checked_action(state,RulesEngine(),seat,announcement(state,spell,payer,target,seat))
    from effects.registry import resolve_effect
    resolve_effect(state,seat,'change_control',{'target_card_id':target.id,'new_controller':seat})
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.players[seat].life == 15
    assert state.players[3-seat].life == 20
    assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('name', ['Woodland Changeling','Goblin Instigator','Myr Superion','Mistvein Borderpost'])
def test_green_creature_search_preserves_color_and_type(name):
    state = board()
    candidate = raw_add(state,name,1,Zone.LIBRARY,cards=ROWS)
    assert search_card_matches(candidate,'green_creature') == (name == 'Woodland Changeling')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('difficulty',['casual','strong','master'])
@pytest.mark.parametrize('name',SPELLS)
def test_all_ai_tiers_materialize_eligible_payment_and_checked_cast(seat,difficulty,name):
    state,spell,payer,_ = setup(name,seat)
    # This low-power wrong subtype/color must never become a cheap payment.
    raw_add(state,'Benthic Infiltrator',seat,cards=ROWS)
    move = next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state,move,seat)
    assert action['cost_choice']['sacrifice_card_ids'] == [payer.id]
    state = checked_action(state,RulesEngine(),seat,action)
    assert state.cards[payer.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_free_cast_keeps_the_qualified_resource_payment(seat,name):
    from effects.registry import resolve_effect
    state,spell,payer,target = setup(name,seat)
    state.players[seat].hand.remove(spell.id)
    spell.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(spell.id)
    state.mechanic_choice_players = {seat}
    resolve_effect(state,seat,'cast_from_graveyard',{'target_card_id':spell.id})
    action = {**announcement(state,spell,payer,target,seat),'from_graveyard':True}
    before = sum(state.players[seat].mana_pool.values())
    state = checked_action(state,RulesEngine(),seat,action)
    assert sum(state.players[seat].mana_pool.values()) == before
    assert state.cards[payer.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('removed',[False,True])
def test_controller_damage_uses_prevention_and_fizzles_with_its_only_target(seat,removed):
    from rules_engine.prevention import add_player_prevention_shield
    from effects.registry import resolve_effect
    state,spell,payer,target = setup('Fodder Launch',seat)
    state = checked_action(state,RulesEngine(),seat,announcement(state,spell,payer,target,seat))
    add_player_prevention_shield(state,3-seat,3)
    if removed:
        resolve_effect(state,seat,'exile',{'target_card_id':target.id})
    state = resolve(state)
    assert state.players[3-seat].life == (20 if removed else 18)
    assert state.cards[payer.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_http_qualified_payment_rejection_and_resumable_resolution(game,seat,name):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    client,controller = game
    state,spell,payer,target = setup(name,seat)
    state.id = controller.state.id
    state.mechanic_choice_players = {1,2}
    controller.state = state
    persist(controller)
    invalid = announcement(state,spell,add(state,'Island',seat),target,seat)
    persist(controller)
    rejected(client,controller,invalid,player_id=seat)
    action = announcement(state,spell,payer,target,seat)
    response = client.post(f'/matches/{state.id}/action',json={'player_id':seat,'action':action})
    assert response.status_code == 200, response.text
    def restore():
        saved = serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state)
        main.ACTIVE_MATCHES.pop(state.id,None)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session),state.id)
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[state.id].state) == saved
        return main.ACTIVE_MATCHES[state.id].state
    restore()
    for _ in range(2):
        actor = main.ACTIVE_MATCHES[state.id].state.priority_player
        response = client.post(f'/matches/{state.id}/action',json={
            'player_id':actor,'action':{'type':'pass_priority'}})
        assert response.status_code == 200, response.text
    final = restore()
    if name == 'Natural Order':
        choice = final.pending_mechanic_choice
        assert choice['player_id'] == seat
        assert choice['effect_payload']['contains'] == 'green_creature'
        assert [final.cards[i].name for i in choice['options']] == ['Baloth Gorger']
        selection = {'type':'choose_mechanic','card_ids':choice['options']}
        response = client.post(f'/matches/{state.id}/action',json={'player_id':seat,'action':selection})
        assert response.status_code == 200, response.text
        final = restore()
        assert not final.pending_mechanic_choice
        assert any(final.cards[i].name == 'Baloth Gorger' for i in final.players[seat].battlefield)
    elif name in {'Goblin Grenade','Fodder Launch'}:
        assert final.players[3-seat].life == 15
    else:
        assert final.players[seat].life == 20


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_controlled_opponent_owned_resource_goes_to_its_owners_graveyard(seat,name):
    from effects.registry import resolve_effect
    state,spell,payer,target = setup(name,seat)
    borrowed = raw_add(state,payer.name,3-seat,cards=ROWS)
    resolve_effect(state,seat,'change_control',{'target_card_id':borrowed.id,'new_controller':seat})
    state = checked_action(state,RulesEngine(),seat,announcement(state,spell,borrowed,target,seat))
    assert borrowed.id in state.players[3-seat].graveyard
    assert borrowed.id not in state.players[seat].graveyard
    assert state.cards[payer.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('difficulty',['casual','strong','master'])
def test_actual_goblin_entry_token_is_an_eligible_lower_loss_payment(seat,difficulty):
    state,spell,payer,_ = setup('Goblin Grenade',seat)
    instigator = raw_add(state,'Goblin Instigator',seat,Zone.HAND,cards=ROWS)
    state = resolve(checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':instigator.id}))
    tokens = [state.cards[i] for i in state.players[seat].battlefield if 'Token' in state.cards[i].types]
    assert len(tokens) == 1
    move = next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id') == spell.id)
    action = AIAgent(difficulty)._materialize_action(state,move,seat)
    assert action['cost_choice']['sacrifice_card_ids'] == [tokens[0].id]
    state = checked_action(state,RulesEngine(),seat,action)
    assert state.cards[tokens[0].id].zone == Zone.CEASED
    assert all(tokens[0].id not in getattr(player, zone) for player in state.players.values()
               for zone in ('battlefield', 'graveyard', 'exile'))
    assert state.cards[payer.id].zone == Zone.BATTLEFIELD
    assert state.cards[instigator.id].zone == Zone.BATTLEFIELD
