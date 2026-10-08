"""Generic closed grammars backed by unchanged executors; no canonical waiver."""
from copy import deepcopy

import pytest
import test_paid_context_goldens as c
from test_closed_loyalty import synthetic_receipt, TAILS
from game_state.state import Zone
from rules_engine.closed_loyalty import compile_body

facts = c.facts


@pytest.mark.parametrize('name', ['Ugin, the Spirit Dragon', 'Renamed, Generic Walker'])
@pytest.mark.parametrize('amount', [1, 3, 7])
@pytest.mark.parametrize('cost', ['+2', '-4', '0'])
def test_source_bound_damage_complete_generic_body(name, amount, cost):
    alias = name.split(',', 1)[0]
    text = f'{cost}: {alias} deals {amount} damage to any target.'
    assert compile_body(text, name)['abilities'][0]['instructions'][0]['effect_key'] == 'deal_damage'
    assert compile_body(text, 'Different Walker') is None


@pytest.mark.parametrize('body,cost', [
    ('Destroy target artifact.', '+1'), ('Destroy target enchantment.', '-2'),
    ('Destroy target artifact or enchantment.', '0'), ('Destroy all creatures.', '-4'),
    ("Exile each permanent with mana value X or less that's one or more colors.", '-X')])
def test_executor_closed_grammars_preserve_every_raw_tail(body, cost):
    text = f'{cost}: {body}'
    assert compile_body(text, 'Generic Walker') is not None
    for tail in TAILS:
        assert compile_body(text + tail, 'Generic Walker') is None


@pytest.mark.parametrize('body', ['Destroy all creatures with power 4 or greater.',
    'You gain 7 life, draw seven cards, then put up to seven permanent cards from your hand onto the battlefield.',
    'You get an emblem with "Creatures you control get +2/+2 and have flying."'])
def test_new_complete_executor_semantics_reject_raw_tails(body):
    assert compile_body('+1: ' + body, 'Generic Walker') is not None
    for tail in TAILS:
        assert compile_body('+1: ' + body + tail, 'Generic Walker') is None


def test_different_source_damage_is_still_rejected():
    assert compile_body('+1: A different walker deals 3 damage to any target.', 'Generic Walker') is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ability', [0, 1, 2])
def test_actual_paid_generic_executor_backed_effects(facts, seat, ability, request):
    c.ACTIONS.clear()
    derived = deepcopy(facts)
    name = 'Renamed, Generic Walker'
    raw = deepcopy(facts['The Wandering Emperor'])
    raw.update(name=name, loyalty='7', oracle_text=
        '+2: Renamed deals 3 damage to any target.\n'
        '-1: Destroy target artifact or enchantment.\n'
        "-X: Exile each permanent with mana value X or less that's one or more colors.")
    derived[name] = raw
    state = c.g.position(facts, seat)
    source = c.g.add(state, derived, name, seat, Zone.HAND)
    state, frame = c.paid(state, seat, source, {'C': 2, 'W': 2})
    state = c.advance(state, lambda s: all(i.id != frame for i in s.stack))
    target = None
    if ability == 1:
        target = c.g.add(state, facts, 'Leyline Binding', 3-seat, Zone.BATTLEFIELD)
    elif ability == 2:
        target = c.g.add(state, facts, 'Suncleanser', 3-seat, Zone.BATTLEFIELD)
    state = c.priority(c.cold(state), seat)
    assert state.cards[source].loyalty == 7
    targets = ({'target_player': 3-seat} if ability == 0 else
               {'target_card_id': target} if ability == 1 else {'x_value': 2})
    state = c.act(state, seat, {'type': 'activate_loyalty', 'card_id': source,
                               'ability_index': ability, 'targets': targets})
    assert state.cards[source].loyalty == [9, 6, 5][ability]
    state = c.advance(c.cold(state), lambda s: not s.stack)
    if ability == 0:
        assert state.players[3-seat].life == 17
    elif ability == 1:
        assert state.cards[target].zone == Zone.GRAVEYARD
    else:
        assert state.cards[target].zone == Zone.EXILE
        assert state.cards[source].zone == Zone.BATTLEFIELD
    synthetic_receipt(request, c.cold(state), raw, ability=ability,
                      executor_backed_generic_paid_witness=True)
