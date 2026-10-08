"""Canonical desired exchange/energy behavior; no product or Oracle rewrites."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

import pytest

import domain_paid_support as g
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / 'evidence'
PHASE = os.environ['ADMISSION_PHASE']
SOURCE = 'Volatile Stormdrake'


@pytest.fixture(scope='module')
def facts():
    rows = json.loads((HERE / 'canonical.json').read_bytes())
    pins = json.loads((HERE / 'provenance.json').read_bytes())
    assert rows[SOURCE]['id'] == '2e6e3232-8bb8-4504-9597-dfdfc6d634bd'
    for name, raw in rows.items():
        body = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(body).hexdigest() == pins['cards'][name]['canonical_fullrowSHA']
    return rows


def record(label, state, **observed):
    with (OUT / f'{PHASE}-{label}.json').open('x') as stream:
        json.dump({'snapshot': serialize_match_snapshot(state), 'observed': observed}, stream, indent=2)


def moves(state, actor):
    before = serialize_match_snapshot(state)
    result = RulesEngine().legal_moves(state, actor)
    assert serialize_match_snapshot(state) == before
    return result


def position(facts, seat, target_name='Raging Goblin', initial_energy=0):
    state = g.position(facts, seat)
    target = g.add(state, facts, target_name, 3-seat)
    alternate = g.add(state, facts, 'Archangel of Wrath' if target_name == 'Raging Goblin'
                      else 'Raging Goblin', 3-seat)
    own = g.add(state, facts, 'Raging Goblin', seat)
    land = g.add(state, facts, 'Forest', 3-seat)
    hidden = g.add(state, facts, 'Forest', 3-seat, Zone.HAND)
    source = g.add(state, facts, SOURCE, seat, Zone.HAND)
    if initial_energy:
        state.players[seat].counters['energy'] = initial_energy
    return state, source, target, alternate, own, land, hidden


def paid_entry(state, source, seat, label):
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    before = serialize_match_snapshot(state)
    paid = g.cast(state, seat, source)
    assert serialize_match_snapshot(state) == before
    assert paid.cards[source].zone == Zone.STACK
    item = next(item for item in paid.stack if item.source_card_id == source)
    assert item.controller == seat and item.payload['mana_spent'] == 2
    assert sum(paid.players[seat].mana_pool.values()) == 0
    for _ in range(16):
        if paid.cards[source].zone == Zone.BATTLEFIELD:
            record(label + '-paid-entry', paid, source=source,
                   full_oracle=paid.cards[source].oracle_text, mana_spent=2)
            return paid
        assert not paid.pending_mechanic_choice and not paid.pending_trigger_order
        paid = g.act(paid, paid.priority_player, 'pass_priority')
    raise AssertionError('Real paid creature entry did not complete within16 public actions')


def target_boundary(state, source, seat, target, alternate, hidden, label):
    offered = moves(state, seat)
    record(label + '-public-target-boundary', state, source=source, target=target,
           alternate=alternate, offered=offered,
           actual_source_controller=state.cards[source].controller,
           actual_target_controller=state.cards[target].controller,
           actual_energy=state.players[seat].counters.get('energy', 0))
    assert hidden not in json.dumps(offered)
    choices = [move for move in offered if move['type'] == 'choose_trigger_target']
    selected = [move for move in choices if move.get('target_card_id') == target]
    assert len(selected) == 1, 'Paid entry lacks the required nontrivial public exchange target witness'
    assert any(move.get('target_card_id') == alternate for move in choices)
    return selected[0]


def progress_to_energy_or_terminal(state):
    for _ in range(16):
        if state.pending_mechanic_choice or state.pending_trigger_order or not state.stack:
            return state
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Bounded exchange resolution did not reach payment or terminal')


def public_energy_option(state, seat, pay):
    offered = moves(state, seat)
    options = []
    for move in offered:
        if move['type'] == 'choose_optional_effect' and move.get('accept') is pay:
            options.append({'type': 'choose_optional_effect', 'stack_id': move['stack_id'], 'accept': pay})
        if move['type'] == 'choose_mechanic' and move.get('player_id') == seat:
            labels = move.get('option_labels', {})
            for option in move.get('options', []):
                label = str(labels.get(option, '')).strip()
                if (pay and re.match(r'^(pay|yes)\b', label, re.I)) or (
                        not pay and re.match(r'^(decline|sacrifice|no|do not pay)\b', label, re.I)):
                    options.append({'type': 'choose_mechanic', 'choice_id': option})
    assert len(options) == 1, 'Required existing-ABI actor-visible energy decision absent or ambiguous'
    return options[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cold', [False, True])
@pytest.mark.parametrize('case,target_name,initial,pay,mv', [
    ('pay-one', 'Raging Goblin', 0, True, 1),
    ('decline-one', 'Raging Goblin', 0, False, 1),
    ('insufficient-seven', 'Atraxa, Grand Unifier', 0, False, 7),
    ('pay-seven', 'Atraxa, Grand Unifier', 3, True, 7)])
def test_paid_complete_exchange_energy_and_sacrifice(facts, seat, cold, case, target_name, initial, pay, mv):
    untouched = deepcopy(facts)
    state, source, target, alternate, _, _, hidden = position(facts, seat, target_name, initial)
    opponent_private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    label = f'{case}-{cold}-{seat}'
    state = paid_entry(state, source, seat, label)
    assert state.cards[source].oracle_text == facts[SOURCE]['oracle_text']
    if cold:
        state = g.restore(state)
    choice = target_boundary(state, source, seat, target, alternate, hidden, label)
    state = checked_action(state, RulesEngine(), seat, choice)
    state = progress_to_energy_or_terminal(state)
    assert state.cards[source].controller == 3-seat and state.cards[source].owner == seat
    assert state.players[seat].counters.get('energy', 0) == initial + 4
    assert state.players[3-seat].counters.get('energy', 0) == 0
    if state.pending_mechanic_choice or state.pending_trigger_order:
        if cold:
            state = g.restore(state)
        action = public_energy_option(state, seat, pay)
        assert moves(state, 3-seat) == []
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3-seat, action)
        assert serialize_match_snapshot(state) == before
        state = checked_action(state, RulesEngine(), seat, action)
    else:
        assert not pay and initial + 4 < mv, 'Affordable optional energy payment silently inferred'
    state = progress_to_energy_or_terminal(state)
    assert not state.stack and not state.pending_mechanic_choice and not state.pending_trigger_order
    assert state.players[seat].counters.get('energy', 0) == initial + 4 - (mv if pay else 0)
    assert state.cards[source].zone == Zone.BATTLEFIELD and source in state.players[3-seat].battlefield
    assert source not in state.players[seat].battlefield
    assert state.cards[target].owner == 3-seat
    if pay:
        assert state.cards[target].controller == seat and state.cards[target].zone == Zone.BATTLEFIELD
        assert target in state.players[seat].battlefield and target not in state.players[3-seat].battlefield
    else:
        assert state.cards[target].zone == Zone.GRAVEYARD and target in state.players[3-seat].graveyard
        assert target not in state.players[seat].graveyard
    assert opponent_private == (state.players[3-seat].hand, state.players[3-seat].library)
    assert facts == untouched
    assert serialize_match_snapshot(g.restore(state)) == serialize_match_snapshot(state)
    record(label + '-complete', state, pay=pay, mana_value=mv, private_unchanged=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['own', 'land', 'private-hand', 'unknown'])
def test_actual_public_exchange_target_rejects_invalid_choices_atomically(facts, seat, bad):
    state, source, target, alternate, own, land, hidden = position(facts, seat)
    label = f'invalid-{bad}-{seat}'
    state = paid_entry(state, source, seat, label)
    valid = target_boundary(state, source, seat, target, alternate, hidden, label)
    bad_id = {'own': own, 'land': land, 'private-hand': hidden, 'unknown': 'missing-card'}[bad]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {**valid, 'target_card_id': bad_id})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_source_admission_and_entry_control_only(facts, seat):
    state, source, _, _, _, _, _ = position(facts, seat)
    state = paid_entry(state, source, seat, f'admission-only-{seat}')
    assert state.cards[source].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_conditional_hexproof_does_not_prohibit_real_paid_spells(facts, seat):
    state = g.position(facts, seat)
    target = g.add(state, facts, SOURCE, 3-seat)
    bolt = g.add(state, facts, 'Lightning Bolt', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    before = serialize_match_snapshot(state)
    paid = g.cast(state, seat, bolt, target_card_id=target)
    assert serialize_match_snapshot(state) == before
    assert paid.stack[-1].payload['mana_spent'] == 1
    for _ in range(16):
        if not paid.stack:
            break
        paid = g.act(paid, paid.priority_player, 'pass_priority')
    assert not paid.stack and paid.cards[target].zone == Zone.GRAVEYARD
    record(f'spell-hexproof-boundary-{seat}', paid, mana_spent=1, target_graveyard=True)
