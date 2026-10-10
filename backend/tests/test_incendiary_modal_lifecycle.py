"""Paid full-body frames and declared native lifecycle seams, without SQL."""
from copy import deepcopy
import json
import pickle

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.oracle_effects import _infer_closed_damage_instruction
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_incendiary_modal_boundaries import FIX, WALKER, permanent
from tests.test_incendiary_modal_root import MODES, PAIRS, RAW, announced, position, reload
from tests import test_soulscar_preflight_rules_audit as damage


def cast(state, seat, source, targets):
    return checked_action(state, RulesEngine(), seat,
                          {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['creature', 'basic_land', 'conflicting_target',
                                'protected_walker', 'protected_land', 'shroud_walker'])
def test_complete_checked_boundary_rejects_illegal_native_recipient_before_payment(seat, case):
    state, source = position(seat)
    walker = permanent(state, WALKER, 3-seat)
    targets = announced(seat, (0, 2))
    targets['mode_targets'][MODES[0]] = {'target_card_id': walker.id}
    if case == 'creature':
        targets['mode_targets'][MODES[0]] = {'target_card_id': f'creature-{3-seat}'}
    elif case == 'basic_land':
        basic = state.players[3-seat].hand.pop()
        state.cards[basic].move_to_zone(Zone.BATTLEFIELD)
        state.players[3-seat].battlefield.append(basic)
        targets['mode_targets'][MODES[2]] = {'target_card_id': basic}
    elif case == 'conflicting_target':
        targets['mode_targets'][MODES[0]]['target_player'] = 3-seat
    else:
        target = 'nonbasic' if case == 'protected_land' else walker.id
        add_keyword_effect(state, target, ['shroud' if case == 'shroud_walker' else 'protection from red'])
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pair', PAIRS)
def test_paid_all_pairs_resolve_in_printed_not_selection_order_and_query_root_pure(seat, pair, monkeypatch):
    state, source = position(seat)
    state = cast(state, seat, source, announced(seat, pair))
    assert not any(state.players[seat].mana_pool.values())
    frame = deepcopy(state.stack[-1])
    state = reload(state)
    before = pickle.dumps(state)
    RulesEngine().legal_moves(state, seat)
    assert pickle.dumps(state) == before
    from effects import registry
    original = registry.resolve_effect
    observed = []
    def observe(current, controller, key, payload):
        observed.append(key)
        return original(current, controller, key, payload)
    monkeypatch.setattr(registry, 'resolve_effect', observe)
    assert resolve_top_of_stack(state)
    expected = [effect['effect_key'] for effect in frame.payload['effects']]
    assert observed[:len(expected)] == expected
    assert frame.controller == seat and frame.source_card_id == source.id
    assert state.cards[source.id].oracle_text == RAW['oracle_text']
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['departed', 'returned', 'protected'])
def test_paid_target_reference_recheck_keeps_other_selected_mode(seat, change):
    state, source = position(seat)
    state = cast(state, seat, source, announced(seat, (0, 2)))
    # Explicit native zone/protection seam after genuine payment, not an invented spell.
    if change == 'protected':
        add_keyword_effect(state, 'nonbasic', ['protection from red'])
    else:
        resolve_effect(state, seat, 'exile', {'target_card_id': 'nonbasic'})
        if change == 'returned':
            state.players[3-seat].exile.remove('nonbasic')
            state.cards['nonbasic'].move_to_zone(Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.append('nonbasic')
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 16
    assert state.cards['nonbasic'].zone == (Zone.EXILE if change == 'departed' else Zone.BATTLEFIELD)
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_copy_from_opponent_retains_full_surface_controller_source_and_target_receipts(seat):
    state, source = position(seat)
    state = cast(state, seat, source, announced(seat, (0, 2)))
    original = deepcopy(state.stack[-1])
    raw = json.loads((FIX / 'coupled_targets/twincast.json').read_text())
    copy_card = permanent(state, raw, 3-seat)
    state.players[3-seat].battlefield.remove(copy_card.id)
    copy_card.move_to_zone(Zone.HAND)
    state.players[3-seat].hand.append(copy_card.id)
    state.players[3-seat].mana_pool = {'U': 2}
    state.priority_player = 3-seat
    state = cast(state, 3-seat, copy_card, {'target_stack_id': original.id})
    assert not any(state.players[3-seat].mana_pool.values())
    state = reload(state)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    while state.pending_mechanic_choice:
        pending = state.pending_mechanic_choice
        assert pending['player_id'] == 3-seat and 'keep' in pending['options']
        state = checked_action(reload(state), RulesEngine(), 3-seat,
                               {'type': 'choose_mechanic', 'card_ids': ['keep']})
    copied = state.stack[-1]
    assert copied.controller == 3-seat and copied.source_card_id == source.id
    assert copied.payload['__copied_card']['oracle_text'] == RAW['oracle_text']
    assert copied.payload['__announced_targets'] == original.payload['__announced_targets']
    assert copied.payload['__announced_target_references'] == original.payload['__announced_target_references']
    assert state.stack[0] == original
    state = reload(state)
    assert resolve_top_of_stack(state) and state.players[3-seat].life == 16
    assert state.cards[source.id].zone == Zone.STACK
    assert resolve_top_of_stack(state) and state.players[3-seat].life == 12
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['conversion', 'doubling'])
def test_paid_broadcast_mode_pauses_resumes_native_damage_replacement_once(seat, first):
    state, source = position(seat)
    mage = damage.add(state, 'Soul-Scar Mage', seat)
    furnace = damage.add(state, 'Furnace of Rath', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 3, 'C': 1}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': furnace, 'targets': {}})
    assert not any(state.players[seat].mana_pool.values())
    state = damage.finish(state)
    furnace = next(cid for cid in state.players[seat].battlefield
                   if state.cards[cid].name == 'Furnace of Rath')
    state.players[seat].mana_pool = {'R': 2, 'C': 3}
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state = cast(state, seat, source, announced(seat, (1, 3)))
    assert not any(state.players[seat].mana_pool.values())
    while state.stack[-1].source_card_id != source.id:
        assert state.stack[-1].source_card_id == mage
        assert state.stack[-1].effect_key == 'temporary_pt_buff'
        assert resolve_top_of_stack(state)
    frame = deepcopy(state.stack[-1])
    assert frame.effect_key == 'effect_sequence'
    assert not resolve_top_of_stack(state)
    pending = state.pending_replacement_choice
    assert pending and pending['player_id'] == 3-seat
    assert {mage, furnace} <= {option['source_id'] for option in pending['options']}
    state = reload(state)
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'choose_replacement', 'replacement_source_id': mage})
    assert pickle.dumps(state) == before
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'choose_replacement',
                           'replacement_source_id': mage if first == 'conversion' else furnace})
    if state.pending_replacement_choice:
        state = checked_action(reload(state), RulesEngine(), 3-seat,
                               {'type': 'choose_replacement', 'replacement_source_id': mage})
    state = damage.finish(reload(state))
    target = state.cards[f'creature-{3-seat}']
    counters = target.counters if target.zone == Zone.BATTLEFIELD else target.last_known_battlefield['counters']
    assert counters.get('-1/-1') == (2 if first == 'conversion' else 4)
    assert state.discards_this_turn == {1: 7, 2: 7}
    assert not state.pending_replacement_choice and not state.stack
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert frame.controller == seat and frame.source_card_id == source.id
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_native_zero_discard_ledger_preserved_by_paid_nonwheel_modes_and_restore(seat):
    state, source = position(seat)
    before = dict(state.discards_this_turn)
    assert before == {1: 0, 2: 0}
    state = cast(state, seat, source, announced(seat, (0, 2)))
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 16 and state.cards['nonbasic'].zone == Zone.GRAVEYARD
    assert state.discards_this_turn == before
    reload(state)


@pytest.mark.parametrize('mode_index', range(4))
def test_internal_single_mode_probe_compiles_only_after_complete_offered_body_validation(mode_index):
    key, payload = _infer_closed_damage_instruction(RAW['oracle_text'], RAW['name'],
                                                    {'mode_text': MODES[mode_index], 'mode_texts': []})
    assert key == ['deal_damage', 'damage_each_creature', 'destroy_permanent', 'each_player_discard'][mode_index]
    assert '__unsupported_instruction' not in payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selection', ['single_list', 'three', 'missing', 'single_probe'])
def test_external_mode_count_contract_rejects_before_payment_even_when_internal_probe_compiles(seat, selection):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    if selection == 'single_probe':
        targets = {'mode_text': MODES[0], 'target_player': 3-seat}
    else:
        chosen = [MODES[0]] if selection == 'single_list' else MODES[:3] if selection == 'three' else []
        targets['mode_texts'] = chosen
        targets['mode_targets'] = {mode: targets['mode_targets'].get(mode, {}) for mode in chosen}
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('selector', ['mode_text', 'mode_texts', 'mode_targets', 'selected_face_index'])
def test_compiler_rejects_nested_mode_selector_alias_even_when_native_target_checks_are_called(selector):
    targets = announced(1, (0, 2))
    targets['mode_targets'][MODES[0]][selector] = MODES[2]
    result = _infer_closed_damage_instruction(RAW['oracle_text'], RAW['name'], targets)
    assert result == ('noop', {'__unsupported_instruction': RAW['oracle_text']})


def test_closed_compiler_binds_generic_source_name_not_named_card_dispatch():
    name = 'Declared parser-only source'
    text = RAW['oracle_text'].replace(RAW['name'], name)
    modes = [mode.replace(RAW['name'], name) for mode in MODES]
    targets = {'mode_texts': list(reversed(modes[:2])), 'mode_targets': {
        modes[0]: {'target_player': 2}, modes[1]: {}}}
    key, payload = _infer_closed_damage_instruction(text, name, targets)
    assert key == 'effect_sequence'
    assert payload['effects'] == [
        {'effect_key': 'deal_damage', 'payload': {'target_player': 2, 'amount': 4}, 'mode_text': modes[0]},
        {'effect_key': 'damage_each_creature', 'payload': {'amount': 2}, 'mode_text': modes[1]},
    ]


@pytest.mark.parametrize('header', ['Prelude. Choose two', 'Choose three', 'Choose two extra'])
def test_closed_family_unknown_envelope_does_not_compile_selected_known_prefix(header):
    body = RAW['oracle_text'].replace('Choose two', header, 1)
    result = _infer_closed_damage_instruction(body, RAW['name'], announced(1, (0, 1)))
    assert result == ('noop', {'__unsupported_instruction': body})
