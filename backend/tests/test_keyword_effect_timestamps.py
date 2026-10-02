"""Resolution-created keyword effects share timestamps, not physical counters."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, object_incarnation, assign_static_order_on_battlefield_entry, assign_effect_timestamp
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view
from rules_engine.continuous import effective_keywords, effective_keyword_counts, continuous_layer_trace
from rules_engine.engine import RulesEngine
from rules_engine.counter_placement import put_counters
from rules_engine.action_validation import checked_action
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_named_counters import CARDS as NAMED
from tests.test_api_input_contracts import game, persist


CARDS = {card['name']:card for card in json.loads((Path(__file__).parent/'fixtures/keyword_effect_timestamps.json').read_text())}
CARDS.update(NAMED)


def add(state,name='Grizzly Bears',player=1,zone=Zone.BATTLEFIELD):
    card = raw_add(state,name,player,zone,cards=CARDS)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state,card.id)
        card.summoning_sick = False
    return card


@pytest.mark.parametrize('until_end_of_turn',[False,True])
def test_resolved_grant_newer_than_humility_restores_keyword_without_retiming_permanent(until_end_of_turn):
    state = fixture()
    card = add(state)
    add(state,'Humility',2)
    original = object_incarnation(card), card.effect_timestamp
    resolve_effect(state,1,'grant_keyword',{'target_card_id':card.id,'keyword':'flying','until_end_of_turn':until_end_of_turn})
    assert 'flying' in effective_keywords(state,card.id)
    assert (object_incarnation(card),card.effect_timestamp) == original


def test_grant_removal_counter_and_later_grant_share_timestamp_order_and_instance_counts():
    state = fixture()
    card = add(state)
    resolve_effect(state,1,'grant_keyword',{'target_card_id':card.id,'keyword':'exalted'})
    put_counters(state,'exalted',3,target_card_id=card.id)
    assert effective_keyword_counts(state,card.id)['exalted'] == 2
    removal = add(state,'Humility',2)
    assert 'exalted' not in effective_keywords(state,card.id)
    resolve_effect(state,1,'grant_keyword',{'target_card_id':card.id,'keyword':'exalted','until_end_of_turn':True})
    assert effective_keyword_counts(state,card.id)['exalted'] == 1
    put_counters(state,'exalted',1,target_card_id=card.id)
    assert effective_keyword_counts(state,card.id)['exalted'] == 2
    layers = continuous_layer_trace(state,card.id)['applied_layers']
    effects = [layer for layer in layers if layer.get('timestamp_origin') == 'resolution']
    assert len(effects) == 2
    assert effects[0]['effect_timestamp'] < removal.effect_timestamp < effects[1]['effect_timestamp']
    RulesEngine()._clear_marked_damage(state)
    assert effective_keyword_counts(state,card.id)['exalted'] == 1  # Only the retimed counter remains effective.


@pytest.mark.parametrize('keyword',['flying','hexproof','lifelink','decayed','exalted'])
def test_independent_resolution_instances_persist_and_cleanup_only_expires_temporary_effects(keyword):
    state = fixture()
    card = add(state)
    for temporary in (False,True,True):
        resolve_effect(state,1,'grant_keyword',{'target_card_id':card.id,'keyword':keyword,'until_end_of_turn':temporary})
    assert card.keywords == [] and not card.counters
    assert effective_keyword_counts(state,card.id)[keyword] == 3
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    saved['cards'][card.id]['keyword_effects'][0]['keyword'] = 'haste'
    assert restored.cards[card.id].keyword_effects[0]['keyword'] == keyword
    assert card.keyword_effects[0]['keyword'] == keyword
    RulesEngine()._clear_marked_damage(restored)
    assert effective_keyword_counts(restored,card.id)[keyword] == 1
    assert len(restored.cards[card.id].keyword_effects) == 1
    restored.cards[card.id].reset_zone_counters(Zone.HAND)
    assert keyword not in effective_keywords(restored,card.id)


def test_team_resolution_shares_one_timestamp_and_does_not_affect_later_entrants():
    state = fixture()
    first, second = add(state), add(state)
    add(state,'Humility',2)
    resolve_effect(state,1,'temporary_pt_buff_all',{'power':1,'toughness':1,'keyword':'flying','controller_only':True})
    assert first.keyword_effects[0]['timestamp'] == second.keyword_effects[0]['timestamp']
    assert 'flying' in effective_keywords(state,first.id)
    assert 'flying' in effective_keywords(state,second.id)
    assert not any(key.startswith('__eot_keyword_') for key in first.counters)
    late = add(state)
    assert 'flying' not in effective_keywords(state,late.id)
    RulesEngine()._clear_marked_damage(state)
    assert not first.keyword_effects and not second.keyword_effects


def test_newer_grant_cannot_override_cannot_have_and_retiming_does_not_change_object_reference():
    state = fixture()
    card = add(state)
    add(state,'Archetype of Imagination',2)
    resolve_effect(state,1,'grant_keyword',{'target_card_id':card.id,'keyword':'flying'})
    assert 'flying' not in effective_keywords(state,card.id)
    incarnation = object_incarnation(card)
    assign_effect_timestamp(state,card.id)
    assert object_incarnation(card) == incarnation
    assert len(card.keyword_effects) == 1
    card.battlefield_incarnation += 1
    assert not any(layer.get('timestamp_origin') == 'resolution' for layer in continuous_layer_trace(state,card.id)['applied_layers'])


def test_legacy_grants_and_temporary_markers_restore_with_explicit_inferred_timestamp():
    state = fixture()
    card = add(state)
    saved = serialize_match_snapshot(state)
    raw = saved['cards'][card.id]
    raw.pop('keyword_effects')
    raw['granted_keywords'] = ['lifelink','lifelink']
    raw['counters']['__eot_keyword_flying'] = 1
    restored = deserialize_match_snapshot(saved)
    assert effective_keyword_counts(restored,card.id)['lifelink'] == 2
    layers = continuous_layer_trace(restored,card.id)['applied_layers']
    assert sum(layer.get('timestamp_origin') == 'legacy_inferred' for layer in layers) == 3
    RulesEngine()._clear_marked_damage(restored)
    assert 'flying' not in effective_keywords(restored,card.id)
    assert effective_keyword_counts(restored,card.id)['lifelink'] == 2


@pytest.mark.parametrize('player',[1,2])
@pytest.mark.parametrize('name',['Jump','Leap'])
def test_canonical_targeted_grants_cast_and_resolve_after_humility_without_dropping_draw(player,name):
    state = fixture()
    card = add(state,player=player)
    removal = add(state,'Humility',3-player)
    spell = add(state,name,player,Zone.HAND)
    state.players[player].mana_pool['U'] = 2
    state.active_player = state.priority_player = player
    state = checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':spell.id,'targets':{'target_card_id':card.id}})
    state = resolve(state)
    target = state.cards[card.id]
    assert 'flying' in effective_keywords(state,card.id)
    assert target.keyword_effects[0]['timestamp'] > removal.effect_timestamp
    assert target.keyword_effects[0]['source_card_id'] == spell.id
    assert target.keyword_effects[0]['source_name'] == name
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert len(state.players[player].hand) == (1 if name == 'Leap' else 0)
    assert serialize_card_view(state,card.id)['keyword_counts']['flying'] == 1
    trace = continuous_layer_trace(state,card.id)['applied_layers']
    created = next(layer for layer in trace if layer.get('timestamp_origin') == 'resolution')
    assert created['source_id'] == spell.id and created['target_id'] == card.id
    RulesEngine()._clear_marked_damage(state)
    assert 'flying' not in effective_keywords(state,card.id)


@pytest.mark.parametrize('player',[1,2])
def test_canonical_targeted_loss_overrides_old_counter_but_not_a_later_grant(player):
    state = fixture()
    card = add(state,player=3-player)
    put_counters(state,'flying',2,target_card_id=card.id)
    spell = add(state,'Canopy Claws',player,Zone.HAND)
    state.active_player = state.priority_player = player
    state = checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':spell.id,'targets':{'target_card_id':card.id}})
    state = resolve(state)
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert 'flying' not in effective_keywords(state,card.id)
    resolve_effect(state,3-player,'grant_keyword',{'target_card_id':card.id,'keyword':'flying','until_end_of_turn':True})
    assert effective_keyword_counts(state,card.id)['flying'] == 1
    RulesEngine()._clear_marked_damage(state)
    assert effective_keyword_counts(state,card.id)['flying'] == 1  # Physical counters never disappeared.


@pytest.mark.parametrize('player',[1,2])
def test_http_resolution_timestamp_and_expiry_survive_sqlite_restart(game,player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = match.state
    card = add(state,player=player)
    removal = add(state,'Humility',3-player)
    spell = add(state,'Jump',player,Zone.HAND)
    state.players[player].mana_pool['U'] = 1
    state.priority_player = state.active_player = player
    persist(match)
    path = f'/matches/{state.id}/action'
    response = client.post(path,json={'player_id':player,'action':{'type':'cast_spell','card_id':spell.id,'targets':{'target_card_id':card.id}}})
    assert response.status_code == 200, response.text
    for _ in range(4):
        if not match.state.stack:
            break
        response = client.post(path,json={'player_id':match.state.priority_player,'action':{'type':'pass_priority'}})
        assert response.status_code == 200, response.text
    assert 'flying' in effective_keywords(match.state,card.id)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session),state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    effect = restored.state.cards[card.id].keyword_effects[0]
    assert effect['timestamp'] > removal.effect_timestamp and effect['timestamp_origin'] == 'resolution'
    assert serialize_card_view(restored.state,card.id)['keyword_counts']['flying'] == 1
    RulesEngine()._clear_marked_damage(restored.state)
    assert not restored.state.cards[card.id].keyword_effects
    assert 'flying' not in effective_keywords(restored.state,card.id)


@pytest.mark.parametrize('player',[1,2])
@pytest.mark.parametrize('name',['Jump','Leap','Canopy Claws'])
def test_ai_targets_known_keyword_effects_by_public_engine_projection_without_drawing(monkeypatch,player,name):
    from ai.agent import AIAgent
    from ai.pending_effects import keyword_target_value
    state = fixture()
    own, opposing = add(state,player=player), add(state,player=3-player)
    put_counters(state,'+1/+1',4,target_card_id=opposing.id)
    if name == 'Canopy Claws':
        put_counters(state,'flying',1,target_card_id=own.id)
        put_counters(state,'flying',1,target_card_id=opposing.id)
    spell = add(state,name,player,Zone.HAND)
    state.players[player].mana_pool['U'] = 2
    state.active_player = state.priority_player = player
    before = serialize_match_snapshot(state)
    def forbidden_draw(*args,**kwargs):
        raise AssertionError('Target projection must not execute later draw instructions')
    monkeypatch.setattr('effects.handlers.draw_cards',forbidden_draw)
    move = next(move for move in RulesEngine().legal_moves(state,player) if move['type'] == 'cast_spell' and move['card_id'] == spell.id)
    action = AIAgent(difficulty='master',archetype='Tempo')._materialize_action(state,move,player)
    assert action['targets']['target_card_id'] == (opposing.id if name == 'Canopy Claws' else own.id)
    assert serialize_match_snapshot(state) == before
    assert keyword_target_value(state,spell,player,action['targets']) > 0


@pytest.mark.parametrize('player',[1,2])
@pytest.mark.parametrize('name',['Leap','Canopy Claws'])
def test_midstack_snapshot_replay_preserves_complete_keyword_effect_state_and_cleanup(player,name):
    state = fixture()
    card = add(state,player=player)
    add(state,'Humility',3-player)
    put_counters(state,'flying',1,target_card_id=card.id)
    spell = add(state,name,player,Zone.HAND)
    state.players[player].mana_pool['U'] = 2
    state.active_player = state.priority_player = player
    state = checked_action(state,RulesEngine(),player,{'type':'cast_spell','card_id':spell.id,'targets':{'target_card_id':card.id}})
    pending = serialize_match_snapshot(state)
    original = resolve(state)
    resumed = resolve(deserialize_match_snapshot(pending))
    assert serialize_match_snapshot(original) == serialize_match_snapshot(resumed)
    RulesEngine()._clear_marked_damage(original)
    RulesEngine()._clear_marked_damage(resumed)
    assert serialize_match_snapshot(original) == serialize_match_snapshot(resumed)


def test_untap_instruction_is_not_tap_and_optional_tap_untap_is_not_fabricated():
    from copy import copy
    from rules_engine.oracle_effects import infer_effect_from_oracle
    from rules_engine.coverage import known_unsupported_mechanics
    state = fixture()
    card = add(state)
    card.tapped = True
    spell = add(state,'Twiddle',zone=Zone.HAND)
    # An explicit instruction fixture isolates lexical dispatch from Twiddle's
    # deliberately unsupported optional two-way choice.
    instruction = copy(spell)
    instruction.oracle_text = 'Untap target creature.'
    key, payload = infer_effect_from_oracle(state,instruction,1,{'target_card_id':card.id})
    assert key == 'untap'
    resolve_effect(state,1,key,payload)
    assert not card.tapped
    key, _ = infer_effect_from_oracle(state,spell,1,{'target_card_id':card.id})
    assert key == 'noop'
    assert 'tap/untap choice fidelity' in known_unsupported_mechanics(spell.oracle_text)
