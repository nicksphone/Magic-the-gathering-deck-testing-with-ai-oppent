from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.combat import combat_damage, declare_attackers
from rules_engine.continuous import effective_power
from rules_engine.stack_engine import resolve_top_of_stack


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
