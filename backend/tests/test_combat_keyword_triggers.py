"""Real card fixtures; attack abilities are stack events, not immediate bonuses."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, Step, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view
from rules_engine.continuous import effective_keyword_counts, effective_keywords, effective_power
from rules_engine.counter_placement import put_counters
from rules_engine.combat import declare_attackers
from rules_engine.restrictions import card_cant_block
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.action_validation import checked_action
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_named_counters import CARDS as NAMED
from tests.test_api_input_contracts import game, persist


CARDS = {c['name']:c for c in json.loads((Path(__file__).parent/'fixtures/combat_keyword_triggers.json').read_text())}
CARDS.update(NAMED)


def add(state,name,player=1,zone=Zone.BATTLEFIELD):
    card = raw_add(state,name,player,zone,cards=CARDS)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state,card.id)
        card.summoning_sick = False
    return card


def attack(state,ids,player=1):
    state.active_player = state.priority_player = player
    state.step = Step.DECLARE_ATTACKERS
    declare_attackers(state,ids)


def settle(state):
    for _ in range(64):
        if not state.stack:
            return
        assert resolve_top_of_stack(state)
    raise AssertionError('Fixture stack did not settle')


def end_combat(state):
    state.step = Step.END_COMBAT
    RulesEngine()._apply_step_start_actions(state)


@pytest.mark.parametrize('player',[1,2])
@pytest.mark.parametrize('name',['Akrasan Squire','Rot-Curse Rakshasa'])
def test_http_keyword_attack_and_delayed_sacrifice_survive_sqlite_restart(game,player,name):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = match.state
    card = add(state,name,player)
    state.active_player = state.priority_player = player
    state.step = Step.DECLARE_ATTACKERS
    persist(match)
    path = f'/matches/{state.id}/action'

    def post(actor,action):
        response = client.post(path,json={'player_id':actor,'action':action})
        assert response.status_code == 200, response.text
        return response.json()

    def pass_stack():
        for _ in range(8):
            if not match.state.stack:
                return
            post(match.state.priority_player,{'type':'pass_priority'})
        raise AssertionError('HTTP priority passes did not resolve keyword trigger')

    post(player,{'type':'attack','attackers':[card.id]})
    assert len(match.state.stack) == 1
    assert match.state.cards[card.id].zone == Zone.BATTLEFIELD
    pass_stack()
    if name == 'Akrasan Squire':
        assert effective_power(match.state,card.id) == 2
    else:
        assert len(match.state.delayed_triggers) == 1
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session),state.id)
    match = main.ACTIVE_MATCHES[state.id]
    if name == 'Akrasan Squire':
        assert effective_power(match.state,card.id) == 2
        assert serialize_card_view(match.state,card.id)['keyword_counts']['exalted'] == 1
    else:
        assert len(match.state.delayed_triggers) == 1
        match.state.step = Step.COMBAT_DAMAGE
        match.state.combat_damage_resolved = True
        match.state.priority_player = player
        persist(match)
        post(player,{'type':'pass_priority'})
        post(3-player,{'type':'pass_priority'})
        assert match.state.step == Step.END_COMBAT
        assert len(match.state.stack) == 1
        assert match.state.cards[card.id].zone == Zone.BATTLEFIELD
        pass_stack()
        assert match.state.cards[card.id].zone == Zone.GRAVEYARD
        assert not match.state.delayed_triggers


@pytest.mark.parametrize('player',[1,2])
def test_exalted_is_one_non_targeted_trigger_per_instance_not_immediate_or_opponent(player):
    state = fixture()
    squire = add(state,'Akrasan Squire',player)
    add(state,'Akrasan Squire',3-player)
    attack(state,[squire.id],player)
    assert effective_power(state,squire.id) == 1
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'exalted_buff'
    assert not state.stack[0].targets and '__announced_targets' not in state.stack[0].payload
    settle(state)
    assert effective_power(state,squire.id) == 2
    RulesEngine()._clear_marked_damage(state)
    assert effective_power(state,squire.id) == 1


@pytest.mark.parametrize('counter_amount',[0,1,4])
def test_static_grants_and_keyword_counters_preserve_instances_but_not_per_counter(counter_amount):
    state = fixture()
    squire = add(state,'Akrasan Squire')
    angel = add(state,'Sublime Archangel')
    put_counters(state,'exalted',counter_amount,target_card_id=squire.id)
    count = 2 + bool(counter_amount)
    assert effective_keyword_counts(state,squire.id)['exalted'] == count
    assert effective_keywords(state,squire.id).count('exalted') == 1
    assert serialize_card_view(state,squire.id)['keyword_counts']['exalted'] == count
    attack(state,[squire.id])
    assert len(state.stack) == count+1  # Archangel's own Exalted also triggers.
    settle(state)
    assert effective_power(state,squire.id) == count+2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_keyword_counts(restored,squire.id)['exalted'] == count
    assert angel.zone == Zone.BATTLEFIELD


def test_noncreature_exalted_and_multiple_sources_stack_independently():
    state = fixture()
    bear = add(state,'Grizzly Bears')
    add(state,'Noble Hierarch')
    add(state,'Cathedral of War')
    add(state,'Sublime Archangel')
    add(state,'Sublime Archangel')
    # Bear: 2; Hierarch: 3; Cathedral: 1; Angels: 2 each.
    attack(state,[bear.id])
    assert len(state.stack) == 10
    settle(state)
    assert effective_power(state,bear.id) == 12


def test_two_declared_attackers_do_not_trigger_exalted_even_if_one_leaves():
    state = fixture()
    first = add(state,'Akrasan Squire')
    second = add(state,'Grizzly Bears')
    attack(state,[first.id,second.id])
    assert not state.stack
    resolve_effect(state,1,'sacrifice',{'target_card_id':second.id})
    assert effective_power(state,first.id) == 1


def test_exalted_trigger_survives_source_removal_and_does_not_buff_a_blinked_object():
    state = fixture()
    bear = add(state,'Grizzly Bears')
    source = add(state,'Akrasan Squire')
    attack(state,[bear.id])
    resolve_effect(state,1,'sacrifice',{'target_card_id':source.id})
    settle(state)
    assert effective_power(state,bear.id) == 3
    state2 = fixture()
    bear = add(state2,'Grizzly Bears')
    add(state2,'Akrasan Squire')
    attack(state2,[bear.id])
    old = state2.stack[0].payload['incarnation']
    bear.move_to_zone(Zone.HAND)
    bear.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state2,bear.id)
    assert bear.battlefield_incarnation != old
    settle(state2)
    assert effective_power(state2,bear.id) == 2


@pytest.mark.parametrize('kind',['exalted','decayed'])
def test_keyword_counts_follow_timestamped_removal_and_new_counter_restoration(kind):
    state = fixture()
    card = add(state,'Akrasan Squire' if kind == 'exalted' else 'Rot-Curse Rakshasa')
    put_counters(state,kind,2,target_card_id=card.id)
    assert effective_keyword_counts(state,card.id)[kind] == 2
    add(state,'Humility',2)
    assert effective_keyword_counts(state,card.id).get(kind,0) == 0
    put_counters(state,kind,1,target_card_id=card.id)
    assert effective_keyword_counts(state,card.id)[kind] == 1
    if kind == 'decayed':
        assert card_cant_block(state,card.id)


def test_decayed_reminder_text_does_not_survive_ability_removal_as_a_block_restriction():
    state = fixture()
    creature = add(state,'Rot-Curse Rakshasa')
    assert card_cant_block(state,creature.id)
    add(state,'Humility',2)
    assert not card_cant_block(state,creature.id)


@pytest.mark.parametrize('player',[1,2])
def test_decayed_counter_blocks_and_attacks_then_uses_two_distinct_counterable_triggers(player):
    state = fixture()
    bear = add(state,'Grizzly Bears',player)
    put_counters(state,'decayed',3,target_card_id=bear.id)
    assert card_cant_block(state,bear.id)
    attack(state,[bear.id],player)
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'decayed_attack'
    assert not state.delayed_triggers
    settle(state)
    assert bear.zone == Zone.BATTLEFIELD and len(state.delayed_triggers) == 1
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    saved['delayed_triggers'][0]['payload']['incarnation'] = -1
    assert restored.delayed_triggers == state.delayed_triggers
    end_combat(restored)
    assert not restored.delayed_triggers
    assert len(restored.stack) == 1 and restored.stack[0].effect_key == 'decayed_sacrifice'
    assert restored.cards[bear.id].zone == Zone.BATTLEFIELD
    settle(restored)
    assert restored.cards[bear.id].zone == Zone.GRAVEYARD
    end_combat(restored)
    assert not restored.stack


def test_printed_plus_counter_decayed_creates_two_delayed_abilities_but_one_sacrifice():
    state = fixture()
    card = add(state,'Rot-Curse Rakshasa')
    put_counters(state,'decayed',2,target_card_id=card.id)
    attack(state,[card.id])
    assert len(state.stack) == 2
    settle(state)
    assert len(state.delayed_triggers) == 2
    end_combat(state)
    assert len(state.stack) == 2
    settle(state)
    assert card.zone == Zone.GRAVEYARD
    assert sum('sacrifices' in line for line in state.log) <= 1


@pytest.mark.parametrize('when',['attack','delayed'])
def test_actual_stifle_counters_each_decayed_stage_without_a_later_sacrifice(when):
    state = fixture()
    card = add(state,'Rot-Curse Rakshasa')
    stifle = add(state,'Stifle',2,Zone.HAND)
    attack(state,[card.id])
    if when == 'delayed':
        settle(state)
        end_combat(state)
    target = state.stack[-1].id
    state.priority_player = 2
    state.players[2].mana_pool['U'] = 1
    state = checked_action(state,RulesEngine(),2,{'type':'cast_spell','card_id':stifle.id,'targets':{'target_stack_id':target}})
    settle(state)
    end_combat(state)
    settle(state)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert not state.delayed_triggers
    assert state.cards[stifle.id].zone == Zone.GRAVEYARD


def test_decayed_delayed_reference_does_not_follow_blink_or_sacrifice_opponent_controlled_object():
    for blink in (False,True):
        state = fixture()
        card = add(state,'Rot-Curse Rakshasa')
        attack(state,[card.id])
        settle(state)
        if blink:
            card.move_to_zone(Zone.HAND)
            card.move_to_zone(Zone.BATTLEFIELD)
            assign_static_order_on_battlefield_entry(state,card.id)
        else:
            resolve_effect(state,2,'change_control',{'target_card_id':card.id})
        end_combat(state)
        settle(state)
        assert card.zone == Zone.BATTLEFIELD


def test_temporary_instances_and_legacy_snapshot_default():
    state = fixture()
    bear = add(state,'Grizzly Bears')
    for _ in range(2):
        resolve_effect(state,1,'grant_keyword',{'target_card_id':bear.id,'keyword':'exalted','until_end_of_turn':True})
    assert effective_keyword_counts(state,bear.id)['exalted'] == 2
    attack(state,[bear.id])
    assert len(state.stack) == 2
    settle(state)
    RulesEngine()._clear_marked_damage(state)
    assert 'exalted' not in effective_keyword_counts(state,bear.id)
    old = serialize_match_snapshot(state)
    old.pop('delayed_triggers')
    assert deserialize_match_snapshot(old).delayed_triggers == []


def test_end_combat_step_queues_delayed_sacrifice_instead_of_sacrificing_immediately():
    state = fixture()
    card = add(state,'Rot-Curse Rakshasa')
    attack(state,[card.id])
    settle(state)
    state.step = Step.COMBAT_DAMAGE
    state.combat_damage_stage = 'regular'
    state.combat_damage_resolved = True
    RulesEngine().next_step(state)
    assert state.step == Step.END_COMBAT and state.stack
    assert card.zone == Zone.BATTLEFIELD
    settle(state)
    assert card.zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player',[1,2])
def test_master_uses_actual_exalted_triggers_to_choose_one_unblocked_attacker(player):
    from ai.agent import AIAgent
    state = fixture()
    state.turn = 3
    squire = add(state,'Akrasan Squire',player)
    hierarch = add(state,'Noble Hierarch',player)
    state.active_player = state.priority_player = player
    state.step = Step.DECLARE_ATTACKERS
    before = serialize_match_snapshot(state)
    result = AIAgent('master')._choose_attackers(state,[squire.id,hierarch.id],player)
    assert result == [squire.id]
    assert serialize_match_snapshot(state) == before


def test_combat_projection_finishes_decayed_sacrifice_before_scoring_board():
    from ai.agent import AIAgent
    from ai.pending_effects import planning_copy
    state = fixture()
    card = add(state,'Rot-Curse Rakshasa')
    state.step = Step.DECLARE_ATTACKERS
    projected = planning_copy(state)
    RulesEngine().take_action(projected,1,{'type':'attack','attackers':[card.id]})
    assert AIAgent('master')._finish_combat_projection(projected,state)
    assert projected.cards[card.id].zone == Zone.GRAVEYARD
    assert state.cards[card.id].zone == Zone.BATTLEFIELD


def test_combat_projection_does_not_rank_unknown_choice_or_newly_drawn_hidden_cards():
    from ai.agent import AIAgent
    from ai.pending_effects import planning_copy
    state = fixture()
    for pending in (False,True):
        projected = planning_copy(state)
        projected.step = Step.END_COMBAT
        if pending:
            projected.pending_mechanic_choice = {'kind':'scry','player_id':1,'options':[],'count':0}
        else:
            cid = projected.players[1].library.pop()
            projected.players[1].hand.append(cid)
            projected.cards[cid].move_to_zone(Zone.HAND)
        assert not AIAgent('master')._finish_combat_projection(projected,state)
