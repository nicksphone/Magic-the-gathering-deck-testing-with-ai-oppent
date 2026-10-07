"""Two full canonical spells; desired semantics, not injected effect records."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from effects.registry import EFFECT_HANDLERS
from game_state.serializers import deserialize_match_snapshot, serialize_card_view
from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import effective_power, effective_toughness, has_keyword, printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.library_permissions import creature_types
from rules_engine.mana import nonland_mana_outputs
from tests.test_canonical_land_animation_audit import position as land_position, resolve, snapshot, record
from tests.test_land_animation_cloudshift_composition import CLOUDSHIFT
from tests.test_linked_damage_targets import raw_card


DIRECTORY = Path(__file__).parent / 'fixtures/multicharacteristic_audit'
ROWS = {}
for entry in json.loads((DIRECTORY / 'provenance.json').read_text())['cards']:
    raw = (DIRECTORY / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row
FAMILIES = ['Turn to Frog', 'Snakeform']


def cast(state, seat, spell, target):
    return checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id},
    })


def position(seat, name, counters=True):
    state, unused = land_position(seat, 'Mutavault')
    # Canonical retained-creature constructed position, not a natural episode.
    state.players[seat].battlefield.remove(unused.id)
    del state.cards[unused.id]
    target = raw_card(state, ROWS['Birds of Paradise'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, target.id)
    if counters:
        for _ in range(2):
            growth = raw_card(state, ROWS['Battlegrowth'], seat, Zone.HAND)
            state.players[seat].mana_pool = {'G': 1}
            state = resolve(cast(state, seat, growth, state.cards[target.id]))
        assert state.cards[target.id].counters.get('+1/+1') == 2
    spell = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = ({'C': 1, 'U': 1} if name == 'Turn to Frog' else {'C': 2, 'G': 1})
    return state, state.cards[target.id], spell


def observed(state, target):
    return {'colors': sorted(card_color_symbols(target, state)),
            'subtypes': sorted(creature_types(target, state)),
            'stats': [effective_power(state, target.id), effective_toughness(state, target.id)],
            'abilities_suppressed': printed_abilities_suppressed(state, target.id),
            'flying': has_keyword(state, target.id, 'flying'),
            'mana_outputs': nonland_mana_outputs(state, target.id, target),
            'counters': deepcopy(target.counters), 'counter_timestamps': deepcopy(target.counter_timestamps),
            'incarnation': object_incarnation(target), 'zone_change_sequence': target.zone_change_sequence,
            'public': serialize_card_view(state, target.id)}


def resolved(request, seat, name, **detail):
    state, target, spell = position(seat, name)
    before = snapshot(state)
    try:
        result = resolve(cast(state, seat, spell, target))
    except ActionRejected as error:
        assert snapshot(state) == before
        record(request, state, before=before, phase='admission_prerequisite_rejected', error=str(error))
        raise
    assert snapshot(state) == before
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert result.cards[spell.id].zone == Zone.GRAVEYARD
    assert snapshot(deserialize_match_snapshot(snapshot(result))) == snapshot(result)
    record(request, result, before=before, observed=observed(result, result.cards[target.id]), **detail)
    return state, target, spell, result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_paid_cast_root_rollback_and_native_roundtrip(request, seat, name):
    resolved(request, seat, name, phase='paid_resolution_control')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('dimension', ['abilities', 'color', 'subtype', 'base_stats', 'counters', 'timestamps'])
def test_desired_full_multicharacteristic_effect_dimension(request, seat, name, dimension):
    state, original, _, result = resolved(request, seat, name, phase='desired_dimension', dimension=dimension)
    target = result.cards[original.id]
    value = observed(result, target)
    if dimension == 'abilities':
        assert value['abilities_suppressed'] and not value['flying'] and value['mana_outputs'] == {}
    elif dimension == 'color':
        assert value['colors'] == (['U'] if name == 'Turn to Frog' else ['G'])
        assert target.colors == ROWS['Birds of Paradise']['colors']
    elif dimension == 'subtype':
        assert set(value['subtypes']) == ({'frog'} if name == 'Turn to Frog' else {'snake'})
        assert target.type_line == ROWS['Birds of Paradise']['type_line']
    elif dimension == 'base_stats':
        assert value['stats'] == [3, 3]  # Real two +1/+1 counters apply after base 1/1.
        assert (target.power, target.toughness) == (original.power, original.toughness)
    elif dimension == 'counters':
        assert target.counters == original.counters and target.counter_timestamps == original.counter_timestamps
    else:
        assert target.type_effects and target.base_stat_effects and target.keyword_effects
        stamps = {effect['timestamp'] for effects in
                  (target.type_effects, target.base_stat_effects, target.keyword_effects) for effect in effects}
        assert len(stamps) == 1
        assert all(effect['incarnation'] == object_incarnation(target) for effect in target.type_effects)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_native_cleanup_restores_original_after_complete_effect(request, seat, name):
    state, target, spell = position(seat, name)
    before = snapshot(state)
    result = resolve(cast(state, seat, spell, target))
    record(request, result, phase='cleanup_prerequisite', before=before,
           observed=observed(result, result.cards[target.id]))
    assert printed_abilities_suppressed(result, target.id), 'Complete-effect prerequisite failed, not skipped'
    assert creature_types(result.cards[target.id], result) == ({'frog'} if name == 'Turn to Frog' else {'snake'})
    for _ in range(48):
        if result.turn != state.turn:
            break
        result = checked_action(result, RulesEngine(), result.priority_player, {'type': 'pass_priority'})
    assert result.turn != state.turn, 'Native cleanup advancement bound reached'
    restored = result.cards[target.id]
    assert not restored.type_effects and not restored.base_stat_effects and not restored.keyword_effects
    assert not printed_abilities_suppressed(result, target.id) and has_keyword(result, target.id, 'flying')
    assert card_color_symbols(restored, result) == set(ROWS['Birds of Paradise']['colors'])
    assert creature_types(restored, result) == {'bird'}
    assert (effective_power(result, target.id), effective_toughness(result, target.id)) == (2, 3)
    assert restored.counters == target.counters
    assert restored.oracle_text == ROWS['Birds of Paradise']['oracle_text']
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_snakeform_draw_observes_complete_change_first(request, monkeypatch, seat):
    state, target, spell = position(seat, 'Snakeform')
    before = snapshot(state)
    top = state.players[seat].library[-1]
    calls = []
    native = EFFECT_HANDLERS['draw_cards']
    def observe_draw(candidate, controller, payload):
        calls.append(observed(candidate, candidate.cards[target.id]))
        return native(candidate, controller, payload)
    monkeypatch.setitem(EFFECT_HANDLERS, 'draw_cards', observe_draw)
    result = resolve(cast(state, seat, spell, target))
    record(request, result, phase='snakeform_draw_order', before=before, at_draw=calls)
    assert snapshot(state) == before
    assert result.players[seat].hand == [top]
    assert result.players[seat].library == state.players[seat].library[:-1]
    assert len(calls) == 1
    assert calls[0]['abilities_suppressed'] and calls[0]['subtypes'] == ['snake'] and calls[0]['stats'] == [3, 3]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_cloudshift_response_all_targets_illegal_no_partial_draw(request, seat, name):
    state, target, spell = position(seat, name)
    blink = raw_card(state, CLOUDSHIFT, seat, Zone.HAND)
    state.players[seat].mana_pool['W'] = 1
    before = snapshot(state)
    result = cast(state, seat, spell, target)
    pending = result.stack[-1].id
    old_reference = (object_incarnation(result.cards[target.id]), result.cards[target.id].zone_change_sequence)
    result = cast(result, seat, blink, result.cards[target.id])
    assert result.stack[-1].effect_key == 'exile_return_immediate'
    for _ in range(2):
        result = checked_action(result, RulesEngine(), result.priority_player, {'type': 'pass_priority'})
    assert len(result.stack) == 1 and result.stack[0].id == pending
    returned = result.cards[target.id]
    assert returned.zone == Zone.BATTLEFIELD
    assert (object_incarnation(returned), returned.zone_change_sequence) != old_reference
    before_resolution = snapshot(result)
    result = resolve(result)
    record(request, result, phase='all_targets_illegal_response', before=before,
           before_resolution=before_resolution, old_reference=old_reference)
    assert result.players[seat].library == state.players[seat].library
    assert result.players[seat].hand == []
    assert not printed_abilities_suppressed(result, target.id)
    assert creature_types(result.cards[target.id], result) == {'bird'}
    assert not result.cards[target.id].counters
    assert any('does not resolve' in entry or 'fizzles' in entry for entry in result.log)
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actor_private_projection_and_known_public_target_root_unchanged(request, seat, name):
    state, target, spell = position(seat, name)
    hidden = raw_card(state, ROWS['Snakeform'], 3-seat, Zone.HAND)
    before = snapshot(state)
    # Audit the projection contract with a real checked choice, not the unrelated
    # whole-menu AI planner. This is not a whole legal-view coverage claim.
    legal = [{'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': target.id}}]
    try:
        checked_action(state, RulesEngine(), seat, legal[0])
    except ActionRejected as error:
        assert snapshot(state) == before
        record(request, state, phase='projection_admission_prerequisite_rejected', before=before, error=str(error))
        raise
    projected, _ = decision_view(state, seat, legal)
    projection = snapshot(projected)
    opaque = projected.cards[hidden.id]
    assert opaque.ai_unknown and not opaque.name and not opaque.oracle_text
    assert opaque.mana_cost is None and opaque.power is None and opaque.toughness is None
    assert not opaque.card_faces and not opaque.printed_characteristics
    assert spell.id in json.dumps(projection) and target.id in json.dumps(projection)
    assert snapshot(state) == before
    record(request, state, phase='actor_projection_control', before=before, actor_projection=projection)
