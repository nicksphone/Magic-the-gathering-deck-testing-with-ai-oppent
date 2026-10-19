"""Desired checked human ordering; missing producer choices are ordinary RED."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from effects import handlers
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from tests import test_soulscar_preflight_rules_audit as base

DIRECTORY = Path(__file__).parent / 'fixtures/soulscar_order_goldens'
# Add one immutable canonical record; do not alter prior 49-case files/records.
base.CARDS['Moment of Heroism'] = json.loads((DIRECTORY / 'moment-of-heroism.json').read_text())


def snapshot(state):
    return serialize_match_snapshot(state)


def record(label, state, **extra):
    path = os.environ.get('MTG_SOULSCAR_ORDER_RECEIPTS')
    if path:
        full = snapshot(state)
        with open(path, 'a') as stream:
            stream.write(json.dumps({'label': label, 'snapshot_sha256': hashlib.sha256(
                json.dumps(full, sort_keys=True).encode()).hexdigest(), 'snapshot': full,
                **extra}, sort_keys=True) + '\n')


def reload_exact(state):
    before = snapshot(state)
    result = base.restore(state)
    assert snapshot(result) == before
    assert snapshot(state) == before
    return result


def act(state, seat, action):
    before = snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snapshot(state) == before, 'Checked action mutated its complete root'
    return result


def paid_spell(state, name, seat, targets=None):
    cid = base.add(state, name, seat, Zone.HAND)
    old_pool = dict(state.players[seat].mana_pool)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': targets or {}})
    assert state.cards[cid].zone == Zone.STACK
    assert state.players[seat].mana_pool != old_pool
    state = base.finish(state)
    spell_types = set(state.cards[cid].types)
    destination = Zone.GRAVEYARD if spell_types & {'Instant', 'Sorcery'} else Zone.BATTLEFIELD
    assert state.cards[cid].zone == destination
    return reload_exact(state)


def episode(seat, family, damage_kind, mage_present=True):
    state = base.position(seat)
    mage = base.add(state, 'Soul-Scar Mage', seat) if mage_present else None
    target = base.add(state, 'Torrential Gearhulk', 3-seat)
    source = None
    if damage_kind == 'lifelink_ability':
        source = base.add(state, 'Prodigal Pyromancer', seat)
        state = paid_spell(state, 'Moment of Heroism', seat, {'target_card_id': source})
        assert has_keyword(state, source, 'lifelink'), 'Real paid grant prerequisite missing'
    if family == 'shield':
        state.active_player = state.priority_player = 3-seat
        state = paid_spell(state, 'Boon of Safety', 3-seat, {'target_card_id': target})
        assert state.cards[target].counters.get('shield') == 1
        second = f'shield-counter:{target}'
    else:
        before_ids = set(state.cards)
        state = paid_spell(state, 'Furnace of Rath', seat)
        second = next(cid for cid in set(state.cards)-before_ids
                      if state.cards[cid].name == 'Furnace of Rath')
        assert state.cards[second].zone == Zone.BATTLEFIELD
    state.active_player = state.priority_player = seat
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    return reload_exact(state), mage, second, source, target


def announce_damage(state, seat, kind, source, target):
    if kind == 'bolt':
        source = base.add(state, 'Lightning Bolt', seat, Zone.HAND)
        action = {'type': 'cast_spell', 'card_id': source, 'targets': {'target_card_id': target}}
    else:
        action = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
                  'targets': {'target_card_id': target}}
    state = act(state, seat, action)
    if kind != 'bolt':
        assert state.cards[source].tapped
    genuine = next(item for item in state.stack if item.source_card_id == source)
    frame = {'id': genuine.id, 'controller': genuine.controller, 'source_card_id': source}
    record('announced-real-damage-frame', state, frame=frame)
    state = base.finish(reload_exact(state))
    return state, source, frame


def observe_damage(monkeypatch):
    events = []
    original = handlers.emit_event
    def capture(state, event, payload):
        if event == 'damage_dealt':
            events.append(dict(payload))
        return original(state, event, payload)
    monkeypatch.setattr(handlers, 'emit_event', capture)
    return events


def choose(state, seat, selected):
    before = snapshot(state)
    pending = state.pending_replacement_choice
    offered = {option['source_id'] for option in pending['options']}
    assert selected in offered, 'Do not manufacture a replacement option'
    for wrong_seat, bad_id in [(3-seat, selected), (seat, 'unoffered-source')]:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), wrong_seat, {
                'type': 'choose_replacement', 'replacement_source_id': bad_id})
        assert snapshot(state) == before
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': selected})
    return base.finish(reload_exact(state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['shield', 'furnace'])
@pytest.mark.parametrize('first', ['conversion', 'other'])
@pytest.mark.parametrize('damage_kind', ['bolt', 'lifelink_ability'])
def test_affected_player_deliberate_orders_resume_to_exact_outcome(seat, family, first, damage_kind, monkeypatch):
    state, mage, other, source, target = episode(seat, family, damage_kind)
    events = observe_damage(monkeypatch)
    state, source, frame = announce_damage(state, seat, damage_kind, source, target)
    record('desired-affected-pause', state, seat=seat, family=family, first=first, kind=damage_kind)
    assert state.pending_replacement_choice is not None, 'Do not silently decide the affected player\'s order'
    assert state.pending_replacement_choice['player_id'] == 3-seat
    assert {mage, other} <= {row['source_id'] for row in state.pending_replacement_choice['options']}
    assert state.cards[target].counters.get('-1/-1', 0) == 0
    assert not events
    assert any(item.id == frame['id'] and item.controller == seat and item.source_card_id == source
               for item in state.stack), 'Real announced frame must survive initial pause'
    state = choose(reload_exact(state), 3-seat, mage if first == 'conversion' else other)
    amount = 3 if damage_kind == 'bolt' else 1
    if family == 'furnace' and first == 'other':
        assert state.pending_replacement_choice is not None
        assert state.pending_replacement_choice['player_id'] == 3-seat
        assert other not in {row['source_id'] for row in state.pending_replacement_choice['options']}
        assert not events and state.players[seat].life == 20
        state = choose(state, 3-seat, mage)
        expected_minus = amount*2
    else:
        expected_minus = 0 if family == 'shield' and first == 'other' else amount
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert not state.stack
    assert state.players[seat].life == 20, 'Converted/prevented damage grants no lifelink'
    assert state.players[3-seat].life == 20
    assert events == [], 'No damage_dealt event means no damage-dealt triggers'
    card = state.cards[target]
    if expected_minus >= 6:
        assert card.zone == Zone.GRAVEYARD and target in state.players[3-seat].graveyard
        assert card.last_known_battlefield['counters'].get('-1/-1') == expected_minus
        assert not card.last_known_battlefield['counters'].get('__damage_marked')
    else:
        assert card.zone == Zone.BATTLEFIELD
        assert card.counters.get('-1/-1', 0) == expected_minus
        assert not card.counters.get('__damage_marked')
        if family == 'shield':
            assert card.counters.get('shield', 0) == (1 if first == 'conversion' else 0)
    if damage_kind == 'bolt':
        assert state.cards[source].zone == Zone.GRAVEYARD
    else:
        assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].tapped
    record('desired-final-outcome', state, expected_minus=expected_minus)
    reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['shield', 'furnace'])
def test_real_paid_lifelink_controls_without_conversion_source(seat, family, monkeypatch):
    state, _, _, source, target = episode(seat, family, 'lifelink_ability', mage_present=False)
    events = observe_damage(monkeypatch)
    state, _, _ = announce_damage(state, seat, 'lifelink_ability', source, target)
    assert not state.pending_replacement_choice
    actual_damage = 0 if family == 'shield' else 2
    assert state.players[seat].life == 20+actual_damage
    assert state.cards[target].counters.get('__damage_marked', 0) == actual_damage
    assert state.cards[target].counters.get('-1/-1', 0) == 0
    assert len(events) == (1 if actual_damage else 0)
    if events:
        assert events[0]['amount'] == actual_damage and events[0]['source_card_id'] == source
    record('real-control-outcome', state, family=family, actual_damage=actual_damage)
    reload_exact(state)
