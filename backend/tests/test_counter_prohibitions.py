"""Canonical counter bans; modified Oracle cases are negative parser fixtures only."""
import json
from pathlib import Path

import pytest

from effects.handlers import (add_counters, add_player_counters, deal_damage,
                             grant_keyword, incubate, return_permanent_to_hand)
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.counter_placement import put_counters
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.move_generator import legal_moves
from rules_engine.damage_results import apply_creature_damage, apply_player_damage
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from tests.test_ai_recurring_engines import add as add_card
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/counter_prohibitions.json').read_text())}
for row in ROWS.values():
    for field in ('power', 'toughness', 'colors', 'keywords'):
        row.setdefault(field, None)
    for field in ('power', 'toughness'):
        if row[field] is not None and not str(row[field]).lstrip('-').isdigit():
            row[field] = None


def source(state, name, player=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, player, zone=zone, cards=ROWS)
    card.loyalty = int(ROWS[name]['loyalty']) if ROWS[name].get('loyalty') is not None else None
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('recipient', [1, 2])
@pytest.mark.parametrize('kind', ['poison', 'energy', 'experience'])
def test_solemnity_blocks_all_players_and_does_not_remove_existing_counters(recipient, kind):
    state = clean()
    add_player_counters(state, recipient, {'counter': kind, 'amount': 2})
    source(state, 'Solemnity', 3-recipient)
    before = serialize_match_snapshot(state)['players']
    add_player_counters(state, 3-recipient, {'target_player': recipient, 'counter': kind, 'amount': 4})
    assert serialize_match_snapshot(state)['players'] == before
    assert not state.stack
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert put_counters(state, kind, 1, target_player=recipient) == 0


@pytest.mark.parametrize('name', ['Grizzly Bears', 'Sol Ring', 'Forest'])
@pytest.mark.parametrize('kind', ['+1/+1', '-1/-1', 'shield'])
def test_solemnity_blocks_permanent_types_for_both_controllers(name, kind):
    state = clean()
    source(state, 'Solemnity', 2)
    for player in (1, 2):
        card = add(state, name, player)
        add_counters(state, player, {'target_card_id': card.id, 'counter': kind, 'amount': 3})
        assert card.counters.get(kind, 0) == 0


def test_saga_lore_is_a_physical_counter_not_an_internal_marker():
    state = clean()
    saga = source(state, 'The First Iroan Games')
    lock = source(state, 'Solemnity')
    RulesEngine()._advance_sagas(state)
    assert saga.counters.get('__lore', 0) == 0 and not state.stack
    return_permanent_to_hand(state, 1, {'target_card_id': lock.id})
    RulesEngine()._advance_sagas(state)
    assert saga.counters['__lore'] == 1 and len(state.stack) == 1


def test_solemnity_does_not_ban_planeswalker_loyalty():
    state = clean()
    source(state, 'Solemnity')
    walker = source(state, "Elspeth, Sun's Champion")
    starting = walker.loyalty
    add_counters(state, 1, {'target_card_id': walker.id, 'counter': 'loyalty', 'amount': 2})
    assert walker.loyalty == starting+2 and 'loyalty' not in walker.counters


@pytest.mark.parametrize('recipient', [1, 2])
def test_melira_is_controller_scoped_and_poison_specific(recipient):
    state = clean()
    source(state, 'Melira, Sylvok Outcast', recipient)
    for player in (1, 2):
        for kind in ('poison', 'experience'):
            add_player_counters(state, 3-player, {'target_player': player, 'counter': kind, 'amount': 2})
        bear = add(state, 'Grizzly Bears', player)
        for kind in ('+1/+1', '-1/-1'):
            add_counters(state, 3-player, {'target_card_id': bear.id, 'counter': kind})
        assert state.players[player].poison == (0 if player == recipient else 2)
        assert state.players[player].counters['experience'] == 2
        assert bear.counters['+1/+1'] == 1
        assert bear.counters.get('-1/-1', 0) == (0 if player == recipient else 1)


def test_tatterkite_blocks_only_itself_and_does_not_block_marked_damage():
    state = clean()
    kite = source(state, 'Tatterkite')
    bear = add(state, 'Grizzly Bears')
    add_counters(state, 2, {'target_card_id': kite.id})
    add_counters(state, 2, {'target_card_id': bear.id})
    assert '+1/+1' not in kite.counters and bear.counters['+1/+1'] == 1
    apply_creature_damage(state, kite.id, 1, None)
    assert kite.counters['__damage_marked'] == 1


def test_infect_ban_does_not_convert_damage_to_life_loss_or_stop_lifelink():
    state = clean()
    source(state, 'Solemnity')
    elf = source(state, 'Glistener Elf')
    grant_keyword(state, 1, {'target_card_id': elf.id, 'keyword': 'lifelink', 'until_end_of_turn': True})
    life = state.players[1].life
    dealt = deal_damage(state, 1, {'target_player': 2, 'amount': 3, '__source_card_id': elf.id})
    assert dealt == 3 and state.players[2].poison == 0 and state.players[2].life == 20
    assert state.players[1].life == life+3
    bear = add(state, 'Grizzly Bears', 2)
    apply_creature_damage(state, bear.id, 3, elf.id)
    assert '-1/-1' not in bear.counters and '__damage_marked' not in bear.counters


def test_toxic_still_causes_life_loss_when_poison_is_banned():
    state = clean()
    source(state, 'Solemnity')
    rat = source(state, 'Blightbelly Rat')
    apply_player_damage(state, 2, 2, rat.id, combat=True)
    assert state.players[2].life == 18 and state.players[2].poison == 0


def test_soul_scar_replacement_still_replaces_damage_if_counters_are_banned():
    state = clean()
    source(state, 'Soul-Scar Mage')
    source(state, 'Solemnity')
    bolt = add(state, 'Lightning Bolt', zone=Zone.HAND)
    bear = add(state, 'Grizzly Bears', 2)
    assert deal_damage(state, 1, {'target_card_id': bear.id, 'amount': 3, '__source_card_id': bolt.id}) == 0
    assert '-1/-1' not in bear.counters and '__damage_marked' not in bear.counters


def test_incubator_entry_counters_are_blocked_but_creation_still_happens():
    state = clean()
    source(state, 'Solemnity')
    incubate(state, 1, {'counters': 4, 'times': 2})
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2 and all(not card.counters for card in tokens)


def test_ballista_spell_entry_counters_are_blocked():
    state = clean()
    source(state, 'Solemnity')
    card = source(state, 'Walking Ballista', zone=Zone.HAND)
    state.players[1].hand.remove(card.id)
    card.zone = Zone.STACK
    add_to_stack(state, card.id, 1, card.name, 'noop', {'x_value': 3})
    resolve_top_of_stack(state)
    assert card.counters.get('+1/+1', 0) == 0


@pytest.mark.parametrize('prefix', ['Whenever a creature dies, ', '{1}: ', 'As long as you control an artifact, ', 'If you cast a spell, '])
def test_unresolved_or_conditional_text_is_not_a_global_prohibition(prefix):
    state = clean()
    lock = source(state, 'Solemnity')
    # Deliberately malformed/unsupported Oracle parser input, never a playable card.
    lock.oracle_text = prefix + "Players can't get counters."
    assert put_counters(state, 'experience', 1, target_player=1) == 1


def test_failed_counter_placement_does_not_cancel_land_animation():
    state = clean()
    source(state, 'Solemnity')
    land = add(state, 'Forest')
    add_counters(state, 1, {'target_card_id': land.id, 'amount': 3, 'animate_land': True})
    assert 'Creature' in land.types and land.power == 0 and '+1/+1' not in land.counters


def test_existing_counters_survive_ban_and_placement_recovers_after_source_leaves():
    state = clean()
    bear = add(state, 'Grizzly Bears')
    put_counters(state, '+1/+1', 2, target_card_id=bear.id)
    lock = source(state, 'Solemnity')
    assert put_counters(state, '+1/+1', 3, target_card_id=bear.id) == 0
    assert bear.counters['+1/+1'] == 2
    return_permanent_to_hand(state, 1, {'target_card_id': lock.id})
    assert put_counters(state, '+1/+1', 1, target_card_id=bear.id) == 1
    assert bear.counters['+1/+1'] == 3


def test_zero_negative_or_internal_placements_do_not_create_physical_counters():
    state = clean()
    bear = add(state, 'Grizzly Bears')
    for kind, amount in [('+1/+1', 0), ('+1/+1', -1), ('__damage_marked', 3)]:
        assert put_counters(state, kind, amount, target_card_id=bear.id) == 0
    assert not bear.counters


def test_loyalty_and_lore_on_ordinary_creatures_use_normal_zone_counters():
    state = clean()
    bear = add(state, 'Grizzly Bears')
    for kind in ('loyalty', 'lore'):
        put_counters(state, kind, 2, target_card_id=bear.id)
    assert bear.counters == {'loyalty': 2, 'lore': 2} and bear.loyalty is None
    return_permanent_to_hand(state, 1, {'target_card_id': bear.id})
    assert not bear.counters and bear.loyalty is None


def test_multitype_permanent_is_blocked_even_if_it_is_also_a_planeswalker():
    state = clean()
    source(state, 'Solemnity')
    walker = source(state, "Elspeth, Sun's Champion")
    # Current characteristics after a creature-animation effect, not printed data.
    walker.types.append('Creature')
    before = walker.loyalty
    add_counters(state, 1, {'target_card_id': walker.id, 'counter': 'loyalty'})
    assert walker.loyalty == before


@pytest.mark.parametrize('player', [1, 2])
def test_animated_walker_cannot_pay_positive_loyalty_but_can_remove_it(player):
    state = clean(player)
    source(state, 'Solemnity', 3-player)
    walker = source(state, "Elspeth, Sun's Champion", player)
    # Current types after an animation effect; printed Oracle remains unchanged.
    walker.types.append('Creature')
    moves = [move for move in legal_moves(state, player) if move['type'] == 'activate_loyalty']
    assert not any(move['ability_index'] == 0 for move in moves)
    assert any(move['ability_index'] == 1 for move in moves)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), player,
                       {'type': 'activate_loyalty', 'card_id': walker.id, 'ability_index': 0})
    assert serialize_match_snapshot(state) == before
    updated = checked_action(state, RulesEngine(), player,
                             {'type': 'activate_loyalty', 'card_id': walker.id, 'ability_index': 1})
    assert updated.cards[walker.id].loyalty == walker.loyalty-3


def test_withering_damage_uses_same_ban_without_becoming_marked_damage():
    state = clean()
    source(state, 'Solemnity')
    bear = add(state, 'Grizzly Bears')
    attacker = add(state, 'Grizzly Bears', 2)
    grant_keyword(state, 2, {'target_card_id': attacker.id, 'keyword': 'wither', 'until_end_of_turn': True})
    apply_creature_damage(state, bear.id, 2, attacker.id)
    assert '-1/-1' not in bear.counters and '__damage_marked' not in bear.counters


@pytest.mark.parametrize('name', ['Solemnity', 'Melira, Sylvok Outcast', 'Tatterkite'])
def test_supported_counter_bans_do_not_report_unknown_prohibition(name):
    assert 'unsupported counter prohibition' not in known_unsupported_mechanics(ROWS[name]['oracle_text'])


@pytest.mark.parametrize('oracle', [
    "As long as you control an artifact, players can't get counters.",
    "{1}: Players can't get counters until end of turn.",
    "Counters can't be put on creatures your opponents control.",
    "You can't get additional poison counters this turn.",
])
def test_unimplemented_counter_bans_are_explicitly_diagnosed(oracle):
    assert 'unsupported counter prohibition' in known_unsupported_mechanics(oracle)
