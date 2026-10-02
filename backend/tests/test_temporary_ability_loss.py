"""Canonical temporary loss/base stats and split-second integration fixtures."""
import json
from pathlib import Path
from copy import deepcopy

import pytest

from ai.pending_effects import keyword_target_value
from effects.registry import resolve_effect
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.continuous import effective_power, effective_toughness, has_keyword, printed_abilities_suppressed, continuous_layer_trace
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.mana import nonland_mana_outputs
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.restrictions import split_second_active
from rules_engine.stack_engine import add_to_stack
from tests.test_ability_suppression import CARDS as PRINTED, add as add_printed
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve
from tests.test_api_input_contracts import game, persist, rejected

CARDS = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/temporary_ability_loss.json').read_text())}


def add(state, name, player=1, zone=Zone.HAND):
    card = raw_add(state, name, player, zone, cards=CARDS)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card


def cast(state, card, targets):
    player = card.controller
    state.active_player = state.priority_player = player
    state.players[player].mana_pool = {'W': 10, 'U': 10, 'B': 10, 'G': 10, 'C': 10}
    return checked_action(state, RulesEngine(), player, {'type': 'cast_spell', 'card_id': card.id, 'targets': targets})


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name', ['Humble', 'Ovinize'])
def test_real_cast_loss_base_stats_counters_snapshot_and_cleanup(player, name):
    state = fixture()
    elf = add_printed(state, 'Llanowar Elves', 3-player)
    elf.counters['+1/+1'] = 1
    spell = add(state, name, player)
    printed = (elf.power, elf.toughness, elf.oracle_text)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(cast(state, spell, {'target_card_id': elf.id}))))
    elf = state.cards[elf.id]
    assert printed_abilities_suppressed(state, elf.id)
    assert nonland_mana_outputs(state, elf.id, elf) == {}
    assert (effective_power(state, elf.id), effective_toughness(state, elf.id)) == (1, 2)
    assert (elf.power, elf.toughness, elf.oracle_text) == printed
    assert elf.base_stat_effects[0]['timestamp'] == elf.keyword_effects[0]['timestamp']
    resolve_effect(state, player, 'grant_keyword', {'target_card_id': elf.id, 'keyword': 'flying'})
    assert has_keyword(state, elf.id, 'flying')
    assert nonland_mana_outputs(state, elf.id, elf) == {}
    trace = continuous_layer_trace(state, elf.id)
    assert 'pt-set' in str(trace) and 'keyword-remove:all-abilities' in str(trace)
    elf.counters["__damage_marked"] = 1
    RulesEngine()._clear_marked_damage(state)
    assert not elf.base_stat_effects and not printed_abilities_suppressed(state, elf.id)
    assert (effective_power(state, elf.id), effective_toughness(state, elf.id)) == (2, 2)
    assert has_keyword(state, elf.id, 'flying')


@pytest.mark.parametrize('player', [1, 2])
def test_base_setters_compete_by_timestamp_not_canonical_stats(player):
    state = fixture()
    elf = add_printed(state, 'Llanowar Elves', player)
    add_printed(state, 'Humility', 3-player)
    spell = add(state, 'Humble', 3-player)
    key, payload = infer_effect_from_oracle(state, spell, 3-player, {'target_card_id': elf.id})
    assert key == 'temporary_ability_loss'
    resolve_effect(state, 3-player, key, payload)
    assert (effective_power(state, elf.id), effective_toughness(state, elf.id)) == (0, 1)
    add_printed(state, 'Humility', 3-player)
    assert (effective_power(state, elf.id), effective_toughness(state, elf.id)) == (1, 1)


@pytest.mark.parametrize('player', [1, 2])
def test_player_effect_freezes_current_creatures_and_expires_on_zone_change(player):
    state = fixture()
    elf = add_printed(state, 'Llanowar Elves', 3-player)
    own = add_printed(state, 'Llanowar Elves', player)
    spell = add(state, 'Sudden Spoiling', player)
    state = resolve(cast(state, spell, {'target_player': 3-player}))
    elf = state.cards[elf.id]
    assert (effective_power(state, elf.id), effective_toughness(state, elf.id)) == (0, 2)
    assert not printed_abilities_suppressed(state, own.id)
    late = add_printed(state, 'Llanowar Elves', 3-player)
    assert not printed_abilities_suppressed(state, late.id)
    old = deepcopy(elf.base_stat_effects)
    elf.move_to_zone(Zone.EXILE)
    assert not elf.base_stat_effects and not elf.keyword_effects
    elf.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, elf.id)
    elf.base_stat_effects = old  # Explicit stale-snapshot record must not apply to a new object.
    assert effective_toughness(state, elf.id) == 1


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('human', [False, True])
def test_merfolk_entry_taps_then_loses_printed_ability(player, human):
    state = fixture()
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {player} if human else set()
    target = add_printed(state, 'Llanowar Elves', 3-player)
    own = add_printed(state, 'Llanowar Elves', player)
    card = add(state, 'Merfolk Trickster', player)
    state = cast(state, card, {})
    rules = RulesEngine()
    for _ in range(32):
        if state.pending_trigger_order or state.pending_mechanic_choice:
            break
        if not state.stack:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    # ETB targets are chosen by the production legal-choice flow, not the spell cast.
    while state.pending_trigger_order or state.pending_mechanic_choice:
        moves = rules.legal_moves(state, player)
        if state.pending_trigger_order:
            assert not any(m.get('target_card_id') == own.id for m in moves)
        choice = next(m for m in moves if target.id in str(m))
        state = checked_action(state, rules, player, choice)
    state = resolve(deserialize_match_snapshot(serialize_match_snapshot(state)))
    assert state.cards[target.id].tapped
    assert printed_abilities_suppressed(state, target.id)
    assert not state.cards[target.id].base_stat_effects
    assert not printed_abilities_suppressed(state, own.id)


@pytest.mark.parametrize('player', [1, 2])
def test_ai_projection_ranks_enemy_without_mutating_hidden_or_live_state(player):
    state = fixture()
    ally = add_printed(state, 'Llanowar Elves', player)
    enemy = add_printed(state, 'Royal Assassin', 3-player)
    spell = add(state, 'Humble', player)
    before = serialize_match_snapshot(state)
    good = keyword_target_value(state, spell, player, {'target_card_id': enemy.id})
    bad = keyword_target_value(state, spell, player, {'target_card_id': ally.id})
    assert good is not None and bad is not None and good > bad
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_split_second_blocks_both_seats_but_allows_mana_and_triggers(player):
    state = fixture()
    elf = add_printed(state, 'Llanowar Elves', 3-player)
    assassin = add_printed(state, 'Royal Assassin', 3-player)
    target = add_printed(state, 'Llanowar Elves', player)
    target.tapped = True
    response = add(state, 'Humble', 3-player)
    spoiling = add(state, 'Sudden Spoiling', player)
    state = cast(state, spoiling, {'target_player': 3-player})
    state.priority_player = 3-player
    assert split_second_active(state)
    moves = RulesEngine().legal_moves(state, 3-player)
    assert not any(m['type'] in {'cast_spell', 'activate_ability', 'cycle_card', 'crew', 'ninjutsu'} for m in moves)
    before = serialize_match_snapshot(state)
    for action in [
        {'type': 'cast_spell', 'card_id': response.id, 'targets': {'target_card_id': target.id}},
        {'type': 'activate_ability', 'card_id': assassin.id, 'ability_index': 0, 'targets': {'target_card_id': target.id}},
    ]:
        with pytest.raises(ActionRejected):
            RulesEngine().take_action(state, 3-player, action, reject_invalid=True)
        assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 3-player, {'type': 'tap_nonland_for_mana', 'card_id': elf.id, 'color': 'G'})
    warden = add_printed(state, 'Soul Warden', player)
    newcomer = add_printed(state, 'Llanowar Elves', player)
    emit_event(state, 'enters_battlefield', {'card_id': newcomer.id, 'controller': player})
    assert any(item.source_card_id == warden.id for item in state.stack)
    assert split_second_active(deserialize_match_snapshot(serialize_match_snapshot(state)))
    state = resolve(state)
    assert not split_second_active(state)


def test_split_second_spell_copy_uses_saved_characteristics_not_source_zone():
    state = fixture()
    spell = add(state, 'Sudden Spoiling', zone=Zone.GRAVEYARD)
    saved = {key: deepcopy(getattr(spell, key)) for key in ('keywords', 'oracle_text')}
    add_to_stack(state, spell.id, 1, 'Copy', 'noop', {'__stack_copy_kind': 'spell', '__copied_card': saved}, is_spell=False)
    spell.keywords = []
    spell.oracle_text = ''
    assert split_second_active(state)
    state.stack[0].payload['__stack_copy_kind'] = 'activated'
    assert not split_second_active(state)


@pytest.mark.parametrize('player', [1, 2])
def test_http_effect_restore_and_atomic_split_second_rejection(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = match.state
    target = add_printed(state, 'Llanowar Elves', 3-player)
    spell = add(state, 'Sudden Spoiling', player)
    response = add(state, 'Humble', 3-player)
    match.state = cast(state, spell, {'target_player': 3-player})
    match.state.priority_player = 3-player
    persist(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert split_second_active(restored.state)
    rejected(client, restored, {'type': 'cast_spell', 'card_id': response.id, 'targets': {'target_card_id': target.id}}, player_id=3-player)
    restored.state = resolve(restored.state)
    persist(restored)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    result = main.ACTIVE_MATCHES[state.id].state
    assert printed_abilities_suppressed(result, target.id)
    assert (effective_power(result, target.id), effective_toughness(result, target.id)) == (0, 2)


@pytest.mark.parametrize('player', [1, 2])
def test_cycling_and_crew_have_moves_before_lock_and_atomic_rejection_during_it(player):
    from game_state.state import CardInstance
    state = fixture()
    state.active_player = state.priority_player = player
    state.players[player].mana_pool = {'U': 10, 'C': 10}
    shark_rows = json.loads((Path(__file__).parent / 'fixtures/ai_oracle_semantics.json').read_text())
    shark = raw_add(state, 'Shark Typhoon', player, Zone.HAND, cards={c['name']: c for c in shark_rows})
    raw = json.loads((Path(__file__).parent / 'fixtures/permanent_spell_context.json').read_text())["Smuggler's Copter"]
    vehicle = CardInstance(id=state.allocate_object_id(), name=raw['name'], owner=player, controller=player,
                           zone=Zone.BATTLEFIELD, types=['Artifact'], type_line=raw['type_line'],
                           power=3, toughness=3, oracle_text=raw['oracle_text'], mana_cost=raw['mana_cost'])
    state.cards[vehicle.id] = vehicle
    state.players[player].battlefield.append(vehicle.id)
    elf = add_printed(state, 'Llanowar Elves', player)
    before_moves = RulesEngine().legal_moves(state, player)
    assert any(m['type'] == 'cycle_card' and m['card_id'] == shark.id for m in before_moves)
    assert any(m['type'] == 'crew' and m['card_id'] == vehicle.id for m in before_moves)
    spell = add(state, 'Sudden Spoiling', 3-player)
    state = cast(state, spell, {'target_player': player})
    state.priority_player = player
    before = serialize_match_snapshot(state)
    assert not any(m['type'] in {'cycle_card', 'crew'} for m in RulesEngine().legal_moves(state, player))
    for action in [
        {'type': 'cycle_card', 'card_id': shark.id, 'x_value': 0},
        {'type': 'crew', 'card_id': vehicle.id, 'crew_card_ids': [elf.id]},
    ]:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), player, action)
        assert serialize_match_snapshot(state) == before


def test_snapshot_records_are_detached_and_legacy_defaults_are_empty():
    state = fixture()
    elf = add_printed(state, 'Llanowar Elves')
    spell = add(state, 'Humble')
    key, payload = infer_effect_from_oracle(state, spell, 1, {'target_card_id': elf.id})
    resolve_effect(state, 1, key, payload)
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    restored.cards[elf.id].base_stat_effects[0]['power'] = 9
    assert saved['cards'][elf.id]['base_stat_effects'][0]['power'] == 0
    assert state.cards[elf.id].base_stat_effects[0]['power'] == 0
    for card in saved['cards'].values():
        card.pop('base_stat_effects', None)
    assert not deserialize_match_snapshot(saved).cards[elf.id].base_stat_effects
