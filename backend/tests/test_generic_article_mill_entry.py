"""Strict entry integration goldens: requires separately owned S2 dispatch hook."""
import json

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_generic_article_mill import ROWS, checked, resolve, restart_state, snapshot
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import position


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_two_tokens_two_altars_deliberate_order_restart_and_exact_four_mills(seat, tmp_path):
    state = position(seat)._state
    altars = [raw_card(state, ROWS['Altar of the Brood'], seat, Zone.BATTLEFIELD).id
              for _ in range(2)]
    spell = raw_card(state, ROWS['Raise the Alarm'], seat, Zone.HAND)
    state.players[seat].mana_pool = dict.fromkeys('WUBRGC', 0)
    state.players[seat].mana_pool.update(W=1, C=1)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    library = list(state.players[3-seat].library)
    battlefield = list(state.players[seat].battlefield)
    state = checked(state, seat, {'type': 'cast_spell', 'card_id': spell.id})
    for _ in range(4):
        if state.pending_trigger_order:
            break
        state = checked(state, state.priority_player, {'type': 'pass_priority'})
    state = restart_state(state)
    assert state.pending_trigger_order
    group = state.pending_trigger_order['groups'][str(seat)]
    assert len(group) == 4
    assert sorted(item['source_card_id'] for item in group) == sorted(altars * 2)
    tokens = [cid for cid in state.players[seat].battlefield if cid not in battlefield]
    assert len(tokens) == 2 and all(state.cards[cid].name == 'Soldier' for cid in tokens)
    assert not any(state.players[seat].mana_pool.values())
    assert state.players[3-seat].library == library
    order = [item['_choice_id'] for item in reversed(group)]
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_trigger_order', 'trigger_order': order[:-1]})
    assert snapshot(state) == before
    state = checked(state, seat, {'type': 'choose_trigger_order', 'trigger_order': order})
    assert [item.source_card_id for item in state.stack] == [item['source_card_id'] for item in reversed(group)]
    (tmp_path / 'announced.json').write_text(json.dumps(snapshot(state), sort_keys=True))
    state = resolve(restart_state(state))
    (tmp_path / 'resolved.json').write_text(json.dumps(snapshot(state), sort_keys=True))
    assert state.players[3-seat].library == library[:-4]
    assert set(library[-4:]).issubset(state.players[3-seat].graveyard)
    assert not state.stack and not state.pending_trigger_order
