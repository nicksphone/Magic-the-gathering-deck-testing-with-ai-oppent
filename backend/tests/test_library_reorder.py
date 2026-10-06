"""Full canonical look/reorder spells; choices are explicit and private."""
from copy import deepcopy
import pickle
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.extra_sequence_support import position

FIXTURES = Path(__file__).parent / 'fixtures/library_reorder'


def setup(name, seat, size=8):
    state = position(seat)
    for cid in state.players[seat].library:
        del state.cards[cid]
    state.players[seat].library.clear()
    raw = json.loads((FIXTURES / (name.lower() + '.json')).read_text())
    seed = json.loads((FIXTURES.parents[2] / 'card_data/builtin_oracle_seed.json').read_text())['cards']
    rows = [{'card_name': name, 'quantity': 1, **raw},
            {'card_name': 'Island', 'quantity': size, **seed['Island']}]
    state.starting_decks[seat] = deepcopy(rows)
    sample = MatchFactory.from_decks(rows, [], seed=7221)
    for card in sample.cards.values():
        card.id = state.allocate_object_id()
        card.owner = card.controller = seat
        state.cards[card.id] = card
        if card.name == name:
            card.move_to_zone(Zone.HAND)
            state.players[seat].hand.append(card.id)
            source = card
        else:
            card.move_to_zone(Zone.LIBRARY)
            state.players[seat].library.append(card.id)
    state.players[seat].mana_pool = {'U': 1}
    assert source.oracle_text == raw['oracle_text']
    return state, source


def restore(state):
    snapshot = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(snapshot)
    assert serialize_match_snapshot(result) == snapshot
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_canonical_reorder_then_optional_shuffle_and_draw(seat, name):
    state, source = setup(name, seat)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    count = 5 if name == 'Index' else 3
    assert len(pending['options']) == count
    assert not RulesEngine().legal_moves(state, 3 - seat)
    order = list(reversed(pending['options']))
    state = restore(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': order})
    if name == 'Ponder':
        assert state.cards[source.id].zone == Zone.STACK
        assert state.pending_mechanic_choice['kind'] == 'library_shuffle'
        assert not state.players[seat].hand
        state = restore(state)
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': ['keep']})
        assert state.players[seat].hand == [order[0]]
        assert state.players[seat].library[-(count - 1):] == list(reversed(order[1:]))
    else:
        assert state.players[seat].library[-count:] == list(reversed(order))
        assert not state.players[seat].hand
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
def test_nonmodal_spell_cannot_replace_its_instructions_with_a_client_mode(seat):
    from tests.spell_admission_safety_support import add
    state = position(seat)
    source = add(state, 'Lightning Bolt', seat)
    state.players[seat].mana_pool = {'R': 1}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source.id,
                                                   'targets': {'mode_text': 'Draw a card'}})
    assert serialize_match_snapshot(state) == before


def cast_and_resolve(state, source, seat):
    candidate = checked_action(state, RulesEngine(), seat,
                               {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    resolve_top_of_stack(candidate)
    return candidate


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
@pytest.mark.parametrize('size', [0, 1, 2, 3, 8])
def test_small_libraries_and_exact_seeded_shuffle(seat, name, size):
    state, source = setup(name, seat, size)
    state = cast_and_resolve(state, source, seat)
    if state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] != 'library_shuffle':
        state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic',
                               'card_ids': state.pending_mechanic_choice['options']})
    if name == 'Index':
        assert state.pending_mechanic_choice is None
        assert len(state.players[seat].library) == size
        assert state.winner is None
        return
    assert state.pending_mechanic_choice['kind'] == 'library_shuffle'
    assert state.winner is None
    expected = list(state.players[seat].library)
    rng = deepcopy(state.rng)
    rng.shuffle(expected)
    resumed = restore(state)
    action = {'type': 'choose_mechanic', 'card_ids': ['shuffle']}
    result = checked_action(state, RulesEngine(), seat, action)
    repeated = checked_action(resumed, RulesEngine(), seat, action)
    assert serialize_match_snapshot(result) == serialize_match_snapshot(repeated)
    if size:
        assert result.players[seat].hand == [expected.pop()]
        assert result.winner is None
    else:
        assert result.winner == 3 - seat
    assert result.players[seat].library == expected
    assert result.pending_mechanic_choice is None
    assert result.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
@pytest.mark.parametrize('invalid', ['missing', 'duplicate', 'foreign', 'wrong_seat', 'stale'])
def test_order_rejection_preserves_complete_root(seat, name, invalid):
    state, source = setup(name, seat)
    state = cast_and_resolve(state, source, seat)
    order = list(state.pending_mechanic_choice['options'])
    actor = seat
    if invalid == 'missing': order.pop()
    if invalid == 'duplicate': order[0] = order[1]
    if invalid == 'foreign': order[0] = source.id
    if invalid == 'wrong_seat': actor = 3 - seat
    if invalid == 'stale': state.players[seat].library.reverse()
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, {'type': 'choose_mechanic', 'card_ids': order})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selection', [[], ['keep', 'shuffle'], ['guess']])
def test_shuffle_requires_one_explicit_supported_choice(seat, selection):
    state, source = setup('Ponder', seat, 1)
    state = cast_and_resolve(state, source, seat)
    before = pickle.dumps(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': selection})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_ai_finishes_using_only_legally_inspected_information(seat, name):
    from ai.agent import AIAgent
    from ai.information import decision_view, is_unknown
    state, source = setup(name, seat)
    state = cast_and_resolve(state, source, seat)
    agent = AIAgent()
    while state.pending_mechanic_choice:
        moves = RulesEngine().legal_moves(state, seat)
        seen = set(state.pending_mechanic_choice['inspected_card_ids'])
        view, _ = decision_view(state, seat, moves)
        assert all(not is_unknown(view.cards[cid]) for cid in seen)
        assert all(is_unknown(view.cards[cid]) for cid in state.players[seat].library if cid not in seen)
        enemy, _ = decision_view(state, 3 - seat, [])
        assert all(is_unknown(enemy.cards[cid]) for cid in state.players[seat].library)
        before = pickle.dumps(state)
        action = agent.choose_action(state, moves, seat).action
        assert pickle.dumps(state) == before
        state = checked_action(state, RulesEngine(), seat, action)
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_countered_reorder_spell_never_inspects_or_reorders_library(seat, name):
    from tests.spell_admission_safety_support import add
    state, source = setup(name, seat)
    original = list(state.players[seat].library)
    state.players[3 - seat].mana_pool = {'U': 2}
    counter = add(state, 'Counterspell', 3 - seat, zone=Zone.HAND)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    target = state.stack[-1].id
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3 - seat, {'type': 'cast_spell', 'card_id': counter.id,
                                                         'targets': {'target_stack_id': target}})
    assert resolve_top_of_stack(state)
    assert state.pending_mechanic_choice is None
    assert state.players[seat].library == original
    assert state.cards[source.id].zone == Zone.GRAVEYARD
