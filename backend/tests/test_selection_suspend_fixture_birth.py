"""Factory-born selection/Suspend stock, not a competitive-deck certificate."""
from copy import deepcopy
import pickle

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_selection_activation_policy import position, relocate
from tests.test_suspend_lifecycle import CARDS, add, restore


def vision_row():
    return {**deepcopy(CARDS['Ancestral Vision']),
            'card_name': 'Ancestral Vision', 'quantity': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_ineligible_population_omits_nonphysical_zero_row_at_birth(seat):
    state, _ = position(seat, 'ineligible')
    assert all(row['quantity'] > 0 for row in state.starting_decks[seat])
    assert not any(row['card_name'] == 'Savannah Lions' for row in state.starting_decks[seat])
    assert not any(card.owner == seat and card.name == 'Savannah Lions'
                   for card in state.cards.values())
    assert restore(state).sideboard_facts == state.sideboard_facts


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_vision_is_bound_at_birth_and_checked_suspend_cold_safe(seat):
    raw = vision_row()
    state, _ = position(seat, additional_own_rows=(raw,))
    card = relocate(state, 'Ancestral Vision', seat, Zone.HAND)
    assert [row for row in state.starting_decks[seat]
            if row['card_name'] == 'Ancestral Vision'] == [raw]
    assert state.sideboard_facts['inventory'][card.id] == {
        'owner': seat, 'stock_key': 'Ancestral Vision'}
    assert card.oracle_text == CARDS['Ancestral Vision']['oracle_text']
    assert sum(c.name == 'Ancestral Vision' and c.owner == seat
               for c in state.cards.values()) == 1
    state.turn = 1
    before = pickle.dumps(state, 5)
    action = {'type': 'suspend', 'card_id': card.id}
    rules = RulesEngine()
    assert any(move['type'] == 'suspend' and move['card_id'] == card.id
               for move in rules.legal_moves(state, seat))
    accepted = checked_action(state, rules, seat, action)
    assert accepted.cards[card.id].zone == Zone.EXILE
    assert accepted.cards[card.id].counters['time'] == 4
    assert accepted.players[seat].mana_pool['U'] == 1
    assert pickle.dumps(state, 5) == before
    assert restore(accepted).sideboard_facts == accepted.sideboard_facts


@pytest.mark.parametrize('seat', [1, 2])
def test_additional_input_is_copied_and_seeded_birth_is_repeatable(seat):
    rows = [vision_row()]
    before = deepcopy(rows)
    first, _ = position(seat, additional_own_rows=rows)
    second, _ = position(seat, additional_own_rows=rows)
    assert rows == before
    assert first.rng.getstate() == second.rng.getstate()
    assert [(cid, c.name, c.zone) for cid, c in first.cards.items()] == [
        (cid, c.name, c.zone) for cid, c in second.cards.items()]
    rows[0]['oracle_text'] = 'Unrecognized caller mutation.'
    assert next(r for r in first.starting_decks[seat]
                if r['card_name'] == 'Ancestral Vision') == before[0]
    assert restore(first).sideboard_facts == first.sideboard_facts


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_corrupt_zero_quantity_still_rejects(seat):
    state, _ = position(seat)
    snapshot = serialize_match_snapshot(state)
    snapshot['starting_decks'][str(seat)][0]['quantity'] = 0
    with pytest.raises(ValueError, match='Invalid starting inventory'):
        deserialize_match_snapshot(snapshot)


@pytest.mark.parametrize('seat', [1, 2])
def test_postcapture_vision_stock_edit_is_not_recaptured(seat):
    state, _ = position(seat)
    card = add(state, 'Ancestral Vision', seat, Zone.HAND, cards=CARDS)
    state.starting_decks[seat].append(vision_row())
    assert card.id not in state.sideboard_facts['inventory']
    with pytest.raises(ValueError, match='does not match original stock'):
        serialize_match_snapshot(state)
