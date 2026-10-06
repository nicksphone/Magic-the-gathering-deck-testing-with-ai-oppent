"""Exact compiler metadata and independent legality, without inferred targets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contracts import ActionRequest
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.oracle_effects import _infer_targeted_search_effect, clause_target_assignments
from tests.favor_lifecycle_support import (
    FAVOR, ROWS, act, assert_private, favor_action, position, resolve_one, restart, snap,
)
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('counter_target', ['selected', 'omitted', 'null'])
def test_exact_clauses_bind_only_explicit_announced_targets_and_keep_payloads(seat, counter_target):
    state, data = position(seat)
    announced = {'target_player': data['affected']}
    if counter_target != 'omitted':
        announced['target_card_id'] = data['target'] if counter_target == 'selected' else None
    before = snap(state)
    key, payload = _infer_targeted_search_effect(FAVOR['oracle_text'], announced)
    assert key == 'effect_sequence'
    search, counter = payload['effects']
    search_text, counter_text = FAVOR['oracle_text'].split('. ', 1)
    search_text += '.'
    assert search['clause_text'] == search_text
    assert counter['clause_text'] == counter_text
    assert search['payload'] == {'target_player': data['affected'], 'contains': 'basic_land',
                                 'destination': 'battlefield', 'count': 1,
                                 'tapped': True, 'shuffle': True}
    assert counter['payload'] == {'target_card_id': announced.get('target_card_id'),
                                  'counter': '+1/+1', 'amount': 2}
    selected = clause_target_assignments(state, state.cards[data['source']], seat, announced,
                                        payload['effects'])
    assert selected == [{'target_player': data['affected']},
                        {'target_card_id': data['target']} if counter_target == 'selected' else {}]
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['missing_player', 'foreign_card', 'wrong_zone', 'extra_alias'])
def test_incomplete_or_invalid_cast_does_not_pay_or_infer_a_target(seat, bad):
    state, data = position(seat)
    action = favor_action(data)
    if bad == 'missing_player':
        del action['targets']['target_player']
    elif bad == 'foreign_card':
        action['targets']['target_card_id'] = 'not-an-offered-card'
    elif bad == 'wrong_zone':
        action['targets']['target_card_id'] = data['caster_library'][0]
    else:
        action['targets']['inferred_target_card_id'] = data['target']
    before = snap(state)
    if bad == 'extra_alias':
        # Extra-field rejection belongs to the existing public typed boundary,
        # not the legacy internal checked-action dictionary's ignored fields.
        with pytest.raises(ValidationError):
            ActionRequest.model_validate({'player_id': seat, 'action': action})
    else:
        with pytest.raises(ActionRejected):
            act(state, seat, action)
    assert snap(state) == before


def leyline(state, seat):
    fixture = Path(__file__).parent / 'fixtures/queued_fizzle/canonical.json'
    provenance = json.loads(fixture.with_name('provenance.json').read_text())
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == provenance['canonical_sha256']
    row = json.loads(fixture.read_text())
    assert row['name'] == 'Leyline of Sanctity' and provenance['facts_modified'] is False
    return raw_card(state, row, seat, Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('illegal_counter', [False, True])
def test_retained_paid_resolution_player_illegal_independent_counter_or_all_illegal(seat, illegal_counter, tmp_path):
    state, data = position(seat, 'veil' if illegal_counter else 'none')
    state = act(state, seat, favor_action(data))
    assert state.stack[-1].payload['mana_spent'] == 4
    if illegal_counter:
        state = act(state, seat, {'type': 'pass_priority'})
        state = act(state, data['affected'], {'type': 'cast_spell', 'card_id': data['response'],
                     'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': data['target']}})
        state = resolve_one(state)
    # Explicit retained-state UNIT premise, not a claimed paid flash-Leyline episode:
    # canonical static player immunity exists when the real paid Favor is resolved.
    leyline(state, data['affected'])
    counters = deepcopy(state.cards[data['target']].counters)
    libraries = {pid: list(player.library) for pid, player in state.players.items()}
    rng = state.rng.getstate()
    state = resolve_one(restart(state, tmp_path, 'retained-resolution'))
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.cards[data['source']].zone == Zone.GRAVEYARD
    assert {pid: list(player.library) for pid, player in state.players.items()} == libraries
    assert state.rng.getstate() == rng
    if not illegal_counter:
        counters['+1/+1'] = counters.get('+1/+1', 0) + 2
    assert state.cards[data['target']].counters == counters
    assert_private(restart(state, tmp_path, 'retained-complete'), data['affected'])


@pytest.mark.parametrize('seat', [1, 2])
def test_legal_player_zero_counter_fail_to_find_never_retargets_after_restart(seat, tmp_path):
    state, data = position(seat, 'zero')
    counters = {cid: dict(card.counters) for cid, card in state.cards.items()}
    state = act(state, seat, favor_action(data))
    state = resolve_one(state)
    assert state.pending_mechanic_choice['continuation_controller'] == seat
    assert state.pending_mechanic_choice['player_id'] == data['affected']
    state = restart(state, tmp_path, 'zero-counter-search')
    before = snap(state)
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({'player_id': data['affected'], 'action': {
            'type': 'choose_mechanic', 'card_ids': [],
            'targets': {'target_card_id': data['target']}}})
    assert snap(state) == before
    state = act(state, data['affected'], {'type': 'choose_mechanic', 'card_ids': []})
    assert state.pending_mechanic_choice is None and not state.stack
    assert {cid: dict(card.counters) for cid, card in state.cards.items()} == counters
    assert_private(restart(state, tmp_path, 'zero-complete'), data['affected'])
