"""Closed-body compiler contracts and genuine paid episodes; no resolver stand-in."""
import sqlite3
import socket

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import _infer_closed_damage_instruction, infer_effect_from_oracle, inspect_target_hints
from tests import test_soulscar_protection_boundaries as boundary

base = boundary.base
prior = boundary.prior


@pytest.mark.parametrize('family', ['prevention', 'broadcast'])
@pytest.mark.parametrize('tail', [' Draw a card.', ' Then exile it.', ' and each player.',
    ' if you control an Island.', ' instead.', ' This damage cannot be prevented.',
    ' except creatures with flying.', ' until end of turn.'])
def test_recognized_complete_body_rejects_unknown_tail(family, tail):
    text = ('Prevent the next 3 damage that would be dealt to any target this turn.'
            if family == 'prevention' else base.CARDS['Pyroclasm']['oracle_text'])
    # Adversarial parser input only, never an altered card/Oracle runtime fixture.
    key, payload = _infer_closed_damage_instruction(text+tail, 'Pyroclasm', {'target_player': 2})
    assert key == 'noop' and payload['__unsupported_instruction'] == text+tail


@pytest.mark.parametrize('selected', ['Target player gains 3 life',
    'Prevent the next 3 damage that would be dealt to any target this turn'])
def test_unselected_unknown_tail_cannot_reward_selected_modal_prefix(selected):
    text = base.CARDS['Healing Salve']['oracle_text'] + ' Draw a card.'
    key, payload = _infer_closed_damage_instruction(text, 'Healing Salve',
        {'mode_text': selected, 'target_player': 2})
    assert key == 'noop' and '__unsupported_instruction' in payload


def test_conflicting_explicit_destinations_are_not_prioritized():
    key, payload = _infer_closed_damage_instruction(base.CARDS['Mending Hands']['oracle_text'],
        'Mending Hands', {'target_card_id': 'explicit-id', 'target_player': 2})
    assert key == 'noop' and '__unsupported_instruction' in payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,amount', [('Healing Salve', 3), ('Mending Hands', 4)])
def test_full_canonical_prevention_compiles_explicit_destination(seat, name, amount):
    state, _, target = boundary.setup(seat)
    source = base.add(state, name, seat, Zone.HAND)
    targets = {'target_card_id': target}
    hints = inspect_target_hints(state, state.cards[source], seat)
    if name == 'Healing Salve':
        targets['mode_text'] = next(mode for mode in hints['modes'] if mode.startswith('Prevent'))
    before = prior.snapshot(state)
    assert infer_effect_from_oracle(state, state.cards[source], seat, targets) == (
        'prevent_damage', {'amount': amount, 'target_card_id': target})
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('bad', [True, '2', 2.0, 0, 3, [], {}])
def test_compiler_does_not_guess_malformed_player_destination(bad):
    text = base.CARDS['Mending Hands']['oracle_text']
    key, payload = _infer_closed_damage_instruction(text, 'Mending Hands', {'target_player': bad})
    assert key == 'noop' and '__unsupported_instruction' in payload


@pytest.mark.parametrize('seat', [1, 2])
def test_no_default_target_and_missing_cast_rejects_root(seat):
    state, _, _ = boundary.setup(seat)
    source = base.add(state, 'Mending Hands', seat, Zone.HAND)
    assert infer_effect_from_oracle(state, state.cards[source], seat, {}) == ('prevent_damage', {'amount': 4})
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source, 'targets': {}})
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_full_modal_envelope_rejects_missing_or_unoffered_mode(seat):
    state, _, target = boundary.setup(seat)
    source = base.add(state, 'Healing Salve', seat, Zone.HAND)
    for selected in (None, 'Prevent the next 3 damage', 'Target player gains 3 life. Draw a card.'):
        key, payload = infer_effect_from_oracle(state, state.cards[source], seat,
            {'target_card_id': target, **({'mode_text': selected} if selected else {})})
        assert key == 'noop' and '__unsupported_instruction' in payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['opposing_creature', 'opposing_player', 'own_player'])
def test_actual_paid_salve_complete_prevention_mode_restores_exact_shield(seat, destination):
    state, _, target = boundary.setup(seat, mage=False)
    source = base.add(state, 'Healing Salve', seat, Zone.HAND)
    mode = next(mode for mode in inspect_target_hints(state, state.cards[source], seat)['modes']
                if mode.startswith('Prevent'))
    targets = {'mode_text': mode}
    if destination == 'opposing_creature':
        targets['target_card_id'] = target
    else:
        targets['target_player'] = 3-seat if destination == 'opposing_player' else seat
    pool = dict(state.players[seat].mana_pool)
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': source, 'targets': targets})
    assert state.players[seat].mana_pool != pool and state.cards[source].zone == Zone.STACK
    state = base.finish(prior.reload_exact(state))
    assert state.cards[source].zone == Zone.GRAVEYARD
    if destination == 'opposing_creature':
        assert state.cards[target].counters.get('__prevent_damage_shield') == 3
    else:
        assert state.players[targets['target_player']].prevent_damage_shield == 3
    prior.record('paid-salve-destination', state, destination=destination)
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_salve_gain_life_mode_unchanged(seat):
    state = base.position(seat)
    source = base.add(state, 'Healing Salve', seat, Zone.HAND)
    mode = next(mode for mode in inspect_target_hints(state, state.cards[source], seat)['modes']
                if mode.startswith('Target player gains'))
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': source,
        'targets': {'mode_text': mode, 'target_player': 3-seat}})
    state = base.finish(prior.reload_exact(state))
    assert state.players[3-seat].life == 23 and state.players[seat].life == 20
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_white_prevention_cannot_target_white_protected_creature(seat):
    state, _, target = boundary.setup(seat, target_name='Black Knight')
    source = base.add(state, 'Mending Hands', seat, Zone.HAND)
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source,
            'targets': {'target_card_id': target}})
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_pyroclasm_compiles_amount_only_without_capturing_board(seat):
    state, _, _ = boundary.setup(seat)
    source = base.add(state, 'Pyroclasm', seat, Zone.HAND)
    before = prior.snapshot(state)
    assert infer_effect_from_oracle(state, state.cards[source], seat, {}) == (
        'damage_each_creature', {'amount': 2})
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_pyroclasm_requires_real_creature_only_resolver(seat):
    state = base.position(seat)
    first = base.add(state, 'Torrential Gearhulk', seat)
    second = base.add(state, 'Torrential Gearhulk', 3-seat)
    state, source = boundary.announce(state, seat, 'Pyroclasm')
    frame = next(item for item in state.stack if item.source_card_id == source)
    assert frame.effect_key == 'damage_each_creature' and frame.payload['amount'] == 2
    state = base.finish(prior.reload_exact(state))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert all(player.life == 20 for player in state.players.values())
    assert all(state.cards[cid].counters.get('__damage_marked') == 2 for cid in (first, second))
    prior.reload_exact(state)


@pytest.mark.parametrize('kind', ['memory', 'file', 'socket'])
def test_audit_denies_all_sql_and_socket_aliases(kind, tmp_path):
    with pytest.raises(RuntimeError, match='SQL/socket denied'):
        if kind == 'socket':
            socket.socket()
        else:
            sqlite3.dbapi2.connect(':memory:' if kind == 'memory' else str(tmp_path/'forbidden.db'))
    assert not list(tmp_path.iterdir())
