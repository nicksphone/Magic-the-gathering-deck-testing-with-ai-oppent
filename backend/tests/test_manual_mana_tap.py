from __future__ import annotations
import hashlib
from itertools import groupby
import json
from pathlib import Path
import random

from tests.controlled_basic_game_support import controlled_basic_game

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import ActionRejected, checked_action
from game_state.serializers import serialize_card_view, serialize_match_snapshot
from card_data.token_definitions import named_artifact_token
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, nonland_mana_outputs
import pytest


def _manual_row(name, quantity):
    data = Path(__file__).parent / 'fixtures/manual_mana_a227'
    sources = (data / 'SOURCES.json').read_bytes()
    assert hashlib.sha256(sources).hexdigest() == 'e450c68b67cb25498e80c245962502715477bb9c903a4a77d931682ae1b5bcb8'
    sources = json.loads(sources)
    assert hashlib.sha256((data / sources['provenance_file']).read_bytes()).hexdigest() == sources['provenance_sha256']
    pin = sources['objects'][name]
    body = (data / pin['file']).read_bytes()
    assert len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256']
    raw = json.loads(body)
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) == pin['fields']
    assert raw['id'] == pin['id'] and raw['oracle_id'] == pin['oracle_id']
    return {**raw, 'card_name': name, 'quantity': quantity,
            'image_uri': raw['image_uris']['normal']}


def _manual_decks(named_sources):
    rng = random.Random(8)
    decks = []
    for owner in (1, 2):
        order = list(range(60))
        rng.shuffle(order)
        names = ['Forest'] * 60
        if owner == 1:
            # Factory shuffles before assigning IDs; preserve the old 053/052 poses.
            for offset, name in enumerate(named_sources):
                names[order[52-offset]] = name
        decks.append([_manual_row(name, sum(1 for _ in copies))
                      for name, copies in groupby(names)])
    return decks


def test_tap_lands_bulk_adds_mana_and_taps_requested_count() -> None:
    deck = [_manual_row('Mountain', 60)]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    p1 = state.players[1]

    # Stage exactly three Mountains as untapped battlefield lands.
    p1.battlefield = []
    for _ in range(3):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.tapped = False

    engine.take_action(state, 1, {"type": "tap_lands_bulk", "land_name": "Mountain", "count": 2})

    tapped = sum(1 for cid in p1.battlefield if state.cards[cid].tapped)
    assert tapped == 2
    assert p1.mana_pool["R"] == 2


def _mana_game(*named_sources):
    if named_sources:
        state = MatchFactory.from_decks(*_manual_decks(named_sources), seed=8)
    else:
        # Existing synthetic Treasure/Mana Creature protocol poses remain UNWAIVED.
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest", "oracle_text": "{T}: Add {G}."}]
        state = controlled_basic_game(deck, deck, seed=8)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def test_manual_treasure_mana_sacrifices_token_and_persists_pool() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    token = state.cards[cid]
    token.name = "Treasure"
    token.types = ["Artifact", "Token"]
    token.type_line = "Token Artifact - Treasure"
    token.oracle_text = named_artifact_token("Treasure")["oracle_text"]
    token.is_token = True
    token.zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(cid)
    assert serialize_card_view(state, cid)["mana_source_colors"] == list("BGRUW")
    result = checked_action(state, RulesEngine(), 1, {"type": "tap_nonland_for_mana", "card_id": cid, "color": "U"})
    assert result.players[1].mana_pool["U"] == 1
    assert cid not in result.players[1].battlefield
    assert result.cards[cid].zone == Zone.CEASED
    assert state.players[1].mana_pool["U"] == 0
    assert cid in state.players[1].battlefield


def test_manual_creature_mana_requires_ready_source_and_valid_color() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    creature = state.cards[cid]
    creature.name = "Mana Creature"
    creature.types = ["Creature"]
    creature.oracle_text = "{T}: Add {G}."
    creature.zone = Zone.BATTLEFIELD
    creature.summoning_sick = True
    state.players[1].battlefield.append(cid)
    action = {"type": "tap_nonland_for_mana", "card_id": cid, "color": "G"}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, action)
    assert serialize_match_snapshot(state) == before
    creature.summoning_sick = False
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {**action, "color": "U"})
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, action)
    result = checked_action(state, RulesEngine(), 1, action)
    assert result.players[1].mana_pool["G"] == 1
    assert result.cards[cid].tapped


@pytest.mark.parametrize("name,types,text,color,amount", [
    ("Llanowar Tribe", ["Creature"], "{T}: Add {G}{G}{G}.", "G", 3),
    ("Sol Ring", ["Artifact"], "{T}: Add {C}{C}.", "C", 2),
    ("Gilded Lotus", ["Artifact"], "{T}: Add three mana of any one color.", "U", 3),
])
def test_fixed_multi_mana_sources_produce_printed_amount(name, types, text, color, amount) -> None:
    state = _mana_game(name)
    cid = state.players[1].library.pop()
    source = state.cards[cid]
    source.zone = Zone.BATTLEFIELD
    source.summoning_sick = False
    state.players[1].battlefield.append(cid)
    expected = {choice: amount for choice in "WUBRG"} if name == "Gilded Lotus" else {color: amount}
    assert nonland_mana_outputs(state, cid, source) == expected
    assert serialize_card_view(state, cid)["mana_source_amounts"] == expected
    assert can_pay_with_pool_and_lands(state, 1, "".join("{" + color + "}" for _ in range(amount)))
    manual = checked_action(state, RulesEngine(), 1, {"type": "tap_nonland_for_mana", "card_id": cid, "color": color})
    assert manual.players[1].mana_pool[color] == amount
    assert manual.cards[cid].tapped
    cost = "".join("{" + color + "}" for _ in range(amount - 1))
    assert auto_pay_cost(state, 1, cost)
    assert state.cards[cid].tapped
    assert state.players[1].mana_pool[color] == 1


def test_one_flexible_source_cannot_pay_two_distinct_colored_pips() -> None:
    state = _mana_game()
    cid = state.players[1].library.pop()
    source = state.cards[cid]
    source.name = "Treasure"
    source.types = ["Artifact", "Token"]
    source.oracle_text = named_artifact_token("Treasure")["oracle_text"]
    source.zone = Zone.BATTLEFIELD
    source.is_token = True
    state.players[1].battlefield.append(cid)
    assert not can_pay_with_pool_and_lands(state, 1, "{R}{G}")
    before = serialize_match_snapshot(state)
    assert not auto_pay_cost(state, 1, "{R}{G}")
    assert serialize_match_snapshot(state) == before
    assert can_pay_with_pool_and_lands(state, 1, "{R}")


def test_basic_is_used_before_dual_to_preserve_other_color() -> None:
    state = _mana_game('Watery Grave', 'Island')
    dual_id = state.players[1].library.pop()
    basic_id = state.players[1].library.pop()
    for cid in (dual_id, basic_id):
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.players[1].battlefield.append(cid)
    dual = state.cards[dual_id]
    basic = state.cards[basic_id]
    assert can_pay_with_pool_and_lands(state, 1, "{U}{B}")
    assert auto_pay_cost(state, 1, "{U}{B}")
    assert dual.tapped and basic.tapped
