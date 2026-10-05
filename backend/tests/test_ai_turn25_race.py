"""Public-board reconstruction, not an exact historical action replay.

Cards/last-known information come from read-only game fdb8f0e8's turn-27
snapshot. Turn-25 life (A9/B18), readiness and the all-single-block mapping
are reconstructed from the log/deaths. Hands and later plays are excluded.
"""
import json
from pathlib import Path
import pytest

from ai.agent import AIAgent, NEXT_COMBAT_FORECAST_BUDGET
from ai.pending_effects import planning_copy
from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone
from rules_engine.continuous import effective_combat_stats


ADELINE = "p1-044"
INITIATE = "p1-015"
HUMAN = "00000000-0000-0000-0000-000000000036"
STOMPERS = ["p2-057", "p2-053", "p2-009"]


def reconstructed_board():
    raw = json.loads(Path(__file__).with_name("fixtures").joinpath(
        "turn25_race_public_cards.json").read_text())
    state = MatchState(id="reconstructed-turn25", players={
        1: PlayerState(1, "Player A", life=9),
        2: PlayerState(2, "Player B", life=18),
    }, cards={}, stack=[])
    for cid, data in raw.items():
        data["zone"] = Zone.BATTLEFIELD
        data["counters"] = {"+1/+1": 1} if cid == INITIATE else {}
        data["tapped"] = cid in {INITIATE, HUMAN}
        data["summoning_sick"] = cid == HUMAN
        state.cards[cid] = CardInstance(**data)
        state.players[data["controller"]].battlefield.append(cid)
    # Observed later library IDs/counts, deliberately no identities or order
    # knowledge. Only enough cards to avoid a spurious empty-library loss.
    libraries = json.loads(Path(__file__).with_name("fixtures").joinpath(
        "turn25_race_opaque_libraries.json").read_text())
    for pid, ids in libraries.items():
        player_id = int(pid)
        state.players[player_id].library = ids
        for cid in ids:
            state.cards[cid] = CardInstance(cid, "", player_id, player_id, Zone.LIBRARY)
            state.cards[cid].ai_unknown = True
    state.turn = 25
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [ADELINE, INITIATE, HUMAN]
    state.attack_targets = {cid: "player:2" for cid in state.attackers}
    state.attackers_declared = True
    state.kept_hands = {1, 2}
    state.pregame_pending = False
    return state


def resolve_blocks(agent, state, blocks):
    sim = planning_copy(state)
    agent.engine.take_action(sim, 3 - state.active_player,
        {"type": "block", "blocks": blocks}, reject_invalid=True)
    assert agent._finish_combat_projection(sim, state)
    return sim


def next_public_attack(agent, state):
    # Conditional board-only forecast: no intervening spells, draws or choices.
    sim = planning_copy(state)
    agent.engine._clear_marked_damage(sim)
    sim.turn = 26
    sim.active_player = sim.priority_player = 2
    sim.step = Step.DECLARE_ATTACKERS
    sim.attackers = []
    sim.attack_targets = {}
    sim.blocks = {}
    sim.attackers_declared = sim.blockers_declared = False
    sim.combat_damage_resolved = False
    sim.combat_damage_stage = "none"
    for cid in sim.players[2].battlefield:
        sim.cards[cid].tapped = False
        sim.cards[cid].summoning_sick = False
    return sim


def test_reconstructed_decline_blocks_accounts_for_next_turn_death_trigger():
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    assert [effective_combat_stats(root, cid) for cid in root.attackers] == [(4, 5), (3, 4), (2, 2)]
    no_blocks = resolve_blocks(agent, root, {})
    assert (no_blocks.players[1].life, no_blocks.players[2].life) == (9, 9)
    future = next_public_attack(agent, no_blocks)
    outcome = agent._project_attack_line(future, 2, STOMPERS, consider_next_combat=False)
    assert outcome is not None
    assert outcome[0].winner == 2
    assert outcome[0].players[1].life == 0
    # Check every legal block, not just the heuristic's chosen response.
    from ai.block_search import block_intents
    agent.engine.take_action(future, 2, {"type": "attack", "attackers": STOMPERS}, reject_invalid=True)
    agent.engine.next_step(future)
    for blocks in block_intents(future, STOMPERS, [ADELINE]):
        result = resolve_blocks(agent, future, blocks)
        assert result.winner == 2


def test_reconstructed_all_single_blocks_matches_observed_deaths_and_life():
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    blocks = {ADELINE: "p2-009", INITIATE: "p2-053", HUMAN: "p2-057"}
    traded = resolve_blocks(agent, root, blocks)
    assert (traded.players[1].life, traded.players[2].life) == (8, 20)
    assert traded.cards[INITIATE].zone == Zone.GRAVEYARD
    assert traded.cards["p2-009"].zone == Zone.GRAVEYARD
    assert traded.cards[HUMAN].zone != Zone.BATTLEFIELD
    future = next_public_attack(agent, traded)
    outcome = agent._project_attack_line(future, 2, STOMPERS[:2], consider_next_combat=False)
    assert outcome is not None
    assert outcome[0].winner is None
    assert outcome[0].players[1].life == 4


@pytest.mark.parametrize("defender", [1, 2])
def test_master_preserves_reconstructed_next_combat_win_without_mutating_root(defender, monkeypatch):
    from game_state.serializers import serialize_match_snapshot
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    if defender == 1:
        root.players = {3 - pid: player for pid, player in root.players.items()}
        for player in root.players.values():
            player.id = 3 - player.id
        for card in root.cards.values():
            card.owner = 3 - card.owner
            card.controller = 3 - card.controller
        root.active_player = 2
        root.priority_player = 1
        root.attack_targets = {cid: "player:1" for cid in root.attackers}
    before = serialize_match_snapshot(root)
    forecast = agent._next_board_attack_wins
    calls = []

    def tracked_forecast(sim, player_id):
        calls.append(player_id)
        return forecast(sim, player_id)

    monkeypatch.setattr(agent, "_next_board_attack_wins", tracked_forecast)
    choice = agent._choose_blocks(root, [{"id": cid} for cid in root.attackers],
                                  [{"id": cid} for cid in STOMPERS])
    assert set(choice) == {ADELINE, INITIATE}
    assert len(choice[ADELINE]) == 2
    assert 0 < len(calls) <= NEXT_COMBAT_FORECAST_BUDGET
    after = resolve_blocks(agent, root, choice)
    assert agent._next_board_attack_wins(after, defender)
    assert serialize_match_snapshot(root) == before


def test_next_combat_forecast_does_not_claim_win_without_death_trigger():
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    root.players[2].battlefield.remove("p2-020")
    root.cards["p2-020"].zone = Zone.GRAVEYARD
    after = resolve_blocks(agent, root, {})
    assert not agent._next_board_attack_wins(after, 2)


def test_adeline_characteristic_power_and_vigilance_not_stored_base_power():
    from rules_engine.continuous import effective_keywords
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    root.cards[ADELINE].power = 999
    root.cards[ADELINE].printed_power = "*"
    assert effective_combat_stats(root, ADELINE) == (4, 5)
    assert "vigilance" in effective_keywords(root, ADELINE)
    root.players[1].battlefield.remove(INITIATE)
    root.players[1].battlefield.remove(HUMAN)
    assert effective_combat_stats(root, ADELINE) == (2, 5)
    root.step = Step.DECLARE_ATTACKERS
    root.priority_player = 1
    root.attackers_declared = False
    root.attackers = []
    root.attack_targets = {}
    agent.engine.take_action(root, 1, {"type": "attack", "attackers": [ADELINE]}, reject_invalid=True)
    assert not root.cards[ADELINE].tapped


def test_next_combat_unknown_choice_is_not_a_win():
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    after = resolve_blocks(agent, root, {})
    after.pending_mechanic_choice = {"kind": "unknown", "player_id": 1}
    assert not agent._next_board_attack_wins(after, 2)


def test_next_combat_without_anthem_is_not_a_win():
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    root.players[1].battlefield.remove("p1-053")
    root.cards["p1-053"].zone = Zone.GRAVEYARD
    after = resolve_blocks(agent, root, {})
    assert not agent._next_board_attack_wins(after, 2)


def high_life_board():
    # Counterfactual workload, not an observed game state.
    root = reconstructed_board()
    root.players[1].life = root.players[2].life = 100
    return root


def record_submitted_blocks(monkeypatch, agent):
    take_action = agent.engine.take_action

    def tracked_action(sim, player_id, action, **kwargs):
        if action.get("type") == "block":
            # Combat deaths prune sim.blocks; retain the submitted intent.
            sim.test_block_intent = {aid: list(bids) for aid, bids in action["blocks"].items()}
        return take_action(sim, player_id, action, **kwargs)

    monkeypatch.setattr(agent.engine, "take_action", tracked_action)


@pytest.mark.parametrize("late_win", [False, True])
def test_forecast_budget_keeps_baseline_when_only_unvisited_line_would_win(monkeypatch, late_win):
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = high_life_board()
    attackers = [{"id": cid} for cid in root.attackers]
    blockers = [{"id": cid} for cid in STOMPERS]
    baseline = agent._search_block_assignments(root, attackers, blockers, consider_next_combat=False)
    calls = []
    record_submitted_blocks(monkeypatch, agent)

    def forecast(sim, player_id):
        calls.append(sim.test_block_intent)
        # A hypothetical win beyond the budget must never be consulted.
        return late_win and len(calls) > NEXT_COMBAT_FORECAST_BUDGET

    monkeypatch.setattr(agent, "_next_board_attack_wins", forecast)
    assert agent._search_block_assignments(root, attackers, blockers) == baseline
    assert len(calls) == NEXT_COMBAT_FORECAST_BUDGET
    assert calls[-1] == {}
    assert len({tuple(sorted((aid, tuple(bids)) for aid, bids in blocks.items()))
                for blocks in calls}) == len(calls)


def test_forecast_budget_reserves_low_ranked_legal_no_block(monkeypatch):
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = high_life_board()
    calls = []
    record_submitted_blocks(monkeypatch, agent)

    def forecast(sim, player_id):
        calls.append(sim.test_block_intent)
        return not sim.test_block_intent

    monkeypatch.setattr(agent, "_next_board_attack_wins", forecast)
    assert agent._choose_blocks(root, [{"id": cid} for cid in root.attackers],
                                [{"id": cid} for cid in STOMPERS]) == {}
    assert len(calls) == NEXT_COMBAT_FORECAST_BUDGET


def test_next_combat_forecast_disables_nested_race_search(monkeypatch):
    agent = AIAgent(difficulty="master", archetype="Ramp")
    root = reconstructed_board()
    after = resolve_blocks(agent, root, {})
    calls = []
    search = agent._search_block_assignments

    def tracked_search(*args, **kwargs):
        calls.append(kwargs.get("consider_next_combat", True))
        return search(*args, **kwargs)

    monkeypatch.setattr(agent, "_search_block_assignments", tracked_search)
    assert agent._next_board_attack_wins(after, 2)
    assert calls == [False]
