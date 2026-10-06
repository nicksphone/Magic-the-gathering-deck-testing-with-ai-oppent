from __future__ import annotations

from ai.agent import AIDecision, AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from scripts.regression_matrix_replay import run_game


def _state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=29)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_BLOCKERS
    state.blockers_declared = True  # These fixtures start after blocker declaration.
    return state


def _creature(state, cid: str, owner: int, name: str, power: int, toughness: int, keywords: list[str]) -> None:
    card = CardInstance(
        id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
        types=["Creature"], power=power, toughness=toughness, keywords=keywords,
        summoning_sick=False,
    )
    state.cards[cid] = card
    state.players[owner].battlefield.append(cid)


def _enter_damage(state) -> None:
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == Step.COMBAT_DAMAGE


def test_first_strike_attacker_kills_blocker_before_regular_step() -> None:
    state = _state()
    _creature(state, "knight", 1, "Youthful Knight", 2, 1, ["first strike"])
    _creature(state, "bear", 2, "Grizzly Bears", 2, 2, [])
    state.attackers = ["knight"]
    state.blocks = {"knight": ["bear"]}

    _enter_damage(state)
    assert state.combat_damage_stage == "first"
    assert state.cards["bear"].zone == Zone.GRAVEYARD
    assert state.cards["knight"].zone == Zone.BATTLEFIELD

    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.combat_damage_stage == "regular"
    assert state.cards["knight"].zone == Zone.BATTLEFIELD


def test_first_strike_blocker_kills_normal_attacker_before_it_deals_damage() -> None:
    state = _state()
    _creature(state, "bear", 1, "Grizzly Bears", 2, 2, [])
    _creature(state, "knight", 2, "Youthful Knight", 2, 1, ["first strike"])
    state.attackers = ["bear"]
    state.blocks = {"bear": ["knight"]}

    _enter_damage(state)
    assert state.cards["bear"].zone == Zone.GRAVEYARD
    assert state.cards["knight"].zone == Zone.BATTLEFIELD


def test_double_strike_uses_two_priority_windows_and_snapshot_resume() -> None:
    state = _state()
    _creature(state, "swiftblade", 1, "Boros Swiftblade", 1, 2, ["double strike"])
    state.attackers = ["swiftblade"]
    state.attack_targets = {"swiftblade": "player:2"}

    _enter_damage(state)
    assert state.players[2].life == 19
    assert state.combat_damage_stage == "first"
    assert state.combat_damage_resolved is False
    assert serialize_match(state)["combat_damage_stage"] == "first"

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.first_strike_damage_ids == {"swiftblade"}
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.players[2].life == 18
    assert state.combat_damage_stage == "regular"
    assert state.combat_damage_resolved is True

    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == Step.END_COMBAT
    assert state.players[2].life == 18


def test_instant_can_be_cast_after_first_damage_before_regular_damage() -> None:
    state = _state()
    _creature(state, "swiftblade", 1, "Boros Swiftblade", 1, 2, ["double strike"])
    state.attackers = ["swiftblade"]
    state.attack_targets = {"swiftblade": "player:2"}
    _enter_damage(state)
    assert state.players[2].life == 19

    shock = CardInstance(
        id="shock", name="Shock", owner=2, controller=2, zone=Zone.HAND,
        types=["Instant"], mana_cost="{R}", oracle_text="Shock deals 2 damage to any target.",
    )
    state.cards[shock.id] = shock
    state.players[2].hand.append(shock.id)
    state.players[2].mana_pool["R"] = 1
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    assert any(move["type"] == "cast_spell" and move.get("card_id") == shock.id for move in engine.legal_moves(state, 2))
    assert state.combat_damage_stage == "first"


def test_first_strike_membership_is_fixed_before_response_window() -> None:
    state = _state()
    _creature(state, "knight", 1, "Youthful Knight", 2, 1, ["first strike"])
    _creature(state, "bear", 1, "Grizzly Bears", 2, 2, [])
    state.attackers = ["knight", "bear"]
    _enter_damage(state)
    assert state.players[2].life == 18

    state.cards["knight"].keywords = []
    state.cards["bear"].keywords = ["first strike"]
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.players[2].life == 16


def test_replay_keeps_both_combat_damage_priority_windows(monkeypatch) -> None:
    state = _state()
    _creature(state, "swiftblade", 1, "Boros Swiftblade", 1, 2, ["double strike"])
    state.attackers = ["swiftblade"]
    state.attack_targets = {"swiftblade": "player:2"}
    state.blockers_declared = True
    monkeypatch.setattr("scripts.regression_matrix_replay.MatchFactory.from_decks", lambda *args, **kwargs: state)
    monkeypatch.setattr(AIAgent, "choose_action", lambda self, state, legal, pid: AIDecision({"type": "pass_priority"}, "test"))
    original_take_action = RulesEngine.take_action
    windows: list[tuple[str, int]] = []

    def record_action(self, state, player_id, action, *, reject_invalid=False):
        assert action["type"] != "combat_damage"
        original_take_action(self, state, player_id, action, reject_invalid=reject_invalid)
        windows.append((state.combat_damage_stage, state.players[2].life))

    monkeypatch.setattr(RulesEngine, "take_action", record_action)

    deck = [{"quantity": 60, "card_name": "Island"}]
    run_game(deck, deck, seed=29, difficulty="strong", max_ticks=4)
    assert windows[1] == ("first", 19)
    assert windows[3] == ("regular", 18)
