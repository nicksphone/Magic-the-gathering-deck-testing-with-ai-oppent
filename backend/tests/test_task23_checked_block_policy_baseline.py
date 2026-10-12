"""Current production choice on full-menu canonical old-board combat roots."""
import json

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_task23_canonical_block_outcomes import blocked, position, Zone, Step


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('scenario', ['equal_life_single', 'first_strike', 'lethal_trample', 'deathtouch_removed'])
def test_current_choice_survives_and_avoids_strictly_dominated_material_loss(seat, difficulty, scenario):
    kwargs = {'first_strike': scenario == 'first_strike', 'trample': scenario == 'lethal_trample'}
    if scenario == 'deathtouch_removed':
        kwargs.update(large_counters=4, remove_deathtouch=True)
    root, attacker, cheap, large, first = position(seat, **kwargs)
    # Declared starting life, not an injected winner or replayed causal life loss.
    root.players[seat].life = 6 if scenario == 'lethal_trample' else 1
    before = serialize_match_snapshot(root)
    legal = RulesEngine().legal_moves(root, seat)
    decision = AIAgent(difficulty=difficulty, archetype='Midrange').choose_action(root, legal, seat)
    assert decision.action['type'] == 'block'
    assignment = decision.action.get('blocks') or {}
    assert not set(assignment) - {attacker}
    chosen = assignment.get(attacker) or []
    outcome = blocked(root, seat, attacker, chosen)
    print(json.dumps({'seat': seat, 'difficulty': difficulty, 'scenario': scenario,
        'selected': ['cheap' if cid == cheap else 'large' if cid == large else 'first' for cid in chosen],
        'life': outcome.players[seat].life,
        'attacker_zone': outcome.cards[attacker].zone.value,
        'cheap_zone': outcome.cards[cheap].zone.value,
        'large_zone': outcome.cards[large].zone.value,
        'first_zone': outcome.cards[first].zone.value if first else None}, sort_keys=True))
    assert serialize_match_snapshot(root) == before
    assert outcome.winner != 3 - seat, 'A legal checked blocking plan prevents immediate loss'
    if scenario == 'equal_life_single':
        assert chosen != [large], 'Equivalent small block saves the same life while retaining strictly more material'
    elif scenario == 'first_strike':
        assert first in chosen
        assert outcome.cards[first].zone == Zone.BATTLEFIELD
        assert outcome.cards[attacker].zone == Zone.GRAVEYARD
    elif scenario == 'lethal_trample':
        assert set(chosen) == {cheap, large}
        assert outcome.players[seat].life == 1 and outcome.cards[attacker].zone == Zone.GRAVEYARD
    else:
        assert outcome.cards[large].zone == Zone.BATTLEFIELD
        assert outcome.cards[attacker].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('difficulty', ['easy', 'strong'])
def test_disabled_search_retains_legacy_non_match_state_fallback(difficulty):
    assert AIAgent(difficulty=difficulty)._search_block_assignments(None, [], []) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['nonlethal', 'nontrample', 'other_step', 'nonplayer_target', 'too_many', 'exhausted'])
def test_emergency_admission_stays_bounded_and_does_not_relabel_unknown(seat, case, monkeypatch):
    from ai import block_search
    root, attacker, _, _, _ = position(seat, trample=case != 'nontrample')
    root.players[seat].life = 6
    if case == 'nonlethal':
        root.players[seat].life = 20
    elif case == 'other_step':
        root.step = Step.POSTCOMBAT_MAIN
    elif case == 'nonplayer_target':
        # Admission-only protocol control, not a legal permanent-target episode.
        root.attack_targets[attacker] = 'card:protocol-target'
    move = next(move for move in RulesEngine().legal_moves(root, seat) if move['type'] == 'block') if case != 'other_step' else None
    attackers = [{'id': attacker}]
    blockers = move['blockers'] if move else [{'id': cid} for cid in root.players[seat].battlefield]
    if case == 'too_many':
        blockers = blockers * 3
    elif case == 'exhausted':
        monkeypatch.setattr(block_search, 'block_intents', lambda *args, **kwargs: None)
    before = serialize_match_snapshot(root)
    assert AIAgent(difficulty='strong')._search_block_assignments(root, attackers, blockers) is None
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', ['first_strike', 'no_deathtouch'])
def test_emergency_uses_effective_traits_and_real_first_strike_outcomes(seat, scenario):
    root, attacker, cheap, large, first = position(seat, trample=True,
        first_strike=scenario == 'first_strike', remove_deathtouch=scenario == 'no_deathtouch')
    root.players[seat].life = 6
    action = AIAgent(difficulty='strong').choose_action(root, RulesEngine().legal_moves(root, seat), seat).action
    assert action['type'] == 'block'
    chosen = (action.get('blocks') or {}).get(attacker) or []
    result = blocked(root, seat, attacker, chosen)
    assert result.winner != 3 - seat
    if first:
        assert first in chosen and result.cards[first].zone == Zone.BATTLEFIELD
        assert result.cards[attacker].zone == Zone.GRAVEYARD
    else:
        assert result.cards[attacker].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_combat_projection_keeps_legacy_fallback_without_claiming_survival(seat, monkeypatch):
    root, attacker, _, _, _ = position(seat, trample=True)
    root.players[seat].life = 6
    move = next(move for move in RulesEngine().legal_moves(root, seat) if move['type'] == 'block')
    agent = AIAgent(difficulty='strong')
    # Protocol unknown: no invented combat outcome or narrowed legal menu.
    monkeypatch.setattr(agent, '_finish_combat_projection', lambda *args: False)
    before = serialize_match_snapshot(root)
    assert agent._search_block_assignments(root, [{'id': attacker}], move['blockers']) is None
    assert serialize_match_snapshot(root) == before
