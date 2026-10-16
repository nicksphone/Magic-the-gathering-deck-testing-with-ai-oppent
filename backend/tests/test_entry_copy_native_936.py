"""Real full-RAW births and checked entry actions; no synthetic copy producer."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_boundary_support_bf62 import raw_card as boundary_raw
from tests.graveyard_batch_native_support_bf62 import choose, place, snapshot
from tests.test_temporary_artifact_type import raw as coating_raw


SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'


def raw(name):
    data = SEED.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    values = [json.loads(line) for line in data.splitlines()]
    value = next((value for value in values if value['name'] == name), None)
    if value is None:
        value = coating_raw(name) if name in {'Cloudshift', 'Disenchant'} else boundary_raw(name)
    assert value['object'] == 'card' and value['name'] == name
    return deepcopy(value)


def position(first=(), second=(), seat=1):
    def deck(names):
        counts = Counter(names)
        counts['Island'] += 60 - sum(counts.values())
        return [{**raw(name), 'card_name': name, 'quantity': count} for name, count in counts.items()]
    state = MatchFactory.from_decks(deck(first), deck(second), seed=991)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    return state


def cast(state, seat, name, **targets):
    state.active_player = state.priority_player = seat
    cid = place(state, name, Zone.HAND, seat)
    state.players[seat].mana_pool = dict(C=30, W=10, U=10, B=10, R=10, G=10)
    before = sum(state.players[seat].mana_pool.values())
    state = checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': cid, **({'targets': targets} if targets else {})})
    assert sum(state.players[seat].mana_pool.values()) < before
    assert state.stack[-1].source_card_id == cid
    return state, cid


def pending_steel(seat, *, target_owner=None):
    target_owner = 3-seat if target_owner is None else target_owner
    names = {seat: ['Sculpting Steel', 'Cloudshift'], target_owner: ['Sol Ring']}
    if target_owner == seat:
        names[seat] = ['Sculpting Steel', 'Cloudshift', 'Sol Ring']
    state = position(names.get(1, []), names.get(2, []), seat)
    target = place(state, 'Sol Ring', Zone.BATTLEFIELD, target_owner)
    state, steel = cast(state, seat, 'Sculpting Steel')
    frame = deepcopy(state.stack[-1])
    assert not resolve_top_of_stack(state), 'Actual permanent spell must pause before copying entry'
    assert state.cards[steel].zone == Zone.STACK
    assert state.pending_mechanic_choice['player_id'] == seat
    assert target in state.pending_mechanic_choice['options']
    return state, steel, target, frame


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_spell_copy_preserves_actual_controller_owner_stock_and_snapshot(seat, foreign):
    state, steel, target, frame = pending_steel(seat, target_owner=3-seat if foreign else seat)
    physical = deepcopy(state.cards[steel].card_faces)
    state = choose(snapshot(state), seat, target)
    assert not state.pending_mechanic_choice and not state.stack
    card = state.cards[steel]
    assert card.zone == Zone.BATTLEFIELD and card.name == 'Sol Ring'
    assert card.controller == card.owner == seat
    assert card.card_faces == physical
    assert card.oracle_text == raw('Sol Ring')['oracle_text']
    assert card.printed_characteristics['name'] == 'Sculpting Steel'
    assert frame.source_card_id == steel
    restored = snapshot(state)
    assert restored.cards[steel].name == 'Sol Ring'
    assert restored.sideboard_facts['inventory'][steel]['stock_key'] == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
def test_real_optional_decline_keeps_full_printed_steel(seat):
    state, steel, target, _ = pending_steel(seat)
    state = checked_action(snapshot(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': []})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[steel].zone == Zone.BATTLEFIELD
    assert state.cards[steel].name == 'Sculpting Steel'
    assert state.cards[steel].oracle_text == raw('Sculpting Steel')['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cloudshift_restores_printed_steel_before_fresh_copy_choice(seat):
    names = {seat: ['Sculpting Steel', 'Cloudshift', 'Liquimetal Coating'], 3-seat: ['Grizzly Bears']}
    state = position(names[1], names[2], seat)
    target = place(state, 'Grizzly Bears', Zone.BATTLEFIELD, 3-seat)
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': target}})
    assert resolve_top_of_stack(state)
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state = choose(state, seat, target)
    first_incarnation = state.cards[steel].battlefield_incarnation
    state, blink = cast(state, seat, 'Cloudshift', target_card_id=steel)
    assert not resolve_top_of_stack(state)
    assert state.cards[steel].zone == Zone.EXILE
    assert state.cards[steel].name == 'Sculpting Steel'
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == seat and target in pending['options']
    assert pending['resolving_item']['source_card_id'] == blink
    state = checked_action(snapshot(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': []})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[steel].name == 'Sculpting Steel'
    assert state.cards[steel].zone == Zone.BATTLEFIELD
    assert state.cards[steel].battlefield_incarnation != first_incarnation
    assert snapshot(state).cards[steel].oracle_text == raw('Sculpting Steel')['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_of_actual_copy_uses_retained_values_not_original_steel(seat):
    names = {seat: ['Sculpting Steel', 'Sol Ring'], 3-seat: ['Sculpting Steel']}
    state = position(names[1], names[2], seat)
    target = place(state, 'Sol Ring', Zone.BATTLEFIELD, seat)
    state, first = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, target)
    state, second = cast(state, 3-seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), 3-seat, first)
    assert state.cards[first].name == state.cards[second].name == 'Sol Ring'
    assert state.cards[second].oracle_text == raw('Sol Ring')['oracle_text']
    assert state.cards[first].owner == seat and state.cards[second].owner == 3-seat
    assert snapshot(state).cards[second].printed_characteristics['name'] == 'Sculpting Steel'


@pytest.mark.parametrize('seat', [1, 2])
def test_real_coated_planeswalker_copies_initial_not_changed_loyalty(seat):
    from rules_engine.counter_placement import put_counters
    names = {seat: ['Sculpting Steel', 'Liquimetal Coating'], 3-seat: ['Teferi, Hero of Dominaria']}
    state = position(names[1], names[2], seat)
    state, walker = cast(state, 3-seat, 'Teferi, Hero of Dominaria')
    assert resolve_top_of_stack(state)
    assert state.cards[walker].loyalty == 4
    put_counters(state, 'loyalty', 3, target_card_id=walker)
    assert state.cards[walker].loyalty == 7
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state.active_player = state.priority_player = seat
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': walker}})
    assert resolve_top_of_stack(state)
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    assert walker in state.pending_mechanic_choice['options']
    state = choose(snapshot(state), seat, walker)
    assert state.cards[steel].loyalty == 4 and state.cards[walker].loyalty == 7
    assert state.cards[steel].name == 'Teferi, Hero of Dominaria'
    assert 'Artifact' not in state.cards[steel].types
    assert snapshot(state).cards[steel].loyalty == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mutation', ['reference', 'drop_row', 'controller', 'raw', 'frame'])
def test_paused_copy_packet_tamper_is_rejected_before_pending_clear_or_any_move(seat, mutation):
    state, steel, target, _ = pending_steel(seat)
    pending = state.pending_mechanic_choice
    plan = pending['effect_payload']['__entry_copy_plan']
    if mutation == 'drop_row':
        plan['entries'].clear()
    elif mutation == 'frame':
        plan['frame']['source_card_id'] = target
    elif mutation == 'reference':
        plan['entries'][0]['reference']['sequence'] += 1
    elif mutation == 'controller':
        plan['entries'][0]['controller'] = 3-seat
    else:
        plan['entries'][0]['clause'] += ' (then draw a card)'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, seat, target)
    assert serialize_match_snapshot(state) == before
    assert state.cards[steel].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_copy_public_view_never_contains_retained_frame_or_physical_record(seat):
    state, _, _, _ = pending_steel(seat)
    public = serialize_match(state)['pending_mechanic_choice']
    assert set(public) <= {'kind', 'player_id', 'options', 'count', 'min_count', 'label',
                           'option_labels', 'option_type_lines', 'entry_card_id'}
    assert '__entry_copy_plan' not in json.dumps(public)
    assert 'characteristic_record' not in json.dumps(public)
    assert 'effect_payload' not in public and 'resolving_item' not in public


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_real_current_face_is_copied_without_gaining_physical_faces(seat):
    from rules_engine.card_faces import apply_transform_face
    names = {seat: ['Sculpting Steel', 'Liquimetal Coating'], 3-seat: ['Delver of Secrets // Insectile Aberration']}
    state = position(names[1], names[2], seat)
    target = next(card.id for card in state.cards.values() if card.owner == 3-seat and card.card_faces)
    card = state.cards[target]
    for player in state.players.values():
        for zone in ('hand', 'library'):
            if target in getattr(player, zone): getattr(player, zone).remove(target)
    card.move_to_zone(Zone.BATTLEFIELD)
    card.controller = 3-seat
    state.players[3-seat].battlefield.append(target)
    apply_transform_face(card, 1)  # Existing face mechanism; not an end-to-end Delver trigger claim.
    coating = place(state, 'Liquimetal Coating', Zone.BATTLEFIELD, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_ability',
        'card_id': coating, 'ability_index': 0, 'targets': {'target_card_id': target}})
    assert resolve_top_of_stack(state)
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    state = choose(snapshot(state), seat, target)
    assert state.cards[steel].name == 'Insectile Aberration'
    assert state.cards[steel].card_faces == [] and state.cards[steel].layout == 'normal'
    assert state.cards[target].selected_face_index == 1
    assert state.cards[steel].power == 3 and state.cards[steel].toughness == 2
