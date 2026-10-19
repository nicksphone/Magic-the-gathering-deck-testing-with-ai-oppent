"""Full-canonical paid loyalty timing audit; no production edits or injected frames."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected
import test_brainstorm_desired as brain


ROWS = {row['name']: row for row in map(json.loads, (
    Path(__file__).parent / 'fixtures/builtin_face_colors/canonical.jsonl'
).read_text().splitlines())}


def paid_emperor(seat, boundary, restore):
    state = brain.position(seat)
    if boundary in {'opponent-turn', 'wrong-actor'}:
        state.active_player = 3 - seat
        state.step = Step.END_STEP
    row = ROWS['The Wandering Emperor']
    sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=4)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    assert card.oracle_text == row['oracle_text']
    assert 'Planeswalker' in card.types and card.loyalty == 3
    state, frame = brain.cast(state, seat, card.id, {'W': 4})
    state = brain.advance(state, lambda s: all(item.id != frame for item in s.stack))
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].entered_turn == state.turn
    assert state.cards[card.id].loyalty == 3
    if state.priority_player != seat:
        state = brain.act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    if boundary == 'nonempty-stack':
        instant = brain.add(state, 'Brainstorm', seat, Zone.HAND)
        state, instant_frame = brain.cast(state, seat, instant, {'U': 1})
        assert any(item.id == instant_frame for item in state.stack)
    return (brain.cold(state) if restore else state), card.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('boundary', ['own-main', 'opponent-turn', 'nonempty-stack', 'wrong-actor'])
def test_paid_entry_turn_loyalty_timing_and_actor(seat, restore, boundary):
    state, source = paid_emperor(seat, boundary, restore)
    action = {'type': 'activate_loyalty', 'card_id': source, 'ability_index': 1, 'targets': {}}
    if boundary == 'wrong-actor':
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            brain.act(state, 3 - seat, action)
        assert serialize_match_snapshot(state) == before
        return
    offered = brain.RULES.legal_moves(state, seat)
    assert any(move['type'] == 'activate_loyalty' and move.get('card_id') == source
               and move.get('ability_index') == 1 for move in offered), 'entry-turn loyalty timing must be offered'
    before = set(state.players[seat].battlefield)
    state = brain.act(state, seat, action)
    assert state.cards[source].loyalty == 2
    frame = next(item.id for item in state.stack if item.source_card_id == source)
    state = brain.advance(state, lambda s: all(item.id != frame for item in s.stack))
    tokens = [state.cards[cid] for cid in set(state.players[seat].battlefield) - before]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.power == token.toughness == 2
    assert 'vigilance' in {keyword.lower() for keyword in token.keywords}
    brain.cold(state)
