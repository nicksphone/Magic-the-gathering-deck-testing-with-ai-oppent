"""Selected printed modes must validate before a real paid cast can resolve."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import validate_cast_targets
from tests.draw_canonical_sidecar import raw_card


FIXTURE = Path(__file__).parent / 'fixtures/ai_modal_targeted_draw'
DATA = (FIXTURE / 'archmages_charm.json').read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '5ac333f8e377a41bfef302900a387187fcfd54a8cc46cadff380c20b59175354'
CHARM = json.loads(DATA)
DRAW = 'Target player draws two cards'
COUNTER = 'Counter target spell'


def position(seat, *, pending=False):
    island = raw_card('Island')
    deck = [{**island, 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7214)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.library.extend(player.hand)
        player.hand.clear()
        for _ in range(3):
            cid = player.library.pop()
            state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
            player.battlefield.append(cid)

    def charm(owner):
        sample = MatchFactory.from_decks(
            [{**CHARM, 'card_name': CHARM['name'], 'quantity': 8}], [], seed=0)
        card = deepcopy(next(iter(sample.cards.values())))
        card.id = state.allocate_object_id()
        card.owner = card.controller = owner
        card.move_to_zone(Zone.HAND)
        state.cards[card.id] = card
        state.players[owner].hand.append(card.id)
        return card.id

    source = charm(seat)
    other = None
    if pending:
        other = charm(3-seat)
        state.priority_player = 3-seat
        state = checked_action(state, RulesEngine(), 3-seat, {
            'type': 'cast_spell', 'card_id': other,
            'targets': {'mode_text': DRAW, 'target_player': 3-seat}})
        state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    return state, source, other


def packet(mode, choice, representation, per_mode):
    selection = {representation: mode if representation == 'mode_text' else [mode]}
    return {**selection, **({'mode_targets': {mode: choice}} if per_mode else choice)}


def cast(state, seat, source, targets):
    return checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': source, 'targets': targets})


def settle(state):
    for _ in range(8):
        if not state.stack:
            return state
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Paid cast did not settle')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('representation', ['mode_text', 'mode_texts'])
@pytest.mark.parametrize('per_mode', [False, True])
@pytest.mark.parametrize('opponent', [False, True])
def test_paid_draw_preserves_selected_recipient(seat, representation, per_mode, opponent):
    state, source, _ = position(seat)
    recipient = 3-seat if opponent else seat
    targets = packet(DRAW, {'target_player': recipient}, representation, per_mode)
    before = pickle.dumps(state)
    after = cast(state, seat, source, targets)
    assert pickle.dumps(state) == before
    frame = after.stack[-1]
    assert frame.source_card_id == source
    assert frame.payload['__announced_targets'] == targets
    assert frame.payload['mana_spent'] == 3
    assert all(after.cards[cid].tapped for cid in after.players[seat].battlefield)
    assert not any(after.players[seat].mana_pool.values())
    after = settle(after)
    assert len(after.players[recipient].hand) == 2
    assert len(after.players[3-recipient].hand) == 0
    assert after.cards[source].zone == Zone.GRAVEYARD
    assert after.cards[source].oracle_text == CHARM['oracle_text']
    assert after.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('representation', ['mode_text', 'mode_texts'])
@pytest.mark.parametrize('per_mode', [False, True])
def test_paid_counter_preserves_selected_stack_target(seat, representation, per_mode):
    state, source, other = position(seat, pending=True)
    target_id = state.stack[-1].id
    targets = packet(COUNTER, {'target_stack_id': target_id}, representation, per_mode)
    before = pickle.dumps(state)
    after = cast(state, seat, source, targets)
    assert pickle.dumps(state) == before
    assert after.stack[-1].payload['__announced_targets'] == targets
    assert after.stack[-1].payload['mana_spent'] == 3
    assert all(after.cards[cid].tapped for cid in after.players[seat].battlefield)
    after = settle(after)
    assert after.cards[source].zone == after.cards[other].zone == Zone.GRAVEYARD
    assert not after.players[1].hand and not after.players[2].hand
    assert not after.stack and after.winner is None


INVALID_SELECTIONS = [
    {}, {'mode_text': None}, {'mode_text': ''}, {'mode_text': 'Draw seven cards'},
    {'mode_texts': None}, {'mode_texts': []}, {'mode_texts': [None]},
    {'mode_texts': [DRAW, DRAW]}, {'mode_texts': [DRAW, COUNTER]},
    {'mode_texts': ['Draw seven cards']}, {'mode_texts': DRAW},
    {'mode_texts': {DRAW: True}}, {'mode_text': DRAW, 'mode_texts': [DRAW]},
    {'mode_text': DRAW, 'mode_texts': [COUNTER]},
]


@pytest.mark.parametrize('selection', INVALID_SELECTIONS)
@pytest.mark.parametrize('per_mode', [False, True])
def test_choose_one_rejects_invalid_selection_without_inventing_modes(selection, per_mode):
    hints = {'modes': [COUNTER, DRAW]}
    targets = {**selection, **({'mode_targets': {DRAW: {}}} if per_mode else {})}
    valid, reason = validate_cast_targets(hints, targets)
    assert not valid and reason


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('targets', [
    {'mode_texts': [DRAW, DRAW], 'mode_targets': {DRAW: {'target_player': 1}}},
    {'mode_texts': [DRAW, COUNTER], 'target_player': 1},
    {'mode_texts': ['Draw seven cards'], 'target_player': 1},
    {'mode_text': None}, {'mode_texts': None},
    {'mode_text': DRAW, 'mode_texts': [COUNTER], 'target_player': 1},
    {'mode_texts': [DRAW], 'mode_targets': {}},
    {'mode_texts': [DRAW], 'mode_targets': {COUNTER: {}}},
    {'mode_texts': [DRAW], 'mode_targets': {DRAW: {'target_player': 1}, COUNTER: {}}},
    {'mode_texts': [DRAW], 'mode_targets': {DRAW: {'target_player': 1}}, 'target_player': 1},
])
def test_invalid_paid_announcement_rejects_atomically(seat, targets):
    state, source, _ = position(seat)
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, deepcopy(targets))
    assert pickle.dumps(state) == before
    assert state.cards[source].zone == Zone.HAND and not state.stack
    assert not any(state.cards[cid].tapped for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('per_mode', [False, True])
def test_selected_draw_still_rejects_hexproof_recipient_atomically(seat, per_mode):
    state, source, _ = position(seat)
    state.turn_player_hexproof = {3-seat: ['blue']}
    targets = packet(DRAW, {'target_player': 3-seat}, 'mode_texts', per_mode)
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert pickle.dumps(state) == before


def test_nonmodal_targets_do_not_acquire_a_mode_selection():
    assert validate_cast_targets({'player_targets': [{'id': 2}]}, {'target_player': 2}) == (True, '')


@pytest.mark.parametrize('choose', ['choose_two_modes', 'choose_one_or_more_modes'])
def test_existing_multiselect_keeps_original_cardinality(choose):
    hints = {'modes': [COUNTER, DRAW], choose: True}
    choices = {COUNTER: {'target_stack_id': 'spell'}, DRAW: {'target_player': 2}}
    assert validate_cast_targets(hints, {'mode_texts': [COUNTER, DRAW], 'mode_targets': choices}) == (True, '')
    one = {'mode_texts': [DRAW], 'mode_targets': {DRAW: {'target_player': 2}}}
    assert validate_cast_targets(hints, one)[0] is (choose == 'choose_one_or_more_modes')
    assert not validate_cast_targets(hints, {'mode_texts': [DRAW, DRAW]})[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('representation', ['mode_text', 'mode_texts'])
@pytest.mark.parametrize('per_mode', [False, True])
def test_paid_counter_selects_lower_spell_and_preserves_unselected_top(seat, representation, per_mode):
    state, source, lower = position(seat, pending=True)
    lower_stack_id = state.stack[-1].id
    # Supply a second complete canonical Charm, then actually pay for its cast.
    middle = deepcopy(state.cards[source])
    middle.id = state.allocate_object_id()
    state.cards[middle.id] = middle
    state.players[seat].hand.append(middle.id)
    for _ in range(3):
        cid = state.players[seat].library.pop()
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        state.players[seat].battlefield.append(cid)
    state = cast(state, seat, middle.id, {'mode_text': DRAW, 'target_player': seat})
    middle_stack_id = state.stack[-1].id
    assert [frame.source_card_id for frame in state.stack] == [lower, middle.id]
    assert all(frame.payload['mana_spent'] == 3 for frame in state.stack)
    targets = packet(COUNTER, {'target_stack_id': lower_stack_id}, representation, per_mode)
    before = pickle.dumps(state)
    after = cast(state, seat, source, targets)
    assert pickle.dumps(state) == before
    assert len(after.stack) == 3
    assert after.stack[-1].payload['__announced_targets'] == targets
    assert after.stack[-1].payload['mana_spent'] == 3
    assert all(after.cards[cid].tapped for cid in after.players[seat].battlefield)
    assert not any(after.players[seat].mana_pool.values())
    for _ in range(4):
        if after.cards[source].zone == Zone.GRAVEYARD:
            break
        after = checked_action(after, RulesEngine(), after.priority_player, {'type': 'pass_priority'})
    assert after.cards[source].zone == Zone.GRAVEYARD
    assert after.cards[lower].zone == Zone.GRAVEYARD
    assert after.cards[middle.id].zone == Zone.STACK
    assert [frame.id for frame in after.stack] == [middle_stack_id]
    after = settle(after)
    assert len(after.players[seat].hand) == 2
    assert not after.players[3-seat].hand
    assert after.cards[middle.id].zone == Zone.GRAVEYARD
    assert all(after.cards[cid].oracle_text == CHARM['oracle_text']
               for cid in (source, lower, middle.id))
    assert not after.stack and after.winner is None


@pytest.mark.parametrize('representation', ['mode_text', 'mode_texts'])
def test_choose_one_nullable_unused_selector_is_not_a_second_selection(representation):
    hints = {'modes': [COUNTER, DRAW]}
    targets = {'mode_text': None, 'mode_texts': None, 'target_player': 1}
    targets[representation] = DRAW if representation == 'mode_text' else [DRAW]
    before = deepcopy(targets)
    assert validate_cast_targets(hints, targets) == (True, '')
    assert targets == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('representation', ['mode_text', 'mode_texts'])
@pytest.mark.parametrize('per_mode', [False, True])
def test_paid_draw_with_nullable_unused_public_mode_selector(seat, representation, per_mode):
    from api_contracts import CastAction

    state, source, _ = position(seat)
    targets = packet(DRAW, {'target_player': seat}, representation, per_mode)
    action = CastAction.model_validate({'type': 'cast_spell', 'card_id': source,
                                       'targets': targets}).model_dump(exclude_none=True)
    unused = 'mode_texts' if representation == 'mode_text' else 'mode_text'
    action['targets'][unused] = None
    assert 'mode_text' in action['targets'] and 'mode_texts' in action['targets']
    before = pickle.dumps(state)
    after = checked_action(state, RulesEngine(), seat, action)
    assert pickle.dumps(state) == before
    assert after.stack[-1].payload['mana_spent'] == 3
    after = settle(after)
    assert len(after.players[seat].hand) == 2 and not after.players[3-seat].hand
    assert after.cards[source].zone == Zone.GRAVEYARD and after.winner is None
