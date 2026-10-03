"""Real exhaustive payments and announced discard counts; no fabricated cards."""
import json
from pathlib import Path
import pytest
from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add, resolve
from tests.test_api_input_contracts import game, persist, rejected

ROWS = {row['name']:row for row in json.loads((Path(__file__).parent/'fixtures/variable_spell_costs.json').read_text())}
NAMES = ["Kaervek's Spite", 'Sickening Dreams']


def setup(name,seat=1):
    state = board(seat)
    spell = raw_add(state,name,seat,Zone.HAND,cards=ROWS)
    hand = [add(state,n,seat,Zone.HAND) for n in ['Island','Swamp','Grizzly Bears']]
    own = [add(state,n,seat) for n in ['Island','Swamp','Grizzly Bears']]
    other = add(state,'Grizzly Bears',3-seat)
    state.players[seat].mana_pool.update(B=10,C=20)
    return state,spell,hand,own,other


def action(spell,seat,hand,x=0):
    return {'type':'cast_spell','card_id':spell.id,'cost_choice':{'id':'base',
        **({'discard_card_ids':[c.id for c in hand[:x]]} if spell.name=='Sickening Dreams' else {})},
        'targets':{'x_value':x} if spell.name=='Sickening Dreams' else {'target_player':3-seat}}


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('x',[0,1,2,3])
def test_announced_x_pays_exact_cards_and_deals_actual_symmetric_damage(seat,x):
    state,spell,hand,own,other = setup('Sickening Dreams',seat)
    moves=RulesEngine().legal_moves(state,seat)
    move=next(m for m in moves if m.get('card_id')==spell.id)
    assert move['target_hints']['requires_x_value'] and move['target_hints']['x_value_max']==3
    assert move['cost_options'][0]['discard_x']
    state=checked_action(state,RulesEngine(),seat,action(spell,seat,hand,x))
    assert len(state.players[seat].hand)==3-x
    assert state.players[seat].mana_pool['B']==9 and state.players[seat].mana_pool['C']==19
    state=resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert [state.players[p].life for p in [1,2]]==[20-x,20-x]
    assert (state.cards[other.id].zone==Zone.GRAVEYARD)==(x>=2)
    assert (state.cards[own[-1].id].zone==Zone.GRAVEYARD)==(x>=2)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('bad',['missing-x','too-high','few','duplicate','source','opponent'])
def test_invalid_resource_x_is_atomic(seat,bad):
    state,spell,hand,_,other=setup('Sickening Dreams',seat)
    payload=action(spell,seat,hand,2)
    if bad=='missing-x': payload['targets']={}
    elif bad=='too-high': payload['targets']['x_value']=4
    elif bad=='few': payload['cost_choice']['discard_card_ids'].pop()
    elif bad=='duplicate': payload['cost_choice']['discard_card_ids']=[hand[0].id]*2
    elif bad=='source': payload['cost_choice']['discard_card_ids'][0]=spell.id
    else: payload['cost_choice']['discard_card_ids'][0]=other.id
    before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): checked_action(state,RulesEngine(),seat,payload)
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('empty',[False,True])
def test_all_resources_are_paid_and_source_survives_hand_discard(seat,empty):
    state,spell,hand,own,other=setup("Kaervek's Spite",seat)
    if empty:
        for card in hand+own:
            getattr(state.players[seat],card.zone.value).remove(card.id)
            card.move_to_zone(Zone.EXILE); state.players[seat].exile.append(card.id)
    option,=collect_cost_options(state,seat,spell)
    assert option.discard_all and option.sacrifice_all
    state=checked_action(state,RulesEngine(),seat,action(spell,seat,hand))
    assert not state.players[seat].hand and not state.players[seat].battlefield
    assert state.cards[spell.id].zone==Zone.STACK
    assert state.cards[other.id].zone==Zone.BATTLEFIELD
    state=resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.players[3-seat].life==15 and state.players[seat].life==20


@pytest.mark.parametrize('seat',[1,2])
def test_spells_can_be_countered_after_resources_are_irrevocably_paid(seat):
    state,spell,hand,own,_=setup("Kaervek's Spite",seat)
    state=checked_action(state,RulesEngine(),seat,action(spell,seat,hand))
    resolve_effect(state,3-seat,'counter_spell',{'target_stack_id':state.stack[-1].id})
    assert not state.players[seat].hand and not state.players[seat].battlefield
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    assert state.players[3-seat].life==20


@pytest.mark.parametrize('seat',[1,2])
def test_copy_uses_announced_x_without_a_second_discard(seat):
    state,spell,hand,_,_=setup('Sickening Dreams',seat)
    state=checked_action(state,RulesEngine(),seat,action(spell,seat,hand,1))
    resolve_effect(state,seat,'copy_spell',{'target_stack_id':state.stack[-1].id})
    state=resolve(state)
    assert len(state.players[seat].hand)==2
    assert state.players[1].life==state.players[2].life==18


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('difficulty',['casual','strong','master'])
def test_ai_chooses_payable_minimum_lethal_x_and_avoids_self_loss(seat,difficulty):
    state,spell,hand,_,_=setup('Sickening Dreams',seat)
    state.players[3-seat].life=1
    move=next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id')==spell.id)
    ai=AIAgent(difficulty)
    result=ai._materialize_action(state,move,seat)
    assert result['targets']['x_value']==1
    assert len(result['cost_choice']['discard_card_ids'])==1
    assert not result.get('_invalid_ai_choice')
    resolved=resolve(checked_action(state,RulesEngine(),seat,result))
    assert resolved.winner==seat
    state.players[seat].life=1
    unsafe=ai._materialize_action(state,move,seat)
    assert unsafe.get('_invalid_ai_choice')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('difficulty',['casual','strong','master'])
def test_ai_does_not_nuke_resources_for_unproductive_fixed_life_loss(seat,difficulty):
    state,spell,hand,_,_=setup("Kaervek's Spite",seat)
    move=next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id')==spell.id)
    ai=AIAgent(difficulty)
    before=serialize_match_snapshot(state)
    assert ai._materialize_action(state,move,seat).get('_invalid_ai_choice')
    assert serialize_match_snapshot(state)==before
    state.players[3-seat].life=5
    chosen=ai._materialize_action(state,move,seat)
    assert not chosen.get('_invalid_ai_choice')
    assert resolve(checked_action(state,RulesEngine(),seat,chosen)).winner==seat


@pytest.mark.parametrize('seat', [1, 2])
def test_mana_ability_consumption_precedes_exhaustive_payment(seat):
    state, spell, hand, own, _ = setup("Kaervek's Spite", seat)
    state.players[seat].mana_pool = {}
    # Two Swamps plus a sacrificial mana ability pay BBB; Island is not black mana.
    add(state, 'Swamp', seat)
    petal = raw_add(state, 'Lotus Petal', seat, cards=ROWS)
    state = checked_action(state, RulesEngine(), seat, action(spell, seat, hand))
    assert state.cards[petal.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].zone == Zone.STACK
    assert not state.players[seat].battlefield
    assert state.log.index(next(line for line in state.log if 'Lotus Petal' in line)) < state.log.index(
        next(line for line in state.log if 'additional cost' in line))


@pytest.mark.parametrize('seat', [1, 2])
def test_departing_death_watcher_sees_entire_sacrifice_batch(seat):
    state, spell, hand, _, _ = setup("Kaervek's Spite", seat)
    artist = raw_add(state, 'Blood Artist', seat, cards=ROWS)
    state = checked_action(state, RulesEngine(), seat, action(spell, seat, hand))
    assert sum(item.source_card_id == artist.id for item in state.stack) == 2
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.players[seat].life == 22
    assert state.players[3-seat].life == 13


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', NAMES)
def test_authorized_free_cast_keeps_mandatory_nonmana_payment(seat, name):
    state, spell, hand, _, _ = setup(name, seat)
    state.players[seat].hand.remove(spell.id)
    spell.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(spell.id)
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
    mana = dict(state.players[seat].mana_pool)
    payload = {**action(spell, seat, hand, 2), 'from_graveyard': True}
    state = checked_action(state, RulesEngine(), seat, payload)
    assert state.players[seat].mana_pool == mana
    assert len(state.players[seat].hand) == (1 if name == 'Sickening Dreams' else 0)
    assert state.cards[spell.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', NAMES)
def test_http_payment_contract_and_atomic_rejection(game, seat, name):
    client, controller = game
    state, spell, hand, own, _ = setup(name, seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    payload = action(spell, seat, hand, 2)
    bad = json.loads(json.dumps(payload))
    bad['cost_choice']['discard_card_ids'] = [hand[0].id]
    rejected(client, controller, bad, seat)
    moves = client.get(f'/matches/{state.id}/legal-moves', params={'player_id': seat}).json()['moves']
    move = next(move for move in moves if move.get('card_id') == spell.id)
    assert move['cost_options'][0]['discard_x' if name == 'Sickening Dreams' else 'discard_all']
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': payload})
    assert response.status_code == 200, response.text
    assert controller.state.cards[spell.id].zone == Zone.STACK
    assert len(controller.state.players[seat].hand) == (1 if name == 'Sickening Dreams' else 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Firestorm', 'Nostalgic Dreams', 'Devastating Dreams'])
def test_unmodeled_resource_x_effects_remain_explicitly_blocked(seat, name):
    from rules_engine.coverage import known_unsupported_mechanics
    state, spell, *_ = setup(name, seat)
    gaps = known_unsupported_mechanics(spell.oracle_text, card_name=name)
    assert gaps
    assert not collect_cost_options(state, seat, spell)
    assert not any(move.get('card_id') == spell.id for move in RulesEngine().legal_moves(state, seat))
