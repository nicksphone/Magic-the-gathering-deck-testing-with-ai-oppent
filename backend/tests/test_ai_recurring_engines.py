"""Canonical public-board payoffs; fixture states are not competitive decks."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.heuristics import recurring_engine_value, _creature_value
from ai.pending_effects import unanswered_action_loses
from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.card_types import printed_card_types
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action


CARDS = {card["name"]: card for card in json.loads(
    (Path(__file__).parent / "fixtures" / "recurring_engines.json").read_text())}


def fixture():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=941)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {"B": 10, "G": 2, "C": 10}
    return state


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    raw = CARDS[name]
    card = CardInstance(id=state.allocate_object_id(), name=name, owner=player, controller=player,
                        zone=zone, types=printed_card_types(raw["type_line"]), type_line=raw["type_line"],
                        mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
                        power=int(raw["power"]) if raw["power"] is not None else None,
                        toughness=int(raw["toughness"]) if raw["toughness"] is not None else None,
                        keywords=raw["keywords"] or [], colors=raw["colors"] or [])
    state.cards[card.id] = card
    getattr(state.players[player], zone.value).append(card.id)
    return card


def resolve(state):
    rules = RulesEngine()
    for _ in range(64):
        if not state.stack or state.winner is not None:
            return state
        state = checked_action(state, rules, state.priority_player, {"type": "pass_priority"})
    raise AssertionError("Unresolved fixture stack")


def wipe_state():
    state = fixture()
    state.players[1].life = 1
    engine = add(state, "The Meathook Massacre", 2)
    bear = add(state, "Grizzly Bears", 2)
    wipe = add(state, "Damnation", zone=Zone.HAND)
    answer = add(state, "Naturalize", zone=Zone.HAND)
    return state, engine, bear, wipe, answer


def test_recurring_creature_rewards_survive_stats_scoring_without_mutating_state():
    state = fixture()
    artist = add(state, "Blood Artist")
    bear = add(state, "Grizzly Bears")
    before = serialize_match_snapshot(state)
    assert recurring_engine_value(state, artist.id) > 0
    assert _creature_value(state, artist.id) > _creature_value(state, bear.id)
    assert serialize_match_snapshot(state) == before
    add(state, "Rest in Peace", 2)
    before = serialize_match_snapshot(state)
    assert recurring_engine_value(state, artist.id) == 0
    assert _creature_value(state, artist.id) < _creature_value(state, bear.id)
    assert serialize_match_snapshot(state) == before


def test_eligibility_not_trigger_condition_or_spent_entry_text_sets_rewards():
    state = fixture()
    hulk = add(state, "Torrential Gearhulk")
    assert recurring_engine_value(state, hulk.id) == 0
    sheoldred = add(state, "Sheoldred, the Apocalypse")
    assert recurring_engine_value(state, sheoldred.id) == 6  # draw is the condition, not the reward
    haruspex = add(state, "Grim Haruspex")
    assert recurring_engine_value(state, haruspex.id) == 3
    state.players[1].battlefield.remove(hulk.id)
    state.players[1].battlefield.remove(sheoldred.id)
    assert recurring_engine_value(state, haruspex.id) == 0  # another nontoken creature required


@pytest.mark.parametrize("style", ["Aggro", "Tokens", "Tribal", "Tempo", "Midrange", "Drain", "Aristocrats", "Control", "Ramp"])
def test_live_creature_payoff_affects_threat_and_cast_values_across_styles(style):
    state = fixture()
    artist = add(state, "Blood Artist", 2)
    bear = add(state, "Grizzly Bears", 2)
    ai = AIAgent(archetype=style)
    assert ai._creature_threat_score(state, artist.id, 1) > ai._creature_threat_score(state, bear.id, 1)
    cast = add(state, "Blood Artist", zone=Zone.HAND)
    move = {"type": "cast_spell", "card_id": cast.id}
    before = ai._cast_bias(state, move, 1)
    add(state, "Rest in Peace", 2)
    assert ai._cast_bias(state, move, 1) < before


def test_projected_wipe_loss_is_real_and_preserves_authoritative_snapshot():
    state, _, _, wipe, _ = wipe_state()
    before = serialize_match_snapshot(state)
    action = {"type": "cast_spell", "card_id": wipe.id, "targets": {}}
    assert unanswered_action_loses(state, 1, action) is True
    assert serialize_match_snapshot(state) == before
    clone = deserialize_match_snapshot(before)
    clone = checked_action(clone, RulesEngine(), 1, action)
    clone = resolve(clone)
    assert clone.winner == 2 and clone.players[1].life == 0


@pytest.mark.parametrize("style", ["Aggro", "Tokens", "Tempo", "Midrange", "Drain", "Aristocrats", "Control", "Ramp"])
def test_remove_public_payoff_before_wiping_instead_of_losing(style):
    state, engine, bear, wipe, answer = wipe_state()
    before = serialize_match_snapshot(state)
    agent = AIAgent(archetype=style, difficulty="master")
    action = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action["card_id"] == answer.id
    assert action["targets"]["target_card_id"] == engine.id
    assert serialize_match_snapshot(state) == before
    state = resolve(checked_action(state, RulesEngine(), 1, action))
    assert engine.id not in state.players[2].battlefield and state.winner is None
    assert unanswered_action_loses(state, 1, {"type": "cast_spell", "card_id": wipe.id, "targets": {}}) is False
    action = agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action["card_id"] == wipe.id
    state = resolve(checked_action(state, RulesEngine(), 1, action))
    assert bear.id not in state.players[2].battlefield
    assert state.players[1].life == 1 and state.winner is None


def test_uncertain_projection_keeps_move_and_no_public_risk_skips_projection():
    state, _, _, wipe, _ = wipe_state()
    moves = RulesEngine().legal_moves(state, 1)
    agent = AIAgent(archetype="Control")
    with patch("ai.pending_effects.unanswered_action_loses", return_value=None):
        assert agent._without_losing_mass_destruction(state, moves, 1) == moves
    state.players[2].battlefield.clear()
    with patch("ai.pending_effects.unanswered_action_loses", side_effect=AssertionError("unnecessary projection")):
        assert agent._without_losing_mass_destruction(state, moves, 1) == moves


def test_snapshot_resume_preserves_safe_sequence_and_decision_purity():
    state, _, _, _, answer = wipe_state()
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    agent = AIAgent(archetype="Midrange", difficulty="master")
    action = agent.choose_action(restored, RulesEngine().legal_moves(restored, 1), 1).action
    assert action["card_id"] == answer.id
    assert serialize_match_snapshot(restored) == before
    assert action == agent.choose_action(state, RulesEngine().legal_moves(state, 1), 1).action


def test_opponent_trigger_target_choice_does_not_certify_loss():
    state = fixture()
    state.players[1].life = 1
    add(state, "Blood Artist", 2)
    add(state, "Grizzly Bears", 2)
    wipe = add(state, "Damnation", zone=Zone.HAND)
    before = serialize_match_snapshot(state)
    assert unanswered_action_loses(state, 1, {"type": "cast_spell", "card_id": wipe.id,
                                             "targets": {}}) is None
    assert serialize_match_snapshot(state) == before


def test_multiple_death_replacements_do_not_mutate_valuation_logs():
    state = fixture()
    artist = add(state, "Blood Artist")
    add(state, "Rest in Peace", 1)
    add(state, "Rest in Peace", 2)
    before = serialize_match_snapshot(state)
    assert recurring_engine_value(state, artist.id) == 0
    assert serialize_match_snapshot(state) == before
