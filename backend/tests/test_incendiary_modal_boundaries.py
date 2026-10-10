"""Separate extensions to the immutable 49-case public full-body contracts."""
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import validate_mode_targets
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.oracle_effects import _infer_closed_damage_instruction
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_incendiary_modal_root import MODES, RAW, announced, position, reload


FIX = Path(__file__).parent / 'fixtures'
WALKER = next(row for row in map(json.loads, (FIX / 'noncreature_sba_caller/canonical.jsonl').read_text().splitlines())
              if row['name'] == 'Jace Beleren')


def permanent(state, raw, seat):
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=7181)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case,legal', [('player', True), ('walker', True), ('creature', False),
    ('basic_land', False), ('nonbasic_land', True), ('conflicting_target', False),
    ('protected_walker', False), ('protected_land', False), ('shroud_walker', False)])
def test_native_mode_validator_enforces_type_nonbasic_and_protection_without_compiler(seat, case, legal):
    state, source = position(seat)
    walker = permanent(state, WALKER, 3-seat)
    targets = announced(seat, (0, 2))
    if case in ('walker', 'protected_walker', 'shroud_walker', 'conflicting_target'):
        targets['mode_targets'][MODES[0]] = {'target_card_id': walker.id}
        if case == 'conflicting_target':
            targets['mode_targets'][MODES[0]]['target_player'] = 3-seat
        elif case != 'walker':
            add_keyword_effect(state, walker.id, ['shroud' if case == 'shroud_walker' else 'protection from red'])
    elif case == 'creature':
        targets['mode_targets'][MODES[0]] = {'target_card_id': f'creature-{3-seat}'}
    elif case == 'basic_land':
        basic = state.players[3-seat].hand.pop()
        state.cards[basic].move_to_zone(Zone.BATTLEFIELD)
        state.players[3-seat].battlefield.append(basic)
        targets['mode_targets'][MODES[2]] = {'target_card_id': basic}
    elif case == 'protected_land':
        add_keyword_effect(state, 'nonbasic', ['protection from red'])
    before = pickle.dumps(state)
    valid, reason = validate_mode_targets(state, source, seat, targets)
    assert valid is legal, reason
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_full_body_damage_targets_real_canonical_planeswalker_not_creature_or_player(seat):
    state, source = position(seat)
    walker = permanent(state, WALKER, 3-seat)
    assert walker.oracle_text == WALKER['oracle_text'] and walker.loyalty == 3
    targets = announced(seat, (0, 2))
    targets['mode_targets'][MODES[0]] = {'target_card_id': walker.id}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    assert state.cards[source.id].zone == Zone.STACK
    assert all(amount == 0 for amount in state.players[seat].mana_pool.values())
    state = reload(state)
    assert resolve_top_of_stack(state)
    state = reload(state)
    assert state.cards[walker.id].zone == Zone.GRAVEYARD
    assert state.cards['nonbasic'].zone == Zone.GRAVEYARD
    assert all(player.life == 20 for player in state.players.values())
    assert not any(state.cards[f'creature-{pid}'].counters.get('__damage_marked') for pid in (1, 2))


@pytest.mark.parametrize('seat', [1, 2])
def test_native_mode_validator_does_not_let_nested_mode_alias_change_target_restrictions(seat):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    targets['mode_targets'][MODES[0]] = {'mode_text': MODES[2], 'target_card_id': 'nonbasic'}
    before = pickle.dumps(state)
    valid, reason = validate_mode_targets(state, source, seat, targets)
    assert not valid, reason
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('alias', ['unknown', 'punctuation', 'case', 'nested_mode_override'])
def test_forged_aliases_reject_atomic_checked_cast_not_because_outer_compiler_falls_back(seat, alias):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    if alias == 'nested_mode_override':
        targets['mode_targets'][MODES[0]] = {'mode_text': MODES[2], 'target_card_id': 'nonbasic'}
    else:
        bad = 'Draw a card' if alias == 'unknown' else MODES[0] + '.' if alias == 'punctuation' else MODES[0].swapcase()
        targets['mode_texts'] = [bad, MODES[2]]
        targets['mode_targets'] = {bad: {'target_player': 3-seat}, MODES[2]: {'target_card_id': 'nonbasic'}}
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('suffix', [' Draw a card.', ' and each player.', ' if you control an Island.'])
@pytest.mark.parametrize('single_probe', [False, True])
def test_unknown_unselected_tail_still_rejects_full_envelope_and_internal_single_probe(suffix, single_probe):
    # Explicit synthetic parser input; full canonical runtime source is never altered.
    body = RAW['oracle_text'] + suffix
    selection = {'mode_text': MODES[0], 'target_player': 2} if single_probe else announced(1, (0, 1))
    key, payload = _infer_closed_damage_instruction(body, RAW['name'], selection)
    assert key == 'noop' and payload['__unsupported_instruction'] == body
