"""Canonical constructed boards: target choice, paid resolution, not full games."""
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.draw_canonical_sidecar import raw_card, reprint
from tests.test_ai_recurring_engines import add
from tests.test_ai_search_prefix import bare_state


FIXTURE = Path(__file__).parent / 'fixtures/ai_targeted_draw'


def position(seat):
    data = (FIXTURE / 'inspiration.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == json.loads(
        (FIXTURE / 'provenance.json').read_text())['card']['sha256']
    rows = {name: raw_card(name) for name in ('Island', 'Thought Reflection')}
    rows['Inspiration'] = json.loads(data)
    rows = {name: {**row, 'image_uri': row.get('image_uris', {}).get('normal')}
            for name, row in rows.items()}
    state = bare_state(seat)
    state.turn = 20
    spell = add(state, 'Inspiration', seat, Zone.HAND, cards=rows)
    lands = [add(state, 'Island', seat, cards=rows).id for _ in range(6)]
    return state, spell, lands, rows


def choose(state, seat, spell, *, full=False, explicit=None):
    rules = RulesEngine()
    moves = rules.legal_moves(state, seat)
    agent = AIAgent(difficulty='strong', archetype='Control')
    before, rng = serialize_match_snapshot(state), random.getstate()
    if full:
        action = agent.choose_action(state, moves, seat).action
    else:
        move = next(m for m in moves if m.get('card_id') == spell.id and m['type'] == 'cast_spell')
        if explicit is not None:
            move = {**move, 'targets': {'target_player': explicit}}
        view, _ = decision_view(state, seat, moves)
        action = complete_action(agent._materialize_action(view, move, seat))
    assert serialize_match_snapshot(state) == before
    assert random.getstate() == rng
    return action


def resolve(state, seat, action):
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    checked_action(state, rules, seat, action)
    assert serialize_match_snapshot(state) == before
    rules.take_action(state, seat, action, reject_invalid=True)
    paused = serialize_match_snapshot(state)
    state = deserialize_match_snapshot(paused)
    assert serialize_match_snapshot(state) == paused
    for _ in range(32):
        if not state.stack or state.winner is not None:
            return state
        rules.take_action(state, state.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
    raise AssertionError('Actual paid spell did not settle')


def empty_library(state, seat):
    player = state.players[seat]
    for cid in list(player.library):
        player.library.remove(cid)
        player.exile.append(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)


@pytest.mark.parametrize('seat', [1, 2])
def test_full_ai_pays_for_its_own_two_cards_instead_of_feeding_opponent(seat):
    state, spell, lands, _ = position(seat)
    action = choose(state, seat, spell, full=True)
    assert action['type'] == 'cast_spell' and action['card_id'] == spell.id
    assert action['targets']['target_player'] == seat
    state = resolve(state, seat, action)
    assert sum(state.cards[cid].tapped for cid in lands) == 4
    assert len(state.players[seat].hand) == 2
    assert len(state.players[3-seat].hand) == 0
    assert state.cards[spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('empty', ['self', 'opponent'])
def test_public_empty_library_outcome_can_override_beneficial_draw_default(seat, empty):
    state, spell, _, _ = position(seat)
    empty_library(state, seat if empty == 'self' else 3-seat)
    action = choose(state, seat, spell)
    assert action['targets']['target_player'] == 3-seat
    state = resolve(state, seat, action)
    assert state.winner == (seat if empty == 'opponent' else None)
    assert len(state.players[3-seat].hand) == (0 if empty == 'opponent' else 2)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_draw_replacement_is_applied_to_the_selected_recipient(seat):
    state, spell, _, rows = position(seat)
    add(state, 'Thought Reflection', seat, cards=rows)
    action = choose(state, seat, spell)
    assert action['targets']['target_player'] == seat
    state = resolve(state, seat, action)
    assert len(state.players[seat].hand) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_deliberate_explicit_legal_target_is_not_overridden(seat):
    state, spell, _, _ = position(seat)
    action = choose(state, seat, spell, explicit=3-seat)
    assert action['targets']['target_player'] == 3-seat
    state = resolve(state, seat, action)
    assert len(state.players[3-seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent_empty', [False, True])
def test_unresolved_own_dredge_is_not_permission_to_give_opponent_free_cards(seat, opponent_empty):
    state, spell, _, rows = position(seat)
    rows['Stinkweed Imp'] = raw_card('Stinkweed Imp')
    add(state, 'Stinkweed Imp', seat, Zone.GRAVEYARD, cards=rows)
    state.mechanic_choice_players = {1, 2}
    if opponent_empty:
        empty_library(state, 3-seat)
    rules = RulesEngine()
    move = next(m for m in rules.legal_moves(state, seat) if m.get('card_id') == spell.id)
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, seat, [move])
    action = AIAgent(archetype='Control')._materialize_action(view, move, seat)
    assert serialize_match_snapshot(state) == before
    if not opponent_empty:
        assert action.get('_invalid_ai_choice')
    else:
        assert action['targets']['target_player'] == 3-seat
        assert resolve(state, seat, complete_action(action)).winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opposing_hand_identities_do_not_change_target_or_root(seat):
    state, spell, _, rows = position(seat)
    first = add(state, 'Island', 3-seat, Zone.HAND, cards=rows)
    second = add(state, 'Thought Reflection', 3-seat, Zone.HAND, cards=rows)
    original = choose(state, seat, spell, full=True)
    reprint(first, 'Thought Reflection')
    reprint(second, 'Island')
    assert choose(state, seat, spell, full=True) == original
    assert original['targets']['target_player'] == seat
