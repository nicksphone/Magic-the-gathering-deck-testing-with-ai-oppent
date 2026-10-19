"""Observe the original tests' real Factory inputs and first Teferi consumer."""
from copy import deepcopy
import hashlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone
from rules_engine.copiable_values import FIELDS
from tests import planeswalkers_canonical_ff593 as canonical
from tests import test_planeswalkers as original


CASES = (
    original.test_attack_can_target_planeswalker_and_reduce_loyalty,
    original.test_planeswalker_loyalty_ability_appears_in_legal_moves,
    original.test_planeswalker_x_loyalty_ability_requires_x_value_and_materializes,
    original.test_unblocked_damage_to_removed_planeswalker_disappears,
    original.test_trample_excess_damage_to_protected_planeswalker_is_prevented,
)
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_SHA = 'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2'
ROWS = {'Island': (50, '450bf6448c1ed549fe3d69fe922cb0ffb8d6fa08751875cc873265f89ad95407'),
        'Teferi, Time Raveler': (146, '07eadb682e59c64f05386d54898eb62591b35b4ada7cf3158efa2fd17dacb420')}


def independent_raw(name):
    data = (canonical.FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    proof = (canonical.FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes()
    assert hashlib.sha256(proof).hexdigest() == PROVENANCE_SHA
    row, digest = ROWS[name]
    data = data.splitlines()[row - 1]
    assert hashlib.sha256(data).hexdigest() == digest
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    return raw


def expected_entry(name, quantity):
    raw = independent_raw(name)
    cached = ScryfallSyncService._normalize_payload(raw, canonical.DISPLAY_IMAGE)
    return {**raw, **cached, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(cached['card_faces_json'])}


def expected_values(name):
    raw = independent_raw(name)
    return {
        'name': raw['name'], 'mana_cost': raw['mana_cost'],
        'type_line': raw['type_line'], 'oracle_text': raw['oracle_text'],
        'types': ['Land'] if name == 'Island' else ['Planeswalker'],
        'colors': raw['colors'], 'keywords': [],
        'power': None, 'toughness': None,
        'printed_power': None, 'printed_toughness': None,
        'loyalty': int(raw['loyalty']) if 'loyalty' in raw else None,
    }


def assert_printed(card, name, *, loyalty=None):
    raw = independent_raw(name)
    expected = expected_values(name)
    current = expected if loyalty is None else {**expected, 'loyalty': loyalty}
    assert {key: getattr(card, key) for key in FIELDS} == current
    assert {key: card.characteristic_record['physical'][key] for key in FIELDS} == expected
    assert card.characteristic_record['values'] == expected
    assert card.layout == raw['layout'] and card.card_faces == []
    assert card.selected_face_index is None


def capture_teferi(monkeypatch):
    factories, consumer = [], []
    real_factory = original.MatchFactory.from_decks

    class BeforeAction(BaseException):
        pass

    def factory(*args, **kwargs):
        state = real_factory(*args, **kwargs)
        factories.append(deepcopy((args, kwargs, state)))
        return state

    def before_action(engine, state, player, action):
        assert action['type'] == 'attack' and player == 1
        consumer.append(deepcopy((state, action)))
        raise BeforeAction

    with monkeypatch.context() as patch:
        patch.setattr(original.MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(original.RulesEngine, 'take_action', before_action)
        with pytest.raises(BeforeAction):
            CASES[0]()
    assert len(consumer) == 1
    state, action = consumer[0]
    target, = action['attack_targets'].values()
    card = state.cards[target.split(':', 1)[1]]
    assert card.owner == card.controller == 2 and card.zone == Zone.BATTLEFIELD
    assert state.active_player == state.priority_player == 1
    assert state.players[2].battlefield.count(card.id) == 1
    return card, factories


@pytest.mark.parametrize('name', ROWS)
def test_full_official_object_and_provenance_are_independently_bound(name):
    raw = independent_raw(name)
    assert canonical.raw_card(name) == raw
    assert raw['keywords'] == [] and not raw.get('card_faces')
    assert 'power' not in raw and 'toughness' not in raw


@pytest.mark.parametrize('body', CASES, ids=lambda body: body.__name__)
def test_original_whole_factory_input_contains_complete_island(body, monkeypatch):
    captured = []

    class BeforeFactory(BaseException):
        pass

    def before_factory(*args, **kwargs):
        captured.append(deepcopy((args, kwargs)))
        raise BeforeFactory

    monkeypatch.setattr(original.MatchFactory, 'from_decks', staticmethod(before_factory))
    with pytest.raises(BeforeFactory):
        body()
    expected = [expected_entry('Island', 60)]
    assert captured == [((expected, expected), {})]


@pytest.mark.parametrize('body', CASES, ids=lambda body: body.__name__)
def test_original_islands_have_genuine_printed_birth_before_protocol_poses(body, monkeypatch):
    captured = []
    real_factory = original.MatchFactory.from_decks

    class AfterFactory(BaseException):
        pass

    def after_factory(*args, **kwargs):
        captured.append(real_factory(*args, **kwargs))
        raise AfterFactory

    monkeypatch.setattr(original.MatchFactory, 'from_decks', staticmethod(after_factory))
    with pytest.raises(AfterFactory):
        body()
    assert len(captured) == 1 and len(captured[0].cards) == 120
    for card in captured[0].cards.values():
        assert_printed(card, 'Island')


def test_actual_attack_target_keeps_full_teferi_and_only_runtime_loyalty_pose(monkeypatch):
    card, factories = capture_teferi(monkeypatch)
    assert_printed(card, 'Teferi, Time Raveler', loyalty=2)
    assert len(factories) == 2
    args, kwargs, birth = factories[1]
    assert args == ([expected_entry('Teferi, Time Raveler', 8)], []) and kwargs == {'seed': 0}
    assert len(birth.cards) == 8
    for born in birth.cards.values():
        assert_printed(born, 'Teferi, Time Raveler')


CORRUPTIONS = {
    'name': 'INTERNAL CORRUPTION', 'mana_cost': '{99}',
    'type_line': 'Artifact', 'oracle_text': 'INTERNAL CORRUPTION',
    'types': ['Creature'], 'colors': ['R'], 'keywords': ['flying'],
    'power': 99, 'toughness': 99, 'printed_power': '99',
    'printed_toughness': '99', 'loyalty': 99,
}


@pytest.mark.parametrize('field', CORRUPTIONS)
def test_coherent_current_retained_corruption_cannot_satisfy_source_oracle(monkeypatch, field):
    card, _ = capture_teferi(monkeypatch)
    assert_printed(card, 'Teferi, Time Raveler', loyalty=2)
    setattr(card, field, deepcopy(CORRUPTIONS[field]))
    card.characteristic_record['values'][field] = deepcopy(CORRUPTIONS[field])
    with pytest.raises(AssertionError):
        assert_printed(card, 'Teferi, Time Raveler', loyalty=2)


@pytest.mark.parametrize('field', CORRUPTIONS)
def test_physical_corruption_cannot_satisfy_source_oracle(monkeypatch, field):
    card, _ = capture_teferi(monkeypatch)
    assert_printed(card, 'Teferi, Time Raveler', loyalty=2)
    card.characteristic_record['physical'][field] = deepcopy(CORRUPTIONS[field])
    with pytest.raises(AssertionError):
        assert_printed(card, 'Teferi, Time Raveler', loyalty=2)


def test_separate_original_poses_do_not_alias_raw_or_printed_records(monkeypatch):
    left, _ = capture_teferi(monkeypatch)
    right, _ = capture_teferi(monkeypatch)
    assert_printed(left, 'Teferi, Time Raveler', loyalty=2)
    assert_printed(right, 'Teferi, Time Raveler', loyalty=2)
    before = deepcopy((right, canonical.raw_card('Teferi, Time Raveler')))
    left.characteristic_record['physical']['oracle_text'] = 'INTERNAL CORRUPTION'
    left.colors.append('R')
    assert (right, canonical.raw_card('Teferi, Time Raveler')) == before


@pytest.mark.parametrize('player', [1, 2])
def test_canonical_island_remains_colorless_without_protocol_overrides(player):
    from rules_engine.colors import card_color_names

    raw = independent_raw('Island')
    card = canonical.canonical_card('Island', id='colorless-island', owner=player,
                                    controller=player, zone=Zone.BATTLEFIELD)
    assert_printed(card, 'Island')
    assert card.colors == raw['colors'] == []
    assert card_color_names(card) == set()
    assert canonical.deck_entry('Island', 60)['colors'] == []
    assert canonical.raw_card('Island') == raw


def test_actual_red_protocol_pose_is_explicit_and_protection_prevents_damage(monkeypatch):
    from rules_engine.colors import card_color_names
    from rules_engine.protection import protected_from_source

    captured = []
    real_combat = original.combat.combat_damage

    class BeforeCombat(BaseException):
        pass

    def before_combat(state):
        captured.append(state)
        raise BeforeCombat

    with monkeypatch.context() as patch:
        patch.setattr(original.combat, 'combat_damage', before_combat)
        with pytest.raises(BeforeCombat):
            CASES[4]()
    state, = captured
    attacker_id, = state.attackers
    target_id = state.attack_targets[attacker_id].split(':', 1)[1]
    attacker, target = state.cards[attacker_id], state.cards[target_id]
    raw_before = independent_raw('Island')
    assert attacker.name == 'Red Trampler' and attacker.mana_cost == '{3}{R}'
    assert attacker.colors == ['R'] and card_color_names(attacker, state) == {'red'}
    assert attacker.characteristic_record['physical']['colors'] == []
    assert attacker.characteristic_record['values']['colors'] == []
    assert protected_from_source(state, target_id, attacker)
    real_combat(state)
    assert target.loyalty == 5 and state.players[2].life == 20
    assert canonical.raw_card('Island') == raw_before
    assert canonical.deck_entry('Island', 60)['colors'] == []
