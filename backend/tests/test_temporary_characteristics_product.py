"""Canonical paid controls and explicit grammar-only negative probes."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.continuous import has_keyword, printed_abilities_suppressed
from rules_engine.temporary_characteristics import compile_temporary_characteristics, temporary_characteristics_candidate
from rules_engine.type_effects import effective_types
from rules_engine.library_permissions import creature_types
from tests.test_canonical_multicharacteristic_audit import FAMILIES, ROWS, cast, observed, position
from tests.test_canonical_land_animation_audit import position as land_position, action, resolve, snapshot, record
from tests.test_land_animation_cloudshift_composition import CLOUDSHIFT
from tests.test_linked_damage_targets import raw_card
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


D = Path(__file__).parent / 'fixtures'
COSTS = json.loads((D / 'cost_reservation_overlap/canonical.json').read_text())
ORNITHOPTER = next(row for row in COSTS.values() if row['name'] == 'Ornithopter')
JUMP = next(row for row in json.loads((D / 'keyword_effect_timestamps.json').read_text()) if row['name'] == 'Jump')
assert ORNITHOPTER['object'] == JUMP['object'] == 'card'


def replacement_target(state, old, row, seat):
    state.players[seat].battlefield.remove(old.id)
    del state.cards[old.id]
    target = raw_card(state, row, seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, target.id)
    return target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_color_replaces_colorless_printed_artifact_without_mutating_it(request, seat, name):
    state, old, spell = position(seat, name, counters=False)
    target = replacement_target(state, old, ORNITHOPTER, seat)
    before = snapshot(state)
    result = resolve(cast(state, seat, spell, target))
    value = observed(result, result.cards[target.id])
    assert value['colors'] == (['U'] if name == 'Turn to Frog' else ['G'])
    assert result.cards[target.id].colors == []
    assert set(effective_types(result, result.cards[target.id])) == {'Artifact', 'Creature'}
    assert value['stats'] == [1, 1] and value['abilities_suppressed'] and not value['flying']
    assert snapshot(state) == before
    assert snapshot(deserialize_match_snapshot(snapshot(result))) == snapshot(result)
    record(request, result, before=before, observed=value)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('grant_later', [False, True])
def test_real_paid_keyword_grant_orders_across_same_stamp_characteristic_change(request, seat, name, grant_later):
    state, target, spell = position(seat, name, counters=False)
    jump = raw_card(state, JUMP, seat, Zone.HAND)
    state.players[seat].mana_pool['U'] = state.players[seat].mana_pool.get('U', 0) + 1
    before = snapshot(state)
    first, second = (spell, jump) if grant_later else (jump, spell)
    result = resolve(cast(state, seat, first, target))
    result = resolve(cast(result, seat, result.cards[second.id], result.cards[target.id]))
    changed = result.cards[target.id]
    assert has_keyword(result, target.id, 'flying') == grant_later
    assert printed_abilities_suppressed(result, target.id)
    removal = next(effect for effect in changed.keyword_effects if effect['operation'] == 'remove')
    grant = next(effect for effect in changed.keyword_effects if effect['operation'] == 'grant')
    assert (grant['timestamp'] > removal['timestamp']) == grant_later
    assert changed.type_effects[0]['timestamp'] == changed.base_stat_effects[0]['timestamp'] == removal['timestamp']
    assert removal['source_card_id'] == spell.id and grant['source_card_id'] == jump.id
    assert all(effect['incarnation'] == object_incarnation(changed) for effect in changed.keyword_effects)
    assert snapshot(state) == before
    record(request, result, before=before, observed=observed(result, changed), grant_later=grant_later)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_postchange_blink_clears_all_layers_for_real_new_object(request, seat, name):
    state, target, spell = position(seat, name, counters=False)
    blink = raw_card(state, CLOUDSHIFT, seat, Zone.HAND)
    state.players[seat].mana_pool['W'] = 1
    before = snapshot(state)
    result = resolve(cast(state, seat, spell, target))
    old = object_incarnation(result.cards[target.id]), result.cards[target.id].zone_change_sequence
    result = resolve(cast(result, seat, result.cards[blink.id], result.cards[target.id]))
    changed = result.cards[target.id]
    assert (object_incarnation(changed), changed.zone_change_sequence) != old
    assert not changed.type_effects and not changed.base_stat_effects and not changed.keyword_effects
    assert not printed_abilities_suppressed(result, target.id) and has_keyword(result, target.id, 'flying')
    assert creature_types(changed, result) == {'bird'}
    assert observed(result, changed)['colors'] == ['G']
    assert snapshot(state) == before
    assert snapshot(deserialize_match_snapshot(snapshot(result))) == snapshot(result)
    record(request, result, before=before, old_reference=old, observed=observed(result, changed))


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_characteristic_change_preserves_actual_animated_land_type(request, seat):
    state, land = land_position(seat, 'Mutavault')
    snake = raw_card(state, ROWS['Snakeform'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 3, 'G': 1}
    before = snapshot(state)
    result = resolve(checked_action(state, RulesEngine(), seat, action(land)))
    result = resolve(cast(result, seat, result.cards[snake.id], result.cards[land.id]))
    changed = result.cards[land.id]
    assert set(effective_types(result, changed)) == {'Land', 'Creature'}
    assert creature_types(changed, result) == {'snake'}
    assert snapshot(state) == before
    record(request, result, before=before, observed=observed(result, changed))


@pytest.mark.parametrize('tail', [' Draw two cards.', ' Draw a card. Gain 1 life.',
                                  ' It gains flying.', ' Draw a card. Unknown instruction.'])
@pytest.mark.parametrize('name', FAMILIES)
def test_grammar_only_unknown_complete_tail_cannot_compile_partial_change_or_draw(name, tail):
    body = ROWS[name]['oracle_text'].split('\n')[0] + tail
    assert temporary_characteristics_candidate(body)
    assert compile_temporary_characteristics(body, {'target_card_id': 'grammar-only-not-a-card'}) is None
