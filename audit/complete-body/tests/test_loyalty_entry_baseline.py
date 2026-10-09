"""Paid unrelated loss beneath an explicitly constructed trusted hand-entry seam.

This seam is not asserted reachable through canonical Ugin's current ultimate.
No stack item, scheduler or parser is replaced: Lightning Bolt is publicly paid.
"""
import json
import os
from pathlib import Path
import pytest
import test_loyalty_entry_lifecycle as e
from test_loyalty_ai_continuations import decide
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.restrictions import card_cant_attack, card_cant_block


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_beneficial_aura_uses_same_settled_decline_baseline(seat, request):
    state=e.position(seat)
    own=e.raw_card(state,e.AURAS['Llanowar Elves'],seat,Zone.BATTLEFIELD)
    enemy=e.raw_card(state,e.AURAS['Llanowar Elves'],3-seat,Zone.BATTLEFIELD)
    aura=e.raw_card(state,e.AURAS['Pacifism'],seat,Zone.HAND)
    bolt=e.raw_card(state,e.SEED['Lightning Bolt'],seat,Zone.HAND)
    assert bolt.oracle_text=='Lightning Bolt deals 3 damage to any target.'
    state,item=e.paid.paid(state,seat,bolt.id,{'R':1},{'target_player':seat})
    assert len(state.stack)==1 and state.stack[0].id==item
    assert state.stack[0].payload['mana_spent']==1
    initial_life=state.players[seat].life
    # Explicit trusted producer seam; do not claim a canonical Ugin stack path.
    resolve_effect(state,seat,'loyalty_hand_entry',{'count':1})
    state=e.cold(state)
    before=serialize_match_snapshot(state)
    declined=e.action(e.cold(state),seat,card_ids=[])
    while declined.stack:
        declined=e.paid.act(declined,declined.priority_player,{'type':'pass_priority'})
    assert declined.players[seat].life==initial_life-3
    assert declined.cards[aura.id].zone==Zone.HAND
    selected,move=decide(state,seat)
    assert move=={'type':'choose_mechanic','card_ids':[aura.id]}
    selected,attachment=decide(selected,seat)
    assert attachment=={'type':'choose_mechanic','choice_id':enemy.id}
    while selected.stack:
        selected=e.paid.act(selected,selected.priority_player,{'type':'pass_priority'})
    assert selected.players[seat].life==declined.players[seat].life
    assert selected.cards[bolt.id].zone==declined.cards[bolt.id].zone==Zone.GRAVEYARD
    assert selected.cards[aura.id].zone==Zone.BATTLEFIELD
    assert selected.cards[aura.id].attached_to==enemy.id
    assert card_cant_attack(selected,enemy.id) and card_cant_block(selected,enemy.id)
    assert not card_cant_attack(selected,own.id) and not card_cant_block(selected,own.id)
    assert serialize_match_snapshot(state)==before
    (Path(os.environ['GAP6_EVIDENCE'])/(request.node.name+'.json')).write_text(json.dumps({
        'scope':'Actual paid Lightning Bolt, then explicitly constructed trusted hand-entry seam; not canonical Ugin reachability',
        'initial':before,'declined':serialize_match_snapshot(declined),'selected':serialize_match_snapshot(selected),
        'actual_card_choice':move,'actual_attachment_choice':attachment},indent=2)+'\n')
