from card_data.fallback_cards import fallback_card_payload
from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from effects.handlers import counter_spell
from rules_engine.ability_model import build_ability_spec
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def test_mana_spent_top_card_selection_is_not_a_draw() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=13)
    canonical = fallback_card_payload("Memory Deluge")
    card = CardInstance(
        id="deluge", name="Memory Deluge", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost=canonical["mana_cost"],
        oracle_text=canonical["oracle_text"],
    )
    spec = build_ability_spec(state, card, 1)
    assert spec.effect.key == "look_top_select_hand"
    assert spec.effect.payload["hand_count"] == 2
    assert spec.effect.payload["top_n_source"] == "mana_spent_to_cast"


def test_paid_memory_deluge_pauses_for_two_cards_and_resumes_after_snapshot() -> None:
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."}]
    state = MatchFactory.from_decks(deck, deck, seed=17)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DRAW
    state.priority_player = 1
    state.mechanic_choice_players.add(1)
    player = state.players[1]
    for _ in range(4):
        land_id = player.library.pop()
        player.battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
    top_ids = list(player.library[-4:])
    for cid, name, cost in zip(top_ids, ("Island", "Negate", "Counterspell", "Sheoldred, the Apocalypse"),
                               ("", "{1}{U}", "{U}{U}", "{2}{B}{B}")):
        state.cards[cid].name = name
        state.cards[cid].mana_cost = cost
    canonical = fallback_card_payload("Memory Deluge")
    deluge = CardInstance(
        id="deluge", name="Memory Deluge", owner=1, controller=1,
        zone=Zone.HAND, types=["Instant"], mana_cost=canonical["mana_cost"],
        oracle_text=canonical["oracle_text"],
    )
    state.cards[deluge.id] = deluge
    player.hand.append(deluge.id)

    rules = RulesEngine()
    rules.take_action(state, 1, {"type": "cast_spell", "card_id": deluge.id, "targets": {}}, reject_invalid=True)
    assert state.stack[-1].effect_key == "look_top_select_hand"
    assert state.stack[-1].payload["mana_spent_to_cast"] == 4
    assert all(state.cards[cid].tapped for cid in player.battlefield)
    assert resolve_top_of_stack(state) is False
    assert state.pending_mechanic_choice["kind"] == "look_top_select_hand"
    assert state.pending_mechanic_choice["count"] == 2
    assert set(state.pending_mechanic_choice["options"]) == set(top_ids)
    assert not set(top_ids).intersection(player.hand)
    decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, rules.legal_moves(state, 1), 1)
    assert decision.action["type"] == "choose_mechanic"
    assert len(decision.action["card_ids"]) == 2
    assert set(decision.action["card_ids"]).issubset(top_ids)

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    chosen = [top_ids[1], top_ids[3]]
    rules.take_action(restored, 1, {"type": "choose_mechanic", "card_ids": chosen}, reject_invalid=True)
    assert restored.pending_mechanic_choice is None
    assert set(chosen).issubset(restored.players[1].hand)
    assert set(restored.players[1].library[:2]) == set(top_ids) - set(chosen)
    assert restored.cards[deluge.id].zone == Zone.GRAVEYARD
    assert not any("draws a card" in line for line in restored.log)


def test_flashback_memory_deluge_looks_at_seven_and_exiles_after_resolution() -> None:
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}."}]
    state = MatchFactory.from_decks(deck, deck, seed=31)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DRAW
    state.priority_player = 1
    player = state.players[1]
    for _ in range(7):
        land_id = player.library.pop()
        player.battlefield.append(land_id)
        state.cards[land_id].zone = Zone.BATTLEFIELD
    top_ids = set(player.library[-7:])
    canonical = fallback_card_payload("Memory Deluge")
    deluge = CardInstance(
        id="deluge-flashback", name="Memory Deluge", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Instant"], mana_cost=canonical["mana_cost"],
        oracle_text=canonical["oracle_text"],
    )
    state.cards[deluge.id] = deluge
    player.graveyard.append(deluge.id)
    before_hand = len(player.hand)
    before_library = len(player.library)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == deluge.id and move["type"] == "cast_spell")
    assert move["from_graveyard"] is True
    assert [option["id"] for option in move["cost_options"]] == ["flashback"]
    RulesEngine().take_action(state, 1, {
        "type": "cast_spell", "card_id": deluge.id, "from_graveyard": True,
        "cost_choice": {"id": "flashback"}, "targets": {},
    }, reject_invalid=True)
    assert state.stack[-1].effect_key == "look_top_select_hand"
    assert state.stack[-1].payload["mana_spent_to_cast"] == 7
    assert resolve_top_of_stack(state) is False
    choice = AIAgent(difficulty="master", archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert len(choice.action["card_ids"]) == 2
    RulesEngine().take_action(state, 1, choice.action, reject_invalid=True)
    assert len(player.hand) == before_hand + 2
    assert len(player.library) == before_library - 2
    assert set(player.library[:5]) == top_ids - set(player.hand)
    assert deluge.zone == Zone.EXILE


def test_countered_flashback_spell_is_exiled() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=29)
    canonical = fallback_card_payload("Memory Deluge")
    deluge = CardInstance(
        id="deluge", name="Memory Deluge", owner=1, controller=1,
        zone=Zone.STACK, types=["Instant"], mana_cost=canonical["mana_cost"],
        oracle_text=canonical["oracle_text"],
    )
    state.cards[deluge.id] = deluge
    state.stack.append(StackItem(
        "deluge-stack", deluge.id, 1, deluge.name, "look_top_select_hand",
        {"mana_spent_to_cast": 7, "hand_count": 2, "__flashback": True},
    ))
    counter_spell(state, 2, {"target_stack_id": "deluge-stack"})
    assert state.stack == []
    assert deluge.zone == Zone.EXILE
    assert deluge.id in state.players[1].exile
    assert deluge.id not in state.players[1].graveyard
