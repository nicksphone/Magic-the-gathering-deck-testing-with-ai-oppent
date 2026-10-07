"""Canonical paid episodes exercising effective-type and real cost readers."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.affinity import _matches
from rules_engine.costs import _eligible_sacrifice_ids, activated_cost_available, parse_activated_cost
from rules_engine.engine import RulesEngine
from rules_engine.land_types import effective_type_line
from rules_engine.library_permissions import creature_types
from rules_engine.type_effects import effective_types
from tests.test_activated_subtype_sacrifice import canonical
from tests.test_canonical_multicharacteristic_audit import FAMILIES, ROWS, cast, position
from tests.test_canonical_land_animation_audit import position as land_position, action, resolve, snapshot, record
from tests.test_linked_damage_targets import raw_card
from tests.test_temporary_characteristics_product import ORNITHOPTER, replacement_target


def reader_position(seat, name, category):
    if category == 'CreatureLand':
        state, target = land_position(seat, 'Mutavault')
        state = resolve(checked_action(state, RulesEngine(), seat, action(target)))
        target = state.cards[target.id]
        spell = raw_card(state, ROWS[name], seat, Zone.HAND)
        state.players[seat].mana_pool = {'C': 1, 'U': 1} if name == 'Turn to Frog' else {'C': 2, 'G': 1}
    else:
        state, target, spell = position(seat, name, counters=category == 'Creature')
        if category == 'ArtifactCreature':
            target = replacement_target(state, target, ORNITHOPTER, seat)
    return state, target, spell


def printed(card):
    return deepcopy((card.type_line, card.oracle_text, card.colors, card.power, card.toughness,
                     card.printed_characteristics, card.counters, card.counter_timestamps))


def advance_cleanup(state):
    turn = state.turn
    for _ in range(48):
        if state.turn != turn:
            return state
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native cleanup advancement bound reached')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('category', ['Creature', 'ArtifactCreature', 'CreatureLand'])
def test_real_line_subtype_cost_readers_restore_and_native_cleanup(request, seat, name, category):
    state, target, spell = reader_position(seat, name, category)
    original = printed(target)
    original_types = set(target.type_effect_base if target.type_effect_base is not None else target.types)
    before = snapshot(state)
    changed = resolve(cast(state, seat, spell, target))
    subtype = 'frog' if name == 'Turn to Frog' else 'snake'
    expected_types = {'Creature'} | ({'Artifact'} if category == 'ArtifactCreature' else
                                   {'Land'} if category == 'CreatureLand' else set())
    readers = []
    for candidate in (changed, deserialize_match_snapshot(snapshot(changed))):
        candidate_before = snapshot(candidate)
        card = candidate.cards[target.id]
        assert set(effective_types(candidate, card)) == expected_types
        line = effective_type_line(candidate, card)
        assert line.split('\u2014', 1)[1].strip().lower() == subtype
        assert creature_types(card, candidate) == {subtype}
        assert target.id in _eligible_sacrifice_ids(candidate, seat, 'subtype_' + subtype)
        assert target.id not in _eligible_sacrifice_ids(candidate, seat, 'subtype_bird')
        # These are actual shared cost-counting queries, not invented affinity spells.
        assert _matches(candidate, card, subtype + 's')
        assert not _matches(candidate, card, 'birds')
        assert printed(card) == original
        assert snapshot(candidate) == candidate_before
        readers.append({'line': line, 'types': sorted(expected_types), 'subtype': subtype})
    assert readers[0] == readers[1]
    cleaned = advance_cleanup(changed)
    card = cleaned.cards[target.id]
    assert not card.type_effects and not card.base_stat_effects and not card.keyword_effects
    assert set(effective_types(cleaned, card)) == original_types
    assert effective_type_line(cleaned, card) == card.type_line
    assert printed(card) == original
    assert target.id not in _eligible_sacrifice_ids(cleaned, seat, 'subtype_' + subtype)
    assert not _matches(cleaned, card, subtype + 's')
    assert snapshot(state) == before
    record(request, cleaned, before=before, changed_snapshot=snapshot(changed), reader_receipts=readers)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_canonical_goblin_cost_selection_loses_subtype_then_recovers_at_cleanup(request, seat, name):
    state, unused, spell = position(seat, name, counters=False)
    state.players[seat].battlefield.remove(unused.id)
    del state.cards[unused.id]
    victim = canonical(state, 'Goblin Instigator', seat)
    source = canonical(state, 'Skirk Prospector', seat)
    assign_static_order_on_battlefield_entry(state, victim.id)
    assign_static_order_on_battlefield_entry(state, source.id)
    cost_text = source.oracle_text.split(':', 1)[0]
    assert parse_activated_cost(cost_text).sacrifice_kind == 'subtype_goblin'
    choice = {'sacrifice_card_ids': [victim.id]}
    def available(candidate):
        return activated_cost_available(candidate, seat, source.id, cost_text,
                                        ability_kind='mana', ability_index=0, payment_choices=choice)
    before = snapshot(state)
    assert available(state) and snapshot(state) == before
    changed = resolve(cast(state, seat, spell, victim))
    current = snapshot(changed)
    assert not available(changed) and snapshot(changed) == current
    restored = deserialize_match_snapshot(current)
    assert not available(restored) and snapshot(restored) == current
    assert printed(changed.cards[victim.id]) == printed(victim)
    assert source.id in _eligible_sacrifice_ids(changed, seat, 'subtype_goblin')
    cleaned = advance_cleanup(changed)
    cleaned_before = snapshot(cleaned)
    assert available(cleaned) and snapshot(cleaned) == cleaned_before
    assert creature_types(cleaned.cards[victim.id], cleaned) == {'goblin', 'rogue'}
    assert snapshot(state) == before
    record(request, cleaned, before=before, changed_snapshot=current,
           canonical_source=source.name, canonical_cost_text=cost_text, selected_id=victim.id)
