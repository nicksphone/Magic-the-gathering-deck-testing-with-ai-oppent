from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.continuous import continuous_layer_trace, effect_timestamp, effective_keywords


def _state() -> object:
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=23)


def test_effect_timestamp_overrides_legacy_static_order_and_survives_snapshot() -> None:
    state = _state()
    target = CardInstance(
        id="timestamp-target", name="Soldier", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature - Soldier",
    )
    older = CardInstance(
        id="older", name="Older", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Creatures you control have flying.", static_order=90, effect_timestamp=2,
    )
    newer = CardInstance(
        id="newer", name="Newer", owner=2, controller=2,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.", static_order=1, effect_timestamp=8,
    )
    state.cards.update({target.id: target, older.id: older, newer.id: newer})
    state.players[1].battlefield.extend([target.id, older.id])
    state.players[2].battlefield.append(newer.id)

    assert effect_timestamp(older) == 2
    assert "flying" not in set(effective_keywords(state, target.id))
    trace = continuous_layer_trace(state, target.id)
    assert [entry["source_id"] for entry in trace["trace"]] == ["older", "newer"]
    assert trace["trace"][1]["effect_timestamp"] == 8
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effect_timestamp(restored.cards["older"]) == 2
    assert effect_timestamp(restored.cards["newer"]) == 8


def test_continuous_uses_static_order_for_grant_remove() -> None:
    state = _state()

    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
    )
    grant = CardInstance(
        id="g",
        name="Grant",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control have flying.",
        static_order=1,
    )
    remove = CardInstance(
        id="r",
        name="Remove",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.",
        static_order=2,
    )
    state.cards[target.id] = target
    state.cards[grant.id] = grant
    state.cards[remove.id] = remove
    state.players[1].battlefield.extend([target.id, grant.id])
    state.players[2].battlefield.append(remove.id)

    kws = set(effective_keywords(state, target.id))
    assert "flying" not in kws

    # Swap ordering so grant applies after remove.
    grant.static_order = 3
    remove.static_order = 2
    kws2 = set(effective_keywords(state, target.id))
    assert "flying" in kws2


def test_continuous_layer_trace_reports_ordered_sources() -> None:
    state = _state()
    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
    )
    grant = CardInstance(
        id="g",
        name="Grant",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control have flying.",
        static_order=1,
    )
    remove = CardInstance(
        id="r",
        name="Remove",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.",
        static_order=2,
    )
    state.cards[target.id] = target
    state.cards[grant.id] = grant
    state.cards[remove.id] = remove
    state.players[1].battlefield.extend([target.id, grant.id])
    state.players[2].battlefield.append(remove.id)

    trace = continuous_layer_trace(state, target.id)
    assert trace["card_name"] == "Soldier"
    assert [entry["source_id"] for entry in trace["trace"]] == ["g", "r"]
    assert trace["trace"][0]["layers"] == ["keyword-grant:flying"]
    assert trace["trace"][1]["layers"] == ["keyword-remove:flying"]


def test_continuous_layer_trace_includes_ordered_applied_layers() -> None:
    state = _state()
    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
        power=2,
        toughness=2,
    )
    anthem = CardInstance(
        id="a",
        name="Anthem",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control get +1/+1 and have flying.",
        static_order=1,
    )
    curse = CardInstance(
        id="c",
        name="Curse",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures your opponents control lose flying.",
        static_order=2,
    )
    state.cards[target.id] = target
    state.cards[anthem.id] = anthem
    state.cards[curse.id] = curse
    state.players[1].battlefield.extend([target.id, anthem.id])
    state.players[2].battlefield.append(curse.id)

    trace = continuous_layer_trace(state, target.id)
    assert [entry["layer"] for entry in trace["applied_layers"]] == [
        "keyword-grant:flying",
        "keyword-remove:flying",
        "pt-mod:1/1",
    ]
    assert [entry["source_id"] for entry in trace["applied_layers"]] == ["a", "c", "a"]
    assert trace["effective_power"] == 3
    assert trace["effective_toughness"] == 3
    assert "flying" not in set(effective_keywords(state, target.id))


def test_continuous_layer_trace_orders_base_pt_setters_by_static_order() -> None:
    state = _state()
    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
        power=2,
        toughness=2,
    )
    first = CardInstance(
        id="f",
        name="First",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control become 1/1.",
        static_order=1,
    )
    second = CardInstance(
        id="s",
        name="Second",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control become 4/4.",
        static_order=2,
    )
    state.cards[target.id] = target
    state.cards[first.id] = first
    state.cards[second.id] = second
    state.players[1].battlefield.extend([target.id, first.id, second.id])

    trace = continuous_layer_trace(state, target.id)
    assert [entry["source_id"] for entry in trace["applied_layers"]] == ["f", "s"]
    assert [entry["layer"] for entry in trace["applied_layers"]] == ["pt-set", "pt-set"]
    assert trace["effective_power"] == 4
    assert trace["effective_toughness"] == 4


def test_continuous_layer_trace_uses_battlefield_order_as_tiebreak() -> None:
    state = _state()
    target = CardInstance(
        id="t",
        name="Soldier",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        type_line="Creature - Human Soldier",
        power=2,
        toughness=2,
    )
    second = CardInstance(
        id="s",
        name="Second",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control become 4/4.",
        static_order=1,
        entered_turn=4,
        instance_order=2,
    )
    first = CardInstance(
        id="f",
        name="First",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Creatures you control become 1/1.",
        static_order=1,
        entered_turn=4,
        instance_order=1,
    )
    state.cards[target.id] = target
    state.cards[first.id] = first
    state.cards[second.id] = second
    state.players[1].battlefield.extend([target.id, second.id, first.id])

    trace = continuous_layer_trace(state, target.id)
    assert [entry["source_id"] for entry in trace["applied_layers"]] == ["s", "f"]
    assert trace["effective_power"] == 1
    assert trace["effective_toughness"] == 1
