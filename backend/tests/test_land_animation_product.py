"""Native animation qualifications; constructed canonical positions, not games."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_card_view
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_ability_spec
from rules_engine.card_types import CREATURE_SUBTYPES
from rules_engine.colors import card_color_symbols
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.land_animation import compile_self_land_animation
from rules_engine.library_permissions import creature_types
from tests.test_canonical_land_animation_audit import (
    FAMILIES, ROWS, ability, action, activate, isolated_api, position, record, resolve, snapshot,
)
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_native_resolved_public_view_subtypes_colors_and_serialized_overlay(request, seat, name):
    state, land = position(seat, name)
    before = snapshot(state)
    candidate = resolve(activate(request, state, seat, land))
    card = candidate.cards[land.id]
    view = serialize_card_view(candidate, card.id)
    assert set(view['types']) == {'Land', 'Creature'}
    assert 'Creature' in view['type_line'] and view['base_type_line'] == ROWS[name]['type_line']
    assert card.colors == ROWS[name]['colors']
    assert card.type_line == ROWS[name]['type_line']
    assert card.oracle_text == ROWS[name]['oracle_text']
    if name == 'Mutavault':
        assert CREATURE_SUBTYPES <= creature_types(card, candidate)
        assert not has_keyword(candidate, card.id, 'changeling')
        assert card_color_symbols(card, candidate) == set()
    else:
        assert creature_types(card, candidate) == {'elemental'}
        assert view['colors'] == ['U', 'W']
    restored = deserialize_match_snapshot(snapshot(candidate))
    assert serialize_card_view(restored, card.id) == view
    assert snapshot(state) == before
    record(request, candidate, phase='public_overlay', public=view)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('newly_played', [False, True])
def test_empty_pool_mutavault_has_real_self_mana_payment_not_false_unfunded_rejection(request, seat, newly_played):
    state, land = position(seat, 'Mutavault', newly_played)
    state.players[seat].mana_pool = {}
    before = snapshot(state)
    assert any(move.get('card_id') == land.id and move['type'] == 'activate_ability'
               for move in RulesEngine().legal_moves(state, seat))
    candidate = checked_action(state, RulesEngine(), seat, action(land))
    assert candidate.cards[land.id].tapped
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    candidate = resolve(candidate)
    assert candidate.cards[land.id].summoning_sick == newly_played
    assert snapshot(state) == before
    record(request, candidate, phase='native_self_payment', before=before)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_tap_then_phase_clears_pool_genuinely_unfunded_mutavault_rejects(request, seat):
    state, land = position(seat, 'Mutavault')
    state.players[seat].mana_pool = {}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'tap_land_for_mana', 'card_id': land.id, 'color': 'C'})
    for _ in range(2):
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.cards[land.id].tapped and sum(state.players[seat].mana_pool.values()) == 0
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action(state.cards[land.id]))
    assert snapshot(state) == before
    record(request, state, phase='genuine_unfunded')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('tail', [' Draw a card.', ' Then destroy target creature.', ' If you control a Forest.'])
def test_unknown_compound_body_fail_closed_without_partial_supported_effect(seat, name, tail):
    state, land = position(seat, name)
    text = ability(land)['text'] + tail
    # Grammar-negative probes, not a rewritten canonical card or executed spell.
    proxy = SimpleNamespace(id=land.id, name=land.name, oracle_text=text, mana_cost='')
    before = snapshot(state)
    assert compile_self_land_animation(state, land, text) is None
    assert build_ability_spec(state, proxy, seat, report_unsupported=False).effect.key == 'noop'
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_self_reference_grammar_uses_printed_identity_not_named_dispatch(seat, name):
    state, land = position(seat, name)
    # Grammar-only derivation; execution tests retain untouched full raw Oracle.
    text = ability(land)['text'].replace('This land', land.name).replace('this land', land.name)
    spec = compile_self_land_animation(state, land, text)
    assert spec is not None and spec[0] == 'animate_self_land'
    assert spec[1]['target_card_id'] == land.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_native_cleanup_expires_all_overlay_dimensions_and_preserves_printed_data(request, seat, name):
    from game_state.state import Step
    state, land = position(seat, name)
    candidate = resolve(activate(request, state, seat, land))
    candidate.step = Step.END_STEP
    candidate.passed_priority.clear()
    for _ in range(10):
        if candidate.turn != state.turn:
            break
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert candidate.turn != state.turn
    card = candidate.cards[land.id]
    assert not card.type_effects and not card.base_stat_effects and not card.keyword_effects
    assert card_color_symbols(card, candidate) == set(ROWS[name]['colors'])
    assert not creature_types(card, candidate) & CREATURE_SUBTYPES
    assert card.type_line == ROWS[name]['type_line'] and card.colors == ROWS[name]['colors']
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)
    record(request, candidate, phase='complete_cleanup')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('replacement_first', [False, True])
def test_native_song_replacement_competes_with_resolved_animation_timestamps(request, seat, name, replacement_first):
    from game_state.state import assign_static_order_on_battlefield_entry
    from tests.test_basic_land_layer_goldens import CARDS
    from tests.test_canonical_global_flash_audit import ROWS as FLASH_ROWS
    state, land = position(seat, name)
    grant = raw_card(state, FLASH_ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, grant.id)
    song = raw_card(state, CARDS['Song of the Dryads'], seat, Zone.HAND)
    state.players[seat].mana_pool = ({'C': 3, 'G': 1} if name == 'Mutavault'
                                    else {'C': 5, 'W': 1, 'U': 1, 'G': 1})
    before = snapshot(state)
    candidate = checked_action(state, RulesEngine(), seat, action(land))
    if not replacement_first:
        candidate = resolve(candidate)
    candidate = checked_action(candidate, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': song.id, 'targets': {'target_card_id': land.id},
    })
    candidate = resolve(candidate)
    card = candidate.cards[land.id]
    view = serialize_card_view(candidate, land.id)
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    assert candidate.cards[song.id].attached_to == land.id
    if replacement_first:
        assert 'Creature' in view['types']
        assert ('elemental' in creature_types(card, candidate) if name == 'Celestial Colonnade'
                else CREATURE_SUBTYPES <= creature_types(card, candidate))
        assert card_color_symbols(card, candidate) == ({'W', 'U'} if name == 'Celestial Colonnade' else set())
    else:
        assert view['types'] == ['Land'] and not creature_types(card, candidate) & CREATURE_SUBTYPES
        assert card_color_symbols(card, candidate) == set()
    assert 'Forest' in view['type_line']
    assert card.type_line == ROWS[name]['type_line'] and card.colors == ROWS[name]['colors']
    assert snapshot(state) == before
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)
    record(request, candidate, phase='native_layer_timestamp_order', replacement_first=replacement_first, public=view)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_http_payment_then_native_resolution_private_views_and_memory_restore(isolated_api, request, seat, name):
    from sqlmodel import Session
    from persistence.repository import Repository
    main, memory, client = isolated_api
    state, land = position(seat, name)
    hidden = raw_card(state, ROWS['Flicker'], 3-seat, Zone.HAND)
    controller = main.MatchController(state=state, rules=RulesEngine(), controllers={seat: 'human', 3-seat: 'ai'},
        ai={}, mode='human_vs_ai', deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(memory) as session:
        main._persist_active_match(Repository(session), controller)
    before = snapshot(state)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action(land)})
    assert response.status_code == 200 and hidden.id not in json.dumps(response.json())
    assert sum(controller.state.players[seat].mana_pool.values()) == 0
    assert snapshot(state) == before
    passed = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {'type': 'pass_priority'}})
    assert passed.status_code == 200 and hidden.id not in json.dumps(passed.json())
    # Never impersonate an AI-controlled HTTP actor; its pass is checked natively.
    controller.state = checked_action(controller.state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    assert not controller.state.stack
    with Session(memory) as session:
        main._persist_active_match(Repository(session), controller)
    final = snapshot(controller.state)
    public = serialize_card_view(controller.state, land.id)
    assert 'Creature' in public['types'] and public['power'] == (2 if name == 'Mutavault' else 4)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(memory) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id].state
    assert snapshot(restored) == final and serialize_card_view(restored, land.id) == public
    view = client.get(f'/matches/{state.id}/legal-moves?player_id={seat}')
    assert view.status_code == 200 and hidden.id not in json.dumps(view.json())
    record(request, restored, phase='http_resolved_restore', public=public,
           transport='Actual human HTTP activation/pass, native checked AI pass, in-process memory persistence restore; not cold server')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_real_flash_flicker_response_departure_does_not_receive_pending_animation(request, seat, name):
    from tests.test_canonical_global_flash_audit import ROWS as FLASH_ROWS
    from game_state.state import assign_static_order_on_battlefield_entry
    state, land = position(seat, name)
    grant = raw_card(state, FLASH_ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, grant.id)
    spell = raw_card(state, ROWS['Flicker'], seat, Zone.HAND)
    assert ROWS['Flicker']['mana_cost'] == '{1}{W}'
    state.players[seat].mana_pool = ({'C': 3, 'W': 1} if name == 'Mutavault'
                                    else {'C': 7, 'W': 3, 'U': 2})
    before = snapshot(state)
    candidate = checked_action(state, RulesEngine(), seat, action(land))
    candidate = resolve(candidate)
    # Actual first animation makes this a legal target for the baseline's
    # creature-only Flicker hints. No types/events are injected for the response.
    candidate = checked_action(candidate, RulesEngine(), seat, action(candidate.cards[land.id]))
    animation_id = candidate.stack[-1].id
    candidate = checked_action(candidate, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': land.id}})
    for _ in range(2):
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert len(candidate.stack) == 1 and candidate.stack[0].id == animation_id
    assert candidate.cards[land.id].zone == Zone.EXILE
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    # Baseline Flicker is known exile-only; this proves departure, not correct blink.
    departed = snapshot(candidate)
    candidate = resolve(candidate)
    assert candidate.cards[land.id].zone == Zone.EXILE
    assert not candidate.cards[land.id].type_effects
    assert not candidate.cards[land.id].base_stat_effects
    assert not candidate.cards[land.id].keyword_effects
    assert snapshot(state) == before
    record(request, candidate, phase='pending_source_departed', departure=departed,
           limit='Flicker return is a separately retained known failure; no reentry claim')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_desired_real_instant_blink_reentry_cannot_inherit_announced_animation(request, seat, name):
    directory = Path(__file__).parent / 'fixtures/canonical_land_animation_response'
    provenance = json.loads((directory / 'provenance.json').read_text())
    raw = (directory / 'ghostly-flicker.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance['sha256']
    row = json.loads(raw)
    state, land = position(seat, name)
    other = raw_card(state, ROWS['Island'], seat, Zone.BATTLEFIELD)
    candidate = activate(request, state, seat, land)
    old = (object_incarnation(candidate.cards[land.id]), candidate.cards[land.id].zone_change_sequence)
    spell = raw_card(candidate, row, seat, Zone.HAND)
    candidate.players[seat].mana_pool = {'C': 2, 'U': 1}
    before = snapshot(candidate)
    try:
        responded = checked_action(candidate, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id,
            'targets': {'target_card_ids': [land.id, other.id]},
        })
    except ActionRejected as error:
        assert snapshot(candidate) == before
        record(request, candidate, phase='pending_reentry_response_rejected', error=str(error), before=before)
        raise
    for _ in range(2):
        responded = checked_action(responded, RulesEngine(), responded.priority_player, {'type': 'pass_priority'})
    record(request, responded, phase='pending_reentry_response_resolved', before=before, old_incarnation=old)
    assert len(responded.stack) == 1
    returned = responded.cards[land.id]
    assert returned.zone == Zone.BATTLEFIELD
    assert (object_incarnation(returned), returned.zone_change_sequence) != old
    candidate = resolve(responded)
    assert 'Creature' not in serialize_card_view(candidate, land.id)['types']
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)
