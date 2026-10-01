"""Canonical experience clauses and shared counters, not whole-card certification."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.pending_effects import planning_copy
from effects.handlers import add_player_counters, destroy_permanent, exile_permanent, return_permanent_to_hand
from game_state.state import Zone, Step, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power, effective_toughness, continuous_layer_trace
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event, emit_event_batch
from rules_engine.player_counters import counter_count, public_counters
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.ward import parse_ward_cost
from tests.test_ai_recurring_engines import add as add_card
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add, resolve, choose


ROWS = {r['name']: dict(r) for r in json.loads((Path(__file__).parent / 'fixtures/player_counters.json').read_text())}
for row in ROWS.values():
    for field in ('power', 'toughness', 'keywords', 'colors'):
        row.setdefault(field, None)
    for field in ('power', 'toughness'):
        if row[field] is not None and not str(row[field]).lstrip('-').isdigit():
            row[field] = None


def source(state, name, player=1):
    card = add_card(state, name, player, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('player', [1, 2])
def test_player_counters_persist_separately_from_source_and_poison(player):
    state = clean()
    card = source(state, 'Minthara, Merciless Soul', player)
    add_player_counters(state, player, {'counter': 'experience', 'amount': 3})
    add_player_counters(state, player, {'counter': 'energy', 'amount': 2})
    add_player_counters(state, player, {'counter': 'poison', 'amount': 4})
    assert counter_count(state.players[player], 'poison') == state.players[player].poison == 4
    assert 'poison' not in state.players[player].counters
    destroy_permanent(state, 3-player, {'target_card_id': card.id})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert public_counters(restored.players[player]) == {'energy': 2, 'experience': 3, 'poison': 4}
    assert serialize_match(restored)['players'][player]['counters'] == public_counters(restored.players[player])
    clone = planning_copy(state)
    clone.players[player].counters['experience'] = 8
    assert state.players[player].counters['experience'] == 3


def test_old_snapshot_defaults_new_fields_without_changing_poison():
    state = clean()
    state.players[1].poison = 7
    raw = serialize_match_snapshot(state)
    raw.pop('players_with_permanent_departure')
    for player in raw['players'].values():
        player.pop('counters')
    restored = deserialize_match_snapshot(raw)
    assert restored.players[1].counters == {} and restored.players[1].poison == 7
    assert not restored.players_with_permanent_departure


def test_shared_poison_counter_effect_reaches_the_existing_loss_rule():
    from rules_engine.state_based_actions import apply_state_based_actions
    state = clean()
    state.players[1].poison = 9
    add_player_counters(state, 2, {'target_player': 1, 'counter': 'poison', 'amount': 1})
    apply_state_based_actions(state)
    assert state.winner == 2
    assert public_counters(state.players[1]) == {'poison': 10}


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('handler', [destroy_permanent, exile_permanent, return_permanent_to_hand])
def test_end_step_departure_is_controller_scoped_and_counter_waits_for_stack(player, handler):
    state = clean()
    state.active_player = player
    source(state, 'Minthara, Merciless Soul', player)
    bear = add(state, 'Grizzly Bears', player)
    handler(state, 3-player, {'target_card_id': bear.id})
    assert player in state.players_with_permanent_departure
    assert state.players[player].counters == {}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 3-player})
    assert not state.stack
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': player})
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'add_player_counters'
    resolve(state)
    assert state.players[player].counters == {'experience': 1}


def test_departure_precedes_source_entry_and_resets_at_next_turn():
    state = clean()
    bear = add(state, 'Grizzly Bears', 1)
    destroy_permanent(state, 2, {'target_card_id': bear.id})
    card = source(state, 'Minthara, Merciless Soul', 1)
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 1})
    resolve(state)
    assert state.players[1].counters == {'experience': 1}
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert not state.players_with_permanent_departure
    assert state.players[1].counters == {'experience': 1}
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 1})
    assert not state.stack and effective_power(state, card.id) == card.power + 1


def test_opponent_departure_and_post_end_step_departure_do_not_trigger():
    state = clean()
    source(state, 'Minthara, Merciless Soul', 1)
    bear = add(state, 'Grizzly Bears', 2)
    destroy_permanent(state, 1, {'target_card_id': bear.id})
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 1})
    assert not state.stack
    own = add(state, 'Grizzly Bears', 1)
    destroy_permanent(state, 2, {'target_card_id': own.id})
    assert not state.stack


@pytest.mark.parametrize('player', [1, 2])
def test_mana_ward_x_uses_trigger_controller_and_resolution_time_count(player):
    state = clean(player)
    card = source(state, 'Minthara, Merciless Soul', 3-player)
    bolt = add(state, 'Lightning Bolt', player, Zone.HAND)
    state.players[player].mana_pool.update(R=1, C=4)
    add_player_counters(state, 3-player, {'counter': 'experience', 'amount': 1})
    state = checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': bolt.id,
                           'targets': {'target_card_id': card.id}})
    assert len(state.stack) == 2
    add_player_counters(state, 3-player, {'counter': 'experience', 'amount': 3})
    # Source control may change; "you" remains the triggered ability's controller.
    card = state.cards[card.id]
    state.players[3-player].battlefield.remove(card.id)
    state.players[player].battlefield.append(card.id)
    card.controller = player
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve(state)
    assert state.pending_mechanic_choice['ward_cost'] == {'kind': 'mana', 'cost': '{4}'}
    assert state.pending_mechanic_choice['option_labels']['pay'].startswith('Pay ward: {4}')
    state = choose(state, ['pay'], player)
    assert state.players[player].mana_pool['C'] == 0


def test_zero_counter_ward_is_a_real_pay_or_decline_choice_and_source_may_leave():
    state = clean()
    card = source(state, 'Minthara, Merciless Soul', 2)
    bolt = add(state, 'Lightning Bolt', 1, Zone.HAND)
    state.players[1].mana_pool.update(R=1)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': bolt.id,
                          'targets': {'target_card_id': card.id}})
    destroy_permanent(state, 1, {'target_card_id': card.id})
    resolve(state)
    assert state.pending_mechanic_choice['ward_cost'] == {'kind': 'mana', 'cost': '{0}'}
    assert state.pending_mechanic_choice['options'] == ['decline', 'pay']
    state = choose(state, ['pay'])
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('name', ['Kalemne, Disciple of Iroas', 'Kelsien, the Plague'])
@pytest.mark.parametrize('player', [1, 2])
def test_named_self_scaling_uses_current_controller_and_preserves_printed_stats(name, player):
    state = clean()
    card = source(state, name, player)
    base = card.power, card.toughness
    assert (effective_power(state, card.id), effective_toughness(state, card.id)) == base
    state.players[player].counters['experience'] = 3
    assert (effective_power(state, card.id), effective_toughness(state, card.id)) == (base[0]+3, base[1]+3)
    assert (card.power, card.toughness) == base
    assert any(entry['layer'] == 'pt-mod:3/3' for entry in continuous_layer_trace(state, card.id)['applied_layers'])


def test_global_player_counter_anthem_is_not_an_unconditional_flat_bonus():
    state = clean()
    card = source(state, 'Minthara, Merciless Soul', 1)
    bear = add(state, 'Grizzly Bears', 1)
    opposing = add(state, 'Grizzly Bears', 2)
    assert effective_power(state, bear.id) == 2
    state.players[1].counters['experience'] = 4
    assert effective_power(state, bear.id) == 6 and effective_toughness(state, bear.id) == 2
    assert effective_power(state, opposing.id) == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_power(restored, bear.id) == 6
    destroy_permanent(restored, 2, {'target_card_id': card.id})
    assert effective_power(restored, bear.id) == 2 and restored.players[1].counters['experience'] == 4


def test_characteristic_defined_token_stats_track_player_not_token_counters():
    state = clean()
    card = source(state, 'Spirit', 1)
    state.players[1].counters['experience'] = 5
    card.counters['+1/+1'] = 2
    assert (effective_power(state, card.id), effective_toughness(state, card.id)) == (7, 7)
    assert serialize_match(state)['players'][1]['battlefield'][0]['power'] == 7


@pytest.mark.parametrize('name,event,card_name,payload', [
    ('Daxos the Returned', 'spell_cast', 'Leather Armor', {}),
    ('Kalemne, Disciple of Iroas', 'spell_cast', 'Tolarian Terror', {}),
    ('Ezuri, Claw of Progress', 'enters_battlefield', 'Grizzly Bears', {}),
    ('Toph, Earthbending Master', 'enters_battlefield', 'Forest', {}),
    ('Katara, Waterbending Master', 'spell_cast', 'Lightning Bolt', {'opponent_turn': True}),
    ('Zuko, Firebending Master', 'spell_cast', 'Lightning Bolt', {'combat': True}),
])
@pytest.mark.parametrize('player', [1, 2])
def test_shared_gain_trigger_conditions(name, event, card_name, payload, player):
    state = clean(player)
    source(state, name, player)
    card = add(state, card_name, player)
    if name == 'Daxos the Returned':
        # Negative: an artifact is not the enchantment specified by Oracle.
        emit_event(state, event, {'source_card_id': card.id, 'controller': player})
        assert not state.stack
        card = source(state, 'Bastion of Remembrance', player)
    if payload.get('opponent_turn'):
        state.active_player = 3-player
    if payload.get('combat'):
        state.step = Step.BEGIN_COMBAT
    emit_event(state, event, {'source_card_id': card.id, 'card_id': card.id, 'controller': player})
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'add_player_counters'
    resolve(state)
    assert state.players[player].counters == {'experience': 1}


def test_another_death_counter_trigger_survives_simultaneous_source_death():
    state = clean()
    meren = source(state, 'Meren of Clan Nel Toth', 1)
    bear = add(state, 'Grizzly Bears', 1)
    from effects.handlers import destroy_all_creatures
    destroy_all_creatures(state, 2, {})
    assert meren.zone == bear.zone == Zone.GRAVEYARD
    assert len(state.stack) == 1 and state.stack[0].effect_key == 'add_player_counters'
    resolve(state)
    assert state.players[1].counters == {'experience': 1}


def test_unknown_player_counter_replacements_still_warn():
    for name in ['Vorinclex, Monstrous Raider', 'Winding Constrictor']:
        assert 'player-counter replacement fidelity' in known_unsupported_mechanics(ROWS[name]['oracle_text'])
    assert parse_ward_cost('{X}') is None
    assert 'unsupported ward cost' in known_unsupported_mechanics('Ward {X}')


@pytest.mark.parametrize('name', ['Meren of Clan Nel Toth', 'Daxos the Returned',
    'Ezuri, Claw of Progress', 'Katara, Waterbending Master', 'Zuko, Firebending Master', 'Toph, Earthbending Master'])
def test_partial_counter_cards_keep_explicit_dependent_clause_warning(name):
    assert 'unsupported player-counter dependent clause' in known_unsupported_mechanics(ROWS[name]['oracle_text'])


def test_supported_counter_clauses_do_not_warn_as_unsupported():
    for name in ['Minthara, Merciless Soul', 'Kalemne, Disciple of Iroas', 'Spirit']:
        assert not known_unsupported_mechanics(ROWS[name]['oracle_text'])


def test_corrupted_dynamic_cost_suffix_is_not_accepted_as_supported():
    # Parser-only malformed input, not a fictional or canonical card fixture.
    line = ROWS['Minthara, Merciless Soul']['oracle_text'].splitlines()[0].rstrip('.')
    assert 'unsupported ward cost' in known_unsupported_mechanics(line + ' UNPARSED-SUFFIX.')


def test_corrupted_scaling_clause_does_not_apply_a_flat_prefix_bonus():
    # Deliberately corrupt input to verify the unsupported-clause boundary.
    state = clean()
    card = source(state, 'Minthara, Merciless Soul', 1)
    lines = card.oracle_text.splitlines()
    lines[-1] = lines[-1].rstrip('.') + ' UNPARSED-SUFFIX.'
    card.oracle_text = '\n'.join(lines)
    assert 'unsupported player-counter dependent clause' in known_unsupported_mechanics(card.oracle_text)
    assert effective_power(state, card.id) == card.power


@pytest.mark.parametrize('name', ['Kalemne, Disciple of Iroas', 'Ezuri, Claw of Progress',
    'Katara, Waterbending Master', 'Zuko, Firebending Master'])
def test_counter_gain_thresholds_and_timing_are_not_ignored(name):
    state = clean()
    source(state, name, 1)
    card = add(state, 'Tolarian Terror' if name.startswith('Ezuri') else 'Grizzly Bears', 1)
    emit_event(state, 'enters_battlefield' if name.startswith('Ezuri') else 'spell_cast',
               {'source_card_id': card.id, 'card_id': card.id, 'controller': 1})
    assert not state.stack and not state.players[1].counters


@pytest.mark.parametrize('archetype', ['Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain', 'Tokens', 'Tribal', 'Reanimator'])
def test_ai_handles_resolved_counter_ward_without_mutating_live_state(archetype):
    state = clean()
    card = source(state, 'Minthara, Merciless Soul', 2)
    state.players[2].counters['experience'] = 3
    removal = add_card(state, 'Terminate', 1, Zone.HAND, cards=ROWS)
    state.players[1].mana_pool.update(B=1, R=1, C=3)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': removal.id,
                          'targets': {'target_card_id': card.id}})
    resolve(state)
    before = serialize_match_snapshot(state)
    move = AIAgent('master', archetype).choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert move == {'type': 'choose_mechanic', 'card_ids': ['pay']}
    assert serialize_match_snapshot(state) == before
    state = choose(state, ['pay'])
    resolve(state)
    assert state.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,spell,kind', [
    ('Minthara, Merciless Soul', 'Minthara, Merciless Soul', 'self'),
    ('Daxos the Returned', 'Bastion of Remembrance', 'cast'),
    ('Kalemne, Disciple of Iroas', 'Tolarian Terror', 'cast'),
    ('Ezuri, Claw of Progress', 'Grizzly Bears', 'entry'),
    ('Toph, Earthbending Master', 'Forest', 'land'),
])
def test_normal_cast_and_land_paths_reach_supported_counter_clauses(player, name, spell, kind):
    state = clean(player)
    if kind != 'self':
        source(state, name, player)
    card = (add_card(state, spell, player, Zone.HAND, cards=ROWS)
            if spell in ROWS else add(state, spell, player, Zone.HAND))
    state.players[player].mana_pool.update(W=1, B=1, G=1, U=1, C=10)
    action = {'type': 'play_land' if kind == 'land' else 'cast_spell', 'card_id': card.id}
    # Oracle X inside ward is not an X the player chooses when casting Minthara.
    state = checked_action(state, RulesEngine(), player, action)
    assert not state.players[player].counters
    if kind == 'self':
        assert len(state.stack) == 1
        resolve(state)
        assert state.cards[card.id].zone == Zone.BATTLEFIELD and not state.players[player].counters
        bear = add(state, 'Grizzly Bears', player)
        destroy_permanent(state, 3-player, {'target_card_id': bear.id})
        state.step = Step.POSTCOMBAT_MAIN
        RulesEngine().next_step(state)
        assert state.step == Step.END_STEP
    elif kind == 'entry':
        resolve(state)
        assert state.cards[card.id].zone == Zone.BATTLEFIELD and not state.players[player].counters
    assert state.stack[-1].effect_key == 'add_player_counters'
    resolve(state)
    assert state.players[player].counters == {'experience': 1}
