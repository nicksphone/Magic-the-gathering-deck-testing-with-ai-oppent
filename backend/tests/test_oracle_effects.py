from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Zone
from effects.registry import resolve_effect
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.oracle_effects import inspect_target_hints


def test_oracle_damage_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Lightning Bolt",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "deal_damage"
    assert payload["amount"] == 3


def test_oracle_counterspell_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-1"})())
    card = CardInstance(
        id="c",
        name="Counterspell",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Counter target spell.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "counter_spell"
    assert payload["target_stack_id"] == "stack-1"


def test_oracle_copy_spell_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-copy"})())
    card = CardInstance(
        id="copy",
        name="Spell Swindle",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Copy target spell.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "copy_spell"
    assert payload["target_stack_id"] == "stack-copy"


def test_oracle_copy_ability_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.stack.append(type("SI", (), {"id": "stack-ability"})())
    card = CardInstance(
        id="copy-ability",
        name="Rings of Brighthearth",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Artifact"],
        oracle_text="Copy target activated ability you control.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "copy_ability"
    assert payload["target_stack_id"] == "stack-ability"
    assert payload["copy_kind"] == "activated ability"


def test_split_card_marks_split_hints() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="split",
        name="Fire // Ice",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Choose one — Fire deals 2 damage divided as you choose among one or two targets; Ice taps target permanent and draws a card.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("split_card") is True
    assert hints.get("face_names") == ["Fire", "Ice"]
    assert hints.get("modes")


def test_copy_spell_handler_replays_target_effect() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.players[2].life = 10
    state.stack.append(type("SI", (), {"id": "stack-dmg", "label": "Lightning Bolt", "source_card_id": "bolt-1", "effect_key": "deal_damage", "payload": {"target_player": 2, "amount": 3}})())
    state.cards["bolt-1"] = CardInstance(
        id="bolt-1",
        name="Lightning Bolt",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )
    resolve_effect(state, 1, "copy_spell", {"target_stack_id": "stack-dmg"})
    assert state.players[2].life == 7


def test_copy_ability_handler_replays_target_ability() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 10
    state.stack.append(
        type(
            "SI",
            (),
            {
                "id": "stack-ability",
                "label": "Soul Warden trigger",
                "source_card_id": "warden-1",
                "effect_key": "gain_life",
                "payload": {"target_player": 1, "amount": 1},
                "targets": ["player:1"],
            },
        )()
    )
    state.cards["warden-1"] = CardInstance(
        id="warden-1",
        name="Soul Warden",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever another creature enters the battlefield, you gain 1 life.",
    )
    resolve_effect(state, 1, "copy_ability", {"target_stack_id": "stack-ability"})
    assert state.players[1].life == 11




def test_oracle_multiclause_sequence_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="m",
        name="Cruel Insight",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Target player loses 2 life. You gain 2 life. Draw a card.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_player": 2})
    assert effect_key == "effect_sequence"
    effects = payload["effects"]
    assert [x["effect_key"] for x in effects] == ["lose_life", "gain_life", "draw_cards"]
    assert effects[0]["payload"]["target_player"] == 2
    assert effects[0]["payload"]["amount"] == 2
    assert effects[1]["payload"]["amount"] == 2


def test_oracle_add_counters_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    target = state.players[1].battlefield[0] if state.players[1].battlefield else state.players[1].hand[0]
    card = CardInstance(
        id="counters",
        name="Growth Pattern",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Put two +1/+1 counters on target creature.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": target})
    assert effect_key == "add_counters"
    assert payload["target_card_id"] == target
    assert payload["amount"] == 2


def test_oracle_token_count_and_keywords_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="tok",
        name="Raise Patrol",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Create two 1/1 white Soldier creature tokens with vigilance.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "create_token"
    assert payload["amount"] == 2
    assert payload["power"] == 1
    assert payload["toughness"] == 1
    assert payload["name"] == "White Soldier"
    assert "vigilance" in payload["keywords"]


def test_oracle_collected_company_style_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="cc",
        name="Collected Company",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{3}{G}",
        oracle_text=(
            "Look at the top six cards of your library. "
            "Put up to two creature cards with mana value 3 or less from among them onto the battlefield. "
            "Put the rest on the bottom of your library in any order."
        ),
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1)
    assert effect_key == "topdeck_put_creatures_battlefield"
    assert payload["top_n"] == 6
    assert payload["max_creatures"] == 2
    assert payload["mv_max"] == 3


def test_oracle_prevent_next_damage_parsing() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    target = state.players[1].hand[0]
    card = CardInstance(
        id="foglet",
        name="Protective Burst",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Prevent the next 3 damage that would be dealt to target creature this turn.",
    )
    effect_key, payload = infer_effect_from_oracle(state, card, 1, action_targets={"target_card_id": target})
    assert effect_key == "prevent_damage"
    assert payload["amount"] == 3
    assert payload["target_card_id"] == target


def test_topdeck_creature_deploy_effect_puts_eligible_creatures_onto_battlefield() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    p1.library = p1.library + p1.hand
    p1.hand = []

    top6 = p1.library[-6:]
    # Build top six: two eligible creatures (<=3 MV), one too expensive creature, three noncreatures.
    state.cards[top6[0]].name = "Spell A"
    state.cards[top6[0]].types = ["Instant"]
    state.cards[top6[0]].mana_cost = "{1}{U}"

    state.cards[top6[1]].name = "Elf 2"
    state.cards[top6[1]].types = ["Creature"]
    state.cards[top6[1]].mana_cost = "{1}{G}"

    state.cards[top6[2]].name = "Big 5"
    state.cards[top6[2]].types = ["Creature"]
    state.cards[top6[2]].mana_cost = "{3}{G}{G}"

    state.cards[top6[3]].name = "Elf 3"
    state.cards[top6[3]].types = ["Creature"]
    state.cards[top6[3]].mana_cost = "{2}{G}"

    state.cards[top6[4]].name = "Spell B"
    state.cards[top6[4]].types = ["Sorcery"]
    state.cards[top6[4]].mana_cost = "{2}{G}"

    state.cards[top6[5]].name = "Spell C"
    state.cards[top6[5]].types = ["Instant"]
    state.cards[top6[5]].mana_cost = "{1}{G}"

    resolve_effect(state, 1, "topdeck_put_creatures_battlefield", {"top_n": 6, "max_creatures": 2, "mv_max": 3})
    names = [state.cards[cid].name for cid in p1.battlefield]
    assert "Elf 2" in names
    assert "Elf 3" in names
    assert "Big 5" not in names
