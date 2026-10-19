"""Real paid ability copies retain conditional instruction and target receipts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_chandra_complete_native_surface import full_card
from tests.test_compleated_loyalty_full import raw_card, SEED
from tests.test_legendary_channels import resolve_to_choice
from tests.test_loyalty_copy_boundaries import ENGINE
from tests.test_wheel_draw import setup

BOUNCE = json.loads((Path(__file__).parent / "fixtures/archangel_pair/unsummon.json").read_bytes())


def paid_copy(seat, target_kind):
    state, source, _, _ = setup("Chandra Ablaze", seat, sizes=(0, 0), cast=False)
    state.mechanic_choice_players = {1, 2}
    discards = [full_card(state, "lightning-bolt.raw.json", seat, Zone.HAND) for _ in range(2)]
    if target_kind == "player":
        old, new = 3 - seat, seat
    else:
        old = raw_card(state, SEED["Llanowar Elves"], 3 - seat, Zone.BATTLEFIELD).id
        new = raw_card(state, SEED["Llanowar Elves"], seat, Zone.BATTLEFIELD).id
    key = "target_player" if target_kind == "player" else "target_card_id"
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 0,
        "targets": {key: old},
    })
    original = state.stack[-1]
    artifact = raw_card(state, ENGINE, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {"C": 2}
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_ability", "card_id": artifact.id, "ability_index": 0,
        "targets": {"target_stack_id": original.id},
    })
    assert state.cards[artifact.id].tapped and not any(state.players[seat].mana_pool.values())
    original_payload = deepcopy(next(item.payload for item in state.stack if item.id == original.id))
    assert not resolve_top_of_stack(state), "The paid copy must pause for actual target choice"
    assert state.pending_mechanic_choice["kind"] == "copy_target"
    copied = state.stack[-1]
    assert copied.id != original.id and copied.controller == seat
    assert copied.payload["__copied_from_stack_id"] == original.id
    return state, source.id, [card.id for card in discards], original.id, original_payload, key, old, new


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("target_kind", ["player", "card"])
@pytest.mark.parametrize("keep", [False, True])
def test_paid_conditional_copy_deliberately_keeps_or_changes_actual_target(seat, target_kind, keep):
    state, source, discards, original, original_payload, key, old, new = paid_copy(seat, target_kind)
    selected = "keep" if keep else f"{key}:{new}"
    assert selected in state.pending_mechanic_choice["options"]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3 - seat, {"type": "choose_mechanic", "card_ids": [selected]})
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = checked_action(state, RulesEngine(), seat, {"type": "choose_mechanic", "card_ids": [selected]})
    copied = state.stack[-1]
    assert copied.payload["__announced_targets"][key] == (old if keep else new)
    assert next(item.payload for item in state.stack if item.id == original) == original_payload
    state = resolve_to_choice(state)
    assert state.pending_mechanic_choice["kind"] == "discard"
    state = checked_action(state, RulesEngine(), seat, {"type": "choose_mechanic", "card_ids": [discards[0]]})
    if target_kind == "player":
        assert state.players[old if keep else new].life == 16
    else:
        assert state.cards[old if keep else new].zone == Zone.GRAVEYARD
    state = resolve_to_choice(state)
    if target_kind == "card" and keep:
        assert not state.pending_mechanic_choice and state.cards[discards[1]].zone == Zone.HAND
    else:
        assert state.pending_mechanic_choice["kind"] == "discard"
        state = checked_action(state, RulesEngine(), seat, {"type": "choose_mechanic", "card_ids": [discards[1]]})
    assert not state.stack and not state.pending_mechanic_choice
    assert state.cards[source].loyalty == 6, "A copy never repays the original loyalty cost"
    if target_kind == "player":
        assert state.players[3 - seat].life == (12 if keep else 16)
        assert state.players[seat].life == (20 if keep else 16)
    else:
        assert state.cards[old].zone == Zone.GRAVEYARD


@pytest.mark.parametrize("seat", [1, 2])
def test_real_paid_bounce_invalidates_only_the_retargeted_copy_before_discard(seat):
    state, source, discards, original, original_payload, key, old, new = paid_copy(seat, "card")
    state = checked_action(state, RulesEngine(), seat, {
        "type": "choose_mechanic", "card_ids": [f"{key}:{new}"],
    })
    response = raw_card(state, BOUNCE, 3 - seat, Zone.HAND)
    state.players[3 - seat].mana_pool = {"U": 1}
    state = checked_action(state, RulesEngine(), seat, {"type": "pass_priority"})
    state = checked_action(state, RulesEngine(), 3 - seat, {
        "type": "cast_spell", "card_id": response.id, "targets": {"target_card_id": new},
    })
    assert not any(state.players[3 - seat].mana_pool.values())
    assert resolve_top_of_stack(state)
    assert state.cards[new].zone == Zone.HAND
    assert resolve_top_of_stack(state)
    assert not state.pending_mechanic_choice
    assert all(state.cards[cid].zone == Zone.HAND for cid in discards)
    assert next(item.payload for item in state.stack if item.id == original) == original_payload
    state = resolve_to_choice(state)
    assert state.pending_mechanic_choice["kind"] == "discard"
    state = checked_action(state, RulesEngine(), seat, {"type": "choose_mechanic", "card_ids": [discards[0]]})
    assert state.cards[old].zone == Zone.GRAVEYARD and state.cards[new].zone == Zone.HAND
    assert state.cards[source].loyalty == 6 and not state.stack


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("index", [1, 2])
def test_paid_targetless_copy_retains_each_real_resolution_and_pays_loyalty_once(seat, index):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7 if index == 2 else 5
    spell = full_card(state, "lightning-bolt.raw.json", seat, Zone.GRAVEYARD) if index == 2 else None
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": index,
    })
    original = state.stack[-1].id
    artifact = raw_card(state, ENGINE, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {"C": 2}
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_ability", "card_id": artifact.id, "ability_index": 0,
        "targets": {"target_stack_id": original},
    })
    assert resolve_top_of_stack(state)
    copied = state.stack[-1].id
    assert copied != original and state.stack[-1].payload["__copied_from_stack_id"] == original
    state = resolve_to_choice(state)
    if index == 2:
        assert state.pending_mechanic_choice["resolving_item"]["id"] == copied
        state = checked_action(state, RulesEngine(), seat, {
            "type": "cast_spell", "card_id": spell.id, "from_graveyard": True,
            "targets": {"target_player": 3 - seat},
        })
        state = resolve_to_choice(state)
        assert state.players[3 - seat].life == 17
        assert state.pending_mechanic_choice["resolving_item"]["id"] == original
        state = checked_action(state, RulesEngine(), seat, {"type": "choose_mechanic", "card_ids": ["decline"]})
        assert state.cards[source.id].zone == Zone.GRAVEYARD
    else:
        assert {pid: len(player.hand) for pid, player in state.players.items()} == {1: 3, 2: 3}
        assert state.discards_this_turn == {seat: 6, 3 - seat: 8}
        assert state.cards[source.id].loyalty == 3
    assert state.cards[artifact.id].tapped and not any(state.players[seat].mana_pool.values())
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize("seat", [1, 2])
def test_declared_compound_grammar_fizzles_before_any_reward_or_discard(seat):
    # This is a grammar protocol fixture, not Chandra's canonical printed body.
    state, source, _, _ = setup("Chandra Ablaze", seat, sizes=(0, 0), cast=False)
    source.oracle_text = ('+1: You get an emblem with "Creatures you control have haste." '
                         'Discard a card. If a red card is discarded this way, '
                         'Chandra deals 4 damage to any target.')
    red = full_card(state, "lightning-bolt.raw.json", seat, Zone.HAND)
    target = raw_card(state, SEED["Llanowar Elves"], 3 - seat, Zone.BATTLEFIELD)
    before_emblems = deepcopy(state.emblems)
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 0,
        "targets": {"target_card_id": target.id},
    })
    response = raw_card(state, BOUNCE, 3 - seat, Zone.HAND)
    state.players[3 - seat].mana_pool = {"U": 1}
    state = checked_action(state, RulesEngine(), seat, {"type": "pass_priority"})
    state = checked_action(state, RulesEngine(), 3 - seat, {
        "type": "cast_spell", "card_id": response.id, "targets": {"target_card_id": target.id},
    })
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].zone == Zone.HAND
    resolved = resolve_top_of_stack(state)
    assert resolved and not state.pending_mechanic_choice
    assert state.emblems == before_emblems and state.cards[red.id].zone == Zone.HAND
    assert state.cards[source.id].loyalty == 6 and not state.stack
