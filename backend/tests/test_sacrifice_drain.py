"""Sacrifice-triggered targeted drain resolves all printed life changes."""

from effects.handlers import sacrifice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state(*, human=False, self_sacrifice=False, hexproof=False):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=674)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {1} if human else set()
    cards = [CardInstance(
        "egotist", "Popular Egotist", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=3, toughness=2,
        oracle_text="{1}{B}, Sacrifice another creature or enchantment: Popular Egotist gains indestructible until end of turn. Tap it.\n"
                    "Whenever you sacrifice a permanent, target opponent loses 1 life and you gain 1 life.",
    )]
    if not self_sacrifice:
        cards.append(CardInstance("elf", "Llanowar Elves", 1, 1, Zone.BATTLEFIELD, ["Creature"],
                                  power=1, toughness=1, oracle_text="{T}: Add {G}."))
    if hexproof:
        cards.append(CardInstance("leyline", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD,
                                  ["Enchantment"], oracle_text="You have hexproof."))
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


def test_sacrifice_trigger_loses_and_gains_life():
    state = _state()
    sacrifice(state, 1, {"target_card_id": "elf"})
    assert [item.source_card_id for item in state.stack] == ["egotist"]
    assert state.stack[-1].payload["target_player"] == 2
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (21, 19)


def test_human_sacrifice_drain_targets_only_opponent_after_snapshot():
    state = _state(human=True)
    sacrifice(state, 1, {"target_card_id": "elf"})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.pending_trigger_order["phase"] == "targets"
    rules = RulesEngine()
    assert {move.get("target_player") for move in rules.legal_moves(state, 1)} == {2}
    state = checked_action(state, rules, 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_player": 2,
    })
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (21, 19)


def test_hexproof_opponent_prevents_targeted_sacrifice_drain():
    state = _state(hexproof=True)
    sacrifice(state, 1, {"target_card_id": "elf"})
    assert not state.stack
    assert (state.players[1].life, state.players[2].life) == (20, 20)


def test_departed_sacrifice_watcher_still_drains():
    state = _state(self_sacrifice=True)
    sacrifice(state, 1, {"target_card_id": "egotist"})
    assert state.cards["egotist"].zone == Zone.GRAVEYARD
    assert [item.source_card_id for item in state.stack] == ["egotist"]
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (21, 19)


def test_sacrifice_drain_fizzles_both_life_changes_if_target_becomes_illegal():
    state = _state(human=True)
    sacrifice(state, 1, {"target_card_id": "elf"})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_player": 2,
    })
    shield = CardInstance("leyline", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD,
                          ["Enchantment"], oracle_text="You have hexproof.")
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert (state.players[1].life, state.players[2].life) == (20, 20)
