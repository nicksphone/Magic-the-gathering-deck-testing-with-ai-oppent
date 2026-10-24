"""Full-print birth witnesses; original effects and mixed HTTP run separately."""
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import random

import pytest

from game_state.state import CardInstance, MatchFactory, Zone

FIXTURES = Path(__file__).parent / 'fixtures'
MODULES = {'bears': 'tests.regression_agent.test_interactions',
           'atraxa': 'tests.test_distinct_card_type_reveal',
           'guide': 'tests.test_interactions_expanded'}
NAMES = {'bears': 'Grizzly Bears', 'atraxa': 'Atraxa, Grand Unifier', 'guide': 'Goblin Guide'}
NATIVE_KEYWORDS = {'bears': [], 'atraxa': ['lifelink', 'deathtouch', 'flying', 'vigilance'],
                   'guide': ['haste']}
RAW_KEYWORDS = {'bears': [], 'atraxa': ['Deathtouch', 'Flying', 'Lifelink', 'Vigilance'],
                'guide': ['Haste']}
COPY_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
               'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')


def official(case):
    if case == 'bears':
        data = (FIXTURES / 'ai_terminal_draw/grizzly-bears.raw.json').read_bytes()
        assert hashlib.sha256(data).hexdigest() == '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c'
        raw = json.loads(data)
    else:
        data = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
        assert hashlib.sha256(data).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
        matches = [json.loads(line) for line in data.splitlines() if json.loads(line)['name'] == NAMES[case]]
        assert len(matches) == 1
        raw = matches[0]
    assert raw['object'] == 'card' and raw['name'] == NAMES[case]
    assert len(raw) == {'bears': 66, 'atraxa': 67, 'guide': 66}[case]
    assert raw['keywords'] == RAW_KEYWORDS[case] and raw.get('card_faces', []) == []
    return raw


def printed(case, raw):
    return dict(name=raw['name'], mana_cost=raw['mana_cost'], type_line=raw['type_line'],
                types=['Creature'], power=int(raw['power']), toughness=int(raw['toughness']),
                printed_power=raw['power'], printed_toughness=raw['toughness'], loyalty=None,
                oracle_text=raw['oracle_text'], keywords=NATIVE_KEYWORDS[case], colors=raw['colors'],
                card_faces=[], layout=raw['layout'], selected_face_index=None, image_uri=None)


class BeforeScene(Exception):
    pass


@pytest.mark.parametrize('case,seat', [('bears', 1), ('bears', 2), ('atraxa', 1), ('guide', 1)])
def test_selected_real_input_has_complete_native_print_before_scene(monkeypatch, case, seat):
    subject = importlib.import_module(MODULES[case])
    raw = official(case)
    expected = printed(case, raw)
    object_id = {'bears': '00000000-0000-0000-0000-000000000001',
                 'atraxa': 'atraxa', 'guide': 'card-goblin-guide'}[case]
    admitted, private_births, scene_births, worlds = [], [], [], []
    inside_private = False
    previous_factory, previous_birth = MatchFactory.from_decks, CardInstance.__post_init__

    def record(card):
        assert card.characteristic_record == {'version': 1, 'physical': expected,
                                              'values': {key: expected[key] for key in COPY_FIELDS}}

    def factory(first, second, *args, **kwargs):
        nonlocal inside_private
        selected = bool(first and first[0].get('object') == 'card' and first[0].get('name') == raw['name'])
        if selected:
            assert len(first) == 1 and first[0]['quantity'] == 8 and second == []
            assert args == () and kwargs == {'seed': 0}
            assert all(first[0].get(key) == value for key, value in raw.items())
            admitted.append(raw['name'])
            before = random.getstate()
            inside_private = True
            try:
                result = previous_factory(first, second, *args, **kwargs)
            finally:
                inside_private = False
            assert random.getstate() == before
            return result
        state = previous_factory(first, second, *args, **kwargs)
        worlds.append((state, state.rng.getstate(), random.getstate(), state.next_object_id, set(state.cards)))
        return state

    def birth(card):
        selected = card.name == raw['name'] and (inside_private or card.id == object_id)
        if selected:
            assert admitted == [raw['name']]
            assert {key: getattr(card, key) for key in expected} == expected
        previous_birth(card)
        if selected:
            record(card)
            (private_births if inside_private else scene_births).append(card.id)

    def scene(state):
        card = state.cards[object_id]
        assert admitted == [raw['name']] and len(private_births) == 8 and scene_births == [object_id]
        assert {key: getattr(card, key) for key in expected} == expected
        record(card)
        assert card.owner == card.controller == seat
        assert card.zone == (Zone.LIBRARY if case == 'guide' else Zone.BATTLEFIELD)
        assert card.id in getattr(state.players[seat], card.zone.value)
        assert card.summoning_sick is (case != 'bears') and not card.tapped
        assert card.instance_order == 0 and card.counters == {} and card.knowledge_snapshot == {}
        assert card.colors is not card.characteristic_record['physical']['colors']
        assert card.characteristic_record['physical']['colors'] is not card.characteristic_record['values']['colors']

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(CardInstance, '__post_init__', birth)
        if case == 'bears':
            previous_add = subject.add

            def add(state, name, *args, **kwargs):
                if name != raw['name']:
                    return previous_add(state, name, *args, **kwargs)
                rng, global_rng = state.rng.getstate(), random.getstate()
                before_id, before_time, before_order = state.next_object_id, state.next_effect_timestamp, state.next_static_order
                before_cards = set(state.cards)
                result = previous_add(state, name, *args, **kwargs)
                assert result == object_id
                scene(state)
                assert state.rng.getstate() == rng and random.getstate() == global_rng
                assert state.next_object_id == before_id + 1
                assert state.next_effect_timestamp == before_time + 1 and state.next_static_order == before_order + 1
                assert set(state.cards) == before_cards | {object_id}
                raise BeforeScene

            patch.setattr(subject, 'add', add)
            with pytest.raises(BeforeScene):
                subject.test_humility_anthem_counter_pump_and_source_departure(seat)
        elif case == 'atraxa':
            previous_world, previous_seed = subject.controlled_basic_game, subject.seed_card_payload

            def world(*args, **kwargs):
                state = previous_world(*args, **kwargs)
                worlds.append((state, state.rng.getstate(), random.getstate(), state.next_object_id, set(state.cards)))
                return state

            def seed(name):
                if name != raw['name']:
                    state, rng, global_rng, next_id, cards = worlds[0]
                    scene(state)
                    assert state.rng.getstate() == rng and random.getstate() == global_rng
                    assert state.next_object_id == next_id and set(state.cards) == cards | {object_id}
                    assert state.cards[object_id].static_order == 0
                    raise BeforeScene
                return previous_seed(name)

            patch.setattr(subject, 'controlled_basic_game', world)
            patch.setattr(subject, 'seed_card_payload', seed)
            with pytest.raises(BeforeScene):
                subject._atraxa_state()
        else:
            def consume(state, player, effect, payload):
                assert player == 1 and effect == 'search_library' and payload == {'contains': 'Goblin'}
                scene(state)
                _, rng, global_rng, next_id, cards = worlds[0]
                assert state.rng.getstate() == rng and random.getstate() == global_rng
                assert state.next_object_id == next_id and len(state.cards) == len(cards) + 4
                raise BeforeScene

            patch.setattr(subject, 'resolve_effect', consume)
            with pytest.raises(BeforeScene):
                subject.test_search_library_returns_all_matching_cards()


@pytest.mark.parametrize('case', ['default', 'truthy-not-bool', 'other-name', 'altered-row', 'replaced-row', 'alternate-table'])
def test_bears_default_and_protocol_inputs_retain_original_constructor(monkeypatch, case):
    subject = importlib.import_module(MODULES['bears'])
    state = subject.position(1)
    name = 'Giant Growth' if case == 'other-name' else 'Grizzly Bears'
    row = subject.CARDS[name]
    previous_factory = MatchFactory.from_decks

    def factory(first, *args, **kwargs):
        assert not (first and first[0].get('object') == 'card' and first[0].get('name') == 'Grizzly Bears')
        return previous_factory(first, *args, **kwargs)

    with monkeypatch.context() as patch:
        if case == 'altered-row': patch.setitem(row, 'oracle_text', row['oracle_text'] + '\nProtocol specimen.')
        if case == 'replaced-row': patch.setitem(subject.CARDS, name, deepcopy(row))
        if case == 'alternate-table': patch.setattr(subject, 'CARDS', dict(subject.CARDS))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        flag = False if case == 'default' else 1 if case == 'truthy-not-bool' else True
        kwargs = {'full_printing': flag} if 'full_printing' in inspect.signature(subject.add).parameters else {}
        before_rng, before_id = state.rng.getstate(), state.next_object_id
        cid = subject.add(state, name, 1, Zone.HAND, owner=2, **kwargs)
        card = state.cards[cid]
        assert card.name == name and card.oracle_text == subject.CARDS[name]['oracle_text']
        assert card.owner == 2 and card.controller == 1 and card.zone == Zone.HAND
        assert state.players[1].hand[-1] == cid and state.next_object_id == before_id + 1
        assert state.rng.getstate() == before_rng and card.layout == ''
        assert card.printed_power is None and card.printed_toughness is None


@pytest.mark.parametrize('field', ['name', 'oracle_text'])
def test_altered_atraxa_declared_source_retains_legacy_birth(monkeypatch, field):
    subject = importlib.import_module(MODULES['atraxa'])
    previous_seed, previous_world, previous_factory = subject.seed_card_payload, subject.controlled_basic_game, MatchFactory.from_decks
    worlds, declared = [], []

    def world(*args, **kwargs):
        state = previous_world(*args, **kwargs)
        worlds.append(state)
        return state

    def seed(name):
        if name == 'Atraxa, Grand Unifier':
            value = deepcopy(previous_seed(name))
            value[field] += ' Protocol specimen'
            declared.append(value)
            return value
        card = worlds[0].cards['atraxa']
        assert card.name == declared[0]['name'] and card.oracle_text == declared[0]['oracle_text']
        assert card.layout == '' and card.power is None and card.colors is None
        raise BeforeScene

    def factory(first, *args, **kwargs):
        assert not (first and first[0].get('object') == 'card' and first[0].get('name') == 'Atraxa, Grand Unifier')
        return previous_factory(first, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(subject, 'controlled_basic_game', world)
        patch.setattr(subject, 'seed_card_payload', seed)
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        with pytest.raises(BeforeScene):
            subject._atraxa_state()


@pytest.mark.parametrize('name', ['Goblin Piledriver', 'Goblin War Marshal', 'Lightning Bolt'])
def test_other_library_loop_branches_are_unchanged_not_canonicalized(monkeypatch, name):
    subject = importlib.import_module(MODULES['guide'])
    previous_factory = MatchFactory.from_decks

    def factory(first, *args, **kwargs):
        assert not (first and first[0].get('object') == 'card' and first[0].get('name') == name)
        return previous_factory(first, *args, **kwargs)

    def consume(state, *_args, **_kwargs):
        card = state.cards['card-' + name.lower().replace(' ', '-')]
        assert card.name == name and card.owner == card.controller == 1 and card.zone == Zone.LIBRARY
        assert card.types == ['Creature'] and card.type_line == '' and card.oracle_text == ''
        assert card.mana_cost == '' and card.colors is None and card.keywords == []
        assert card.power is None and card.toughness is None and card.layout == ''
        raise BeforeScene

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
        patch.setattr(subject, 'resolve_effect', consume)
        with pytest.raises(BeforeScene):
            subject.test_search_library_returns_all_matching_cards()
