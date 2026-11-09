"""Canonical death-draw uncertainty must not select a proven native combat loss."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.pending_effects import combat_expansion_available, decision_projection_scope
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache
from tests.test_ai_block_retention import position, declare, decide_and_finish


def combat_root(seat, *, first_strike=False, empty_library=False):
    names = ['Sprite Dragon', 'Grim Haruspex']
    if first_strike:
        names.append('Thalia, Guardian of Thraben')
    state, attackers, blockers, _ = position(seat, ['Grizzly Bears'], names, life=2)
    # Declared old-board tap/depleted-library conditions, not claimed paid setup.
    state.cards[blockers[1]].tapped = True
    if empty_library:
        player = state.players[seat]
        for cid in player.library:
            state.cards[cid].move_to_zone(Zone.EXILE)
        player.exile.extend(player.library)
        player.library.clear()
    state = declare(state, seat, attackers)
    offered = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'block')
    assert blockers[0] in {b['id'] for b in offered['blockers']}
    assert blockers[1] not in {b['id'] for b in offered['blockers']}
    assert state.players[seat].life == 2 and not state.players[seat].hand
    assert not state.stack and state.winner is None
    return state, attackers[0], blockers


def finish(root, seat, groups):
    normalized = {aid: [bids] if isinstance(bids, str) else list(bids)
                  for aid, bids in groups.items()}
    state = checked_action(root, RulesEngine(), seat, {'type': 'block', 'blocks': normalized})
    for _ in range(80):
        if state.winner is not None or state.step == Step.END_COMBAT:
            return state
        if state.pending_mechanic_choice:
            owner = state.pending_mechanic_choice['player_id']
            move = AIAgent().choose_action(state, RulesEngine().legal_moves(state, owner), owner).action
        else:
            owner = state.priority_player
            move = {'type': 'pass_priority'}
        state = checked_action(state, RulesEngine(), owner, move)
    raise AssertionError('Native death-draw combat did not finish')


@pytest.mark.parametrize('seat', [1, 2])
def test_native_block_draws_and_survives_while_no_block_loses(seat):
    root, attacker, blockers = combat_root(seat)
    before = serialize_match_snapshot(root)
    survived = finish(root, seat, {attacker: [blockers[0]]})
    lost = finish(root, seat, {})
    assert survived.winner is None and survived.players[seat].life == 2
    assert survived.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert survived.cards[blockers[1]].zone == Zone.BATTLEFIELD
    assert len(survived.players[seat].hand) == 1
    assert len(survived.players[seat].library) == len(root.players[seat].library)-1
    assert lost.winner == 3-seat
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
@pytest.mark.parametrize('restored', [False, True])
def test_actual_chooser_keeps_survival_when_death_draw_projection_is_unknown(seat, difficulty, restored):
    root, _, blockers = combat_root(seat)
    before = serialize_match_snapshot(root)
    state = deserialize_match_snapshot(deepcopy(before)) if restored else root
    rng = state.rng.getstate()
    _, outcome = decide_and_finish(state, seat, 'Aristocrats', difficulty)
    assert outcome.winner is None and outcome.players[seat].life == 2
    assert outcome.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert len(outcome.players[seat].hand) == 1
    assert serialize_match_snapshot(root) == serialize_match_snapshot(state) == before
    assert state.rng.getstate() == rng and query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_search_does_not_rank_hidden_draw_as_a_completed_survival(seat):
    root, _, _ = combat_root(seat)
    before = serialize_match_snapshot(root)
    offered = next(m for m in RulesEngine().legal_moves(root, seat) if m['type'] == 'block')
    original = deepcopy(offered)
    with decision_projection_scope(root, seat, 8):
        selected = AIAgent('master')._search_block_assignments(root,
            offered['attackers'], offered['blockers'], consider_next_combat=False)
        assert combat_expansion_available()
    assert selected is None
    assert serialize_match_snapshot(root) == before and offered == original
    assert query_cache(root) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_known_safe_first_strike_incumbent_is_kept_despite_an_unknown_candidate(seat):
    root, attacker, blockers = combat_root(seat, first_strike=True)
    before = serialize_match_snapshot(root)
    offered = next(m for m in RulesEngine().legal_moves(root, seat) if m['type'] == 'block')
    with decision_projection_scope(root, seat, 8):
        selected = AIAgent('master')._search_block_assignments(root,
            offered['attackers'], offered['blockers'], consider_next_combat=False)
        assert combat_expansion_available()
    assert selected is not None
    actual = finish(root, seat, selected)
    assert actual.winner is None and actual.players[seat].life == 2
    assert actual.cards[attacker].zone == Zone.GRAVEYARD
    assert all(actual.cards[cid].zone == Zone.BATTLEFIELD for cid in blockers)
    assert not actual.players[seat].hand
    assert serialize_match_snapshot(root) == before and query_cache(root) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_known_empty_library_losses_remain_rankable_without_survival_claim(seat):
    root, attacker, blockers = combat_root(seat, empty_library=True)
    before = serialize_match_snapshot(root)
    assert finish(root, seat, {}).winner == 3-seat
    assert finish(root, seat, {attacker: [blockers[0]]}).winner == 3-seat
    offered = next(m for m in RulesEngine().legal_moves(root, seat) if m['type'] == 'block')
    with decision_projection_scope(root, seat, 8):
        selected = AIAgent('master')._search_block_assignments(root,
            offered['attackers'], offered['blockers'], consider_next_combat=False)
        assert combat_expansion_available()
    assert selected is not None
    assert finish(root, seat, selected).winner == 3-seat
    assert serialize_match_snapshot(root) == before and query_cache(root) is None
