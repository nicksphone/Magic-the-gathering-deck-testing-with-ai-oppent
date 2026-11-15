"""Complete Oracle modal draws: real chooser, private boundaries, paid outcomes."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.draw_canonical_sidecar import raw_card, reprint
from tests.test_ai_recurring_engines import add
from tests.test_ai_targeted_draw import choose, empty_library, position, resolve


FIXTURE = Path(__file__).parent / 'fixtures/ai_modal_targeted_draw'
DRAW = 'Target player draws two cards'
COUNTER = 'Counter target spell'


def modal_position(seat, *, pending=False):
    state, inspiration, lands, rows = position(seat)
    data = (FIXTURE / 'archmages_charm.json').read_bytes()
    provenance = json.loads((FIXTURE / 'provenance.json').read_text())
    assert hashlib.sha256(data).hexdigest() == provenance['sha256']
    raw = json.loads(data)
    assert raw['id'] == provenance['id'] and raw['oracle_id'] == provenance['oracle_id']
    rows[raw['name']] = raw
    state.players[seat].hand.remove(inspiration.id)
    if pending:
        inspiration.owner = inspiration.controller = 3-seat
        state.players[3-seat].hand.append(inspiration.id)
        for _ in range(4):
            add(state, 'Island', 3-seat, cards=rows)
        state.priority_player = 3-seat
        state = checked_action(state, RulesEngine(), 3-seat, {
            'type': 'cast_spell', 'card_id': inspiration.id,
            'targets': {'target_player': seat}})
        state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    else:
        inspiration.move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(inspiration.id)
    charm = add(state, raw['name'], seat, Zone.HAND, cards=rows)
    return state, charm, lands, rows


@pytest.mark.parametrize('seat', [1, 2])
def test_full_ai_chooses_paid_modal_draw_win_instead_of_countering(seat):
    state, spell, lands, _ = modal_position(seat, pending=True)
    empty_library(state, 3-seat)
    action = choose(state, seat, spell, full=True)
    result = resolve(state, seat, action)
    assert result.winner == seat, action
    assert action['targets'] == {'mode_text': DRAW, 'target_player': 3-seat}
    assert sum(result.cards[cid].tapped for cid in lands) == 3
    assert result.cards[spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_draw_mode_can_win_through_the_pending_opposing_spell(seat):
    state, spell, lands, _ = modal_position(seat, pending=True)
    empty_library(state, 3-seat)
    result = resolve(state, seat, {
        'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'mode_text': DRAW, 'target_player': 3-seat}})
    assert result.winner == seat
    assert sum(result.cards[cid].tapped for cid in lands) == 3
    assert len(result.players[seat].hand) == len(result.players[3-seat].hand) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_nonterminal_modal_draw_keeps_existing_counter_preference(seat):
    state, spell, lands, _ = modal_position(seat, pending=True)
    action = choose(state, seat, spell, full=True)
    assert action['targets']['mode_text'] == COUNTER
    result = resolve(state, seat, action)
    assert result.winner is None
    assert not result.stack and not result.players[seat].hand
    assert sum(result.cards[cid].tapped for cid in lands) == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('double', [False, True])
def test_modal_draw_without_counter_target_pays_to_draw_for_self(seat, double):
    state, spell, lands, rows = modal_position(seat)
    if double:
        add(state, 'Thought Reflection', seat, cards=rows)
    action = choose(state, seat, spell, full=True)
    assert action['targets'] == {'mode_text': DRAW, 'target_player': seat}
    result = resolve(state, seat, action)
    assert len(result.players[seat].hand) == (4 if double else 2)
    assert len(result.players[3-seat].hand) == 0
    assert sum(result.cards[cid].tapped for cid in lands) == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent_empty', [False, True])
def test_unknown_own_draw_does_not_block_counter_or_proven_opposing_deckout(seat, opponent_empty):
    state, spell, lands, rows = modal_position(seat, pending=True)
    rows['Stinkweed Imp'] = raw_card('Stinkweed Imp')
    add(state, 'Stinkweed Imp', seat, Zone.GRAVEYARD, cards=rows)
    state.mechanic_choice_players = {1, 2}
    if opponent_empty:
        empty_library(state, 3-seat)
    action = choose(state, seat, spell, full=True)
    assert action['targets']['mode_text'] == (DRAW if opponent_empty else COUNTER)
    result = resolve(state, seat, action)
    assert result.winner == (seat if opponent_empty else None)
    assert sum(result.cards[cid].tapped for cid in lands) == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_private_hand_identities_and_library_order_do_not_change_modal_win(seat):
    state, spell, _, rows = modal_position(seat, pending=True)
    empty_library(state, 3-seat)
    first = add(state, 'Island', 3-seat, Zone.HAND, cards=rows)
    second = add(state, 'Thought Reflection', 3-seat, Zone.HAND, cards=rows)
    original = choose(state, seat, spell, full=True)
    reprint(first, 'Thought Reflection')
    reprint(second, 'Island')
    state.players[seat].library.reverse()
    assert choose(state, seat, spell, full=True) == original
    assert original['targets'] == {'mode_text': DRAW, 'target_player': 3-seat}


@pytest.mark.parametrize('seat', [1, 2])
def test_deliberate_modal_draw_recipient_is_not_overridden(seat):
    state, spell, _, _ = modal_position(seat)
    action = choose(state, seat, spell, explicit=3-seat)
    assert action['targets'] == {'mode_text': DRAW, 'target_player': 3-seat}
    result = resolve(state, seat, action)
    assert len(result.players[seat].hand) == 0
    assert len(result.players[3-seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_counter_mode_is_not_replaced_by_a_winning_draw(seat):
    state, spell, lands, _ = modal_position(seat, pending=True)
    empty_library(state, 3-seat)
    rules = RulesEngine()
    move = next(m for m in rules.legal_moves(state, seat) if m.get('card_id') == spell.id)
    move = {**move, 'targets': {'mode_text': COUNTER, 'target_stack_id': state.stack[-1].id}}
    view, _ = decision_view(state, seat, [move])
    action = complete_action(AIAgent(archetype='Control')._materialize_action(view, move, seat))
    assert action['targets'] == move['targets']
    result = resolve(state, seat, action)
    assert result.winner is None and not result.stack
    assert sum(result.cards[cid].tapped for cid in lands) == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_unresolved_private_draw_without_a_safe_mode_does_not_cast(seat):
    state, spell, lands, rows = modal_position(seat)
    rows['Stinkweed Imp'] = raw_card('Stinkweed Imp')
    add(state, 'Stinkweed Imp', seat, Zone.GRAVEYARD, cards=rows)
    state.mechanic_choice_players = {1, 2}
    action = choose(state, seat, spell, full=True)
    assert action['type'] == 'pass_priority', action
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.cards[spell.id].zone == Zone.HAND and not result.stack
    assert not any(result.cards[cid].tapped for cid in lands)


@pytest.mark.parametrize('seat', [1, 2])
def test_preset_self_recipient_is_not_forecast_as_an_opposing_deckout(seat):
    state, spell, lands, _ = modal_position(seat, pending=True)
    empty_library(state, 3-seat)
    action = choose(state, seat, spell, explicit=seat)
    assert action['targets']['mode_text'] == COUNTER
    result = resolve(state, seat, action)
    assert result.winner is None and not result.stack
    assert sum(result.cards[cid].tapped for cid in lands) == 3
