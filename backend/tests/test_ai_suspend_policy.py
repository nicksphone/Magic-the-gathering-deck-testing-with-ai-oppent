"""Canonical fixed-Suspend policy; controlled continuations, not historical games."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from ai.suspend_policy import idle_suspend, optional_cast
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_suspend_lifecycle import CARDS, add, setup, ready, restore, act, one


def agent():
    return AIAgent(difficulty='strong', archetype='Midrange', opponent_archetype='Aggro')


def moves(state, seat):
    return RulesEngine().legal_moves(deepcopy(state), seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rift Bolt', 'Errant Ephemeron', 'Ancestral Vision'])
def test_pending_useful_cast_complete_private_deterministic_restore(seat, name):
    state, cid = setup(seat, name)
    state = ready(state, seat, cid)
    before = serialize_match_snapshot(state)
    legal = moves(state, seat)
    original_moves = deepcopy(legal)
    view, _ = decision_view(state, seat, legal)
    assert all(is_unknown(view.cards[c]) for p in view.players.values() for c in p.library)
    action = optional_cast(agent(), state, legal, seat)
    assert action['type'] == 'cast_spell', action
    assert action['card_id'] == cid and action['from_exile']
    assert action['cost_choice']['id']
    if name == 'Rift Bolt':
        assert action['targets']['target_player'] == 3-seat
    assert optional_cast(agent(), restore(state), legal, seat) == action
    altered = deepcopy(state)
    for player in altered.players.values():
        player.library.reverse()
    assert optional_cast(agent(), altered, moves(altered, seat), seat) == action
    assert serialize_match_snapshot(state) == before
    assert legal == original_moves
    result = act(state, seat, action)
    assert result.pending_mechanic_choice is None
    result = one(result)
    if name == 'Errant Ephemeron':
        from rules_engine.continuous import has_keyword
        assert has_keyword(result, cid, 'haste')
    if name == 'Ancestral Vision':
        assert len(result.players[seat].hand) == len(state.players[seat].hand) + 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['no-target', 'prohibition', 'bad-target'])
def test_pending_decline_controls(seat, control):
    state, cid = setup(seat)
    state = ready(state, seat, cid)
    if control == 'prohibition':
        add(state, 'Drannith Magistrate', 3-seat, cards=CARDS)
    else:
        add(state, 'Ivory Mask', 3-seat, cards=CARDS)
        if control == 'no-target':
            add(state, 'Ivory Mask', seat, cards=CARDS)
    before = serialize_match_snapshot(state)
    action = optional_cast(agent(), state, moves(state, seat), seat)
    assert action == {'type': 'choose_mechanic', 'card_ids': ['decline']}
    result = act(state, seat, action)
    assert not result.pending_mechanic_choice
    assert result.cards[cid].zone == Zone.EXILE
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rift Bolt', 'Errant Ephemeron', 'Ancestral Vision'])
def test_idle_early_investment(seat, name):
    state, cid = setup(seat, name)
    state.turn = 1
    state.players[seat].mana_pool = {'R': 1} if name == 'Rift Bolt' else {'U': 1, 'C': 1}
    before = serialize_match_snapshot(state)
    action = idle_suspend(agent(), state, moves(state, seat), seat)
    assert action == {'type': 'suspend', 'card_id': cid}
    result = act(state, seat, action)
    assert result.cards[cid].zone == Zone.EXILE
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['normal-cast', 'unpayable', 'late', 'race', 'prohibition'])
def test_idle_controls(seat, control):
    state, cid = setup(seat, 'Errant Ephemeron')
    state.turn = 1
    if control == 'normal-cast': state.players[seat].mana_pool = {'U': 1, 'C': 6}
    if control == 'unpayable': state.players[seat].mana_pool.clear()
    if control == 'late': state.turn = 10
    if control == 'race': state.players[seat].life = 4
    if control == 'prohibition': add(state, 'Drannith Magistrate', 3-seat, cards=CARDS)
    before = serialize_match_snapshot(state)
    assert idle_suspend(agent(), state, moves(state, seat), seat) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_known_interaction_reservation(seat):
    from tests.test_surveil_mill import add as canonical_add
    state, cid = setup(seat, 'Ancestral Vision')
    state.turn = 1
    canonical_add(state, 'Counterspell', seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    assert idle_suspend(agent(), state, moves(state, seat), seat) is None
    state.players[seat].mana_pool = {'U': 3}
    assert idle_suspend(agent(), state, moves(state, seat), seat) == {'type': 'suspend', 'card_id': cid}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payable', [True, False])
def test_optional_actual_tax_and_tactical_burn(seat, payable):
    from tests.test_surveil_mill import add as canonical_add
    state, cid = setup(seat)
    state = ready(state, seat, cid)
    canonical_add(state, 'Thalia, Guardian of Thraben', 3-seat)
    state.players[seat].mana_pool = {'C': 1} if payable else {}
    before = serialize_match_snapshot(state)
    action = optional_cast(agent(), state, moves(state, seat), seat)
    assert action['type'] == ('cast_spell' if payable else 'choose_mechanic')
    result = act(state, seat, action)
    assert not result.pending_mechanic_choice
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_countered_final_trigger_has_no_cast_decision(seat):
    from rules_engine.suspend import remove_time_counters
    from rules_engine.events import flush_staged_triggers
    from tests.test_counterability_scope import add_card
    # Explicit fixture: a real counter targets the last-counter triggered ability.
    state, cid = setup(seat)
    state = act(state, seat, {'type': 'suspend', 'card_id': cid})
    remove_time_counters(state, cid, 1)
    flush_staged_triggers(state)
    assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    assert optional_cast(agent(), state, moves(state, seat), seat) is None
    target = state.stack[-1].id
    counter = add_card(state, 'Stifle', Zone.HAND, 3-seat)
    state.players[3-seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': target}})
    state = one(state)
    assert not state.stack and not state.pending_mechanic_choice
    assert state.cards[cid].zone == Zone.EXILE and not state.cards[cid].counters.get('time')
    assert optional_cast(agent(), restore(state), moves(state, seat), seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_unsupported_variable_suspend_not_fabricated(seat):
    from game_state.state import MatchFactory, Step
    own = [{**CARDS['Aeon Chronicler'], 'card_name': 'Aeon Chronicler', 'quantity': 1}]
    other = [{'card_name': 'Swamp', 'quantity': 60}]
    state = MatchFactory.from_decks(own if seat == 1 else other,
                                    other if seat == 1 else own, seed=941)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.priority_player = state.active_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].mana_pool = {'U': 2, 'C': 10}
    assert idle_suspend(agent(), state, moves(state, seat), seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_public_pressure_reserves_tempo(seat):
    from tests.test_ai_recurring_engines import add as canonical_add
    state, _ = setup(seat, 'Ancestral Vision')
    state.turn = 1
    state.players[seat].life = 6
    for _ in range(3): canonical_add(state, 'Grizzly Bears', 3-seat)
    assert idle_suspend(agent(), state, moves(state, seat), seat) is None
