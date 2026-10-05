"""Domain and affinity must consume the same current land-type view."""
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.domain import basic_land_type_count
from tests.test_affinity import setup, add, PERMANENTS
from tests.test_land_type_layers import CARDS


@pytest.mark.parametrize('seat',[1,2])
def test_domain_includes_global_type_addition_and_replacement(seat):
    state,_=setup(seat,'Spire Golem')
    add(state,'Hallowed Fountain',seat,cards=PERMANENTS)
    assert basic_land_type_count(state,seat)==2
    moon=add(state,'Blood Moon',3-seat,cards=PERMANENTS)
    assert basic_land_type_count(state,seat)==1
    add(state,'Urborg, Tomb of Yawgmoth',seat,cards=PERMANENTS)
    assert basic_land_type_count(state,seat)==1
    state.players[3-seat].battlefield.remove(moon.id)
    state.players[3-seat].graveyard.append(moon.id)
    moon.move_to_zone(Zone.GRAVEYARD)
    assert basic_land_type_count(state,seat)==3
    before=serialize_match_snapshot(state)
    restored=deserialize_match_snapshot(before)
    assert basic_land_type_count(restored,seat)==3
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Prismatic Omen','Dryad of the Ilysian Grove'])
def test_domain_distinct_types_are_controller_scoped(seat,name):
    state,_=setup(seat,'Spire Golem')
    add(state,'Darksteel Citadel',seat,cards=PERMANENTS)
    add(state,'Hallowed Fountain',3-seat,cards=PERMANENTS)
    add(state,name,seat,cards=CARDS)
    assert basic_land_type_count(state,seat)==5
    assert basic_land_type_count(state,3-seat)==2
