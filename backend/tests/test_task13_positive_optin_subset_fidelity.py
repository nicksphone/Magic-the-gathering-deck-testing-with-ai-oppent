"""Independent retained-print witnesses; parent runs genuine RED then GREEN."""
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import random

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, MatchState, PlayerState, Zone

FIXTURES = Path(__file__).parent / 'fixtures'
PINS = {
    'cost_reservation_overlap/canonical.json': 'fd6c5a98c5d88557589f6fa5f7b87dcb33a88be5bff76aa6a316595d1aa1f9ec',
    'knowledge_profiles/seed155-scryfall.jsonl': '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
    'browser_inline26/canonical.jsonl': '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd',
}
COST = ('Tormenting Voice', 'Deadly Dispute')
MANA = ('Nissa, Who Shakes the World', 'Tropical Island', 'Forest', 'Island',
        'Snow-Covered Forest', 'Ugin, the Spirit Dragon', 'Yavimaya, Cradle of Growth',
        'Counterspell', 'Growth Spiral', 'Llanowar Elves')
COPY = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
        'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')


def official(name, family):
    path = ('cost_reservation_overlap/canonical.json' if family == 'cost' else
            'browser_inline26/canonical.jsonl' if name == 'Snow-Covered Forest' else
            'knowledge_profiles/seed155-scryfall.jsonl')
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == PINS[path]
    raw = (json.loads(data)[name] if family == 'cost' else
           next(row for row in map(json.loads, data.splitlines()) if row['name'] == name))
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) >= 60
    return raw


def expected_print(raw):
    kinds = ('Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land', 'Planeswalker', 'Sorcery')
    return dict(name=raw['name'], mana_cost=raw['mana_cost'], type_line=raw['type_line'],
                types=[kind for kind in kinds if kind in raw['type_line'].split(' \u2014 ')[0].split()],
                power=int(raw['power']) if raw.get('power') is not None else None,
                toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
                printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                loyalty=int(raw['loyalty']) if raw.get('loyalty') is not None else None,
                oracle_text=raw['oracle_text'], keywords=[], colors=raw['colors'],
                card_faces=[], layout=raw['layout'], selected_face_index=None, image_uri=None)


def opted_add(subject, state, name, seat, zone, flag=True):
    # Same test observes the genuine old producer in RED, not a missing-keyword error.
    kwargs = {'full_printing': flag} if 'full_printing' in inspect.signature(subject.add).parameters else {}
    return subject.add(state, name, seat, zone, **kwargs)


@pytest.mark.parametrize('family,name', [('cost', name) for name in COST] + [('mana', name) for name in MANA])
@pytest.mark.parametrize('seat', [1, 2])
def test_selected_optin_has_full_raw_before_real_birth(monkeypatch, family, name, seat):
    subject = importlib.import_module('tests.test_additional_cost_draw_body' if family == 'cost'
                                      else 'tests.test_additive_mana')
    raw = official(name, family)
    expected = expected_print(raw)
    assert raw['keywords'] == (['Treasure'] if family == 'cost' and name == 'Deadly Dispute' else []) and raw.get('card_faces', []) == []
    zone = Zone.HAND if family == 'cost' else Zone.BATTLEFIELD
    state = MatchState('optin-fidelity', {pid: PlayerState(pid, 'P' + str(pid)) for pid in (1, 2)},
                       {}, [], rng=random.Random(71))
    before = deepcopy(state)
    legacy_row = deepcopy(subject.ROWS[name])
    admitted, births = [], []
    prior_factory, prior_birth = MatchFactory.from_decks, CardInstance.__post_init__

    def factory(first, second, *args, **kwargs):
        assert len(first) == 1 and first[0]['quantity'] == 8 and second == []
        assert args == () and kwargs == {'seed': 0}
        assert all(first[0].get(key) == value for key, value in raw.items())
        admitted.append(name)
        return prior_factory(first, second, *args, **kwargs)

    def birth(card):
        assert admitted == [name]
        assert {key: getattr(card, key) for key in expected} == expected
        prior_birth(card)
        assert card.characteristic_record == {'version': 1, 'physical': expected,
                                              'values': {key: expected[key] for key in COPY}}
        births.append(card.id)

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        card = opted_add(subject, state, name, seat, zone)
    assert admitted == [name] and len(births) == 9 and births[-1] == card.id
    assert {key: getattr(card, key) for key in expected} == expected
    assert card.owner == card.controller == seat and card.zone == zone
    assert card.summoning_sick is False and not card.tapped
    assert card.colors is not card.characteristic_record['physical']['colors']
    assert card.characteristic_record['physical']['colors'] is not card.characteristic_record['values']['colors']
    assert state.rng.getstate() == before.rng.getstate()
    assert state.next_object_id == before.next_object_id + (family == 'mana')
    assert card.id == (f'p{seat}-001' if family == 'cost' else '00000000-0000-0000-0000-000000000001')
    assert set(state.cards) == {card.id}
    assert getattr(state.players[seat], zone.value) == [card.id]
    assert all(not player.hand and not player.library and not player.battlefield
               for pid, player in state.players.items() if pid != seat)
    # The source operand is detached, not a mutable alias to the caller's legacy row.
    assert subject.ROWS[name] == legacy_row
    assert raw == official(name, family)


@pytest.mark.parametrize('family', ['cost', 'mana'])
@pytest.mark.parametrize('case', ['default', 'truthy-not-bool', 'unregistered', 'changed-row', 'copied-row', 'copied-table'])
def test_nonadmitted_inputs_keep_original_constructor_without_raw_birth(monkeypatch, family, case):
    subject = importlib.import_module('tests.test_additional_cost_draw_body' if family == 'cost'
                                      else 'tests.test_additive_mana')
    name = 'Tormenting Voice' if family == 'cost' else 'Forest'
    if case == 'unregistered':
        name = 'Cathartic Reunion' if family == 'cost' else 'Wild Growth'
    state = MatchState('legacy-optin', {pid: PlayerState(pid, 'P' + str(pid)) for pid in (1, 2)},
                       {}, [], rng=random.Random(72))
    row = subject.ROWS[name]
    prior_birth = CardInstance.__post_init__
    births = []

    def no_factory(*_args, **_kwargs):
        raise AssertionError('Nonadmitted input reached canonical Factory')

    def birth(card):
        prior_birth(card)
        births.append(card.id)

    with monkeypatch.context() as patch:
        if case == 'changed-row': patch.setitem(row, 'oracle_text', row['oracle_text'] + '\nProtocol specimen.')
        if case == 'copied-row': patch.setitem(subject.ROWS, name, dict(deepcopy(row), name='Protocol specimen'))
        if case == 'copied-table': patch.setattr(subject, 'ROWS', dict(subject.ROWS))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(no_factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        flag = False if case == 'default' else 1 if case == 'truthy-not-bool' else True
        card = opted_add(subject, state, name, 1, Zone.HAND, flag)
        assert card.name == name and card.oracle_text == subject.ROWS[name]['oracle_text']
        assert births == [card.id] and len(state.cards) == 1


class BeforeExileScene(Exception):
    pass


@pytest.mark.parametrize('name,owner', [('Ugin, the Spirit Dragon', 1), ('Elvish Mystic', 1), ('Topiary Stomper', 2)])
def test_colored_exile_positive_birth_keeps_real_print_before_scene(monkeypatch, name, owner):
    subject = importlib.import_module('tests.test_colored_mass_exile')
    raw = official(name, 'mana')
    expected = expected_print(raw)
    if name == 'Topiary Stomper': expected['keywords'] = ['vigilance']
    admitted, scene_births = [], []
    prior_factory, prior_birth = MatchFactory.from_decks, CardInstance.__post_init__

    def factory(first, second, *args, **kwargs):
        if first and first[0].get('object') == 'card' and first[0].get('name') == name:
            assert len(first) == 1 and first[0]['quantity'] == 8 and second == []
            assert args == () and kwargs == {'seed': 0}
            assert all(first[0].get(key) == value for key, value in raw.items())
            admitted.append(name)
        return prior_factory(first, second, *args, **kwargs)

    def birth(card):
        target = card.id == f'{name}-{owner}'
        if target:
            assert admitted == [name]
            assert {key: getattr(card, key) for key in expected} == expected
        prior_birth(card)
        if target:
            assert card.characteristic_record == {'version': 1, 'physical': expected,
                                                  'values': {key: expected[key] for key in COPY}}
            scene_births.append(card.id)

    def before_scene(card):
        assert admitted == [name] and scene_births == [f'{name}-{owner}']
        assert card.id == 'Ugin, the Spirit Dragon-1' and card.loyalty == 7
        raise BeforeExileScene

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        patch.setattr(subject, 'extract_loyalty_abilities', before_scene)
        with pytest.raises(BeforeExileScene):
            subject.test_x_loyalty_exiles_colored_permanents_by_mana_value_on_both_sides()
