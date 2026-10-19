"""Desired fixture-source fidelity, not HTTP/browser or stock qualification.

STATIC PREP: all22 full RAW objects are pinned; no tests have been run.
No server module is imported; tests execute its exact selected branch with
real constructors/rules and a capture-only publisher when separately granted.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone


ROOT = Path(__file__).resolve().parents[2]
SUBJECT = Path(__file__).with_name('browser_fixture_server.py')
SOURCES = Path(__file__).parent / 'fixtures/browser_positive83/SOURCES.json'
SOURCES_SHA = 'cb515e9c199a4dba208e3a9c22af8bec840dcc265aeffe9b453706d39d56f994'
BRANCHES = {
    'attacking_token_target': ['Adeline, Resplendent Cathar', 'Grizzly Bears',
                               'Teferi, Hero of Dominaria', 'Island'],
    'modal_copy_target': ["Kolaghan's Command", 'Sol Ring', 'Grizzly Bears', 'Island'],
    'divided_copy_target': ['Pyrotechnics', 'Grizzly Bears', 'Island'],
    'copy_target': ['Lightning Bolt', 'Island'],
    'phyrexian_ability': ['Pestilent Souleater', 'Island'],
    'variable_life_x': ['Toxic Deluge', 'Giant Spider', 'Grizzly Bears', 'Island'],
    'draw_cap': ['Spirit of the Labyrinth', 'Divination', 'Island'],
    'nonland_mana': ['Llanowar Elves', 'Sol Ring', 'Gilded Lotus', 'Island'],
    'draw_replacement': ['Thought Reflection', 'Stinkweed Imp', 'Island'],
    'company': ['Collected Company', 'Grizzly Bears', 'Llanowar Elves',
                'Island', 'Plains', 'Swamp', 'Mountain', 'Forest'],
}
NAMES = sorted({name for names in BRANCHES.values() for name in names})
FIELDS = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'keywords', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'colors', 'layout', 'card_faces')
COPIABLE_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
                   'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
                   'keywords', 'colors')


def _raw(name):
    data = SOURCES.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    proof = json.loads(data)
    assert name not in proof['missing_full_RAW'], 'Missing approved full RAW: ' + name
    record = proof['cards'][name]
    path = ROOT / record['path']
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    location = list(record['location'])
    if location and location[0] == 'line':
        value = json.loads(data.splitlines()[location[1] - 1])
        location = location[2:]
    else:
        value = json.loads(data)
    for key in location:
        value = value[key]
    assert value['object'] == 'card' and value['name'] == name
    assert value['id'] == record['id'] and value['oracle_id'] == record['oracle_id']
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    assert hashlib.sha256(encoded.encode()).hexdigest() == record['object_sha256']
    assert len(value) == record['fields']
    return value


def _facts(card):
    return {key: deepcopy(getattr(card, key)) for key in FIELDS}


def _expected_native_keywords(raw):
    """Bounded RAW annotation + whole-declaration oracle, NOT production inference.

    These22 pinned objects have only Flying/Reach/Vigilance in the native
    baseline list. Stinkweed's Dredge and Mill annotations describe other
    mechanics, not CardInstance.keywords. Unknown annotations fail closed.
    In particular a colon/gains clause is not an innate keyword declaration.
    """
    annotations = raw['keywords']
    assert type(annotations) is list and all(type(word) is str for word in annotations)
    assert len(annotations) == len(set(annotations))
    native = {'Flying', 'Reach', 'Vigilance'}
    non_list = {'Dredge', 'Mill'}
    assert set(annotations) <= native | non_list, 'Unreviewed RAW keyword annotation'
    declarations = [line.split(' (', 1)[0].strip().rstrip('.')
                    for line in raw.get('oracle_text', '').splitlines()]
    result = []
    for word in annotations:
        if word in non_list:
            assert word.lower() in raw['oracle_text'].lower()
            continue
        assert word in declarations, 'RAW keyword is not a standalone printed declaration'
        result.append(word.lower())
    return result


def _assert_birth_facts(facts, raw):
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'layout'):
        assert facts[key] == raw.get(key, '')
    assert facts['colors'] == raw.get('colors', [])
    assert facts['card_faces'] == raw.get('card_faces', [])
    types = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    assert facts['types'] == [word for word in raw['type_line'].split('\u2014')[0].split()
                              if word in types]
    assert facts['keywords'] == _expected_native_keywords(raw), 'Printed keywords changed'
    for key in ('power', 'toughness'):
        printed = raw.get(key)
        assert facts['printed_' + key] == printed
        assert facts[key] == (int(printed) if printed is not None
                              and str(printed).lstrip('+-').isdigit() else None)
    loyalty = raw.get('loyalty')
    assert facts['loyalty'] == (int(loyalty) if loyalty is not None else None)


def _assert_copiable_values(values, raw):
    # Independent expected values come from complete RAW, never from the
    # producer/helper/live card or production copiable-value accessor.
    assert type(values) is dict and set(values) == set(COPIABLE_FIELDS)
    expected = {key: raw.get(key, '') for key in ('name', 'mana_cost', 'type_line', 'oracle_text')}
    native_types = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
                    'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    expected['types'] = [word for word in raw['type_line'].split('\u2014')[0].split()
                         if word in native_types]
    for key in ('power', 'toughness'):
        printed = raw.get(key)
        expected['printed_' + key] = printed
        expected[key] = (int(printed) if printed is not None
                         and str(printed).lstrip('+-').isdigit() else None)
    expected['loyalty'] = int(raw['loyalty']) if raw.get('loyalty') is not None else None
    expected['colors'] = raw.get('colors', [])
    expected['keywords'] = _expected_native_keywords(raw)
    for key in COPIABLE_FIELDS:
        assert values[key] == expected[key], 'Copiable value changed: ' + key


def _assert_native_card_fidelity(card, captured_birth, raw):
    _assert_birth_facts(captured_birth, raw)
    record = card.characteristic_record
    assert type(record) is dict and set(record) == {'version', 'physical', 'values'}
    assert type(record['version']) is int and record['version'] == 1
    _assert_birth_facts(record['physical'], raw)
    _assert_copiable_values(record['values'], raw)
    # Current power/toughness/loyalty may be legitimate scene poses. Temporary
    # keyword grants live in keyword_effects, not these retained print fields.
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'layout',
                'printed_power', 'printed_toughness', 'colors', 'card_faces', 'keywords'):
        assert getattr(card, key) == captured_birth[key], 'Live printed field changed: ' + key


@pytest.mark.parametrize('name', NAMES)
def test_complete_existing_source_is_fresh_and_identity_bound(name):
    first = _raw(name)
    second = _raw(name)
    assert first == second and first is not second
    first['oracle_text'] = 'EXPLICIT CORRUPTED COPY; never a card or producer input'
    assert _raw(name) == second


@pytest.mark.parametrize('face_kind', list(BRANCHES))
def test_actual_producer_branch_has_full_facts_at_birth_and_first_consumer(face_kind, monkeypatch):
    wanted = {name: _raw(name) for name in BRANCHES[face_kind]}
    tree = ast.parse(SUBJECT.read_text())
    original = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'fixture')
    branch = next(node for node in original.body if isinstance(node, ast.If)
                  and ast.dump(node.test) == ast.dump(ast.parse(
                      'face_kind == ' + repr(face_kind), mode='eval').body))
    fragment = deepcopy(original)
    fragment.decorator_list = []
    fragment.body = [deepcopy(branch)]
    births = []
    published = []
    original_post_init = CardInstance.__post_init__

    def observe_birth(card):
        # Observe actual constructor operands BEFORE native printed capture.
        facts = _facts(card)
        original_post_init(card)
        births.append((card, facts))

    def verify(state):
        for name, raw in wanted.items():
            cards = [card for card in state.cards.values() if card.name == name]
            assert cards, 'No actual producer card for ' + name
            for card in cards:
                captured = [facts for born, facts in births if born is card]
                assert len(captured) == 1, 'Card lacks its actual native birth observation'
                _assert_native_card_fidelity(card, captured[0], raw)

    def observe_consumer(function):
        def call(state, *args, **kwargs):
            # Ignore unrelated native materializer queries. The Company branch's
            # first consumer is the actual explicitly named spell, not a helper.
            if face_kind != 'company' or (args and getattr(args[0], 'id', None) == 'company'):
                verify(state)
            return function(state, *args, **kwargs)
        return call

    def publish(state, deck, **kwargs):
        verify(state)
        assert kwargs.get('capture_original_stock', True) is True
        assert state.sideboard_facts, 'Canonical fixtures must not erase original stock'
        for card_id, binding in state.sideboard_facts['inventory'].items():
            assert state.cards[card_id].printed_characteristics.get(
                'name', state.cards[card_id].name) == binding['stock_key']
        if face_kind == 'company':
            assert kwargs['mainboards'] == state.starting_decks
            assert kwargs['mainboards'][1] != kwargs['mainboards'][2]
            assert all(sum(row['quantity'] for row in rows) == 60
                       for rows in kwargs['mainboards'].values())
        published.append((state, deepcopy(deck)))
        return state

    # Real handlers are always called after the observation; no fake engine,
    # Main module replacement, SQL, TestClient or publish/API acceptance claim.
    from effects import handlers, registry
    from rules_engine import ability_model, combat
    with monkeypatch.context() as observing:
        observing.setattr(CardInstance, '__post_init__', observe_birth)
        consumers = {
            'attacking_token_target': (combat, 'declare_attackers'),
            'modal_copy_target': (handlers, 'copy_spell'),
            'divided_copy_target': (handlers, 'copy_spell'),
            'copy_target': (handlers, 'copy_spell'),
            'draw_replacement': (registry, 'resolve_effect'),
            'company': (ability_model, 'build_ability_spec'),
        }
        selected = [consumers[face_kind]] if face_kind in consumers else []
        for module, name in selected:
            observing.setattr(module, name, observe_consumer(getattr(module, name)))
        namespace = {'CardInstance': CardInstance, 'MatchFactory': MatchFactory,
                     'StackItem': StackItem, 'Step': Step, 'Zone': Zone,
                     'Path': Path, '__file__': str(SUBJECT), 'publish': publish}
        exec(compile(ast.Module(body=[fragment], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
        result = namespace['fixture'](face_kind=face_kind)
    assert len(published) == 1 and published[0][0] is result


def test_company_native_birth_slots_stock_rng_and_both_mainboards(monkeypatch):
    """Execute the exact branch, observing TRUE Factory inputs before its call."""
    import random
    from collections import Counter

    tree = ast.parse(SUBJECT.read_text())
    original = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'fixture')
    branch = next(node for node in original.body if isinstance(node, ast.If)
                  and ast.dump(node.test) == ast.dump(ast.parse(
                      "face_kind == 'company'", mode='eval').body))
    fragment = deepcopy(original)
    fragment.decorator_list = []
    fragment.body = [deepcopy(branch)]
    factory = MatchFactory.from_decks
    observed = []
    published = []

    def observe_factory(deck_a, deck_b, *args, **kwargs):
        state = factory(deck_a, deck_b, *args, **kwargs)
        # Ignore the separate eight-card Factory template for the standalone spell.
        if len(state.cards) == 120:
            assert kwargs == {'seed': 34} and args == ()
            assert state.starting_decks == {1: deck_a, 2: deck_b}
            assert [len(state.players[p].hand) for p in (1, 2)] == [7, 7]
            assert [len(state.players[p].library) for p in (1, 2)] == [53, 53]
            assert set(state.cards) == {f'p{p}-{n:03d}' for p in (1, 2)
                                        for n in range(1, 61)}
            expected = ['Grizzly Bears', 'Llanowar Elves', 'Island',
                        'Plains', 'Swamp', 'Mountain']
            assert [state.cards[cid].name for cid in state.players[2].library[-6:]] == expected
            # Independent raw facts at actual birth, not the producer helper's output.
            for card in state.cards.values():
                _assert_native_card_fidelity(card, _facts(card), _raw(card.name))
                assert state.sideboard_facts['inventory'][card.id]['stock_key'] == card.name
            for p, deck in ((1, deck_a), (2, deck_b)):
                assert Counter(card.name for card in state.cards.values() if card.owner == p) == Counter(
                    {name: sum(row['quantity'] for row in deck if row['card_name'] == name)
                     for name in {row['card_name'] for row in deck}})
                assert state.players[p].hand == [f'p{p}-{n:03d}' for n in range(60, 53, -1)]
            rng = random.Random(34)
            rng.shuffle(list(range(60)))
            rng.shuffle(list(range(60)))
            assert state.rng.getstate() == rng.getstate()
            observed.append((state, deepcopy(state.starting_decks),
                             deepcopy(state.sideboard_facts), deck_a, deck_b))
        return state

    def publish(state, deck, **kwargs):
        assert len(observed) == 1 and state is observed[0][0]
        assert len(state.cards) == 121 and state.cards['company'].name == 'Collected Company'
        assert kwargs.get('capture_original_stock', True) is True
        assert kwargs['mainboards'] == observed[0][1] == state.starting_decks
        assert kwargs['mainboards'][1] is observed[0][3]
        assert kwargs['mainboards'][2] is observed[0][4]
        assert state.sideboard_facts == observed[0][2]
        published.append(state)
        return state

    with monkeypatch.context() as observing:
        observing.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        namespace = {'CardInstance': CardInstance, 'MatchFactory': MatchFactory,
                     'StackItem': StackItem, 'Step': Step, 'Zone': Zone,
                     'Path': Path, '__file__': str(SUBJECT), 'publish': publish}
        exec(compile(ast.Module(body=[fragment], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
        result = namespace['fixture'](face_kind='company')
    assert published == [result]


def test_company_publisher_uses_supplied_mainboards_without_changing_default():
    """Static publisher seam; no Main import or HTTP acceptance claim."""
    tree = ast.parse(SUBJECT.read_text())
    publish = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'publish')
    call = next(node for node in ast.walk(publish) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'MatchController')
    value = next(node.value for node in call.keywords if node.arg == 'mainboards')
    expected = ast.parse('{1: deck, 2: deck} if mainboards is None else mainboards', mode='eval').body
    assert ast.dump(value) == ast.dump(expected)
    assert publish.args.kwonlyargs[-1].arg == 'mainboards'
    assert isinstance(publish.args.kw_defaults[-1], ast.Constant)
    assert publish.args.kw_defaults[-1].value is None


@pytest.mark.parametrize('surface', ['live', 'physical', 'values', 'coherent'])
def test_genuine_souleater_rejects_unprinted_flying_on_each_retained_surface(surface):
    """Explicit corruption controls, not altered canonical positive inputs."""
    from tests.browser_positive83_canonical import card as printed_card

    raw = _raw('Pestilent Souleater')
    card = printed_card(raw['name'], id='oracle-souleater', owner=1,
                        controller=1, zone=Zone.BATTLEFIELD)
    captured = _facts(card)
    _assert_native_card_fidelity(card, captured, raw)
    assert _expected_native_keywords(raw) == []
    if surface in {'live', 'coherent'}:
        card.keywords = ['flying']
    if surface in {'physical', 'coherent'}:
        card.characteristic_record['physical']['keywords'] = ['flying']
    if surface in {'values', 'coherent'}:
        card.characteristic_record['values']['keywords'] = ['flying']
    with pytest.raises(AssertionError, match='[Kk]eyword'):
        _assert_native_card_fidelity(card, captured, raw)


@pytest.mark.parametrize('field', list(COPIABLE_FIELDS))
def test_genuine_factory_copy_values_reject_every_corrupted_field(field):
    from tests.browser_positive83_canonical import card as printed_card

    raw = _raw('Pestilent Souleater')
    card = printed_card(raw['name'], id='copy-oracle-souleater', owner=2,
                        controller=2, zone=Zone.BATTLEFIELD)
    captured = _facts(card)
    _assert_native_card_fidelity(card, captured, raw)
    before = deepcopy(card.characteristic_record)
    previous = card.characteristic_record['values'][field]
    if type(previous) is list:
        corrupt = previous + (['flying'] if field == 'keywords' else ['EXPLICIT_CORRUPTION'])
    elif type(previous) is int:
        corrupt = previous + 1
    elif previous is None:
        corrupt = 1
    else:
        corrupt = previous + ' EXPLICIT_CORRUPTION'
    card.characteristic_record['values'][field] = corrupt
    assert card.characteristic_record['physical'] == before['physical']
    assert _facts(card) == captured
    with pytest.raises(AssertionError, match='Copiable value changed: ' + field):
        _assert_native_card_fidelity(card, captured, raw)


@pytest.mark.parametrize('player', [1, 2])
def test_resolved_temporary_infect_grant_is_not_printed_or_copiable_baseline(player):
    """Real resolution-handler control, NOT a paid-activation/HTTP certificate."""
    from effects.handlers import grant_keyword
    from rules_engine.continuous import has_keyword
    from tests.browser_positive83_canonical import card as printed_card, entry

    raw = _raw('Pestilent Souleater')
    assert raw['keywords'] == []
    assert 'gains infect' in raw['oracle_text'].lower()
    deck = [entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=83)
    source = printed_card(raw['name'], id='temporary-infect-source', owner=player,
                          controller=player, zone=Zone.BATTLEFIELD)
    state.cards[source.id] = source
    state.players[player].battlefield.append(source.id)
    captured = _facts(source)
    record = deepcopy(source.characteristic_record)
    _assert_native_card_fidelity(source, captured, raw)
    assert source.keywords == [] and not has_keyword(state, source.id, 'infect')
    grant_keyword(state, player, {'target_card_id': source.id, 'keyword': 'infect',
                                  'until_end_of_turn': True})
    assert has_keyword(state, source.id, 'infect')
    assert source.keywords == [] and source.keyword_effects
    assert source.characteristic_record == record
    _assert_native_card_fidelity(source, captured, raw)
