"""Real board, empty final requirement: payment protocol, not a zero-cost cast."""
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.mana import _payment_requirements, _spell_payment_plan, auto_pay_cost
from rules_engine.mana_abilities import PaidManaStep
from rules_engine.spell_cost_witness import escape_payment_condition
from tests.test_spell_cost_overlap_investigation import escape_position, unchanged_root


def plan(state, seat, spell, goal):
    return _spell_payment_plan(state, seat, _payment_requirements('{0}', False, 0, 0, 0)[0],
        payment_context=('spell', set(spell.types)), source_card_id=spell.id,
        oracle_text=spell.oracle_text, post_payment_condition=goal)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_requirement_admits_real_nonempty_causal_plan(seat):
    state, tower, _, spell, _ = escape_position(seat)
    goal = escape_payment_condition(seat, spell.id, 4)
    assert not goal(state)
    with unchanged_root(state):
        payment = plan(state, seat, spell, goal)
    assert payment is not None
    req, resources, (steps, snow) = payment
    assert not any(req.values()) and resources is None and not snow
    assert len(steps) == 1 and isinstance(steps[0], PaidManaStep)
    assert steps[0].source_id == tower.id and steps[0].color == 'B'


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_requirement_payment_executes_admitted_plan_without_spending(seat):
    state, tower, creature, spell, grave = escape_position(seat)
    goal = escape_payment_condition(seat, spell.id, 4)
    with unchanged_root(state):
        assert plan(state, seat, spell, goal) is not None
    before_pool = dict(state.players[seat].mana_pool)
    details = {}
    result = auto_pay_cost(state, seat, '{0}', source_card_id=spell.id,
        oracle_text=spell.oracle_text, spell_types=set(spell.types),
        apply_modifiers=False, payment_details=details, post_payment_condition=goal)
    receipt = {'result': result, 'final_goal': goal(state), 'details': details,
               'initial_pool': before_pool, 'snapshot': serialize_match_snapshot(state)}
    path = Path(__file__).parents[3] / 'evidence'
    with (path / f'{os.environ["ADMISSION_PHASE"]}-payment-{seat}.json').open('x') as out:
        json.dump(receipt, out, indent=2)
    assert result and goal(state)
    assert state.cards[tower.id].tapped
    assert state.cards[creature.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert set(state.players[seat].graveyard) == {spell.id, creature.id, *grave}
    assert details['mana_spent'] == 0
    assert state.players[seat].mana_pool.get('C', 0) == before_pool.get('C', 0)
    assert state.players[seat].mana_pool.get('B', 0) == before_pool.get('B', 0) + 2


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_requirement_empty_plan_is_still_inert_payment(seat):
    state, tower, creature, spell, _ = escape_position(seat, initial=4)
    goal = escape_payment_condition(seat, spell.id, 4)
    with unchanged_root(state):
        payment = plan(state, seat, spell, goal)
    assert payment is not None and payment[2][0] == []
    details = {}
    with unchanged_root(state):
        assert auto_pay_cost(state, seat, '{0}', source_card_id=spell.id,
            oracle_text=spell.oracle_text, apply_modifiers=False,
            payment_details=details, post_payment_condition=goal)
    assert details['mana_spent'] == 0
    assert not state.cards[tower.id].tapped and state.cards[creature.id].zone == Zone.BATTLEFIELD
