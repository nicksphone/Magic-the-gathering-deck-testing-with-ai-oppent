"""Paid selection occurrence identity; duplicate bodies are explicit protocols."""
from copy import deepcopy
import pickle

import pytest

from ai.information import decision_view
from ai import selection_activation
from ai.selection_activation import pending_selection_expectation
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_ai_selection_activation_policy as policy


BODY = ('Look at the top four cards of your library. You may reveal a creature card '
        'with mana value 3 or less from among them and put it into your hand. '
        'Put the rest on the bottom of your library in a random order.')


def paid_selection(monkeypatch, seat, *, bad_first=None, inspected=False):
    if bad_first is not None:
        original_row = policy.row

        def protocol_row(slug, quantity):
            row = deepcopy(original_row(slug, quantity))
            if slug == 'recruitment-officer':
                # This is an adversarial grammar input at factory birth, not canonical Oracle.
                if bad_first == 'quoted':
                    row['oracle_text'] = '"{1}: Draw a card."\n{3}{W}: ' + BODY
                else:
                    bodies = [BODY + ' (then draw a card)', BODY]
                    if not bad_first:
                        bodies.reverse()
                    row['oracle_text'] = '\n'.join('{3}{W}: ' + body for body in bodies)
            return row

        monkeypatch.setattr(policy, 'row', protocol_row)
    state, source = policy.position(seat)
    index = int(bad_first is True or bad_first == 'quoted')
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'activate_ability' and move['card_id'] == source.id
               and move['ability_index'] == index for move in moves)
    RulesEngine().take_action(state, seat, {'type': 'activate_ability',
        'card_id': source.id, 'ability_index': index}, reject_invalid=True)
    assert sum(state.players[seat].mana_pool.values()) == 0
    item = state.stack[-1]
    assert item.source_card_id == source.id and item.effect_key == 'topdeck_reveal_creature_to_hand'
    if inspected:
        state.mechanic_choice_players = {seat}
        assert resolve_top_of_stack(state) is False
        assert state.pending_mechanic_choice['kind'] == 'topdeck_reveal_creature'
        assert state.pending_mechanic_choice['resolving_item']['id'] == item.id
    return state, index


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad_first', [False, True, 'quoted'])
@pytest.mark.parametrize('inspected', [False, True])
def test_paid_duplicate_normalized_bodies_retain_actual_occurrence_through_restore(
        monkeypatch, seat, bad_first, inspected):
    state, index = paid_selection(monkeypatch, seat, bad_first=bad_first, inspected=inspected)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    seen = []
    original_schema = selection_activation._schema

    def observe(ability):
        seen.append((ability['index'], ability['raw_effect_text']))
        return original_schema(ability)

    monkeypatch.setattr(selection_activation, '_schema', observe)
    for branch in (state, restored):
        view, _ = decision_view(branch, seat, [])
        before = pickle.dumps(view, 5)
        count = len(seen)
        expectation = pending_selection_expectation(view, seat)
        assert seen[count:] == [(index, BODY)]
        if inspected:
            # Known inspected cards intentionally have no exchangeable future-draw prior.
            assert expectation is None
        else:
            assert expectation is not None and 0 < expectation <= 1
        assert pickle.dumps(view, 5) == before
        item = (view.pending_mechanic_choice['resolving_item'] if inspected
                else {'payload': view.stack[-1].payload})
        assert item['payload']['__ability_index'] == index
        assert item['payload']['__ability_raw_effect_text'] == BODY


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['missing_index', 'missing_raw', 'bool_index',
                                 'wrong_index', 'wrong_raw', 'non_string_raw'])
def test_missing_or_mismatched_private_occurrence_never_guesses_normalized_first_match(
        monkeypatch, seat, fault):
    state, _ = paid_selection(monkeypatch, seat)
    view, _ = decision_view(state, seat, [])
    assert pending_selection_expectation(view, seat) is not None
    payload = view.stack[-1].payload
    if fault == 'missing_index':
        payload.pop('__ability_index', None)
    elif fault == 'missing_raw':
        payload.pop('__ability_raw_effect_text', None)
    elif fault == 'bool_index':
        payload['__ability_index'] = False
    elif fault == 'wrong_index':
        payload['__ability_index'] = 100
    elif fault == 'non_string_raw':
        payload['__ability_raw_effect_text'] = None
    else:
        payload['__ability_raw_effect_text'] = BODY + ' (then draw a card)'
    before = pickle.dumps(view, 5)
    assert pending_selection_expectation(view, seat) is None
    assert pickle.dumps(view, 5) == before
