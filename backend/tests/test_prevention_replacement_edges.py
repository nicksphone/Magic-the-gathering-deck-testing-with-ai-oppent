from __future__ import annotations

from effects.registry import resolve_effect
from effects.handlers import deal_damage, gain_life
from rules_engine import combat
from rules_engine.ability_model import build_ability_spec
from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.replacement import replacement_options, replace_die_zone, replace_draw_cards
from fastapi.testclient import TestClient
from main import ACTIVE_MATCHES, MatchController, app


def _state() -> object:
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck, seed=17)


def test_global_damage_cant_be_prevented_ignores_player_shield() -> None:
    state = _state()
    state.players[2].prevent_damage_shield = 5
    eid = "eid-global-no-prevent"
    state.cards[eid] = CardInstance(
        id=eid,
        name="No Prevent",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Damage can't be prevented.",
    )
    state.players[1].battlefield.append(eid)
    before = state.players[2].life
    deal_damage(state, controller=1, payload={"target_player": 2, "amount": 3})
    assert state.players[2].life == before - 3


def test_transformed_draw_life_replacements_consume_each_source_once() -> None:
    state = _state()
    gain_replacement = CardInstance(
        id="gain-replacement",
        name="Gain Replacement",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
    )
    draw_replacement = CardInstance(
        id="draw-replacement",
        name="Draw Replacement",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would draw a card, gain 1 life instead.",
    )
    state.cards[gain_replacement.id] = gain_replacement
    state.cards[draw_replacement.id] = draw_replacement
    state.players[1].battlefield.extend([gain_replacement.id, draw_replacement.id])
    before = state.players[1].life
    hand_before = len(state.players[1].hand)

    gain_life(state, 1, {"target_player": 1, "amount": 3})

    assert state.players[1].life == before + 3
    assert len(state.players[1].hand) == hand_before


def _thought_reflection(state, cid: str) -> None:
    card = CardInstance(
        id=cid, name="Thought Reflection", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text="If you would draw a card, draw two cards instead.",
    )
    state.cards[cid] = card
    state.players[1].battlefield.append(cid)


def _draw_step_doubler(state, cid: str, *, archive: bool = False) -> None:
    card = CardInstance(
        id=cid,
        name="Alhammarret's Archive" if archive else "Teferi's Ageless Insight",
        owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Artifact"] if archive else ["Enchantment"],
        oracle_text=(
            "If you would gain life, you gain twice that much life instead.\n"
            if archive else ""
        ) + "If you would draw a card except the first one you draw in each of your draw steps, draw two cards instead.",
    )
    state.cards[cid] = card
    state.players[1].battlefield.append(cid)


def test_conditional_draw_doubling_exempts_only_first_actual_draw_in_own_step() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 2
    state.step = Step.UPKEEP
    _draw_step_doubler(state, "insight")
    before = len(state.players[1].hand)
    RulesEngine().next_step(state)
    assert len(state.players[1].hand) == before + 1
    assert state.draws_in_current_draw_step[1] == 1
    resolve_effect(state, 1, "draw_cards", {"amount": 2})
    assert len(state.players[1].hand) == before + 5
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.draws_in_current_draw_step[1] == 5
    restored.step = Step.PRECOMBAT_MAIN
    before = len(restored.players[1].hand)
    resolve_effect(restored, 1, "draw_cards", {"amount": 1})
    assert len(restored.players[1].hand) == before + 2


def test_two_conditional_draw_doublers_are_cumulative_after_first_draw() -> None:
    state = _state()
    state.turn = 2
    state.step = Step.DRAW
    _draw_step_doubler(state, "insight")
    _draw_step_doubler(state, "archive", archive=True)
    assert replacement_options(state, "card_draw", target_player=1) == []
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert len(state.players[1].hand) == before + 1
    assert {option["source_id"] for option in replacement_options(state, "card_draw", target_player=1)} == {
        "insight", "archive",
    }
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert len(state.players[1].hand) == before + 5


def test_replaced_first_draw_does_not_use_draw_step_exception() -> None:
    state = _state()
    state.step = Step.DRAW
    _draw_step_doubler(state, "insight")
    dredger = CardInstance(
        id="stinkweed", name="Stinkweed Imp", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Creature"],
        oracle_text="Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\nDredge 5 (If you would draw a card, you may mill five cards instead. If you do, return this card from your graveyard to your hand.)",
    )
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    RulesEngine().take_action(state, 1, {"type": "choose_mechanic", "choice_id": dredger.id}, reject_invalid=True)
    assert state.draws_in_current_draw_step[1] == 0
    assert len(state.players[1].hand) == before + 1
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert len(state.players[1].hand) == before + 2
    assert state.draws_in_current_draw_step[1] == 1


def test_archive_life_and_draw_replacements_remain_independent() -> None:
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    _draw_step_doubler(state, "archive", archive=True)
    before_life = state.players[1].life
    gain_life(state, 1, {"target_player": 1, "amount": 3})
    assert state.players[1].life == before_life + 6

    lich = CardInstance(
        id="lich", name="Lich", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"],
        oracle_text=(
            "As this enchantment enters, you lose life equal to your life total.\n"
            "You don't lose the game for having 0 or less life.\n"
            "If you would gain life, draw that many cards instead.\n"
            "Whenever you're dealt damage, sacrifice that many nontoken permanents. If you can't, you lose the game.\n"
            "When this enchantment is put into a graveyard from the battlefield, you lose the game."
        ),
    )
    state.cards[lich.id] = lich
    state.players[1].battlefield.append(lich.id)
    state.players[1].life = 0
    assert {option["source_id"] for option in replacement_options(state, "life_gain", target_player=1)} == {
        "archive", "lich",
    }
    for first_source, expected_draws in (("lich", 6), ("archive", 12)):
        trial = deserialize_match_snapshot(serialize_match_snapshot(state))
        before_hand = len(trial.players[1].hand)
        gain_life(trial, 1, {
            "target_player": 1, "amount": 3, "__replacement_source_id": first_source,
        })
        assert len(trial.players[1].hand) == before_hand + expected_draws
        assert trial.players[1].life == 0
        assert trial.winner is None


def test_unconditional_draw_doubling_applies_once_per_source_and_original_draw() -> None:
    state = _state()
    _thought_reflection(state, "reflection-one")
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 3})
    assert len(state.players[1].hand) == before + 6
    _thought_reflection(state, "reflection-two")
    before = len(state.players[1].hand)
    assert replace_draw_cards(state, 1, 1)[1]["__used_replacement_source_ids"] == ["card_draw:reflection-two"]
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert len(state.players[1].hand) == before + 4
    assert {o["source_id"] for o in replacement_options(state, "card_draw", target_player=1)} == {
        "reflection-one", "reflection-two",
    }


def test_draw_step_uses_unconditional_draw_doubling() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 2
    state.step = Step.UPKEEP
    _thought_reflection(state, "reflection")
    before = len(state.players[1].hand)
    RulesEngine().next_step(state)
    assert state.step == Step.DRAW
    assert len(state.players[1].hand) == before + 2


def test_human_stack_choice_between_draw_doublers_is_resumable() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    _thought_reflection(state, "reflection-one")
    _thought_reflection(state, "reflection-two")
    spell = CardInstance(
        id="ancestral", name="Ancestral Recall", owner=1, controller=1,
        zone=Zone.STACK, types=["Instant"],
        oracle_text="Target player draws three cards.",
    )
    state.cards[spell.id] = spell
    add_to_stack(state, spell.id, 1, spell.name, "draw_cards", {"target_player": 1, "amount": 3})
    before = len(state.players[1].hand)
    resolve_top_of_stack(state)
    assert state.pending_replacement_choice is not None
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    for index in range(3):
        assert restored.pending_replacement_choice is not None
        assert restored.cards[spell.id].zone == Zone.STACK
        RulesEngine().take_action(restored, 1, {
            "type": "choose_replacement", "replacement_source_id": "reflection-one" if index != 1 else "reflection-two",
        }, reject_invalid=True)
        if index == 0:
            restored = deserialize_match_snapshot(serialize_match_snapshot(restored))
    assert restored.pending_replacement_choice is None
    assert len(restored.players[1].hand) == before + 12
    assert restored.cards[spell.id].zone == Zone.GRAVEYARD


def test_dredge_choices_preserve_draw_replacement_context_across_pause() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    _thought_reflection(state, "reflection")
    dredger = CardInstance(
        id="stinkweed", name="Stinkweed Imp", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Creature"],
        oracle_text="Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\nDredge 5 (If you would draw a card, you may mill five cards instead. If you do, return this card from your graveyard to your hand.)",
    )
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    engine = RulesEngine()
    for index in range(3):
        assert state.pending_mechanic_choice and state.pending_mechanic_choice["kind"] == "draw"
        engine.take_action(state, 1, {"type": "choose_mechanic", "choice_id": "draw"}, reject_invalid=True)
        if index == 0:
            state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.pending_mechanic_choice is None
    assert len(state.players[1].hand) == before + 2


def test_human_draw_replacement_choice_can_select_dredge_or_doubling() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    _thought_reflection(state, "reflection")
    dredger = CardInstance(
        id="stinkweed", name="Stinkweed Imp", owner=1, controller=1,
        zone=Zone.GRAVEYARD, types=["Creature"],
        oracle_text="Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\nDredge 5 (If you would draw a card, you may mill five cards instead. If you do, return this card from your graveyard to your hand.)",
    )
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert {option["source_id"] for option in state.pending_replacement_choice["options"]} == {
        "reflection", "stinkweed",
    }
    RulesEngine().take_action(state, 1, {
        "type": "choose_replacement", "replacement_source_id": "stinkweed",
    }, reject_invalid=True)
    assert state.pending_replacement_choice is None
    assert dredger.id in state.players[1].hand
    assert len(state.players[1].hand) == before + 1


def test_draw_replacement_pauses_preserve_later_effect_clauses() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    _thought_reflection(state, "reflection-one")
    _thought_reflection(state, "reflection-two")
    before_hand = len(state.players[1].hand)
    before_life = state.players[1].life
    resolve_effect(state, 1, "effect_sequence", {"effects": [
        {"effect_key": "draw_cards", "payload": {"amount": 2}},
        {"effect_key": "gain_life", "payload": {"amount": 3}},
    ]})
    assert state.pending_replacement_choice is not None
    assert state.players[1].life == before_life
    engine = RulesEngine()
    for index in range(2):
        engine.take_action(state, 1, {
            "type": "choose_replacement", "replacement_source_id": "reflection-one",
        }, reject_invalid=True)
        if index == 0:
            assert state.pending_replacement_choice is not None
            assert state.players[1].life == before_life
    assert state.pending_replacement_choice is None
    assert len(state.players[1].hand) == before_hand + 8
    assert state.players[1].life == before_life + 3


def test_http_draw_step_replacement_choice_resumes() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    state.turn = 2
    state.step = Step.UPKEEP
    _thought_reflection(state, "reflection-one")
    _thought_reflection(state, "reflection-two")
    RulesEngine().next_step(state)
    assert state.pending_replacement_choice is not None
    deck = [{"quantity": 60, "card_name": "Island"}]
    match = MatchController(
        state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={},
        mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            legal = client.get(f"/matches/{state.id}/legal-moves", params={"player_id": 1})
            assert legal.status_code == 200
            assert {move["replacement_source_id"] for move in legal.json()["moves"]} == {
                "reflection-one", "reflection-two",
            }
            before = len(state.players[1].hand)
            response = client.post(f"/matches/{state.id}/action", json={
                "player_id": 1,
                "action": {"type": "choose_replacement", "replacement_source_id": "reflection-one"},
            })
            assert response.status_code == 200
            assert response.json()["pending_replacement_choice"] is None
            assert len(ACTIVE_MATCHES[state.id].state.players[1].hand) == before + 4
        finally:
            ACTIVE_MATCHES.pop(state.id, None)


def test_skullcrack_style_turn_restrictions_apply_and_expire_at_cleanup() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell = CardInstance(
        id="skullcrack-style",
        name="Skullcrack",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Skullcrack deals 3 damage to target player. Players can't gain life this turn. Damage can't be prevented this turn.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1, {"target_player": 2})
    assert spec.effect.key == "effect_sequence"
    resolve_effect(state, 1, spec.effect.key, {**spec.effect.payload, "target_player": 2})

    assert state.turn_cant_gain_life == {1, 2}
    assert state.turn_damage_cant_be_prevented is True
    life_before = state.players[2].life
    resolve_effect(state, 2, "gain_life", {"target_player": 2, "amount": 5})
    assert state.players[2].life == life_before
    state.players[2].prevent_damage_shield = 5
    deal_damage(state, 1, {"target_player": 2, "amount": 2})
    assert state.players[2].life == life_before - 2

    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    assert state.turn_cant_gain_life == set()
    assert state.turn_damage_cant_be_prevented is False


def test_turn_restrictions_survive_snapshot_restore() -> None:
    state = _state()
    state.turn_cant_gain_life = {2}
    state.turn_damage_cant_be_prevented = True
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))

    assert restored.turn_cant_gain_life == {2}
    assert restored.turn_damage_cant_be_prevented is True


def test_controller_scoped_damage_cant_be_prevented_ignores_shield() -> None:
    state = _state()
    state.players[2].prevent_damage_shield = 5
    aid = "aid-scope-no-prevent"
    src = "src-bolt"
    state.cards[aid] = CardInstance(
        id=aid,
        name="Aggro Lock",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Damage that would be dealt by sources you control can't be prevented.",
    )
    state.players[1].battlefield.append(aid)
    state.cards[src] = CardInstance(
        id=src,
        name="Bolt Source",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
    )
    state.players[1].battlefield.append(src)
    before = state.players[2].life
    deal_damage(state, controller=1, payload={"target_player": 2, "amount": 2, "__source_card_id": src})
    assert state.players[2].life == before - 2


def test_you_or_permanent_you_control_damage_prevention_applies_to_player_and_perm() -> None:
    state = _state()
    shield = CardInstance(
        id="shield-broad",
        name="Broad Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a source would deal damage to you or a permanent you control, prevent 1 of that damage.",
    )
    state.cards[shield.id] = shield
    state.players[1].battlefield.append(shield.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 2
    card.toughness = 2

    before_life = state.players[1].life
    deal_damage(state, controller=2, payload={"target_player": 1, "amount": 3})
    assert state.players[1].life == before_life - 2

    deal_damage(state, controller=2, payload={"target_card_id": cid, "amount": 3})
    assert card.counters.get("__damage_marked", 0) == 2


def test_damage_replacement_re_evaluates_remaining_sources() -> None:
    state = _state()
    for cid, name in (("chain-ward-a", "Chain Ward A"), ("chain-ward-b", "Chain Ward B")):
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a source would deal damage to you, prevent 1 of that damage.",
        )
        state.players[1].battlefield.append(cid)

    before = state.players[1].life
    deal_damage(state, controller=2, payload={"target_player": 1, "amount": 3})

    assert state.players[1].life == before - 1
    assert sum("selected from 2" in line for line in state.log) == 1


def test_human_damage_replacement_chain_prompts_for_remaining_source() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for index, name in enumerate(("Human Ward A", "Human Ward B"), start=1):
        cid = f"human-chain-{index}"
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a source would deal damage to you, prevent 1 of that damage.",
            static_order=index,
        )
        state.players[1].battlefield.append(cid)
    source = CardInstance(
        id="human-chain-source",
        name="Damage Spell",
        owner=2,
        controller=2,
        zone=Zone.STACK,
        types=["Sorcery"],
    )
    state.cards[source.id] = source
    add_to_stack(
        state,
        source_card_id=source.id,
        controller=2,
        label=source.name,
        effect_key="deal_damage",
        payload={"target_player": 1, "amount": 3},
    )

    assert resolve_top_of_stack(state) is False
    first_choice = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, first_choice)

    assert state.pending_replacement_choice is not None
    assert state.pending_replacement_choice["resume_kind"] == "damage_chain"
    assert state.players[1].life == 20
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.pending_replacement_choice == state.pending_replacement_choice
    choice_count = 1
    while state.pending_replacement_choice is not None:
        next_choice = RulesEngine().legal_moves(state, 1)[0]
        RulesEngine().take_action(state, 1, next_choice)
        choice_count += 1

    assert state.pending_replacement_choice is None
    assert choice_count == 2
    assert state.players[1].life == 19
    assert state.cards[source.id].zone == Zone.GRAVEYARD


def test_human_permanent_damage_replacement_chain_prompts_for_remaining_source() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for index, name in enumerate(("Permanent Ward A", "Permanent Ward B"), start=1):
        cid = f"permanent-chain-{index}"
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a source would deal damage to a creature you control, prevent 1 of that damage.",
            static_order=index,
        )
        state.players[1].battlefield.append(cid)
    target_id = state.players[1].hand[0]
    target = state.cards[target_id]
    target.zone = Zone.BATTLEFIELD
    target.types = ["Creature"]
    target.power = 3
    target.toughness = 4
    state.players[1].hand.remove(target_id)
    state.players[1].battlefield.append(target_id)
    source = CardInstance(
        id="permanent-chain-source",
        name="Permanent Damage Spell",
        owner=2,
        controller=2,
        zone=Zone.STACK,
        types=["Sorcery"],
    )
    state.cards[source.id] = source
    add_to_stack(
        state,
        source_card_id=source.id,
        controller=2,
        label=source.name,
        effect_key="deal_damage",
        payload={"target_card_id": target_id, "amount": 3},
    )

    assert resolve_top_of_stack(state) is False
    first_choice = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, first_choice)
    assert state.pending_replacement_choice is not None
    second_choice = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, second_choice)

    assert state.pending_replacement_choice is None
    assert target.counters.get("__damage_marked", 0) == 1


def test_you_or_creature_you_control_damage_prevention_applies_to_player_and_perm() -> None:
    state = _state()
    shield = CardInstance(
        id="shield-broad-2",
        name="Broad Ward Two",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a source would deal damage to you or a creature you control, prevent 1 of that damage.",
    )
    state.cards[shield.id] = shield
    state.players[1].battlefield.append(shield.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 2
    card.toughness = 2

    before_life = state.players[1].life
    deal_damage(state, controller=2, payload={"target_player": 1, "amount": 3})
    assert state.players[1].life == before_life - 2

    deal_damage(state, controller=2, payload={"target_card_id": cid, "amount": 3})
    assert card.counters.get("__damage_marked", 0) == 2


def test_replacement_effect_logs_redirection() -> None:
    state = _state()
    repl_id = "repl-draw"
    state.cards[repl_id] = CardInstance(
        id=repl_id,
        name="Life to Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
    )
    state.players[1].battlefield.append(repl_id)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "gain_life", {"amount": 2})
    assert len(state.players[1].hand) == before + 2
    assert any("replacement effect applied: gain_life -> draw_cards" in line.lower() for line in state.log)


def test_replacement_effect_prefers_latest_timestamp_source() -> None:
    state = _state()
    early = CardInstance(
        id="early",
        name="Early Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=1,
        entered_turn=1,
    )
    late = CardInstance(
        id="late",
        name="Late Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=2,
        entered_turn=2,
    )
    state.cards[early.id] = early
    state.cards[late.id] = late
    state.players[1].battlefield.extend([early.id, late.id])
    before = len(state.players[1].hand)

    resolve_effect(state, 1, "gain_life", {"amount": 1})

    assert len(state.players[1].hand) == before + 1
    assert any("source: late knowledge" in line.lower() for line in state.log)
    assert not any("source: early knowledge" in line.lower() for line in state.log if "replacement effect applied" in line.lower())


def test_replacement_options_expose_timestamp_ordered_sources() -> None:
    state = _state()
    early = CardInstance(
        id="choice-early",
        name="Early Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=1,
    )
    late = CardInstance(
        id="choice-late",
        name="Late Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=2,
    )
    state.cards.update({early.id: early, late.id: late})
    state.players[1].battlefield.extend([early.id, late.id])

    options = replacement_options(state, "life_gain", target_player=1)

    assert [item["source_id"] for item in options] == [late.id, early.id]
    assert options[0]["name"] == late.name
    assert options[0]["static_order"] == 2


def test_ability_spec_carries_explicit_replacement_source_choice() -> None:
    state = _state()
    spell = CardInstance(
        id="replacement-spell",
        name="Life Spell",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{1}{W}",
        oracle_text="Target player gains 3 life.",
    )
    state.cards[spell.id] = spell

    spec = build_ability_spec(
        state,
        spell,
        1,
        {"target_player": 1, "replacement_source_id": "choice-late"},
    )

    assert spec.choices["replacement_source_id"] == "choice-late"
    assert spec.effect.payload["__replacement_source_id"] == "choice-late"


def test_human_replacement_choice_pauses_and_resumes_stack_resolution() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    early = CardInstance(
        id="pause-early",
        name="Early Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=1,
    )
    late = CardInstance(
        id="pause-late",
        name="Late Knowledge",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If you would gain life, draw that many cards instead.",
        static_order=2,
    )
    source = CardInstance(
        id="pause-source",
        name="Life Spell",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Sorcery"],
    )
    state.cards.update({early.id: early, late.id: late, source.id: source})
    state.players[1].battlefield.extend([early.id, late.id])
    add_to_stack(
        state,
        source_card_id=source.id,
        controller=1,
        label=source.name,
        effect_key="gain_life",
        payload={"target_player": 1, "amount": 1},
    )

    assert resolve_top_of_stack(state) is False
    assert state.pending_replacement_choice is not None
    assert len(state.stack) == 1
    choices = RulesEngine().legal_moves(state, 1)
    assert {choice["replacement_source_id"] for choice in choices} == {early.id, late.id}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.pending_replacement_choice == state.pending_replacement_choice
    assert len(restored.stack) == 1

    RulesEngine().take_action(
        state,
        1,
        {"type": "choose_replacement", "replacement_source_id": early.id},
    )

    assert state.pending_replacement_choice is None
    assert state.stack == []
    assert state.players[1].life == 20
    assert len(state.players[1].hand) == 8
    assert source.id in state.players[1].graveyard
    assert any("chooses replacement source" in line.lower() for line in state.log)


def test_human_replacement_choice_pauses_lethal_state_based_zone_change() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name in (("sba-rep-a", "First Ward"), ("sba-rep-b", "Second Ward")):
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a permanent you control would die, exile it instead.",
        )
        state.players[1].battlefield.append(cid)
    creature_id = state.players[1].hand[0]
    creature = state.cards[creature_id]
    creature.zone = Zone.BATTLEFIELD
    creature.types = ["Creature"]
    creature.power = 2
    creature.toughness = 2
    creature.counters["__damage_marked"] = 2
    state.players[1].hand.remove(creature_id)
    state.players[1].battlefield.append(creature_id)

    apply_state_based_actions(state)

    assert state.pending_replacement_choice is not None
    assert creature.zone == Zone.BATTLEFIELD
    move = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, move)

    assert state.pending_replacement_choice is None
    assert creature.zone == Zone.EXILE
    assert creature_id in state.players[1].exile


def test_human_replacement_choice_pauses_combat_death_zone_change() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name in (("combat-rep-a", "First Ward"), ("combat-rep-b", "Second Ward")):
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a permanent you control would die, exile it instead.",
        )
        state.players[1].battlefield.append(cid)
    creature_id = state.players[1].hand[0]
    creature = state.cards[creature_id]
    creature.zone = Zone.BATTLEFIELD
    creature.types = ["Creature"]
    creature.toughness = 2
    creature.counters["__damage_marked"] = 2
    state.players[1].hand.remove(creature_id)
    state.players[1].battlefield.append(creature_id)

    combat._remove_dead_creatures(state)

    assert state.pending_replacement_choice is not None
    move = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, move)

    assert state.pending_replacement_choice is None
    assert creature.zone == Zone.EXILE
    assert creature_id in state.players[1].exile


def test_human_replacement_choice_pauses_legend_rule_zone_change() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    for cid, name in (("legend-rep-a", "First Ward"), ("legend-rep-b", "Second Ward")):
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            oracle_text="If a permanent you control would die, exile it instead.",
        )
        state.players[1].battlefield.append(cid)
    legends = []
    for index in (1, 2):
        cid = f"legendary-copy-{index}"
        card = CardInstance(
            id=cid,
            name="Twin Sage",
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Legendary", "Creature"],
            type_line="Legendary Creature — Wizard",
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
        legends.append(cid)

    apply_state_based_actions(state)

    assert state.pending_replacement_choice is not None
    move = RulesEngine().legal_moves(state, 1)[0]
    RulesEngine().take_action(state, 1, move)

    assert state.pending_replacement_choice is None
    assert state.cards[legends[1]].zone == Zone.EXILE
    assert legends[1] in state.players[1].exile


def test_optional_stack_effect_can_be_declined() -> None:
    state = _state()
    source = state.players[1].hand[0]
    state.players[1].hand.remove(source)
    state.cards[source].zone = Zone.STACK
    add_to_stack(
        state,
        source,
        1,
        "Optional Charm",
        "gain_life",
        {"target_player": 1, "amount": 3, "__may": True, "__may_choose": False},
    )
    before = state.players[1].life
    resolve_top_of_stack(state)
    assert state.players[1].life == before
    assert any("declines optional effect" in line.lower() for line in state.log)


def test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = state.players[1].hand.pop()
    state.players[1].battlefield.append(atk)
    state.cards[atk].zone = Zone.BATTLEFIELD
    state.cards[atk].types = ["Creature"]
    state.cards[atk].power = 3
    state.cards[atk].toughness = 3
    state.cards[atk].summoning_sick = False
    state.cards[atk].oracle_text = "Damage can't be prevented."

    state.players[2].prevent_damage_shield = 5
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}

    before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == before - 3


def test_damage_to_permanent_respects_creature_prevention_replacement() -> None:
    state = _state()
    shield = CardInstance(
        id="shield",
        name="Protective Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a source would deal damage to a creature you control, prevent 1 of that damage.",
    )
    state.cards[shield.id] = shield
    state.players[1].battlefield.append(shield.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 2
    card.toughness = 2

    deal_damage(state, controller=2, payload={"target_card_id": cid, "amount": 2})

    assert card.counters.get("__damage_marked", 0) == 1
    assert card.zone == Zone.BATTLEFIELD


def test_multiple_static_prevention_replacements_re_evaluate_remaining_effects() -> None:
    state = _state()
    for index, name in enumerate(("Early Ward", "Late Ward"), start=1):
        shield = CardInstance(
            id=f"shield-{index}",
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            static_order=index,
            oracle_text="If a source would deal damage to you, prevent 1 of that damage.",
        )
        state.cards[shield.id] = shield
        state.players[1].battlefield.append(shield.id)

    before = state.players[1].life
    deal_damage(state, controller=2, payload={"target_player": 1, "amount": 3})

    assert state.players[1].life == before - 1
    assert any("late ward selected from 2" in line.lower() for line in state.log)


def test_damage_prevention_accepts_explicit_replacement_source_choice() -> None:
    state = _state()
    for index, name in enumerate(("Early Ward", "Late Ward"), start=1):
        shield = CardInstance(
            id=f"choice-shield-{index}",
            name=name,
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Enchantment"],
            static_order=index,
            oracle_text="If a source would deal damage to you, prevent 1 of that damage.",
        )
        state.cards[shield.id] = shield
        state.players[1].battlefield.append(shield.id)

    before = state.players[1].life
    deal_damage(
        state,
        controller=2,
        payload={
            "target_player": 1,
            "amount": 3,
            "__replacement_source_id": "choice-shield-1",
        },
    )

    assert state.players[1].life == before - 1
    assert any("early ward selected from 2" in line.lower() for line in state.log)


def test_destroy_permanent_clears_stale_damage_and_prevention_counters() -> None:
    state = _state()
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.counters["__damage_marked"] = 2
    card.counters["__deathtouch_damaged"] = 1
    card.counters["__prevent_damage_shield"] = 3

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.GRAVEYARD
    assert "__damage_marked" not in card.counters
    assert "__deathtouch_damaged" not in card.counters
    assert "__prevent_damage_shield" not in card.counters


def test_destroy_permanent_puts_stolen_creature_into_its_owners_graveyard() -> None:
    state = _state()
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[2].battlefield.append(cid)
    card = state.cards[cid]
    card.owner = 1
    card.controller = 2
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    resolve_effect(state, 2, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.GRAVEYARD
    assert cid not in state.players[2].battlefield
    assert cid in state.players[1].graveyard
    assert cid not in state.players[2].graveyard


def test_destroy_permanent_respects_die_to_exile_replacement() -> None:
    state = _state()
    replacement = CardInstance(
        id="rep",
        name="Rest in Peace",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="When this enchantment enters, exile all graveyards.\nIf a card or token would be put into a graveyard from anywhere, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[1].battlefield.append(replacement.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.EXILE
    assert cid in state.players[1].exile
    assert cid not in state.players[1].graveyard


def test_destroy_permanent_respects_nontoken_die_replacement_variant() -> None:
    state = _state()
    replacement = CardInstance(
        id="rep",
        name="Death Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a nontoken creature you control would die, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[1].battlefield.append(replacement.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.EXILE
    assert cid in state.players[1].exile
    assert cid not in state.players[1].graveyard


def test_destroy_permanent_respects_rest_in_peace_for_artifact() -> None:
    state = _state()
    replacement = CardInstance(
        id="rep",
        name="Rest in Peace",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="When this enchantment enters, exile all graveyards.\nIf a card or token would be put into a graveyard from anywhere, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[1].battlefield.append(replacement.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Artifact"]

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.EXILE
    assert cid in state.players[1].exile
    assert cid not in state.players[1].graveyard


def test_destroy_permanent_respects_another_creature_variant() -> None:
    state = _state()
    replacement = CardInstance(
        id="rep",
        name="Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If another creature you control would die, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[1].battlefield.append(replacement.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.EXILE
    assert cid in state.players[1].exile
    assert cid not in state.players[1].graveyard


def test_destroy_permanent_respects_artifact_or_enchantment_variant() -> None:
    state = _state()
    replacement = CardInstance(
        id="rep",
        name="Prism Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If an artifact or enchantment you control would die, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[1].battlefield.append(replacement.id)
    cid = state.players[1].hand[0]
    state.players[1].hand.remove(cid)
    state.players[1].battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Artifact"]

    resolve_effect(state, 1, "destroy_permanent", {"target_card_id": cid})

    assert card.zone == Zone.EXILE
    assert cid in state.players[1].exile
    assert cid not in state.players[1].graveyard


def test_nontoken_death_replacement_does_not_exile_tokens() -> None:
    state = _state()
    replacement = CardInstance(
        id="nontoken-rep",
        name="Nontoken Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a nontoken creature you control would die, exile it instead.",
    )
    token = CardInstance(
        id="token",
        name="Soldier Token",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature", "Token"],
    )
    creature = CardInstance(
        id="real-creature",
        name="Bear",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
    )
    state.cards[replacement.id] = replacement
    state.cards[token.id] = token
    state.cards[creature.id] = creature
    state.players[1].battlefield.extend([replacement.id, token.id, creature.id])

    assert replace_die_zone(state, 1, token.id) == "graveyard"
    assert replace_die_zone(state, 1, creature.id) == "exile"


def test_explicit_die_replacement_source_is_honored() -> None:
    state = _state()
    first = CardInstance(
        id="die-rep-a",
        name="First Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a permanent you control would die, exile it instead.",
    )
    second = CardInstance(
        id="die-rep-b",
        name="Second Ward",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a permanent you control would die, exile it instead.",
    )
    state.cards[first.id] = first
    state.cards[second.id] = second
    state.players[1].battlefield.extend([first.id, second.id])
    creature_id = state.players[1].hand[0]
    creature = state.cards[creature_id]
    creature.types = ["Creature"]
    state.players[1].hand.remove(creature_id)
    state.players[1].battlefield.append(creature_id)
    creature.zone = Zone.BATTLEFIELD

    assert replace_die_zone(state, 1, creature_id, first.id) == "exile"
    assert any(first.name in line for line in state.log)
