from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine import combat
from rules_engine.stack_engine import resolve_top_of_stack


HOPEFUL_ORACLE = (
    "Training (Whenever this creature attacks with another creature with greater power, "
    "put a +1/+1 counter on this creature.)\n"
    "{2}{W}, Remove two +1/+1 counters from among creatures you control: "
    "Destroy target artifact or enchantment."
)


def _attack_state(companion_power=2, companions=1):
    deck = [
        {"quantity": 30, "card_name": "Hopeful Initiate", "type_line": "Creature — Human Warlock",
         "mana_cost": "{W}", "power": "1", "toughness": "2", "oracle_text": HOPEFUL_ORACLE},
        {"quantity": 30, "card_name": "Grizzly Bears", "type_line": "Creature — Bear",
         "mana_cost": "{1}{G}", "power": "2", "toughness": "2", "oracle_text": ""},
    ]
    state = MatchFactory.from_decks(deck, deck, seed=27)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.DECLARE_ATTACKERS
    state.active_player = state.priority_player = 1

    def put(name):
        cards = state.players[1]
        zone = next(zone for zone in (cards.hand, cards.library) if any(state.cards[cid].name == name for cid in zone))
        card_id = next(cid for cid in zone if state.cards[cid].name == name)
        zone.remove(card_id)
        cards.battlefield.append(card_id)
        card = state.cards[card_id]
        card.move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, card_id)
        card.summoning_sick = False
        return card_id

    trainer = put("Hopeful Initiate")
    others = [put("Grizzly Bears") for _ in range(companions)]
    for card_id in others:
        state.cards[card_id].power = companion_power
    return state, trainer, others


def test_training_triggers_once_for_multiple_larger_attackers_and_survives_snapshot():
    state, trainer, others = _attack_state(companions=2)
    combat.declare_attackers(state, [trainer, *others])
    assert len([item for item in state.stack if item.source_card_id == trainer]) == 1
    assert state.cards[trainer].counters.get("+1/+1", 0) == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    for card_id in others:
        state.cards[card_id].power = 0
    resolve_top_of_stack(state)
    assert state.cards[trainer].counters["+1/+1"] == 1


def test_training_does_not_trigger_for_equal_power_attackers():
    state, trainer, others = _attack_state(companion_power=1)
    combat.declare_attackers(state, [trainer, *others])
    assert not any(item.source_card_id == trainer for item in state.stack)


def test_training_does_not_trigger_when_attacking_alone():
    state, trainer, _ = _attack_state()
    combat.declare_attackers(state, [trainer])
    assert not any(item.source_card_id == trainer for item in state.stack)


def test_training_trigger_does_not_buff_reentered_source():
    state, trainer, others = _attack_state()
    combat.declare_attackers(state, [trainer, *others])
    assert any(item.source_card_id == trainer for item in state.stack)
    state.players[1].battlefield.remove(trainer)
    state.players[1].hand.append(trainer)
    state.cards[trainer].move_to_zone(Zone.HAND)
    state.players[1].hand.remove(trainer)
    state.players[1].battlefield.append(trainer)
    state.cards[trainer].move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, trainer)
    resolve_top_of_stack(state)
    assert state.cards[trainer].counters.get("+1/+1", 0) == 0
