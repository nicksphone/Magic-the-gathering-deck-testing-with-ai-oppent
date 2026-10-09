"""Real activation hint surfaces, retained sources and announced X semantics."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine import oracle_effects, targeting
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_counter_activation_admission_audit import board
from tests.test_generic_protection_damage import position, raw_card, FIREWALKER
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_self_graveyard_replacement_audit import act, restart, snap

PATH = Path(__file__).parent / 'fixtures/ability_hint_copy/goblin-dynamo.json'
PROVENANCE = json.loads(PATH.with_name(PATH.name+'.provenance.json').read_text())
assert hashlib.sha256(PATH.read_bytes()).hexdigest() == PROVENANCE['sha256']
DYNAMO = json.loads(PATH.read_text())
assert DYNAMO['oracle_id'] and DYNAMO['name'] == 'Goblin Dynamo'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [1, 3])
def test_actual_hint_copy_is_pure_and_distinct_from_real_protection_source(seat, count, monkeypatch, tmp_path):
    state, source_id, target = board(seat, counters=count)
    action = {'type': 'activate_ability', 'card_id': source_id, 'ability_index': 1,
              'targets': {'target_player': 3-seat} if count == 1 else {'target_card_id': target}}
    state = act(state, seat, action)
    state = restart(state, tmp_path, 'actual-stack-before-hint-observation')
    before_lki = deepcopy(state.stack[0].payload.get('__source_lki'))
    observations = []
    phase = {'in_hint': False}
    original_hint = oracle_effects.inspect_target_hints
    original_protection = targeting.validate_protection_targets

    def inspect(candidate, surface, controller, announced=None, *, source_kind='spell'):
        if surface.id != source_id:
            return original_hint(candidate, surface, controller, announced, source_kind=source_kind)
        assert source_kind == 'activated'
        before = snap(candidate)
        assert surface is not candidate.cards[source_id]
        assert surface.mana_cost == ''
        assert candidate.cards[source_id].mana_cost == '{X}{X}'
        assert surface.oracle_text == 'It deals 1 damage to any target.'
        assert announced == action['targets'] and 'x_value' not in announced
        phase['in_hint'] = True
        try:
            result = original_hint(candidate, surface, controller, announced, source_kind=source_kind)
        finally:
            phase['in_hint'] = False
        assert not result.get('requires_x_value')
        assert snap(candidate) == before
        observations.append(('hint', id(surface)))
        return result

    def protection(candidate, source, announced, *args, **kwargs):
        if source.id == source_id and not phase['in_hint']:
            assert source.mana_cost == '{X}{X}'
            assert kwargs.get('source_lki') == before_lki
            assert id(source) != observations[-1][1]
            before = snap(candidate)
            result = original_protection(candidate, source, announced, *args, **kwargs)
            assert snap(candidate) == before
            observations.append(('protection', id(source)))
            return result
        return original_protection(candidate, source, announced, *args, **kwargs)

    monkeypatch.setattr(oracle_effects, 'inspect_target_hints', inspect)
    monkeypatch.setattr(targeting, 'validate_protection_targets', protection)
    state = passes(state)  # Genuine priority passes, repeated through checked_action.
    assert any(kind == 'hint' for kind, _ in observations)
    assert any(kind == 'protection' for kind, _ in observations)
    assert state.cards[source_id].mana_cost == '{X}{X}'
    if count == 1:
        assert state.cards[source_id].zone == Zone.GRAVEYARD
        assert state.players[3-seat].life == 19
    else:
        assert state.cards[target].counters['__damage_marked'] == 1
    assert_private(state)
    restart(state, tmp_path, 'actual-hint-only-copy-resolution')


def dynamo_board(seat):
    state, target = position(seat, 'White Knight')
    source = raw_card(state, DYNAMO, seat, Zone.BATTLEFIELD)
    source.summoning_sick = False  # Controlled retained board, not cast/entry certification.
    state.players[seat].mana_pool = {'R': 1, 'C': 3}
    return state, source.id, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected_x', [0, 2, 3])
def test_canonical_x_cost_sacrifice_keeps_selected_x_real_lki_and_damage(seat, selected_x, tmp_path):
    state, source, _ = dynamo_board(seat)
    reference = object_incarnation(state.cards[source])
    sequence = state.cards[source].zone_change_sequence
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
                             'targets': {'target_player': 3-seat, 'x_value': selected_x}})
    assert state.players[seat].mana_pool.get('R', 0) == 0
    assert state.players[seat].mana_pool.get('C', 0) == 3-selected_x
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[source].zone_change_sequence == sequence+1
    assert state.players[seat].graveyard.count(source) == 1
    item = state.stack[-1]
    assert item.source_card_id == source and item.controller == seat and item.effect_key == 'deal_damage'
    assert item.payload['amount'] == selected_x
    assert item.payload['__announced_targets'] == {'target_player': 3-seat, 'x_value': selected_x}
    lki = deepcopy(item.payload['__source_lki'])
    assert lki['battlefield_incarnation'] == reference and lki['color_names'] == ['red']
    state = passes(restart(state, tmp_path, 'canonical-paid-x-and-sacrifice'))
    assert not state.stack and state.players[3-seat].life == 20-selected_x
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert_private(state)
    restart(state, tmp_path, 'canonical-selected-x-resolved')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('problem', ['missing', 'negative', 'boolean', 'unpayable', 'protected'])
def test_canonical_x_invalid_activation_never_taps_sacrifices_or_pays(seat, problem):
    state, source, _ = dynamo_board(seat)
    targets = {'target_player': 3-seat, 'x_value': 2}
    if problem == 'missing':
        targets.pop('x_value')
    elif problem in {'negative', 'boolean', 'unpayable'}:
        targets['x_value'] = {'negative': -1, 'boolean': True, 'unpayable': 4}[problem]
    else:
        target = raw_card(state, FIREWALKER, 3-seat, Zone.BATTLEFIELD)
        targets = {'target_card_id': target.id, 'x_value': 2}
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1, 'targets': targets})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_nonmatching_protection_receives_paid_canonical_x_damage(seat, tmp_path):
    state, source, target = dynamo_board(seat)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 1,
                             'targets': {'target_card_id': target, 'x_value': 2}})
    assert state.cards[target].zone == Zone.BATTLEFIELD
    state = passes(restart(state, tmp_path, 'red-source-lki-nonmatching-protection'))
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[seat].mana_pool.get('C', 0) == 1
    assert_private(state)
