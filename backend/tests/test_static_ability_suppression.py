"""Canonical static/replacement sources; snapshots are fixture positions, not decks."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords, continuous_layer_trace
from rules_engine.counter_replacements import counter_options
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.token_replacements import token_creation_amount
from rules_engine.draw_restrictions import can_draw_card
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.library_permissions import top_library_creature_for_type
from rules_engine.hooks import CostContext, apply_cost_modifiers
from tests.test_ability_suppression import CARDS as PREVIOUS
from tests.test_ai_recurring_engines import fixture, add as raw_add
from game_state.state import Zone, assign_static_order_on_battlefield_entry

CARDS = {**PREVIOUS, **{c['name']: c for c in json.loads((Path(__file__).parent/'fixtures/static_ability_suppression.json').read_text())}}


def add(state, name, player=1):
    card = raw_add(state, name, player, cards=CARDS)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('older', [True, False])
def test_real_creature_anthem_and_keyword_sources_stop_under_humility_regardless_of_timestamp(player, older):
    state = fixture()
    if older:
        removal = add(state, 'Humility', 3-player)
    anthem = add(state, 'Elvish Clancaller', player)
    elf = add(state, 'Llanowar Elves', player)
    archetype = add(state, 'Archetype of Imagination', player)
    if not older:
        removal = add(state, 'Humility', 3-player)
    assert effective_power(state, elf.id) == effective_toughness(state, elf.id) == 1
    assert 'flying' not in effective_keywords(state, elf.id)
    assert not any(row.get('source_id') in {anthem.id, archetype.id} for row in continuous_layer_trace(state, elf.id)['applied_layers'])
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(restored, player, 'destroy_permanent', {'target_card_id': removal.id})
    assert effective_power(restored, elf.id) == effective_toughness(restored, elf.id) == 2
    assert 'flying' in effective_keywords(restored, elf.id)


@pytest.mark.parametrize('player', [1, 2])
def test_real_counter_and_token_replacements_stop_when_their_creature_sources_lose_abilities(player):
    state = fixture()
    mentor = add(state, 'Conclave Mentor', player)
    doubler = add(state, 'Adrix and Nev, Twincasters', player)
    elf = add(state, 'Llanowar Elves', player)
    payload = {'counter': '+1/+1', 'amount': 1, 'target_card_id': elf.id}
    assert any(option['source_card_id'] == mentor.id for option in counter_options(state, player, payload))
    resolve_effect(state, player, 'add_counters', payload)
    assert elf.counters['+1/+1'] == 2
    assert token_creation_amount(state, player, 2) == 4
    add(state, 'Dress Down', 3-player)
    assert counter_options(state, player, payload) == []
    resolve_effect(state, player, 'add_counters', payload)
    assert elf.counters['+1/+1'] == 3
    assert token_creation_amount(state, player, 2) == 2
    assert mentor.oracle_text == CARDS[mentor.name]['oracle_text']
    assert doubler.oracle_text == CARDS[doubler.name]['oracle_text']


@pytest.mark.parametrize('player', [1, 2])
def test_real_life_replacement_and_draw_restriction_stop_under_ability_loss(player):
    state = fixture()
    add(state, 'Rhox Faithmender', player)
    add(state, 'Spirit of the Labyrinth', 3-player)
    state.draws_this_turn[player] = 1
    assert not can_draw_card(state, player)
    life = state.players[player].life
    resolve_effect(state, player, 'gain_life', {'amount': 2})
    assert state.players[player].life == life + 4
    add(state, 'Humility', 3-player)
    assert can_draw_card(state, player)
    resolve_effect(state, player, 'gain_life', {'amount': 2})
    assert state.players[player].life == life + 6


@pytest.mark.parametrize('player', [1, 2])
def test_real_extra_land_and_top_library_permissions_stop_under_ability_loss(player):
    state = fixture()
    add(state, 'Azusa, Lost but Seeking', player)
    realmwalker = add(state, 'Realmwalker', player)
    realmwalker.chosen_creature_type = 'elf'
    elf = add(state, 'Llanowar Elves', player)
    state.players[player].battlefield.remove(elf.id)
    elf.move_to_zone(Zone.LIBRARY)
    state.players[player].library.append(elf.id)
    assert compute_max_land_plays_this_turn(state, player) == 3
    assert top_library_creature_for_type(state, player) is elf
    add(state, 'Humility', 3-player)
    assert compute_max_land_plays_this_turn(state, player) == 1
    assert top_library_creature_for_type(state, player) is None


@pytest.mark.parametrize('player', [1, 2])
def test_real_poison_prohibition_and_noncreature_tax_stop_under_ability_loss(player):
    state = fixture()
    add(state, 'Melira, Sylvok Outcast', player)
    add(state, 'Thalia, Guardian of Thraben', 3-player)
    def tax():
        return apply_cost_modifiers(CostContext(player, 'Synthetic cost-context fixture', '{1}', state=state,
                                               spell_types={'Instant'})).generic_increase
    assert counter_placement_forbidden(state, 'poison', target_player=player)
    assert tax() == 1
    add(state, 'Humility', 3-player)
    assert not counter_placement_forbidden(state, 'poison', target_player=player)
    assert tax() == 0


@pytest.mark.parametrize('player', [1, 2])
def test_synthetic_creature_humility_keeps_its_single_effect_across_layers(player):
    state = fixture()
    source = add(state, 'Humility', player)
    source.types.append('Creature')  # Explicit animation fixture, not a fabricated card.
    source.power = source.toughness = 8
    assert effective_power(state, source.id) == effective_toughness(state, source.id) == 1
    trace = continuous_layer_trace(state, source.id)['applied_layers']
    assert any(row['layer'] == 'keyword-remove:all-abilities' for row in trace)
    assert any(row['layer'] == 'pt-set' for row in trace)


@pytest.mark.parametrize('player', [1, 2])
def test_real_aura_discount_stops_under_ability_loss_in_synthetic_cost_context(player):
    state = fixture()
    add(state, 'Transcendent Envoy', player)
    def discount():
        return apply_cost_modifiers(CostContext(player, 'Synthetic Aura cost-context fixture', '{2}', state=state,
                                               spell_types={'Enchantment'}, oracle_text='Enchant creature.')).generic_reduction
    assert discount() == 1
    add(state, 'Humility', 3-player)
    assert discount() == 0


@pytest.mark.parametrize('player', [1, 2])
def test_synthetic_independent_second_ability_does_not_inherit_cross_layer_continuation(player):
    state = fixture()
    source = add(state, 'Humility', player)
    source.types.append('Creature')
    source.power = source.toughness = 8
    # Separate synthetic ability: continuation belongs to an effect, not its whole source.
    source.oracle_text += '\nCreatures you control have base power and toughness 8/8.'
    assert effective_power(state, source.id) == effective_toughness(state, source.id) == 1


@pytest.mark.parametrize('player', [1, 2])
def test_ai_recurring_reward_value_uses_actual_suppression_and_recovers_when_loss_ends(player):
    from ai.heuristics import recurring_engine_value
    state = fixture()
    artist = add(state, 'Blood Artist', player)
    assert recurring_engine_value(state, artist.id) > 0
    suppression = add(state, 'Humility', 3-player)
    assert recurring_engine_value(state, artist.id) == 0
    resolve_effect(state, player, 'destroy_permanent', {'target_card_id': suppression.id})
    assert recurring_engine_value(state, artist.id) > 0


@pytest.mark.parametrize('player', [1, 2])
def test_ability_loss_does_not_remove_physical_shield_counter_replacement(player):
    state = fixture()
    elf = add(state, 'Llanowar Elves', player)
    resolve_effect(state, player, 'add_counters', {'counter': 'shield', 'amount': 1, 'target_card_id': elf.id})
    add(state, 'Humility', 3-player)
    resolve_effect(state, 3-player, 'deal_damage', {'amount': 3, 'target_card_id': elf.id})
    assert elf.zone == Zone.BATTLEFIELD
    assert elf.counters.get('shield', 0) == 0
    assert elf.counters.get('__damage_marked', 0) == 0


def test_stat_query_builds_loss_sources_per_layer_query_not_per_permanent(monkeypatch):
    import rules_engine.continuous as layers
    state = fixture()
    creatures = [add(state, 'Llanowar Elves', 1+(index%2)) for index in range(30)]
    before = serialize_match_snapshot(state)
    calls = []
    original = layers._printed_ability_loss_sources
    def counted(state):
        calls.append(1)
        return original(state)
    monkeypatch.setattr(layers, '_printed_ability_loss_sources', counted)
    assert effective_power(state, creatures[0].id) == 1
    assert len(calls) == 2  # Base-stat and delta queries each prepare once.
    assert serialize_match_snapshot(state) == before
