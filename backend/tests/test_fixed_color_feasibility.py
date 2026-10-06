"""Conservative fixed-color impossibility; no time targets or card-name rules."""
import json
from pathlib import Path
import pytest
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.mana import can_pay_with_pool_and_lands, auto_pay_cost
from rules_engine.mana_abilities import proven_missing_fixed_color
from tests.test_mana_executor_choices import ROWS, position, add
from tests.test_additive_mana import aura

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,3,5])
def test_unavailable_color_does_not_trial_resource_permutations(seat,count,monkeypatch):
    state=position(seat)
    for _ in range(count): add(state,'Skirk Prospector',seat)
    before=serialize_match_snapshot(state)
    import rules_engine.mana_abilities as abilities
    def unexpected(*args,**kwargs): raise AssertionError('impossible color must not execute trial activations')
    monkeypatch.setattr(abilities,'activate_planned_mana_ability',unexpected)
    assert not can_pay_with_pool_and_lands(state,seat,'{U}')
    assert serialize_match_snapshot(state)==before

@pytest.mark.parametrize('seat',[1,2])
def test_positive_resource_count_reservation_and_pool_deficit(seat):
    state=position(seat)
    sources=[add(state,'Skirk Prospector',seat) for _ in range(3)]
    before=serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state,seat,'{R}{R}{R}')
    assert not can_pay_with_pool_and_lands(state,seat,'{R}{R}{R}{R}')
    assert can_pay_with_pool_and_lands(state,seat,'{R}{R}',reserved_card_ids=[sources[0].id])
    assert not can_pay_with_pool_and_lands(state,seat,'{R}{R}{R}',reserved_card_ids=[sources[0].id])
    assert serialize_match_snapshot(state)==before
    state.players[seat].mana_pool['U']=1
    assert can_pay_with_pool_and_lands(state,seat,'{U}')
    assert not can_pay_with_pool_and_lands(state,seat,'{U}{U}')
    assert auto_pay_cost(state,seat,'{R}{R}',reserved_card_ids=[sources[0].id])
    assert state.cards[sources[0].id].zone==Zone.BATTLEFIELD

@pytest.mark.parametrize('seat',[1,2])
def test_filter_prerequisite_conversion_and_complete_mixed_output(seat):
    state=position(seat)
    add(state,'Forest',seat);add(state,'Flooded Grove',seat);add(state,'Skirk Prospector',seat)
    before=serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state,seat,'{U}{U}')
    assert can_pay_with_pool_and_lands(state,seat,'{G}{U}')
    assert serialize_match_snapshot(state)==before
    assert auto_pay_cost(state,seat,'{G}{U}')

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('mode',['bonus','replacement','layer','snow','life'])
def test_complex_contexts_and_metadata_keep_original_search(seat,mode):
    state=position(seat)
    land=add(state,'Snow-Covered Forest' if mode=='snow' else 'Forest',seat)
    cost='{G}'
    if mode=='bonus':
        aura(state,'Wild Growth',3-seat,land);cost='{G}{G}'
    elif mode=='replacement':
        add(state,'Mana Reflection',seat);add(state,'Damping Sphere',3-seat);cost='{C}'
    elif mode=='layer':
        aura(state,'Spreading Seas',3-seat,land);cost='{U}'
    elif mode=='snow': cost='{S}'
    else:
        add(state,'Vesper Ghoul',seat);state.players[seat].life=2;cost='{U}'
        assert not can_pay_with_pool_and_lands(state,seat,cost,protected_life=2)
    before=serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state,seat,cost)
    assert serialize_match_snapshot(state)==before
    assert auto_pay_cost(state,seat,cost)

@pytest.mark.parametrize('seat',[1,2])
def test_continuous_source_departure_cannot_be_assumed_color_stable(seat):
    rows=json.loads((Path(__file__).parent/'fixtures/land_types.json').read_text())
    if isinstance(rows,dict): rows=rows.get('data',rows.get('cards',[]))
    ROWS.update({row['name']:row for row in rows})
    state=position(seat)
    add(state,'Magus of the Moon',seat);add(state,'Tropical Island',seat)
    assert not proven_missing_fixed_color(state,seat,{'U':1},('spell',set()))
