"""Damage events using canonical cards and explicit core-operation fixtures."""
import pytest

from effects.handlers import deal_damage, deal_damage_batch, grant_keyword
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.combat import _combat_damage_step, _resolve_damage_step
from rules_engine.damage_results import (apply_creature_damage, apply_player_damage,
                                        collect_damage_counters, flush_damage_counters)
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_counter_prohibitions import source as damage_source
from tests.test_counter_replacements import source, choose
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


@pytest.mark.parametrize('player', [1, 2])
def test_infect_placer_is_source_controller_not_recipient_or_active_player(player):
    state = clean()
    source(state, 'Vorinclex, Monstrous Raider', player)
    elf = damage_source(state, 'Glistener Elf', player)
    apply_player_damage(state, 3-player, 3, elf.id)
    assert state.players[3-player].poison == 6
    assert state.players[3-player].life == 20


def test_last_known_controller_remains_counter_placer():
    state = clean()
    source(state, 'Vorinclex, Monstrous Raider', 2)
    apply_player_damage(state, 1, 3, None, source_lki={'controller': 2, 'keywords': ['infect']})
    assert state.players[1].poison == 6


def test_combat_infect_is_not_an_effect_for_doubling_season():
    state = clean()
    source(state, 'Doubling Season', 2)
    bear = add(state, 'Grizzly Bears', 2)
    elf = damage_source(state, 'Glistener Elf')
    apply_creature_damage(state, bear.id, 1, elf.id)
    assert bear.counters['-1/-1'] == 1


def test_spell_infect_counters_are_effect_results():
    state = clean()
    source(state, 'Doubling Season', 2)
    bear = add(state, 'Grizzly Bears', 2)
    elf = damage_source(state, 'Glistener Elf')
    apply_creature_damage(state, bear.id, 1, elf.id, counter_is_effect=True)
    assert bear.counters['-1/-1'] == 2


def test_another_replacement_enables_effect_only_doubler():
    state = clean()
    source(state, 'Doubling Season', 2)
    source(state, 'Winding Constrictor', 2)
    bear = add(state, 'Grizzly Bears', 2)
    elf = damage_source(state, 'Glistener Elf')
    apply_creature_damage(state, bear.id, 1, elf.id)
    assert bear.counters['-1/-1'] == 4


def test_simultaneous_toxic_is_one_poison_placement():
    state = clean()
    source(state, 'Winding Constrictor', 2)
    rats = [damage_source(state, 'Blightbelly Rat') for _ in range(2)]
    state.attackers = [rat.id for rat in rats]
    _combat_damage_step(state, 2, set(), False)
    assert state.players[2].poison == 3
    assert state.players[2].life == 16


def test_infect_and_toxic_results_share_one_placement():
    state = clean()
    source(state, 'Winding Constrictor', 2)
    rat = damage_source(state, 'Blightbelly Rat')
    grant_keyword(state, 1, {'target_card_id': rat.id, 'keyword': 'infect'})
    apply_player_damage(state, 2, 2, rat.id, combat=True)
    assert state.players[2].poison == 4
    assert state.players[2].life == 20


def test_simultaneous_infect_is_one_placement():
    state = clean()
    source(state, 'Winding Constrictor', 2)
    elves = [damage_source(state, 'Glistener Elf') for _ in range(2)]
    state.attackers = [elf.id for elf in elves]
    _combat_damage_step(state, 2, set(), False)
    assert state.players[2].poison == 3


def test_collector_is_match_scoped_and_exception_safe():
    state, other = clean(), clean()
    elf = damage_source(state, 'Glistener Elf')
    other_elf = damage_source(other, 'Glistener Elf')
    with pytest.raises(RuntimeError):
        with collect_damage_counters(state):
            apply_player_damage(other, 2, 1, other_elf.id)
            raise RuntimeError('fixture')
    apply_player_damage(state, 2, 1, elf.id)
    assert state.players[2].poison == other.players[2].poison == 1


def test_queue_preserves_recipients_and_survives_snapshot():
    state = clean()
    source(state, 'Winding Constrictor', 2)
    source(state, 'Vorinclex, Monstrous Raider', 1)
    elf = damage_source(state, 'Glistener Elf')
    with collect_damage_counters(state) as packets:
        apply_player_damage(state, 2, 1, elf.id)
        apply_player_damage(state, 1, 2, elf.id)
    flush_damage_counters(state, packets)
    assert state.pending_replacement_choice['player_id'] == 2
    assert state.players[1].poison == state.players[2].poison == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add')
    assert state.players[2].poison == 4
    assert state.players[1].poison == 4
    assert state.pending_replacement_choice is None


def test_combat_choice_defers_lifelink_and_state_based_actions():
    state = clean()
    source(state, 'Winding Constrictor', 2)
    source(state, 'Vorinclex, Monstrous Raider', 1)
    elf = damage_source(state, 'Glistener Elf')
    grant_keyword(state, 1, {'target_card_id': elf.id, 'keyword': 'lifelink'})
    state.attackers = [elf.id]
    state.players[2].poison = 7
    _resolve_damage_step(state)
    assert state.pending_replacement_choice['combat_damage_needs_sba']
    assert state.players[1].life == 20 and state.winner is None
    apply_state_based_actions(state)
    assert state.winner is None
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add')
    assert state.players[2].poison == 11
    assert state.players[1].life == 21 and state.winner == 1


def test_soul_scar_result_applies_recipient_modifier():
    state = clean()
    damage_source(state, 'Soul-Scar Mage')
    bear = source(state, 'Winding Constrictor', 2)
    bolt = add(state, 'Lightning Bolt', 1, Zone.HAND)
    deal_damage(state, 1, {'target_card_id': bear.id, 'amount': 1, '__source_card_id': bolt.id})
    assert bear.counters['-1/-1'] == 2


def test_counter_ban_wins_before_modifier_choices():
    state = clean()
    damage_source(state, 'Solemnity')
    source(state, 'Winding Constrictor', 2)
    source(state, 'Vorinclex, Monstrous Raider')
    elf = damage_source(state, 'Glistener Elf')
    apply_player_damage(state, 2, 3, elf.id)
    assert state.players[2].poison == 0 and state.pending_replacement_choice is None


def test_damage_batch_retains_lifelink_credit_across_multiple_pauses():
    state = clean()
    target = source(state, 'Winding Constrictor', 2)
    source(state, 'Vorinclex, Monstrous Raider')
    elf = damage_source(state, 'Glistener Elf')
    grant_keyword(state, 1, {'target_card_id': elf.id, 'keyword': 'lifelink'})
    deal_damage_batch(state, 1, {'__source_card_id': elf.id, 'recipients': [
        {'target_player': 2, 'amount': 1}, {'target_card_id': target.id, 'amount': 1}]})
    assert state.players[1].life == 20
    state = choose(state, 'double')
    assert state.players[2].poison == 3 and state.pending_replacement_choice
    assert state.cards[target.id].zone == Zone.BATTLEFIELD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double')
    assert state.players[1].life == 22
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert not state.pending_replacement_choice


def test_effect_provenance_survives_competing_order_and_restart():
    state = clean()
    source(state, 'Doubling Season', 2)
    target = source(state, 'Winding Constrictor', 2)
    source(state, 'Vorinclex, Monstrous Raider', 1)
    elf = damage_source(state, 'Glistener Elf')
    apply_creature_damage(state, target.id, 1, elf.id)
    assert {o['name'] for o in state.pending_replacement_choice['options']} == {
        'Winding Constrictor', 'Vorinclex, Monstrous Raider'}
    state = choose(state, 'add')
    assert state.pending_replacement_choice['counter_payload']['__counter_is_effect']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double')
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert any('8' in line and 'counters' in line for line in state.log)
