"""Full real loyalty surfaces at the two original engine-positive boundaries."""
from copy import deepcopy
import hashlib
import json
import re

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone
from rules_engine.copiable_values import FIELDS
from tests import planeswalkers_canonical_ff593 as canonical
from tests import test_planeswalkers as original


CASES = (
    (original.test_planeswalker_loyalty_ability_appears_in_legal_moves,
     'Teferi, Time Raveler', 3),
    (original.test_planeswalker_x_loyalty_ability_requires_x_value_and_materializes,
     'Ugin, the Spirit Dragon', 4),
)
ROWS = {
    'Teferi, Time Raveler': (146, '07eadb682e59c64f05386d54898eb62591b35b4ada7cf3158efa2fd17dacb420'),
    'Ugin, the Spirit Dragon': (110, 'a7eaf555f3ec52827474274c5bf4eceadcc5afa29988b82530f35cd9b546062f'),
}
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA = 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'


def independent_raw(name):
    data = (canonical.FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    proof = (canonical.FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == PROVENANCE_SHA
    line, digest = ROWS[name]
    row = data.splitlines()[line - 1]
    assert hashlib.sha256(row).hexdigest() == digest
    raw = json.loads(row)
    assert raw['object'] == 'card' and raw['name'] == name
    return raw


def printed_abilities(name):
    result = []
    for line in independent_raw(name)['oracle_text'].splitlines():
        match = re.fullmatch(r'([+\u2212-]?(?:\d+|X)):\s*(.+)', line)
        if match:
            result.append((match[1].replace('\u2212', '-'), match[2]))
    return result


def expected_values(name):
    raw = independent_raw(name)
    assert raw['keywords'] == [] and not raw.get('card_faces')
    assert 'power' not in raw and 'toughness' not in raw
    return {'name': raw['name'], 'mana_cost': raw['mana_cost'],
            'type_line': raw['type_line'], 'oracle_text': raw['oracle_text'],
            'types': ['Planeswalker'], 'colors': raw['colors'], 'keywords': [],
            'power': None, 'toughness': None, 'printed_power': None,
            'printed_toughness': None, 'loyalty': int(raw['loyalty'])}


def assert_source(card, name, current_loyalty):
    raw = independent_raw(name)
    expected = expected_values(name)
    assert {key: getattr(card, key) for key in FIELDS} == {**expected, 'loyalty': current_loyalty}
    assert {key: card.characteristic_record['physical'][key] for key in FIELDS} == expected
    assert card.characteristic_record['values'] == expected
    assert card.layout == raw['layout'] and card.card_faces == []
    assert card.selected_face_index is None


def capture_original(monkeypatch, case):
    frames, captured = [], []
    real_factory = original.MatchFactory.from_decks
    real_moves = original.RulesEngine.legal_moves
    real_extract = original.extract_loyalty_abilities

    class AtConsumer(BaseException):
        pass

    def factory(*args, **kwargs):
        state = real_factory(*args, **kwargs)
        frames.append((args, kwargs, state))
        return state

    def before_moves(engine, state, player):
        moves = real_moves(engine, state, player)
        card = state.cards[state.players[1].battlefield[-1]]
        captured.append({'state': state, 'card': card, 'moves': moves,
                         'abilities': real_extract(card), 'frames': frames})
        raise AtConsumer

    def after_extract(card):
        abilities = real_extract(card)
        captured.append({'state': frames[0][2], 'card': card, 'moves': None,
                         'abilities': abilities, 'frames': frames})
        raise AtConsumer

    with monkeypatch.context() as patch:
        patch.setattr(original.MatchFactory, 'from_decks', staticmethod(factory))
        if case is CASES[0]:
            patch.setattr(original.RulesEngine, 'legal_moves', before_moves)
        else:
            patch.setattr(original, 'extract_loyalty_abilities', after_extract)
        with pytest.raises(AtConsumer):
            case[0]()
    result, = captured
    return deepcopy(result)


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[1])
def test_complete_official_loyalty_parent_is_pinned_and_fresh(case):
    _, name, _ = case
    raw = independent_raw(name)
    assert canonical.raw_card(name) == raw
    assert canonical.raw_card(name) is not canonical.raw_card(name)
    assert raw['loyalty'] == ('4' if name == CASES[0][1] else '7')


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[1])
def test_actual_original_loyalty_consumer_receives_complete_real_card(case, monkeypatch):
    captured = capture_original(monkeypatch, case)
    state, card = captured['state'], captured['card']
    assert_source(card, case[1], case[2])
    assert state.cards[card.id] is card
    assert card.owner == card.controller == 1 and card.zone == Zone.BATTLEFIELD
    assert state.players[1].battlefield.count(card.id) == 1
    assert state.active_player == state.priority_player == 1
    assert state.step == original.Step.PRECOMBAT_MAIN


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[1])
def test_actual_factory_birth_retains_full_parent_before_current_counter_pose(case, monkeypatch):
    captured = capture_original(monkeypatch, case)
    assert_source(captured['card'], case[1], case[2])
    assert len(captured['frames']) == 2
    args, kwargs, birth = captured['frames'][1]
    raw = independent_raw(case[1])
    normalized = ScryfallSyncService._normalize_payload(raw, canonical.DISPLAY_IMAGE)
    expected = {**raw, **normalized, 'card_name': case[1], 'quantity': 8,
                'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    assert args == ([expected], []) and kwargs == {'seed': 0}
    assert len(birth.cards) == 8
    for card in birth.cards.values():
        assert_source(card, case[1], int(raw['loyalty']))


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[1])
def test_native_parser_preserves_all_printed_loyalty_cost_and_text_order(case, monkeypatch):
    captured = capture_original(monkeypatch, case)
    assert_source(captured['card'], case[1], case[2])
    parsed = captured['abilities']
    printed = printed_abilities(case[1])
    assert [ability['text'] for ability in parsed] == [body for _, body in printed]
    assert len(parsed) == len(printed)
    for ability, (cost, _) in zip(parsed, printed):
        assert ability['x_cost'] is cost.endswith('X')
        assert ability['x_sign'] == (-1 if cost.startswith('-') else 1) if cost.endswith('X') else ability['x_sign'] == 0
        assert ability['delta'] == (0 if cost.endswith('X') else int(cost))


def test_original_two_move_contract_is_two_real_printed_abilities(monkeypatch):
    captured = capture_original(monkeypatch, CASES[0])
    assert_source(captured['card'], CASES[0][1], 3)
    moves = [move for move in captured['moves']
             if move.get('type') == 'activate_loyalty' and move.get('card_id') == captured['card'].id]
    assert [(move['ability_index'], move['ability_x_cost']) for move in moves] == [(0, False), (1, False)]
    assert [cost for cost, _ in printed_abilities(CASES[0][1])] == ['+1', '-3']


def test_real_printed_x_index_materializes_and_pays_actual_counter_cost(monkeypatch):
    captured = capture_original(monkeypatch, CASES[1])
    state, card = captured['state'], captured['card']
    assert_source(card, CASES[1][1], 4)
    printed = printed_abilities(CASES[1][1])
    assert [cost for cost, _ in printed] == ['+2', '-X', '-10']
    assert [index for index, (cost, _) in enumerate(printed) if cost.endswith('X')] == [1]
    assert captured['abilities'][0]['x_cost'] is False
    assert captured['abilities'][1]['x_cost'] is True
    engine = original.RulesEngine()
    moves = engine.legal_moves(state, 1)
    x_moves = [move for move in moves if move.get('type') == 'activate_loyalty'
               and move.get('card_id') == card.id and move.get('ability_x_cost')]
    assert len(x_moves) == 1 and x_moves[0]['ability_index'] == 1
    assert x_moves[0]['target_hints']['requires_x_value'] is True
    ai = original.AIAgent(difficulty='master', archetype='Control')
    action = ai._materialize_action(state, x_moves[0], 1)
    assert action.get('_invalid_ai_choice') is not True
    value = int(action['targets']['x_value'])
    assert 0 < value <= 4 and action['ability_index'] == 1
    engine.take_action(state, 1, action)
    assert state.cards[card.id].loyalty == 4 - value
    assert card.id in state.loyalty_activated_this_turn
    assert state.stack[-1].source_card_id == card.id and state.stack[-1].controller == 1


CORRUPTIONS = {'oracle_text': 'INTERNAL CORRUPTION', 'mana_cost': '{99}',
               'types': ['Creature'], 'loyalty': 99}


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[1])
@pytest.mark.parametrize('field', CORRUPTIONS)
@pytest.mark.parametrize('surface', ['coherent', 'physical'])
def test_independent_real_source_oracle_rejects_typed_corruption(case, field, surface, monkeypatch):
    captured = capture_original(monkeypatch, case)
    card = captured['card']
    assert_source(card, case[1], case[2])
    if surface == 'physical':
        card.characteristic_record['physical'][field] = deepcopy(CORRUPTIONS[field])
    else:
        setattr(card, field, deepcopy(CORRUPTIONS[field]))
        card.characteristic_record['values'][field] = deepcopy(CORRUPTIONS[field])
    with pytest.raises(AssertionError):
        assert_source(card, case[1], case[2])


def test_separate_original_ugin_births_do_not_alias_records_or_full_raw(monkeypatch):
    left = capture_original(monkeypatch, CASES[1])['card']
    right = capture_original(monkeypatch, CASES[1])['card']
    assert_source(left, CASES[1][1], 4)
    assert_source(right, CASES[1][1], 4)
    before = deepcopy((right, canonical.raw_card(CASES[1][1])))
    left.characteristic_record['physical']['oracle_text'] = 'INTERNAL CORRUPTION'
    left.colors.append('R')
    assert (right, canonical.raw_card(CASES[1][1])) == before
