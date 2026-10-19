"""NEW paid ward/protection and public/private controls; no APNAP-wide claim."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.information import decision_view, is_unknown
from game_state.observations import remembered_hand_card
from game_state.serializers import serialize_match
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.agent_control_facts import ROWS
from tests.test_self_entry_control_paid import paid_targeted_entry
from tests.test_source_linked_exile import (
    position, cast, next_main, raw_card, action, snap,
    deserialize_match_snapshot, resolve_top_of_stack, Zone,
)

ROOT = Path(__file__).resolve().parents[2]
WARD_ROWS = {r['name']: r for r in json.loads((ROOT / 'backend/tests/fixtures/ward.json').read_bytes())}
VEIL = json.loads((ROOT / 'backend/tests/fixtures/favor_target_lifecycle/snakeskin-veil.json').read_bytes())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_actual_paid_entry_ward_is_resumable_response_cost(seat, pay):
    state, _ = position(seat)
    target = raw_card(state, WARD_ROWS['Tolarian Terror'], seat, Zone.HAND)
    state = cast(state, seat, target.id)
    actor = 3 - seat
    state = next_main(state, actor)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    source = raw_card(state, ROWS['Agent of Treachery'], actor, Zone.HAND)
    state = cast(state, actor, source.id)
    moves = RulesEngine().legal_moves(state, actor)
    choice = next(m for m in moves if m['type'] == 'choose_trigger_target'
                  and m.get('target_card_id') == target.id)
    state = action(state, actor, deepcopy(choice))
    trigger = next(item.id for item in state.stack if item.effect_key == 'change_control')
    assert state.stack[-1].effect_key == 'ward_payment'
    assert state.stack[-1].payload['target_stack_id'] == trigger
    assert state.cards[target.id].controller == seat
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'ward_payment'
    assert state.pending_mechanic_choice['player_id'] == actor
    token = 'pay' if pay else 'decline'
    assert token in state.pending_mechanic_choice['options']
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [token]})
    assert snap(state) == before
    state = deserialize_match_snapshot(before)
    pool = sum(state.players[actor].mana_pool.values())
    untapped = {cid for cid in state.players[actor].battlefield if not state.cards[cid].tapped}
    state = action(state, actor, {'type': 'choose_mechanic', 'card_ids': [token]})
    if pay:
        assert sum(state.players[actor].mana_pool.values()) < pool or any(state.cards[cid].tapped for cid in untapped)
        assert any(item.id == trigger for item in state.stack)
        assert resolve_top_of_stack(state)
        assert state.cards[target.id].controller == actor
    else:
        assert all(item.id != trigger for item in state.stack)
        assert state.cards[target.id].controller == seat
    state = deserialize_match_snapshot(snap(state))
    assert state.cards[target.id].controller == (actor if pay else seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_hexproof_response_invalidates_entry_target(seat):
    state, _, target, actor = paid_targeted_entry(seat)
    spell = raw_card(state, VEIL, seat, Zone.HAND)
    state = cast(state, seat, spell.id, {'target_card_id': target})
    assert state.cards[target].counters.get('+1/+1', 0) == 1
    state = deserialize_match_snapshot(snap(state))
    assert resolve_top_of_stack(state)
    assert state.cards[target].controller == seat
    assert state.cards[target].owner == seat
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_entry_decision_views_preserve_private_root_and_rng(seat):
    state, source, target, actor = paid_targeted_entry(seat)
    before, rng = snap(state), random.getstate()
    for viewer in (seat, actor):
        moves = RulesEngine().legal_moves(state, viewer)
        view, _ = decision_view(state, viewer, moves)
        assert view.cards[source].name == state.cards[source].name
        assert view.cards[target].name == state.cards[target].name
        enemy = 3 - viewer
        public = serialize_match(view)
        rendered_hand = {row['id']: row for row in public['players'][enemy]['hand']}
        for cid in state.players[enemy].library:
            assert is_unknown(view.cards[cid])
        for cid in state.players[enemy].hand:
            if remembered_hand_card(state, viewer, state.cards[cid]) is None:
                assert is_unknown(view.cards[cid])
                assert rendered_hand[cid]['name'] == view.cards[cid].name
                assert rendered_hand[cid]['name'] != state.cards[cid].name
    assert snap(state) == before
    assert random.getstate() == rng
