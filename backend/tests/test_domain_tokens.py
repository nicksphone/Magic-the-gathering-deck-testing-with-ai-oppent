from __future__ import annotations

from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.domain import basic_land_type_count
from rules_engine.cast_choice import build_cast_hints
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.coverage import known_unsupported_mechanics
from tests.domain_printed_fixtures76 import card as canonical_card, complete_state, deck, library_card, put_in_hand, raw


HERD_ORACLE = raw('Herd Migration')['oracle_text']


def _land(state, card_id: str, controller: int, name: str, type_line: str) -> None:
    assert raw(name)['type_line'] == type_line
    state.cards[card_id] = canonical_card(name,
        id=card_id, owner=controller, controller=controller, zone=Zone.BATTLEFIELD,
    )
    state.players[controller].battlefield.append(card_id)


def test_domain_counts_distinct_subtypes_not_names_or_opponent_lands() -> None:
    state = MatchFactory.from_decks([deck('Forest', 60)] * 2, [deck('Island', 60)])
    _land(state, "forest", 1, "Forest", "Basic Land — Forest")
    _land(state, "garden", 1, "Jetmir's Garden", "Land — Mountain Forest Plains")
    _land(state, "tower", 1, "Raffine's Tower", "Land — Plains Island Swamp")
    _land(state, "duplicate", 1, "Forest", "Basic Land — Forest")
    _land(state, "name-only", 1, "Waterlogged Grove", "Land")
    _land(state, "opponent", 2, "Plains", "Basic Land — Plains")
    assert basic_land_type_count(state, 1) == 5
    assert basic_land_type_count(state, 2) == 1


def test_domain_token_count_is_evaluated_when_effect_resolves() -> None:
    state = MatchFactory.from_decks([deck('Forest', 60)], [deck('Island', 60)])
    card = canonical_card('Herd Migration',
        id="domain-spell", owner=1, controller=1, zone=Zone.STACK,
    )
    assert known_unsupported_mechanics(HERD_ORACLE) == ["domain"]
    assert build_cast_hints(state, card, 1)["action_has_target_text"] is False
    key, payload = infer_effect_from_oracle(state, card, 1)
    assert key == "create_token"
    assert payload["per_basic_land_type"] is True
    assert payload["name"] == "Beast"
    resolve_effect(state, 1, key, payload)
    assert not state.players[1].battlefield

    _land(state, "forest", 1, "Forest", "Basic Land — Forest")
    _land(state, "dual", 1, "Tropical Island", "Land — Forest Island")
    resolve_effect(state, 1, key, payload)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2
    assert all(token.name == "Beast" and token.power == token.toughness == 3 for token in tokens)
    assert all(token.colors == ["G"] for token in tokens)

    ability = CardInstance(
        id="ability", name="Herd Migration ability", owner=1, controller=1, zone=Zone.STACK,
        types=["Sorcery"], oracle_text="Search your library for a basic land card, reveal it, put it into your hand, then shuffle.",
    )
    assert infer_effect_from_oracle(state, ability, 1)[0] == "search_library"


def test_activated_only_spell_text_does_not_trigger_name_guess() -> None:
    state = MatchFactory.from_decks([deck('Forest', 60)], [deck('Island', 60)])
    card = CardInstance(
        id="activated-only", name="Training Bolt", owner=1, controller=1,
        zone=Zone.STACK, types=["Sorcery"],
        oracle_text="{1}, Discard this card: Draw a card.",
    )
    assert infer_effect_from_oracle(state, card, 1)[0] == "noop"


def test_herd_migration_cast_creates_domain_tokens_not_search_effect() -> None:
    state = complete_state('Forest', 'Island', spell='Herd Migration', lands=('Temple Garden',))
    put_in_hand(state, 'Herd Migration')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = state.active_player = 1
    player = state.players[1]
    spell_id = player.hand[0]
    spell = state.cards[spell_id]
    for index in range(7):
        land_id = library_card(state, 'Temple Garden' if index == 0 else 'Forest')
        land = state.cards[land_id]
        land.zone = Zone.BATTLEFIELD
        player.battlefield.append(land_id)

    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": spell_id}, reject_invalid=True)
    assert state.stack and state.stack[-1].effect_key == "create_token"
    resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in player.battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2
    assert spell_id in player.graveyard
