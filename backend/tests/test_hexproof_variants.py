"""Canonical source-quality hexproof; unknown predicate families stay unverified."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_keywords, has_keyword
from rules_engine.counter_placement import put_counters
from rules_engine.targeting import validate_hexproof_shroud_targets
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action, ActionRejected
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_named_counters import CARDS as NAMED
from tests.test_api_input_contracts import game, persist, snapshot


CARDS = {card['name']:card for card in json.loads((Path(__file__).parent/'fixtures/hexproof_variants.json').read_text())}
CARDS.update(NAMED)


def add(state,name,player=1,zone=Zone.BATTLEFIELD):
    card = raw_add(state,name,player,zone,cards=CARDS)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state,card.id)
        card.summoning_sick = False
    return card


@pytest.mark.parametrize('player',[1,2])
@pytest.mark.parametrize('target_name,source_name,blocked',[
    ('Knight of Malice','Swords to Plowshares',True),
    ('Knight of Malice','Royal Assassin',False),
    ('Knight of Grace','Royal Assassin',True),
    ('Knight of Grace','Swords to Plowshares',False),
    ('Eradicator Valkyrie','Ugin, the Spirit Dragon',True),
    ('Eradicator Valkyrie','Swords to Plowshares',False),
])
def test_canonical_metadata_does_not_promote_variant_to_unrestricted_hexproof(player,target_name,source_name,blocked):
    state = fixture()
    target = add(state,target_name,player)
    source = add(state,source_name,3-player)
    keywords = effective_keywords(state,target.id)
    assert 'hexproof' not in keywords and 'hexproof from' not in keywords
    assert has_keyword(state,target.id,'hexproof')  # Ability-family queries still match.
    assert validate_hexproof_shroud_targets(state,3-player,{'target_card_id':target.id},source)[0] == (not blocked)
    assert validate_hexproof_shroud_targets(state,player,{'target_card_id':target.id},source)[0]


@pytest.mark.parametrize('player',[1,2])
def test_white_spell_is_rejected_atomically_and_nonmatching_spell_can_resolve(player):
    state = fixture()
    target = add(state,'Knight of Malice',3-player)
    white = add(state,'Swords to Plowshares',player,Zone.HAND)
    assassin = add(state,'Royal Assassin',player)
    state.active_player = state.priority_player = player
    state.players[player].mana_pool['W'] = 2
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':white.id,'targets':{'target_card_id':target.id}})
    assert serialize_match_snapshot(state) == before
    target.tapped = True
    state = checked_action(state,RulesEngine(),player,{'type':'activate_ability','card_id':assassin.id,'ability_index':0,'targets':{'target_card_id':target.id}})
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player',[1,2])
def test_variant_acquired_in_response_rechecks_on_resolution_and_snapshot(player):
    state = fixture()
    target = add(state,'Grizzly Bears',3-player)
    white = add(state,'Swords to Plowshares',player,Zone.HAND)
    state.active_player = state.priority_player = player
    state.players[player].mana_pool['W'] = 1
    state = checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':white.id,'targets':{'target_card_id':target.id}})
    put_counters(state,'hexproof from white',2,target_card_id=target.id)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.BATTLEFIELD
    assert state.cards[white.id].zone == Zone.GRAVEYARD
    assert any('does not resolve' in line for line in state.log)


def test_variant_counter_removal_and_actual_unrestricted_grants_are_distinct():
    state = fixture()
    target = add(state,'Knight of Malice',2)
    black = add(state,'Royal Assassin')
    assert validate_hexproof_shroud_targets(state,1,{'target_card_id':target.id},black)[0]
    resolve_effect(state,2,'grant_keyword',{'target_card_id':target.id,'keyword':'hexproof'})
    assert not validate_hexproof_shroud_targets(state,1,{'target_card_id':target.id},black)[0]
    assert [effect['keyword'] for effect in target.keyword_effects] == ['hexproof']
    assert not target.counters
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not validate_hexproof_shroud_targets(restored,1,{'target_card_id':target.id},black)[0]
    target.reset_zone_counters(Zone.HAND)
    assert validate_hexproof_shroud_targets(state,1,{'target_card_id':target.id},black)[0]
    add(state,'Humility')
    assert not has_keyword(state,target.id,'hexproof')
    put_counters(state,'hexproof from white',3,target_card_id=target.id)
    assert effective_keywords(state,target.id) == ['hexproof from white']


@pytest.mark.parametrize('player',[1,2])
def test_http_rejects_white_target_without_mutating_sqlite_and_restores_variant_view(game,player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = match.state
    target = add(state,'Knight of Malice',3-player)
    white = add(state,'Swords to Plowshares',player,Zone.HAND)
    state.priority_player = state.active_player = player
    state.players[player].mana_pool['W'] = 1
    persist(match)
    before = snapshot(match)
    response = client.post(f'/matches/{state.id}/action',json={'player_id':player,'action':{'type':'cast_spell','card_id':white.id,'targets':{'target_card_id':target.id}}})
    assert response.status_code == 422, response.text
    assert snapshot(match) == before
    hints = inspect_target_hints(state,white,player)
    assert target.id not in {entry['id'] for entry in hints.get('creature_targets',[])}
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session),state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert effective_keywords(restored.state,target.id) == ['first strike','hexproof from white']


def test_graveyard_hexproof_is_not_a_permanent_targeting_restriction():
    state = fixture()
    target = add(state,'Knight of Malice',2,Zone.GRAVEYARD)
    source = add(state,'Swords to Plowshares')
    assert validate_hexproof_shroud_targets(state,1,{'target_card_id':target.id},source)[0]


@pytest.mark.parametrize('player',[1,2])
def test_planeswalker_activation_is_filtered_and_rejected_but_other_sources_remain_legal(player):
    state = fixture()
    target = add(state,'Eradicator Valkyrie',3-player)
    pw = add(state,'Ugin, the Spirit Dragon',player)
    pw.loyalty = 7
    state.priority_player = state.active_player = player
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state,RulesEngine(),player,{'type':'activate_loyalty','card_id':pw.id,'ability_index':0,'targets':{'target_card_id':target.id}})
    assert serialize_match_snapshot(state) == before
    legal = RulesEngine().legal_moves(state,player)
    ability = next(move for move in legal if move['type'] == 'activate_loyalty' and move['card_id'] == pw.id and move['ability_index'] == 0)
    assert target.id not in {entry['id'] for entry in ability.get('target_hints',{}).get('creature_targets',[])}
    white = add(state,'Swords to Plowshares',player,Zone.HAND)
    state.players[player].mana_pool['W'] = 1
    state = checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':white.id,'targets':{'target_card_id':target.id}})
    state = resolve(state)
    assert state.cards[target.id].zone == Zone.EXILE


def test_cannot_have_hexproof_overrides_newer_variant_counter_and_temporary_grant():
    state = fixture()
    target = add(state,'Knight of Malice',2)
    add(state,'Archetype of Endurance')
    put_counters(state,'hexproof from black',1,target_card_id=target.id)
    resolve_effect(state,2,'grant_keyword',{'target_card_id':target.id,'keyword':'hexproof','until_end_of_turn':True})
    assert not has_keyword(state,target.id,'hexproof')
    assert effective_keywords(state,target.id) == ['first strike']


@pytest.mark.parametrize('keyword',['hexproof','exalted','lifelink'])
def test_resolved_grants_keep_base_metadata_and_physical_counters_unchanged(keyword):
    from rules_engine.continuous import effective_keyword_counts
    state = fixture()
    target = add(state,'Grizzly Bears')
    base = list(target.keywords)
    for _ in range(2):
        resolve_effect(state,1,'grant_keyword',{'target_card_id':target.id,'keyword':keyword})
    assert target.keywords == base and not target.counters
    assert effective_keyword_counts(state,target.id)[keyword] == 2
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    saved['cards'][target.id]['keyword_effects'].clear()
    assert [effect['keyword'] for effect in restored.cards[target.id].keyword_effects] == [keyword,keyword]
    target.reset_zone_counters(Zone.GRAVEYARD)
    assert keyword not in effective_keywords(state,target.id)
    old = serialize_match_snapshot(state)
    old['cards'][target.id].pop('keyword_effects')
    assert deserialize_match_snapshot(old).cards[target.id].keyword_effects == []


def test_trigger_target_options_use_original_departed_source_not_a_new_incarnation():
    from game_state.state import StackItem
    from rules_engine.events import capture_last_known_battlefield, trigger_target_options
    state = fixture()
    target = add(state,'Eradicator Valkyrie',2)
    pw = add(state,'Ugin, the Spirit Dragon')
    capture_last_known_battlefield(state,pw.id)
    item = StackItem(id=state.allocate_object_id(),source_card_id=pw.id,controller=1,label='source-quality fixture',
                     effect_key='deal_damage',payload={'__trigger_target_clause':'Ugin deals 3 damage to any target.',
                                                      '__source_lki':dict(pw.last_known_battlefield)})
    # Explicit incarnation fixture: the old ability retains its planeswalker
    # source quality even when this card ID represents a new creature object.
    pw.battlefield_incarnation = int(pw.battlefield_incarnation or 0) + 1
    pw.types = ['Creature']
    assert target.id not in {option.get('target_card_id') for option in trigger_target_options(state,item)}
