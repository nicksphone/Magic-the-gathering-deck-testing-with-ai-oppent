from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
    state = MatchFactory.from_decks(deck, deck, seed=119)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def _incubator(state):
    return next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].name == "Incubator")


def test_incubate_creates_transforming_artifact_and_snapshot_preserves_counters():
    state = _state()
    resolve_effect(state, 1, "incubate", {"counters": 3})
    token = _incubator(state)
    assert token.types == ["Artifact", "Token"]
    assert token.power is None and token.counters == {"+1/+1": 3}
    assert token.summoning_sick and len(token.card_faces) == 2

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    token = _incubator(restored)
    restored.players[1].mana_pool["G"] = 2
    move = next(m for m in RulesEngine().legal_moves(restored, 1) if m["type"] == "activate_ability" and m["card_id"] == token.id)
    RulesEngine().take_action(restored, 1, move, reject_invalid=True)
    assert restored.stack[-1].effect_key == "transform_card"
    resolve_top_of_stack(restored)
    assert "Creature" in token.types and token.selected_face_index == 1
    assert (effective_power(restored, token.id), effective_toughness(restored, token.id)) == (3, 3)
    assert token.summoning_sick


def test_zero_counter_incubator_dies_after_transforming():
    state = _state()
    resolve_effect(state, 1, "incubate", {"counters": 0})
    token = _incubator(state)
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 1})
    apply_state_based_actions(state)
    assert token.zone == Zone.CEASED


def test_noncreature_incubator_is_ready_to_attack_after_next_own_turn_starts():
    state = _state()
    resolve_effect(state, 1, "incubate", {"counters": 2})
    token = _incubator(state)
    assert token.summoning_sick
    engine = RulesEngine()
    state.step = Step.CLEANUP
    engine.next_step(state)
    assert token.summoning_sick
    state.step = Step.CLEANUP
    engine.next_step(state)
    assert state.active_player == 1 and not token.summoning_sick
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 1})
    assert "Creature" in token.types and not token.summoning_sick


def test_sunfall_exiles_creatures_then_incubates_exiled_count():
    state = _state()
    for owner in (1, 2):
        card = CardInstance(f"creature-{owner}", "Test Creature", owner, owner, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
        state.cards[card.id] = card
        state.players[owner].battlefield.append(card.id)
    spell = CardInstance("sunfall", "Sunfall", 1, 1, Zone.STACK, ["Sorcery"], oracle_text="Exile all creatures. Incubate X, where X is the number of creatures exiled this way.")
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "exile_all_creatures_incubate"
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert all(state.cards[f"creature-{owner}"].zone == Zone.EXILE for owner in (1, 2))
    assert _incubator(state).counters == {"+1/+1": 2}


def test_seedshark_incubates_cast_spells_mana_value_not_paid_cost():
    state = _state()
    shark = CardInstance("shark", "Chrome Host Seedshark", 1, 1, Zone.BATTLEFIELD, ["Creature"],
                         oracle_text="Whenever you cast a noncreature spell, incubate X, where X is that spell's mana value.")
    spell = CardInstance("spell", "Test Spell", 1, 1, Zone.STACK, ["Instant"], mana_cost="{X}{U}")
    state.cards.update({shark.id: shark, spell.id: spell})
    state.players[1].battlefield.append(shark.id)
    add_to_stack(state, spell.id, 1, spell.name, "noop", {"x_value": 2})
    assert state.stack[-1].effect_key == "incubate"
    assert state.stack[-1].payload["counters"] == 3
    resolve_top_of_stack(state)
    assert _incubator(state).counters == {"+1/+1": 3}


def test_fixed_incubate_enters_trigger_and_creature_cast_does_not_trigger_seedshark():
    state = _state()
    source = CardInstance("source", "Incubating Creature", 1, 1, Zone.BATTLEFIELD, ["Creature"],
                          oracle_text="When this creature enters, incubate 2.")
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    emit_event(state, "enters_battlefield", {"card_id": source.id, "controller": 1})
    assert state.stack[-1].effect_key == "incubate"
    resolve_top_of_stack(state)
    assert _incubator(state).counters == {"+1/+1": 2}

    shark = CardInstance("shark", "Chrome Host Seedshark", 1, 1, Zone.BATTLEFIELD, ["Creature"],
                         oracle_text="Whenever you cast a noncreature spell, incubate X, where X is that spell's mana value.")
    creature = CardInstance("creature", "Creature Spell", 1, 1, Zone.STACK, ["Creature"], mana_cost="{3}{G}")
    state.cards.update({shark.id: shark, creature.id: creature})
    state.players[1].battlefield.append(shark.id)
    add_to_stack(state, creature.id, 1, creature.name, "noop", {})
    assert all(item.effect_key != "incubate" for item in state.stack)


def test_incubate_twice_uses_land_count_and_unknown_x_is_not_silently_zero():
    state = _state()
    for index in range(3):
        cid = state.players[1].hand.pop()
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.players[1].battlefield.append(cid)
    spell = CardInstance("dawn", "Glistening Dawn", 1, 1, Zone.STACK, ["Sorcery"],
                         oracle_text="Incubate X twice, where X is the number of lands you control.")
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "incubate"
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].name == "Incubator"]
    assert len(tokens) == 2 and all(token.counters == {"+1/+1": 3} for token in tokens)

    unknown = CardInstance("unknown", "Unknown Variable", 1, 1, Zone.STACK, ["Sorcery"],
                           oracle_text="Incubate X, where X is an unsupported value.")
    state.cards[unknown.id] = unknown
    assert build_ability_spec(state, unknown, 1).effect.key == "noop"
    assert build_ability_spec(state, unknown, 1, action_targets={"x_value": 5}).effect.key == "noop"
