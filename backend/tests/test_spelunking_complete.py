"""Canonical controlled mechanics, not games/AI; JSON restore is not SQL restart."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random

import pytest

from api_contracts import LandAction
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, object_incarnation, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.card_types import printed_card_types
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import compile_optional_land_instruction


FIXTURE = Path(__file__).parent / 'fixtures/spelunking_complete'
encoded = (FIXTURE/'facts.json').read_bytes()
PROVENANCE = json.loads((FIXTURE/'provenance.json').read_text())
assert sha256(encoded).hexdigest() == PROVENANCE['facts_sha256']
FACTS = json.loads(encoded)
for name, row in FACTS.items():
    assert sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == PROVENANCE['cards'][name]['object_sha256']


def add(state, name, seat, zone):
    raw = FACTS[name]
    if raw.get('object') == 'card':
        sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7311)
        card = deepcopy(next(iter(sample.cards.values())))
        card.id, card.owner, card.controller = state.allocate_object_id(), seat, seat
        card.move_to_zone(zone)
    else:
        # The provenance distinguishes the complete printed row from full raw JSON.
        card = CardInstance(id=state.allocate_object_id(), name=name, owner=seat, controller=seat,
            zone=zone, mana_cost=raw['mana_cost'], oracle_text=raw['oracle_text'],
            type_line=raw['type_line'], types=printed_card_types(raw['type_line']),
            keywords=deepcopy(raw.get('keywords', [])), colors=deepcopy(raw.get('colors', [])))
    assert (card.name, card.mana_cost, card.oracle_text, card.type_line) == tuple(
        raw[k] for k in ('name', 'mana_cost', 'oracle_text', 'type_line'))
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        card.summoning_sick = False
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def position(seat, *, static=False, manual=False, land='Hidden Courtyard',
             existing_cave=False, draw_name=None, extras=()):
    deck = [{**FACTS['Forest'], 'card_name': 'Forest', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7311)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step, state.turn = Step.PRECOMBAT_MAIN, 5
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = manual
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.mana_pool = {}
    for _ in range(8):
        add(state, 'Forest', seat, Zone.BATTLEFIELD)
    source = add(state, 'Spelunking', seat, Zone.BATTLEFIELD if static else Zone.HAND)
    selected = add(state, land, seat, Zone.HAND) if land is not None else None
    if existing_cave:
        add(state, 'Hidden Courtyard', seat, Zone.BATTLEFIELD)
    other = [add(state, name, seat, zone) for name, zone in extras]
    drawn = add(state, draw_name, seat, Zone.LIBRARY) if draw_name else None
    return state, source, selected, drawn, other


def act(state, seat, action):
    before, supplied = serialize_match_snapshot(state), deepcopy(action)
    rng, local = random.getstate(), state.rng.getstate()
    try:
        result = checked_action(state, RulesEngine(), seat, action)
    finally:
        assert serialize_match_snapshot(state) == before and action == supplied
        assert random.getstate() == rng and state.rng.getstate() == local
    return result


def settle(state):
    for _ in range(48):
        if state.pending_mechanic_choice or state.pending_replacement_choice or not state.stack:
            return state
        assert not state.pending_trigger_order, 'No guessed trigger ordering'
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Bounded native settlement exhausted')


def cast(state, seat, source, targets=None):
    paid = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                            'cost_choice': {'id': 'base'}, 'targets': targets or {}})
    assert paid.cards[source].zone == Zone.STACK
    return settle(paid)


def restore(state):
    before = serialize_match_snapshot(state)
    encoded = json.dumps(before, sort_keys=True, separators=(',', ':'), allow_nan=False)
    result = deserialize_match_snapshot(json.loads(encoded))
    assert json.dumps(serialize_match_snapshot(result), sort_keys=True, separators=(',', ':'), allow_nan=False) == encoded
    assert result.rng.getstate() == state.rng.getstate()
    return result


def choose_land(state, seat, cid=None):
    assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
    return settle(act(state, seat, {'type': 'choose_mechanic', 'card_ids': [] if cid is None else [cid]}))


def body():
    return FACTS['Spelunking']['oracle_text'].splitlines()[0].split(', ', 1)[1]


def test_complete_canonical_instruction_and_existing_period_form():
    expected = ('effect_sequence', {'effects': [
        {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
        {'effect_key': 'put_land_from_hand', 'payload': {'optional': True, 'tapped': False,
            'gain_life_if_put_subtype': {'subtype': 'Cave', 'amount': 4}}},
    ]})
    assert compile_optional_land_instruction(body()) == expected
    ordinary = compile_optional_land_instruction('Draw two cards. You may put a land card from your hand onto the battlefield tapped.')
    assert ordinary == ('effect_sequence', {'effects': [
        {'effect_key': 'draw_cards', 'payload': {'amount': 2}},
        {'effect_key': 'put_land_from_hand', 'payload': {'optional': True, 'tapped': True}},
    ]})


@pytest.mark.parametrize('suffix', [' Then draw a card.', ' and scry 1.', ' (Unknown instruction.)'])
def test_protocol_unknown_complete_suffix_never_grants_partial_draw(suffix):
    assert compile_optional_land_instruction(body()+suffix) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected,existing', [('cave', False), ('noncave', False),
                                             ('decline', False), ('decline', True), ('noncave', True)])
def test_paid_draw_then_deliberate_zero_or_one_land_and_only_this_way_life(seat, selected, existing):
    state, source, land, _, _ = position(seat, land='Hidden Courtyard' if selected == 'cave' else 'Forest', existing_cave=existing)
    hand, library, life = len(state.players[seat].hand), len(state.players[seat].library), state.players[seat].life
    state = cast(state, seat, source)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert len(state.players[seat].hand) == hand and len(state.players[seat].library) == library-1
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_from_hand' and pending['min_count'] == 0 and land in pending['options']
    for view in (serialize_match(state), serialize_match(state, look_players=(3-seat,))):
        assert set(view['pending_mechanic_choice']) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    assert not RulesEngine().legal_moves(state, 3-seat)
    state = choose_land(restore(state), seat, None if selected == 'decline' else land)
    assert state.cards[land].zone == (Zone.HAND if selected == 'decline' else Zone.BATTLEFIELD)
    assert state.players[seat].life == life + (4 if selected == 'cave' else 0)
    if selected != 'decline':
        assert not state.cards[land].tapped and state.land_entries_this_turn[seat] == 1
    assert state.players[seat].lands_played_this_turn == 0
    assert len(state.players[seat].library) == library-1
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('drawn_land', [True, False])
def test_drawn_land_is_eligible_but_no_eligible_land_still_draws(seat, drawn_land):
    state, source, _, drawn, _ = position(seat, land=None,
        draw_name='Hidden Courtyard' if drawn_land else 'Spelunking')
    state = cast(state, seat, source)
    assert drawn in state.players[seat].hand and state.players[seat].life == 20
    if drawn_land:
        assert drawn in state.pending_mechanic_choice['options']
        state = choose_land(state, seat, drawn)
        assert state.players[seat].life == 24
    else:
        assert state.pending_mechanic_choice is None and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('manual', [False, True])
def test_plain_tapland_source_absent_or_not_yet_entered_is_not_a_static_source(seat, manual):
    state, source, land, _, _ = position(seat, manual=manual)
    state = act(state, seat, {'type': 'play_land', 'card_id': land})
    assert state.cards[source].zone == Zone.HAND
    assert state.cards[land].zone == Zone.BATTLEFIELD and state.cards[land].tapped
    with pytest.raises(ActionRejected):
        act(restore(state), seat, {'type': 'play_land', 'card_id': source, 'entry_choice': 'untapped'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('manual', [False, True])
def test_ordinary_tapland_static_auto_default_or_deliberate_replacement_order(seat, manual):
    state, _, land, _, _ = position(seat, static=True, manual=manual)
    moves = [m for m in RulesEngine().legal_moves(state, seat) if m.get('type') == 'play_land' and m.get('card_id') == land]
    if not manual:
        result = act(state, seat, {'type': 'play_land', 'card_id': land})
        assert result.cards[land].zone == Zone.BATTLEFIELD and not result.cards[land].tapped
    else:
        assert {m.get('entry_choice') for m in moves} == {'tapped', 'untapped'}
        for choice in ('tapped', 'untapped'):
            request = {'type': 'play_land', 'card_id': land, 'entry_choice': choice}
            LandAction.model_validate(request)
            result = act(restore(state), seat, request)
            assert result.cards[land].tapped is (choice == 'tapped')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('static', [False, True])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life', 'untapped'])
def test_shock_payment_and_untapped_order_remain_distinct_native_choices(seat, static, choice):
    state, _, land, _, _ = position(seat, static=static, manual=True, land='Sacred Foundry')
    request = {'type': 'play_land', 'card_id': land, 'entry_choice': choice}
    if choice == 'untapped' and not static:
        with pytest.raises(ActionRejected):
            act(state, seat, request)
        return
    LandAction.model_validate(request)
    result = act(state, seat, request)
    assert result.players[seat].life == (18 if choice == 'pay_two_life' else 20)
    assert result.cards[land].tapped is (choice == 'tapped')


@pytest.mark.parametrize('seat', [1, 2])
def test_effect_entry_pause_json_actor_and_selected_reference_exact_once(seat):
    state, source, land, _, _ = position(seat, manual=True, land='Sacred Foundry')
    library = len(state.players[seat].library)
    state = cast(state, seat, source)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': [land]})
    state = choose_land(state, seat, land)
    assert state.pending_mechanic_choice['kind'] == 'land_entry' and state.cards[land].zone == Zone.HAND
    assert set(state.pending_mechanic_choice['options']) == {'tapped', 'untapped', 'pay_two_life'}
    result = settle(act(restore(state), seat, {'type': 'choose_mechanic', 'choice_id': 'untapped'}))
    assert result.cards[land].zone == Zone.BATTLEFIELD and not result.cards[land].tapped
    assert result.players[seat].life == 20 and len(result.players[seat].library) == library-1
    assert result.land_entries_this_turn[seat] == 1
    with pytest.raises(ActionRejected):
        act(result, seat, {'type': 'choose_mechanic', 'choice_id': 'untapped'})


@pytest.mark.parametrize('seat', [1, 2])
def test_mandatory_draw_replacement_pause_does_not_replay_draw_or_skip_land(seat):
    state, source, _, _, refs = position(seat, manual=True,
        extras=[('Thought Reflection', Zone.BATTLEFIELD)]*2)
    library, hand = len(state.players[seat].library), len(state.players[seat].hand)
    state = cast(state, seat, source)
    assert state.pending_replacement_choice['resume_kind'] == 'draw_event'
    assert state.pending_mechanic_choice is None
    state = settle(act(restore(state), seat, {'type': 'choose_replacement', 'replacement_source_id': refs[0]}))
    assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
    assert len(state.players[seat].library) == library-4 and len(state.players[seat].hand) == hand+3
    state = choose_land(state, seat)
    assert len(state.players[seat].library) == library-4 and not state.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_conditional_life_replacement_pauses_only_after_the_selected_cave_entered(seat):
    state, source, land, _, refs = position(seat, manual=True,
        extras=[('Boon Reflection', Zone.BATTLEFIELD)]*2)
    state = cast(state, seat, source)
    state = choose_land(state, seat, land)
    if state.pending_mechanic_choice:
        assert state.pending_mechanic_choice['kind'] == 'land_entry'
        state = settle(act(state, seat, {'type': 'choose_mechanic', 'choice_id': 'untapped'}))
    assert state.cards[land].zone == Zone.BATTLEFIELD
    assert state.pending_replacement_choice['resume_kind'] == 'gain_event'
    receipt = state.pending_replacement_choice['gain_payload']['__put_land_receipt']
    assert receipt['card_id'] == land and receipt['matched_subtype'] is True
    assert receipt['entry_reference'] == [object_incarnation(state.cards[land]), state.cards[land].zone_change_sequence]
    assert receipt['entry_reference'][1] == receipt['from_reference'][1] + 1
    state = settle(act(restore(state), seat, {'type': 'choose_replacement', 'replacement_source_id': refs[0]}))
    assert state.players[seat].life == 36 and state.land_entries_this_turn[seat] == 1
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('static', [False, True])
def test_protocol_effect_put_tapped_without_intrinsic_competitor(seat, static):
    state, _, land, _, _ = position(seat, static=static, manual=True, land='Forest')
    original = serialize_match_snapshot(state)
    projected = deepcopy(state)
    resolve_effect(projected, seat, 'put_land_from_hand', {
        'land_id': land, '__land_reference': [object_incarnation(state.cards[land]), state.cards[land].zone_change_sequence],
        'optional': True, 'tapped': True})
    assert projected.cards[land].zone == Zone.BATTLEFIELD
    assert projected.cards[land].tapped is (not static)
    assert serialize_match_snapshot(state) == original


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_printed_ability_suppression_removes_static_untapped_entry(seat):
    state, source, land, _, spells = position(seat, static=True,
        extras=[('Song of the Dryads', Zone.HAND)])
    state = cast(state, seat, spells[0], {'target_card_id': source})
    assert printed_abilities_suppressed(state, source)
    state = act(state, seat, {'type': 'play_land', 'card_id': land})
    assert state.cards[land].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_protocol_stale_selected_land_cannot_be_rebound_after_leave_reenter(seat):
    state, source, land, _, _ = position(seat)
    state = cast(state, seat, source)
    assert state.pending_mechanic_choice['kind'] == 'land_from_hand'
    # Explicit stale-request protocol, not an invented native zone-change outcome.
    state.cards[land].move_to_zone(Zone.EXILE)
    state.cards[land].move_to_zone(Zone.HAND)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'card_ids': [land]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life', 'untapped'])
def test_automatic_mode_preserves_explicit_shock_payment_and_order_choices(seat, choice):
    state, _, land, _, _ = position(seat, static=True, manual=False, land='Sacred Foundry')
    state = act(state, seat, {'type': 'play_land', 'card_id': land, 'entry_choice': choice})
    assert state.players[seat].life == (18 if choice == 'pay_two_life' else 20)
    assert state.cards[land].tapped is (choice == 'tapped')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life', 'untapped'])
def test_automatic_mode_effect_shock_pause_keeps_deliberate_choice_and_labels(seat, choice):
    state, source, land, _, _ = position(seat, manual=False, land='Sacred Foundry')
    state = choose_land(cast(state, seat, source), seat, land)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_entry' and set(pending['options']) == {'tapped', 'pay_two_life', 'untapped'}
    assert 'Enter untapped' in pending['option_labels']['untapped']
    state = settle(act(restore(state), seat, {'type': 'choose_mechanic', 'choice_id': choice}))
    assert state.players[seat].life == (18 if choice == 'pay_two_life' else 20)
    assert state.cards[land].zone == Zone.BATTLEFIELD and state.cards[land].tapped is (choice == 'tapped')
    assert state.land_entries_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_new_untapped_literal_is_rejected_when_not_natively_offered(seat):
    state, _, land, _, _ = position(seat)
    request = {'type': 'play_land', 'card_id': land, 'entry_choice': 'untapped'}
    LandAction.model_validate(request)
    with pytest.raises(ActionRejected):
        act(state, seat, request)


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_controlled_untap_source_does_not_change_our_entry(seat):
    state, _, land, _, _ = position(seat)
    add(state, 'Spelunking', 3-seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'play_land', 'card_id': land})
    assert state.cards[land].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_conditional_gain_uses_existing_canonical_life_replacement(seat):
    state, source, land, _, _ = position(seat)
    add(state, 'Tainted Remedy', 3-seat, Zone.BATTLEFIELD)
    state = choose_land(cast(state, seat, source), seat, land)
    assert state.cards[land].zone == Zone.BATTLEFIELD and state.players[seat].life == 16


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_canonical_gain_prevention_is_not_bypassed_by_the_selected_receipt(seat):
    state, source, land, _, spells = position(seat, extras=[('Skullcrack', Zone.HAND)])
    add(state, 'Mountain', seat, Zone.BATTLEFIELD)
    add(state, 'Mountain', seat, Zone.BATTLEFIELD)
    state = cast(state, seat, spells[0], {'target_player': 3-seat})
    state = choose_land(cast(state, seat, source), seat, land)
    assert state.cards[land].zone == Zone.BATTLEFIELD and state.players[seat].life == 20
