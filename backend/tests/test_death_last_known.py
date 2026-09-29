"""Death triggers use the permanent as it last existed on the battlefield."""

from effects.handlers import destroy_all_creatures, destroy_permanent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.card_faces import apply_transform_face
from rules_engine.continuous import effective_power
from rules_engine.stack_engine import resolve_top_of_stack


HERO_ORACLE = (
    "Valiant — Whenever this creature becomes the target of a spell or ability you control "
    "for the first time each turn, put a +1/+1 counter on it.\n"
    "When this creature dies, it deals damage equal to its power to each opponent."
)


def _state():
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=601)
    state.pregame_pending = False
    return state


def _put(state, card):
    state.cards[card.id] = card
    state.players[card.controller].battlefield.append(card.id)
    return card


def _hero(cid):
    return CardInstance(
        cid, "Heartfire Hero", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=1, toughness=1, oracle_text=HERO_ORACLE,
        counters={"+1/+1": 1, "__eot_power": 2},
    )


def test_single_death_uses_effective_power_before_exit_and_survives_snapshot():
    state = _state()
    hero = _put(state, _hero("hero"))
    _put(state, CardInstance(
        "anthem", "Glorious Anthem", 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        oracle_text="Creatures you control get +1/+1.",
    ))
    assert effective_power(state, hero.id) == 5

    destroy_permanent(state, 2, {"target_card_id": hero.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    triggers = [item for item in state.stack if item.source_card_id == hero.id]
    assert len(triggers) == 1
    assert triggers[0].payload["amount"] == 5
    life = state.players[2].life
    assert resolve_top_of_stack(state)
    assert state.players[2].life == life - 5


def test_simultaneous_deaths_preserve_each_creatures_effective_power():
    state = _state()
    first = _put(state, _hero("first"))
    second = _put(state, _hero("second"))
    second.counters["+1/+1"] = 2
    assert effective_power(state, first.id) == 4
    assert effective_power(state, second.id) == 5

    destroy_all_creatures(state, 2, {})
    amounts = sorted(item.payload["amount"] for item in state.stack if item.source_card_id in {first.id, second.id})
    assert amounts == [4, 5]


def test_wipe_preserves_power_granted_by_a_simultaneously_dying_lord():
    state = _state()
    scamp = _put(state, CardInstance(
        "scamp", "Cacophony Scamp", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=1, toughness=1, type_line="Creature — Phyrexian Goblin Warrior",
        oracle_text=(
            "Whenever this creature deals combat damage to a player, you may sacrifice it. "
            "If you do, proliferate. (Choose any number of permanents and/or players, "
            "then give each another counter of each kind already there.)\n"
            "When this creature dies, it deals damage equal to its power to any target."
        ),
    ))
    _put(state, CardInstance(
        "chieftain", "Goblin Chieftain", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=2, toughness=2, type_line="Creature — Goblin",
        oracle_text=(
            "Haste (This creature can attack and {T} as soon as it comes under your control.)\n"
            "Other Goblin creatures you control get +1/+1 and have haste."
        ),
    ))
    assert effective_power(state, scamp.id) == 2

    destroy_all_creatures(state, 2, {})
    trigger = next(item for item in state.stack if item.source_card_id == scamp.id)
    assert trigger.payload["amount"] == 2
    assert state.cards[scamp.id].last_known_battlefield["power"] == 2

    state.players[1].graveyard.remove(scamp.id)
    state.players[1].battlefield.append(scamp.id)
    state.cards[scamp.id].zone = Zone.BATTLEFIELD
    assign_static_order_on_battlefield_entry(state, scamp.id)
    assert state.cards[scamp.id].last_known_battlefield == {}


def test_transformed_back_face_self_death_trigger_survives_front_face_reset():
    state = _state()
    faces = [
        {"name": "The Fall of Lord Konda", "type_line": "Enchantment — Saga", "oracle_text": (
            "(As this Saga enters and after your draw step, add a lore counter.)\n"
            "I — Exile target creature an opponent controls with mana value 4 or greater.\n"
            "II — Each player gains control of all permanents they own.\n"
            "III — Exile this Saga, then return it to the battlefield transformed under your control."
        )},
        {"name": "Fragment of Konda", "type_line": "Enchantment Creature — Human Noble", "power": "1", "toughness": "3", "oracle_text": "Defender\nWhen this creature dies, draw a card."},
    ]
    card = _put(state, CardInstance(
        "konda", faces[0]["name"], 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        layout="transform", card_faces=faces, oracle_text=faces[0]["oracle_text"],
    ))
    apply_transform_face(card, 1)
    assert card.selected_face_index == 1

    destroy_permanent(state, 2, {"target_card_id": card.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[card.id].selected_face_index == 0
    triggers = [item for item in state.stack if item.source_card_id == card.id]
    assert len(triggers) == 1
    assert triggers[0].effect_key == "draw_cards"
