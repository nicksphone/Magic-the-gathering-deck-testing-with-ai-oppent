"""Native priority after drawing is a real response frontier, even on a stack."""
from copy import deepcopy
import random

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from tests.test_draw_private_frontier import RULES, digest, fixture, settle
from tests.draw_canonical_sidecar import raw_card
from tests.test_linked_damage_targets import raw_card as born_card


@pytest.mark.parametrize('seat', [1, 2])
def test_drawn_bolt_can_win_before_an_already_announced_draw_resolves(seat):
    state, study, _, mountain = fixture(seat)
    opponent = 3-seat
    # Complete canonical birth, followed only by an explicit public board pose.
    vision = born_card(state, raw_card('Vision Skeins'), opponent, Zone.HAND)
    for _ in range(2):
        player = state.players[opponent]
        cid = next(x for x in player.library if state.cards[x].name == 'Island')
        player.library.remove(cid)
        player.battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        state.cards[cid].tapped = state.cards[cid].summoning_sick = False
        assign_static_order_on_battlefield_entry(state, cid)
    state.priority_player = opponent
    state = checked_action(state, RULES, opponent, complete_action({
        'type': 'cast_spell', 'card_id': vision.id, 'cost_choice': {'id': 'base'}}))
    assert state.stack[-1].payload['mana_spent'] == 2
    while state.priority_player != seat:
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    assert len(state.stack) == 1 and state.stack[-1].source_card_id == vision.id
    action = complete_action({'type': 'cast_spell', 'card_id': study,
                              'cost_choice': {'id': 'base'}})
    moves = RULES.legal_moves(state, seat)
    view, _ = decision_view(state, seat, moves)
    before, vbefore = digest(state), digest(view)
    rng, local = random.getstate(), state.rng.getstate()
    flag = AIAgent('master', 'Control')._draw_cast_loses(view, action, seat)
    assert digest(view) == vbefore and digest(state) == before
    assert random.getstate() == rng and state.rng.getstate() == local

    paid = checked_action(state, RULES, seat, action)
    assert paid.stack[-1].payload['mana_spent'] == 3
    assert not paid.cards[mountain].tapped
    lost = settle(deepcopy(paid), [])
    assert lost.winner == opponent and seat in lost.failed_draw_players

    rescued = deepcopy(paid)
    for _ in range(4):
        if len(rescued.stack) == 1:
            break
        rescued = checked_action(rescued, RULES, rescued.priority_player,
                                 {'type': 'pass_priority'})
    assert rescued.winner is None and not rescued.players[seat].library
    assert rescued.stack[-1].source_card_id == vision.id
    while rescued.priority_player != seat:
        rescued = checked_action(rescued, RULES, rescued.priority_player,
                                 {'type': 'pass_priority'})
    bolt = next(x for x in rescued.players[seat].hand
                if rescued.cards[x].name == 'Lightning Bolt')
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == bolt
               for m in RULES.legal_moves(rescued, seat))
    rescued = checked_action(rescued, RULES, seat, complete_action({
        'type': 'cast_spell', 'card_id': bolt, 'cost_choice': {'id': 'base'},
        'targets': {'target_player': opponent}}))
    assert rescued.stack[-1].payload['mana_spent'] == 1 and rescued.cards[mountain].tapped
    won = settle(rescued, [])
    assert won.winner == seat and not won.failed_draw_players
    assert won.players[opponent].life <= 0
    assert digest(state) == before and random.getstate() == rng and state.rng.getstate() == local
    assert flag is None, 'Do not auto-pass a newly acquired hand into the older draw object'
