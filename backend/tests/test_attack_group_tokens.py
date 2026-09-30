import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.combat import combat_damage, declare_attackers
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.action_validation import ActionRejected
from effects.handlers import create_token


ADELINE_ORACLE = (
    "Vigilance\nAdeline's power is equal to the number of creatures you control.\n"
    "Whenever you attack, for each opponent, create a 1/1 white Human creature token "
    "that's tapped and attacking that player or a planeswalker they control."
)


def _state():
    deck = [
        {"quantity": 30, "card_name": "Adeline, Resplendent Cathar", "type_line": "Legendary Creature — Human Knight",
         "power": "*", "toughness": "4", "oracle_text": ADELINE_ORACLE},
        {"quantity": 30, "card_name": "Grizzly Bears", "type_line": "Creature — Bear",
         "power": "2", "toughness": "2", "oracle_text": ""},
    ]
    state = MatchFactory.from_decks(deck, deck, seed=38)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS

    def put(name):
        player = state.players[1]
        zone = next(zone for zone in (player.hand, player.library) if any(state.cards[cid].name == name for cid in zone))
        card_id = next(cid for cid in zone if state.cards[cid].name == name)
        zone.remove(card_id)
        player.battlefield.append(card_id)
        card = state.cards[card_id]
        card.move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, card_id)
        card.summoning_sick = False
        return card_id

    return state, put("Adeline, Resplendent Cathar"), put("Grizzly Bears")


def test_adeline_attack_group_triggers_once_and_token_enters_tapped_attacking():
    state, adeline, bear = _state()
    assert effective_power(state, adeline) == 2
    declare_attackers(state, [adeline, bear])
    assert len([item for item in state.stack if item.source_card_id == adeline]) == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(state)
    tokens = [cid for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1
    token = tokens[0]
    assert state.cards[token].tapped
    assert token in state.attackers
    assert state.attack_targets[token] == "player:2"
    assert effective_power(state, adeline) == 3
    assert not state.stack
    combat_damage(state)
    assert state.players[2].life == 14


def test_adeline_triggers_when_another_creature_attacks_without_her():
    state, adeline, bear = _state()
    declare_attackers(state, [bear])
    assert len([item for item in state.stack if item.source_card_id == adeline]) == 1


def test_adeline_does_not_trigger_if_no_attackers_are_declared():
    state, adeline, _ = _state()
    declare_attackers(state, [])
    assert not any(item.source_card_id == adeline for item in state.stack)


def _opposing_planeswalker(state, loyalty=1):
    card = CardInstance(
        id="teferi", name="Teferi, Hero of Dominaria", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Planeswalker"], loyalty=loyalty,
        type_line="Legendary Planeswalker — Teferi",
    )
    state.cards[card.id] = card
    state.players[2].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def test_human_chooses_attacking_token_defender_after_snapshot():
    state, _, bear = _state()
    planeswalker = _opposing_planeswalker(state)
    state.mechanic_choice_players = {1}
    declare_attackers(state, [bear])
    resolve_top_of_stack(state)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    pending = state.pending_mechanic_choice
    assert pending["kind"] == "attacking_token_target"
    assert set(pending["options"]) == {"player:2", f"planeswalker:{planeswalker}"}
    assert not any(state.cards[cid].is_token for cid in state.players[1].battlefield)
    moves = legal_moves(state, 1)
    assert moves[0]["options"] == pending["options"]
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 2, {"type": "choose_mechanic", "card_ids": [f"planeswalker:{planeswalker}"]}, reject_invalid=True)
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": ["planeswalker:missing"]}, reject_invalid=True)
    assert state.pending_mechanic_choice == pending
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": [f"planeswalker:{planeswalker}"]}, reject_invalid=True)
    token = next(cid for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert state.attack_targets[token] == f"planeswalker:{planeswalker}"
    assert state.pending_mechanic_choice is None
    combat_damage(state)
    assert state.players[2].life == 18
    assert state.cards[planeswalker].loyalty == 0


def test_ai_selects_one_loyalty_planeswalker_over_nonlethal_face_damage():
    state, _, bear = _state()
    planeswalker = _opposing_planeswalker(state)
    state.mechanic_choice_players = {1}
    declare_attackers(state, [bear])
    resolve_top_of_stack(state)
    decision = AIAgent().choose_action(state, legal_moves(state, 1), 1)
    assert decision.action == {"type": "choose_mechanic", "card_ids": [f"planeswalker:{planeswalker}"]}


def test_multiple_attacking_tokens_choose_separate_defenders():
    state, _, _ = _state()
    planeswalker = _opposing_planeswalker(state, loyalty=3)
    state.mechanic_choice_players = {1}
    create_token(state, 1, {"name": "Human", "power": 1, "toughness": 1, "amount": 2,
                            "tapped_and_attacking": True})
    assert state.pending_mechanic_choice["kind"] == "attacking_token_target"
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": ["player:2"]}, reject_invalid=True)
    assert state.pending_mechanic_choice["kind"] == "attacking_token_target"
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": [f"planeswalker:{planeswalker}"]}, reject_invalid=True)
    token_targets = [state.attack_targets[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert sorted(token_targets) == sorted(["player:2", f"planeswalker:{planeswalker}"])
    assert state.pending_mechanic_choice is None


def test_stale_planeswalker_choice_is_rejected_before_token_enters():
    state, _, bear = _state()
    planeswalker = _opposing_planeswalker(state)
    state.mechanic_choice_players = {1}
    declare_attackers(state, [bear])
    resolve_top_of_stack(state)
    state.players[2].battlefield.remove(planeswalker)
    state.players[2].graveyard.append(planeswalker)
    state.cards[planeswalker].move_to_zone(Zone.GRAVEYARD)
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": [f"planeswalker:{planeswalker}"]}, reject_invalid=True)
    assert not any(state.cards[cid].is_token for cid in state.players[1].battlefield)
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": ["player:2"]}, reject_invalid=True)
    assert any(state.cards[cid].is_token for cid in state.players[1].battlefield)


def test_attacking_token_count_is_frozen_before_sequential_choices():
    state, _, _ = _state()
    _opposing_planeswalker(state)
    state.mechanic_choice_players = {1}
    for name in ("Forest", "Island"):
        card = CardInstance(id=name.lower(), name=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
                            types=["Land"], type_line=f"Basic Land — {name}")
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)
    create_token(state, 1, {"name": "Human", "power": 1, "toughness": 1,
                            "per_basic_land_type": True, "tapped_and_attacking": True})
    assert state.pending_mechanic_choice["remaining_amount"] == 2
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": ["player:2"]}, reject_invalid=True)
    state.players[1].battlefield.remove("island")
    state.players[1].graveyard.append("island")
    state.cards["island"].move_to_zone(Zone.GRAVEYARD)
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "card_ids": ["player:2"]}, reject_invalid=True)
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == 2
