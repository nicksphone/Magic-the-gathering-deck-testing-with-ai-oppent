"""Unknown records are planning placeholders, never invented gameplay cards."""
from unittest.mock import patch

import pytest

from ai.agent import AIAgent, AIDecision
from ai.information import decision_view
from game_state.state import CardInstance, Zone
from game_state.serializers import serialize_match_snapshot
from tests.test_ai_search_prefix import bare_state
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Aggro', 'Tokens', 'Drain'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_all_agent_paths_receive_only_their_allowed_information(seat, style, difficulty):
    state = bare_state(seat)
    other = 3-seat
    own = CardInstance('own', 'Lightning Bolt', seat, seat, Zone.HAND, ['Instant'],
                       mana_cost='{R}', oracle_text='Lightning Bolt deals 3 damage to any target.')
    hidden = CardInstance('hidden', 'Counterspell', other, other, Zone.HAND, ['Instant'],
                          mana_cost='{U}{U}', oracle_text='Counter target spell.')
    state.cards[own.id] = own
    state.cards[hidden.id] = hidden
    state.players[seat].hand.append(own.id)
    state.players[other].hand.append(hidden.id)
    state.log.append('AI TRACE private hand Counterspell')
    before = serialize_match_snapshot(state)
    ai = AIAgent(archetype=style, difficulty=difficulty)
    def inspect(view, moves, actor):
        assert actor == seat
        assert view.cards[own.id].name == own.name
        assert view.cards[hidden.id].name == ''
        assert view.cards[hidden.id].oracle_text == ''
        assert view.cards[hidden.id].mana_cost is None
        assert not view.cards[hidden.id].types
        assert len(view.players[other].hand) == 1
        for player in view.players.values():
            assert all(view.cards[cid].name == '' for cid in player.library)
        assert not any('Counterspell' in line for line in view.log)
        return AIDecision({'type': 'pass_priority'}, 'information boundary probe')
    with patch.object(ai, '_choose_action', side_effect=inspect):
        ai.choose_action(state, [{'type': 'pass_priority'}], seat)
    assert serialize_match_snapshot(state) == before


def counter_position(seat=1):
    state = bare_state(seat)
    other = 3-seat
    bolt = CardInstance('bolt', 'Lightning Bolt', seat, seat, Zone.HAND, ['Instant'],
                        mana_cost='{R}', oracle_text='Lightning Bolt deals 3 damage to any target.')
    counter = CardInstance('counter', 'Counterspell', other, other, Zone.HAND, ['Instant'],
                           mana_cost='{U}{U}', oracle_text='Counter target spell.')
    for card in [bolt, counter]:
        state.cards[card.id] = card
        state.players[card.owner].hand.append(card.id)
    state.players[seat].mana_pool = {'R': 1}
    state.players[other].mana_pool = {'U': 2}
    return state, bolt, counter


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Aggro', 'Tokens', 'Drain'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_real_decisions_ignore_unexposed_hand_and_library_identity(seat, style, difficulty):
    state, _, hidden = counter_position(seat)
    state.turn = 12
    moves = RulesEngine().legal_moves(state, seat)
    before = serialize_match_snapshot(state)
    first = AIAgent(archetype=style, difficulty=difficulty).choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    # Counterspell -> canonical basic Island; no public observation has changed.
    hidden.name = 'Island'
    hidden.types = ['Land']
    hidden.mana_cost = ''
    hidden.oracle_text = '{T}: Add {U}.'
    for player in state.players.values():
        player.library.reverse()
    after = serialize_match_snapshot(state)
    second = AIAgent(archetype=style, difficulty=difficulty).choose_action(state, moves, seat)
    assert first == second
    assert serialize_match_snapshot(state) == after


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_reply_is_not_cast_but_its_actual_owner_can_counter(seat):
    state, bolt, counter = counter_position(seat)
    state.players[seat].hand.remove(bolt.id)
    bolt.move_to_zone(Zone.STACK)
    add_to_stack(state, bolt.id, seat, bolt.name, 'deal_damage', {'target_player': 3-seat, 'amount': 3})
    state.priority_player = 3-seat
    opponent_moves = RulesEngine().legal_moves(state, 3-seat)
    own_view, _ = decision_view(state, seat, [])
    assert own_view.cards[bolt.id].oracle_text == bolt.oracle_text
    assert not any(move['type'] == 'cast_spell' for move in RulesEngine().legal_moves(own_view, 3-seat))
    actual_view, _ = decision_view(state, 3-seat, opponent_moves)
    assert actual_view.cards[counter.id].name == 'Counterspell'
    assert any(move['type'] == 'cast_spell' for move in RulesEngine().legal_moves(actual_view, 3-seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['scry', 'scry_top_order', 'surveil', 'surveil_top_order', 'topdeck_bottom_order',
                                  'search_library', 'look_top_select_hand',
                                  'choose_revealed_discard', 'choose_revealed_exile'])
def test_only_authorized_choice_observations_are_available(seat, kind):
    state, _, card = counter_position(seat)
    if kind not in {'choose_revealed_discard', 'choose_revealed_exile'}:
        state.players[card.owner].hand.remove(card.id)
        card.move_to_zone(Zone.LIBRARY)
        state.players[card.owner].library.append(card.id)
    state.pending_mechanic_choice = {'kind': kind, 'player_id': seat, 'options': [card.id]}
    permitted, _ = decision_view(state, seat, [])
    assert permitted.cards[card.id].oracle_text == card.oracle_text
    state.pending_mechanic_choice['player_id'] = 3-seat
    unpermitted, _ = decision_view(state, seat, [])
    assert unpermitted.cards[card.id].name == ''


def test_legal_top_library_source_is_visible_but_other_library_cards_are_not():
    state = bare_state()
    top = state.players[1].library[-1]
    view, moves = decision_view(state, 1, [{'type': 'play_land', 'card_id': top, 'from_library': True}])
    assert view.cards[top].name == 'Island'
    assert all(view.cards[cid].name == '' for cid in state.players[1].library if cid != top)
    moves[0]['card_id'] = 'changed'
    assert top != moves[0]['card_id']


def test_hidden_faces_and_custom_metadata_do_not_survive_the_information_boundary():
    state, _, card = counter_position()
    state.players[2].hand.remove(card.id)
    card.move_to_zone(Zone.EXILE)
    card.exile_face_down = True
    card.card_faces = [{'name': 'Counterspell', 'oracle_text': card.oracle_text}]
    card.private_note = {'hidden': 'Counterspell'}
    state.players[2].exile.append(card.id)
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, 1, [])
    assert not view.cards[card.id].card_faces
    assert not hasattr(view.cards[card.id], 'private_note')
    assert view.cards[card.id].exile_face_down
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_foretold_owner_can_still_inspect_their_real_card_and_cast_cost(seat):
    from tests.test_foretell import setup
    from rules_engine.action_validation import checked_action
    state, cid = setup(seat=seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'foretell', 'card_id': cid})
    own, _ = decision_view(state, seat, [])
    other, _ = decision_view(state, 3-seat, [])
    assert own.cards[cid].name == state.cards[cid].name
    assert own.cards[cid].foretell_record == state.cards[cid].foretell_record
    assert other.cards[cid].name == '' and not other.cards[cid].foretell_record


def test_unknown_record_never_becomes_a_free_or_alternative_cost_spell():
    from game_state.serializers import deserialize_match_snapshot
    state, _, counter = counter_position()
    view, _ = decision_view(state, 1, [])
    # Snapshot-based checked projections do not retain transient Python markers.
    restored = deserialize_match_snapshot(serialize_match_snapshot(view))
    assert not hasattr(restored.cards[counter.id], 'ai_unknown')
    move = {'type': 'cast_spell', 'card_id': counter.id, 'free_cast': True,
            'cost_options': [{'id': 'free', 'mana_cost': ''}]}
    assert AIAgent()._materialize_action(restored, move, 2)['_invalid_ai_choice']
