"""A paused genuine batch cannot drop an eligible row or change its admission."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.graveyard_batch_entry import PLAN, finish_choice, plan_matches
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, place, position, snapshot


def observed_state(state):
    result = deepcopy(vars(state))
    result['rng'] = state.rng.getstate()
    return result


def paused(caster):
    names = ('Open the Vaults', 'Rancor', 'Sol Ring', 'Ornithopter')
    state = position(names, names, active=caster)
    targets = {owner: place(state, 'Ornithopter', Zone.BATTLEFIELD, owner) for owner in (1, 2)}
    artifacts = {owner: place(state, 'Sol Ring', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    aura = place(state, 'Rancor', Zone.GRAVEYARD, caster)
    state, source = cast_vaults(state, caster)
    assert resolve_top_of_stack(state) is False
    state = snapshot(state)
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == caster and pending['entry_card_id'] == aura
    assert set(row['id'] for row in pending['effect_payload'][PLAN]['entries']) == {aura, *artifacts.values()}
    assert all(row['admitted'] is True for row in pending['effect_payload'][PLAN]['entries'])
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [aura, *artifacts.values()])
    return state, targets[caster], artifacts, aura, source


@pytest.mark.parametrize('caster', [1, 2])
@pytest.mark.parametrize('mutation', ['delete-eligible-row', 'flip-admitted-false'])
@pytest.mark.parametrize('consumer', ['plan-match', 'resume-before-clear'])
def test_retained_cohort_mutation_rejects_without_changing_atomic_root(caster, mutation, consumer):
    state, target, artifacts, _, _ = paused(caster)
    payload = state.pending_mechanic_choice['effect_payload']
    rows = payload[PLAN]['entries']
    victim = next(row for row in rows if row['id'] == artifacts[3-caster])
    if mutation == 'delete-eligible-row':
        rows.remove(victim)
    else:
        victim['admitted'] = False
    before = observed_state(state)
    if consumer == 'plan-match':
        accepted = plan_matches(state, caster, payload)
    else:
        accepted = finish_choice(state, caster, {'type': 'choose_mechanic', 'choice_id': target})
    assert observed_state(state) == before
    assert accepted is False
    assert state.pending_mechanic_choice is not None
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in artifacts.values())


@pytest.mark.parametrize('caster', [1, 2])
def test_complete_snapshot_roster_resumes_and_commits_all_owners(caster):
    state, target, artifacts, aura, source = paused(caster)
    assert plan_matches(state, caster, state.pending_mechanic_choice['effect_payload'])
    assert finish_choice(state, caster, {'type': 'choose_mechanic', 'choice_id': target})
    assert state.pending_mechanic_choice is None
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in [aura, *artifacts.values()])
    assert all(state.cards[cid].controller == owner for owner, cid in artifacts.items())
    assert state.cards[aura].attached_to == target
    assert state.cards[source].zone == Zone.GRAVEYARD
