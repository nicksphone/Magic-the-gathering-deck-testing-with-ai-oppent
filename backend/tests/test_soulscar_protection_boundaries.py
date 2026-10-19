"""Paid canonical episodes; strict desired failures, no SQL/socket or product edits."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.oracle_effects import inspect_target_hints
from tests import test_soulscar_preflight_rules_audit as base
from tests import test_soulscar_affected_order_goldens as prior

DIRECTORY = Path(__file__).parent / 'fixtures/soulscar_protection_boundaries'
for filename in DIRECTORY.glob('*.json'):
    raw = json.loads(filename.read_text())
    if isinstance(raw, dict) and raw.get('object') == 'card':
        base.CARDS[raw['name']] = raw


def setup(seat, target_name='Kor Firewalker', mage=True):
    state = base.position(seat)
    # Explicit rules fixture resources, never claimed as natural play.
    for player in state.players.values():
        player.mana_pool['G'] = 5
    source = base.add(state, 'Soul-Scar Mage', seat) if mage else None
    target = base.add(state, target_name, 3-seat)
    return state, source, target


def announce(state, seat, name, targets=None):
    source = base.add(state, name, seat, Zone.HAND)
    pool = dict(state.players[seat].mana_pool)
    state = prior.act(state, seat, {
        'type': 'cast_spell', 'card_id': source, 'targets': targets or {}})
    assert state.cards[source].zone == Zone.STACK
    assert state.players[seat].mana_pool != pool
    prior.record('paid-canonical-announcement', state, name=name, source=source)
    return prior.reload_exact(state), source


def damage(state, seat, family, target):
    if family == 'spell':
        state, source = announce(state, seat, 'Hornet Sting', {'target_card_id': target})
    else:
        source = base.add(state, 'Prodigal Sorcerer', seat)
        state = prior.paid_spell(state, 'Moment of Heroism', seat, {'target_card_id': source})
        state = prior.act(state, seat, {'type': 'activate_ability', 'card_id': source,
            'ability_index': 0, 'targets': {'target_card_id': target}})
        assert state.cards[source].tapped
    frame = next(item for item in state.stack if item.source_card_id == source)
    frame_id = frame.id
    state = base.finish(prior.reload_exact(state))
    prior.record('legal-protected-damage-resolution', state, family=family, target=target,
                 source=source, frame_id=frame_id)
    return state, source, frame_id


@pytest.mark.parametrize('seat', [1, 2])
def test_red_target_protection_rejects_before_mutation(seat):
    state, _, target = setup(seat)
    source = base.add(state, 'Lightning Bolt', seat, Zone.HAND)
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source,
            'targets': {'target_card_id': target}})
    assert prior.snapshot(state) == before
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
def test_other_color_paid_damage_is_legal_and_converts(seat, family, monkeypatch):
    state, _, target = setup(seat)
    events = prior.observe_damage(monkeypatch)
    state, _, _ = damage(state, seat, family, target)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].counters.get('-1/-1') == 1
    assert not state.cards[target].counters.get('__damage_marked')
    assert not events and state.players[seat].life == 20
    prior.reload_exact(state)


def paid_prevention(state, seat, target, prevention):
    state.active_player = state.priority_player = 3-seat
    if prevention == 'shield':
        state = prior.paid_spell(state, 'Boon of Safety', 3-seat, {'target_card_id': target})
        assert state.cards[target].counters.get('shield') == 1
        state.active_player = state.priority_player = seat
        return prior.reload_exact(state)
    name = 'Healing Salve'
    amount = 3
    source = base.add(state, name, 3-seat, Zone.HAND)
    hints = inspect_target_hints(state, state.cards[source], 3-seat)
    targets = {'target_card_id': target}
    if prevention == 'salve':
        targets['mode_text'] = next(mode for mode in hints['modes']
                                    if mode.startswith('Prevent the next'))
    pool = dict(state.players[3-seat].mana_pool)
    state = prior.act(state, 3-seat, {'type': 'cast_spell', 'card_id': source,
        'targets': targets})
    assert state.players[3-seat].mana_pool != pool
    state = base.finish(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[target].counters.get('__prevent_damage_shield') == amount
    state.active_player = state.priority_player = seat
    return prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('first', ['conversion', 'prevention'])
@pytest.mark.parametrize('prevention', ['salve', 'shield'])
def test_protected_legal_damage_has_deliberate_prevention_conversion_order(
        seat, family, first, prevention, monkeypatch):
    state, mage, target = setup(seat)
    state = paid_prevention(state, seat, target, prevention)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    events = prior.observe_damage(monkeypatch)
    state, source, frame_id = damage(state, seat, family, target)
    pending = state.pending_replacement_choice
    assert pending is not None, 'Affected player must choose applicable prevention/conversion'
    assert pending['player_id'] == 3-seat
    offered = {row['source_id'] for row in pending['options']}
    assert mage in offered and len(offered) >= 2
    assert any(item.id == frame_id and item.source_card_id == source for item in state.stack)
    assert not events and not state.cards[target].counters.get('-1/-1')
    # Use the actually offered prevention identity, never a manufactured source receipt.
    chosen = mage if first == 'conversion' else next(cid for cid in offered if cid != mage)
    state = prior.choose(prior.reload_exact(state), 3-seat, chosen)
    assert not state.pending_replacement_choice and not state.stack
    assert state.cards[target].counters.get('-1/-1', 0) == (1 if first == 'conversion' else 0)
    field, amount = ('__prevent_damage_shield', 3) if prevention == 'salve' else ('shield', 1)
    assert state.cards[target].counters.get(field, 0) == (
        amount if first == 'conversion' else amount-1)
    assert not state.cards[target].counters.get('__damage_marked')
    assert not events and state.players[seat].life == 20
    prior.record('desired-prevention-order-result', state, first=first, target=target)
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('prevention', ['salve', 'shield'])
def test_paid_prevention_without_conversion_source(seat, family, prevention, monkeypatch):
    state, _, target = setup(seat, mage=False)
    state = paid_prevention(state, seat, target, prevention)
    events = prior.observe_damage(monkeypatch)
    state, _, _ = damage(state, seat, family, target)
    assert not state.pending_replacement_choice
    field, remaining = ('__prevent_damage_shield', 2) if prevention == 'salve' else ('shield', 0)
    assert state.cards[target].counters.get(field, 0) == remaining
    assert not state.cards[target].counters.get('-1/-1')
    assert not state.cards[target].counters.get('__damage_marked')
    assert not events and state.players[seat].life == 20
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_untargeted_red_damage_admits_protection_conversion_event(seat):
    state, mage, target = setup(seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, source = announce(state, seat, 'Pyroclasm')
    actual = next(item for item in state.stack if item.source_card_id == source)
    prior.record('actual-pyroclasm-compiled-frame', state, effect_key=actual.effect_key,
                 payload=actual.payload, target=target)
    state = base.finish(state)
    assert state.players[3-seat].life == 20, 'Each creature is not the opposing player'
    assert state.pending_replacement_choice is not None
    assert state.pending_replacement_choice['player_id'] == 3-seat
    assert mage in {row['source_id'] for row in state.pending_replacement_choice['options']}


def until_battlefield(state, source):
    for _ in range(24):
        if state.cards[source].zone == Zone.BATTLEFIELD:
            return prior.reload_exact(state)
        assert state.stack and not state.pending_mechanic_choice
        state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Real response did not resolve within fixture continuation bound')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('timing', ['before', 'response', 'removed_response'])
def test_real_suppression_timing_changes_conversion_at_resolution(seat, timing, monkeypatch):
    state, mage, target = setup(seat, target_name='Black Knight')
    if timing == 'before':
        state = prior.paid_spell(state, 'Humility', seat)
        assert printed_abilities_suppressed(state, mage)
    state, bolt = announce(state, seat, 'Lightning Bolt', {'target_card_id': target})
    if timing != 'before':
        for _ in range(4):
            if state.priority_player == 3-seat:
                break
            state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
        assert state.priority_player == 3-seat
        state, dress = announce(state, 3-seat, 'Dress Down')
        state = until_battlefield(state, dress)
        assert printed_abilities_suppressed(state, mage)
        assert any(item.source_card_id == bolt for item in state.stack)
        if timing == 'removed_response':
            for _ in range(4):
                if state.priority_player == seat:
                    break
                state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
            assert state.priority_player == seat
            state, naturalize = announce(state, seat, 'Naturalize', {'target_card_id': dress})
            for _ in range(16):
                if state.cards[naturalize].zone == Zone.GRAVEYARD:
                    break
                state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
            assert state.cards[dress].zone == Zone.GRAVEYARD
            assert not printed_abilities_suppressed(state, mage)
            assert any(item.source_card_id == bolt for item in state.stack)
    events = prior.observe_damage(monkeypatch)
    state = base.finish(prior.reload_exact(state))
    card = state.cards[target]
    assert card.zone == Zone.GRAVEYARD and state.cards[bolt].zone == Zone.GRAVEYARD
    last = card.last_known_battlefield['counters']
    restored = timing == 'removed_response'
    assert last.get('-1/-1', 0) == (3 if restored else 0)
    assert last.get('__damage_marked', 0) == (0 if restored else 3)
    assert len(events) == (0 if restored else 1)
    prior.record('suppression-timing-result', state, timing=timing, target=target)
    prior.reload_exact(state)
