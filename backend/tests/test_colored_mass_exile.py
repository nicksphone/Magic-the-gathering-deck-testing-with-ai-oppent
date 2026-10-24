from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import card_data.seed_cards as seed_module
from tests.test_knowledge_ingest import _official_card

from card_data.seed_cards import seed_card_payload
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_loyalty_abilities
from rules_engine.stack_engine import resolve_top_of_stack


_FULL_PRINTING_TABLE = seed_module.SEED_CARD_DATA
_FULL_PRINTING_FIELDS = ('name',
 'type_line',
 'mana_cost',
 'oracle_text',
 'colors',
 'power',
 'toughness',
 'loyalty',
 'keywords',
 'layout',
 'card_faces')
_FULL_PRINTING_CASES = {'Ugin, the Spirit Dragon': '842cada16866d961ab004bba9cfd0baab801fa34f0c6001d59453e9b34f26a28',
 'Elvish Mystic': '13cf9c091375d9749f6d167a9862231525c89e159dc97b29f992a5165ba759d7',
 'Topiary Stomper': 'bcab90c737fb62f430e40b59e4f475ac5264af27da6c395036d4b3d3856edb50'}


def test_x_loyalty_exiles_colored_permanents_by_mana_value_on_both_sides() -> None:
    forest = {"quantity": 60, "card_name": "Forest", "type_line": "Basic Land — Forest"}
    state = MatchFactory.from_decks([forest], [forest], seed=55)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1

    def permanent(name: str, owner: int, *, token: bool = False, full_printing=False) -> CardInstance:
        data = seed_card_payload(name) if not token else None
        if (not token and type(data) is dict and full_printing is True and seed_module.SEED_CARD_DATA is _FULL_PRINTING_TABLE
                and name in _FULL_PRINTING_CASES
                and hashlib.sha256(repr(tuple((type(data.get(field)).__name__, data.get(field))
                    for field in _FULL_PRINTING_FIELDS)).encode()).hexdigest() == _FULL_PRINTING_CASES[name]):
            full = _official_card(name)
            sample = MatchFactory.from_decks(
                [{**deepcopy(full), 'card_name': name, 'quantity': 8, 'image_uri': None}], [], seed=0)
            template = next(value for value in sample.cards.values() if value.zone == Zone.LIBRARY)
            card = replace(template, id=f'{name}-{owner}', owner=owner, controller=owner,
                           zone=Zone.BATTLEFIELD, instance_order=0, summoning_sick=True)
            if name == 'Ugin, the Spirit Dragon':
                card.loyalty = 7
            state.cards[card.id] = card
            state.players[owner].battlefield.append(card.id)
            return card
        card = CardInstance(
            id=f"{name}-{owner}", name=name, owner=owner, controller=owner,
            zone=Zone.BATTLEFIELD,
            types=[part for part in ("Creature", "Artifact", "Planeswalker") if data and part in data.get("type_line", "")]
            if data else (["Artifact"] if name == "Treasure" else ["Creature"]),
            type_line=data.get("type_line", "") if data else "Token",
            mana_cost=data.get("mana_cost", "") if data else "",
            oracle_text=data.get("oracle_text", "") if data else "",
            colors=data.get("colors") if data else (["W"] if name == "White Spirit" else []),
            loyalty=7 if name == "Ugin, the Spirit Dragon" else None,
        )
        state.cards[card.id] = card
        state.players[owner].battlefield.append(card.id)
        return card

    ugin = permanent("Ugin, the Spirit Dragon", 1, full_printing=True)
    mystic = permanent("Elvish Mystic", 1, full_printing=True)
    stomper = permanent("Topiary Stomper", 2, full_printing=True)
    spirit = permanent("White Spirit", 2, token=True)
    treasure = permanent("Treasure", 2, token=True)
    forest_id = state.players[1].library.pop()
    state.players[1].battlefield.append(forest_id)
    state.cards[forest_id].zone = Zone.BATTLEFIELD

    rules = RulesEngine()
    abilities = extract_loyalty_abilities(ugin)
    assert [(ability["delta"], ability["x_sign"]) for ability in abilities] == [(2, 0), (0, -1), (-10, 0)]
    assert not any(move.get("ability_index") == 2 for move in rules.legal_moves(state, 1))
    rules.take_action(state, 1, {"type": "activate_loyalty", "card_id": ugin.id, "ability_index": 1, "targets": {"x_value": 3}})
    assert state.stack[-1].effect_key == "exile_colored_permanents_mana_value_at_most"
    assert ugin.loyalty == 4
    resolve_top_of_stack(state)

    for card in (mystic, stomper, spirit):
        assert card.zone == Zone.EXILE
        assert card.id in state.players[card.owner].exile
    for card in (ugin, treasure, state.cards[forest_id]):
        assert card.zone == Zone.BATTLEFIELD
    assert not any("Oracle effect not inferred" in line for line in state.log)


def test_x_zero_exiles_colored_zero_mana_tokens_but_not_colorless_tokens() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=56)
    spirit = CardInstance(id="spirit", name="White Spirit", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], colors=["W"])
    treasure = CardInstance(id="treasure", name="Treasure", owner=2, controller=2, zone=Zone.BATTLEFIELD, types=["Artifact"], colors=[])
    for card in (spirit, treasure):
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)

    from effects.registry import resolve_effect
    resolve_effect(state, 1, "exile_colored_permanents_mana_value_at_most", {"mv_max": 0})
    assert spirit.zone == Zone.EXILE
    assert treasure.zone == Zone.BATTLEFIELD
