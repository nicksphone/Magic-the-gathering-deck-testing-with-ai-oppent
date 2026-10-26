"""Canonical controlled positions for face-local costs, not exported game traces."""
from copy import deepcopy

import pytest

from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from tests.scheduler_fixture_position import ordinary_position
from tests.test_training_environment import keep, place
from training.environment import TrainingEnvironment
from training.decision_frame import build_decision_frame, encode_state, encode_action


def position(seat):
    environment = TrainingEnvironment()
    environment.reset("Tempo" if seat == 1 else "Burn", "Burn" if seat == 1 else "Tempo", seed=17)
    keep(environment)
    state = environment._state
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    ordinary_position(state)
    source = place(environment, "Brazen Borrower", seat, Zone.HAND)
    target = place(environment, "Monastery Swiftspear", 3 - seat, Zone.BATTLEFIELD)
    islands = [card for card in state.cards.values() if card.owner == seat and card.name == "Island"][:5]
    assert len(islands) == 5
    for card in islands:
        player = state.players[seat]
        for zone in ("library", "hand", "battlefield", "graveyard", "exile"):
            if card.id in getattr(player, zone):
                getattr(player, zone).remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(card.id)
        assign_static_order_on_battlefield_entry(state, card.id)
        card.tapped = False
    return environment, source, target


def choices(environment, source):
    return {prompt["hint"].get("selected_face_index", 0): prompt["hint"]
            for prompt in environment.prompts() if prompt["hint"].get("card_id") == source
            and prompt["hint"]["type"] == "cast_spell"}


def action(source, target, face):
    return {"type": "cast_spell", "card_id": source, "selected_face_index": face,
            "cost_choice": {"id": "base"}, "targets": {"target_card_id": target} if face else {}}


def frame(environment, context):
    seat = environment.acting_seat
    return build_decision_frame(environment.observe(seat), environment.prompts(seat),
        public_context=environment.decision_context(seat) if context else None)


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("face", [0, 1])
@pytest.mark.parametrize("context", [False, True])
def test_real_face_local_base_costs_encode_roundtrip_and_execute(seat, face, context):
    environment, source, target = position(seat)
    offered = choices(environment, source)
    assert set(offered) == {0, 1}
    assert [offered[index]["cost_options"][0]["id"] for index in (0, 1)] == ["base", "base"]
    assert offered[0]["cost_options"][0]["mana_cost"] == "{1}{U}{U}"
    assert offered[1]["cost_options"][0]["mana_cost"] == "{1}{U}"
    before = environment.snapshot()
    current, bindings = frame(environment, context)
    assert environment.snapshot() == before
    proposed = action(source, target, face)
    chosen = environment.lookup(proposed, seat)["action"]
    public = bindings.action(chosen)
    assert bindings.actual_action(public) == chosen
    assert encode_state(current) and encode_action(current, public)
    other = bindings.action(environment.lookup(action(source, target, 1 - face), seat)["action"])
    assert public["cost_choice"]["id"] != other["cost_choice"]["id"]
    environment.step(bindings.actual_action(public), seat)
    assert environment._state.cards[source].zone == Zone.STACK
    environment.step({"type": "pass_priority"})
    environment.step({"type": "pass_priority"})
    state = environment._state
    if face == 0:
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert state.cards[target].zone == Zone.BATTLEFIELD
    else:
        assert state.cards[source].zone == Zone.EXILE and state.cards[target].zone == Zone.HAND
        assert state.adventure_permissions[source] == seat
        offered = choices(environment, source)
        assert set(offered) == {0} and offered[0]["from_exile"] is True
        current, bindings = frame(environment, context)
        chosen = environment.lookup({**action(source, target, 0), "from_exile": True}, seat)["action"]
        assert bindings.actual_action(bindings.action(chosen)) == chosen
        assert encode_action(current, bindings.action(chosen))
        environment.step(chosen, seat)
        environment.step({"type": "pass_priority"})
        environment.step({"type": "pass_priority"})
        assert environment._state.cards[source].zone == Zone.BATTLEFIELD
        assert source not in environment._state.adventure_permissions


@pytest.mark.parametrize("seat", [1, 2])
def test_nested_selected_face_matches_real_engine_face_choice(seat):
    environment, source, target = position(seat)
    proposed = action(source, target, 1)
    proposed.pop("selected_face_index")
    proposed["targets"]["selected_face_index"] = 1
    chosen = environment.lookup(proposed, seat)["action"]
    current, bindings = frame(environment, True)
    public = bindings.action(chosen)
    assert bindings.actual_action(public) == chosen
    assert encode_action(current, public)
    environment.step(bindings.actual_action(public), seat)
    assert environment._state.cards[source].name == "Petty Theft"


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("face", [0, 1])
def test_cost_alias_cannot_be_transplanted_to_another_face(seat, face):
    environment, source, target = position(seat)
    _, bindings = frame(environment, False)
    public = bindings.action(environment.lookup(action(source, target, face), seat)["action"])
    other = bindings.action(environment.lookup(action(source, target, 1 - face), seat)["action"])
    public["cost_choice"]["id"] = other["cost_choice"]["id"]
    with pytest.raises(ValueError, match="Cost reference"):
        bindings.actual_action(public)


@pytest.mark.parametrize("seat", [1, 2])
def test_main_face_implicit_and_explicit_zero_share_the_same_cost(seat):
    environment, source, target = position(seat)
    _, bindings = frame(environment, False)
    explicit = action(source, target, 0)
    implicit = deepcopy(explicit)
    implicit.pop("selected_face_index")
    assert bindings.action(implicit)["cost_choice"] == bindings.action(explicit)["cost_choice"]
    conflicting_target_face = deepcopy(explicit)
    conflicting_target_face["targets"]["selected_face_index"] = 1
    chosen = environment.lookup(conflicting_target_face, seat)["action"]
    assert bindings.action(chosen)["cost_choice"] == bindings.action(explicit)["cost_choice"]
    assert bindings.actual_action(bindings.action(chosen)) == chosen


@pytest.mark.parametrize("seat", [1, 2])
def test_opaque_card_and_cost_identifier_renaming_preserves_both_face_features(seat):
    environment, source, target = position(seat)
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    ids = {cid: "renamed-public-" + str(i) for i, cid in enumerate(observation["known_cards"])}
    ids["base"] = "renamed-cost-option"

    def rename(value):
        if isinstance(value, dict):
            return {ids.get(key, key): rename(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rename(item) for item in value]
        return ids.get(value, value) if isinstance(value, str) else value

    original, one = build_decision_frame(observation, prompts)
    renamed, two = build_decision_frame(rename(observation), rename(prompts))
    assert encode_state(original) == encode_state(renamed)
    for face in (0, 1):
        chosen = environment.lookup(action(source, target, face), seat)["action"]
        assert encode_action(original, one.action(chosen)) == encode_action(renamed, two.action(rename(chosen)))
        assert two.actual_action(two.action(rename(chosen))) == rename(chosen)


@pytest.mark.parametrize("seat", [1, 2])
def test_conflicting_descriptors_within_one_face_still_reject(seat):
    environment, source, _ = position(seat)
    prompts = deepcopy(environment.prompts())
    hint = next(p["hint"] for p in prompts if p["hint"].get("card_id") == source
                and p["hint"]["type"] == "cast_spell" and p["hint"].get("selected_face_index", 0) == 0)
    changed = deepcopy(hint["cost_options"][0])
    changed["mana_cost"] = "{9}{U}"
    hint["cost_options"].append(changed)  # Deliberate malformed protocol, not a real card cost.
    with pytest.raises(ValueError, match="conflicting offered descriptors"):
        build_decision_frame(environment.observe(seat), prompts)
