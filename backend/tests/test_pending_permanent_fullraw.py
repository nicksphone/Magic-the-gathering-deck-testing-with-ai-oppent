"""Real before-birth cases for hosted CI. Not locally qualified by inert checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchState, PlayerState, Zone
from tests import pending_permanent_fullraw as fullraw
from tests import test_pending_removal as pending
from tests import test_permanent_spell_context as permanent


RAW_SHA = 'bbc868c335b6f5bc7e5a02f5aafe92bf16e25ede7652a0f2e7d5ae5428c5048a'
FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*FIELDS, 'card_faces', 'layout', 'selected_face_index', 'image_uri')
CASES = (
    ('pending', 'Sprite Dragon', ('Creature',), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Go for the Throat', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Fatal Push', ('Instant',), Zone.HAND, 2, None),
    ('pending', 'Mind Stone', ('Artifact',), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Naturalize', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Phyrexian Arena', ('Enchantment',), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Counterspell', ('Instant',), Zone.HAND, 2, None),
    ('pending', 'Lightning Bolt', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Giant Growth', ('Instant',), Zone.HAND, 2, None),
    ('pending', 'Darksteel Myr', ('Creature', 'Artifact'), Zone.BATTLEFIELD, 1, None),
    ('pending', 'Darksteel Colossus', ('Creature', 'Artifact'), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Doom Blade', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Abrade', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Thrashing Brontodon', ('Creature',), Zone.BATTLEFIELD, 1, None),
    ('pending', 'Slice in Twain', ('Instant',), Zone.HAND, 1, None),
    ('pending', 'Bastion of Remembrance', ('Enchantment',), Zone.BATTLEFIELD, 1, None),
    ('pending', 'Blood Artist', ('Creature',), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Leyline of the Void', ('Enchantment',), Zone.BATTLEFIELD, 2, None),
    ('pending', 'Murder', ('Instant',), Zone.HAND, 1, None),
    ('permanent', 'Prodigal Pyromancer', ('Creature',), Zone.HAND, 1, ()),
    ('permanent', 'Wall of Omens', ('Creature',), Zone.HAND, 1, ('defender',)),
    ('permanent', 'Soul Warden', ('Creature',), Zone.HAND, 1, ()),
    ('permanent', 'Curiosity', ('Enchantment',), Zone.HAND, 1, ()),
    ('permanent', "Smuggler's Copter", ('Artifact',), Zone.BATTLEFIELD, 2, ('flying',)),
    ('permanent', 'Reclamation Sage', ('Creature',), Zone.HAND, 2, ()),
    ('permanent', 'Sol Ring', ('Artifact',), Zone.BATTLEFIELD, 2, ()),
    ('permanent', 'Ulamog, the Infinite Gyre', ('Creature',), Zone.HAND, 1, ('indestructible',)),
    ('permanent', 'Monastery Swiftspear', ('Creature',), Zone.BATTLEFIELD, 1, ('haste',)),
    ('permanent', 'Lightning Bolt', ('Instant',), Zone.HAND, 1, ()),
)


def _raw(name):
    body = (Path(__file__).parent / 'fixtures/pending_permanent_fullraw/canonical.jsonl').read_bytes()
    assert hashlib.sha256(body).hexdigest() == RAW_SHA
    rows = [json.loads(line) for line in body.splitlines()]
    assert len(rows) == 28 and len({row['name'] for row in rows}) == 28
    return next(row for row in rows if row['name'] == name)


def _game():
    return MatchState(id='task13-before-birth', players={
        seat: PlayerState(id=seat, name=f'Seat {seat}') for seat in (1, 2)
    }, cards={}, stack=[], rng=random.Random(711))


def _table(family):
    return pending.CARDS if family == 'pending' else permanent.DATA


def _old_row(family, name):
    if family == 'permanent':
        return deepcopy(permanent.DATA[name])
    rows = {}
    for filename in ('pending_removal.json', 'ineffective_destruction.json', 'self_removal.json'):
        body = (Path(__file__).parent / 'fixtures' / filename).read_text()
        rows.update({row['name']: row for row in json.loads(body)})
    return deepcopy(rows[name])


def _call(family, game, name, zone, seat):
    if family == 'pending':
        return pending.add_card(game, name, zone, seat)
    return permanent.card(game, name, zone, seat)


def _strict(actual, expected):
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _strict(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            _strict(left, right)
    else:
        assert actual == expected


@pytest.mark.parametrize('family,name,types,zone,seat,keywords', CASES,
                         ids=[family + ':' + name for family, name, *_ in CASES])
def test_complete_raw_and_printed_facts_precede_genuine_birth(
        family, name, types, zone, seat, keywords, monkeypatch):
    raw = _raw(name)
    expected = {key: deepcopy(raw.get(key)) for key in (
        'name', 'mana_cost', 'type_line', 'oracle_text', 'layout', 'colors')}
    expected.update(types=list(types), power=int(raw['power']) if raw.get('power') is not None else None,
                    toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'), loyalty=None,
                    keywords=deepcopy(raw['keywords']) if family == 'pending' else list(keywords),
                    card_faces=[], selected_face_index=None, image_uri=None)
    events, normalized, births = [], [], []
    native_normalize = ScryfallSyncService._normalize_payload
    native_birth = CardInstance.__post_init__

    def observe_normalize(cls, incoming, image_uri, rulings=None):
        normalized.append(deepcopy(incoming))
        events.append('normalize')
        assert image_uri, 'No placeholder art writes'
        return native_normalize.__func__(cls, incoming, image_uri, rulings)

    def observe_birth(obj):
        births.append((obj, {field: deepcopy(getattr(obj, field)) for field in PHYSICAL}))
        events.append('birth')
        assert obj.characteristic_record is None
        return native_birth(obj)

    monkeypatch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalize))
    monkeypatch.setattr(CardInstance, '__post_init__', observe_birth)
    # Imported callers register these genuine prints using their unchanged autouse tables.
    monkeypatch.setitem(_table(family), name, _old_row(family, name))
    table_before = deepcopy(_table(family))
    game = _game()
    root_rng = game.rng
    rng, process_rng = game.rng.getstate(), random.getstate()
    root = {key: deepcopy(value) for key, value in vars(game).items()
            if key not in {'rng', 'cards', 'players'}}
    players = {key: deepcopy(vars(value)) for key, value in game.players.items()}
    obj = _call(family, game, name, zone, seat)
    assert type(obj) is CardInstance
    assert events == ['normalize', 'birth'] and normalized == [raw]
    assert len(births) == 1 and births[0][0] is obj
    _strict(births[0][1], expected)
    _strict({field: getattr(obj, field) for field in PHYSICAL}, expected)
    _strict(obj.characteristic_record, {
        'version': 1, 'physical': expected, 'values': {field: expected[field] for field in FIELDS},
    })
    assert obj.id == (name + '-0' if family == 'pending' else name)
    _strict((obj.owner, obj.controller, obj.zone), (seat, seat, zone))
    assert game.cards == {obj.id: obj} and game.cards[obj.id] is obj
    players[seat][zone.value].append(obj.id)
    assert {key: vars(value) for key, value in game.players.items()} == players
    assert {key: value for key, value in vars(game).items()
            if key not in {'rng', 'cards', 'players'}} == root
    assert game.rng is root_rng and game.rng.getstate() == rng and random.getstate() == process_rng
    assert obj.summoning_sick is True and obj.tapped is False
    assert (obj.instance_order, obj.static_order, obj.effect_timestamp, obj.zone_change_sequence) == (0, 0, 0, 0)
    assert obj.counters == {} and obj.keyword_effects == [] and obj.printed_characteristics == {}
    obj.keywords.append('fixture-mutation')
    obj.colors.append('fixture-mutation')
    obj.card_faces.append({'fixture-mutation': True})
    assert _table(family) == table_before and _raw(name) == raw


def test_pending_catalog_lists_are_independent_without_lowercasing():
    game = _game()
    original = deepcopy(pending.CARDS['Sprite Dragon'])
    first = pending.add_card(game, 'Sprite Dragon', Zone.BATTLEFIELD, 2)
    second = pending.add_card(game, 'Sprite Dragon', Zone.BATTLEFIELD, 2)
    assert (first.id, second.id) == ('Sprite Dragon-0', 'Sprite Dragon-1')
    assert game.cards[first.id] is first and game.cards[second.id] is second
    assert first.keywords == second.keywords == ['Flying', 'Haste']
    assert 'haste' not in first.keywords
    assert first.keywords is not second.keywords
    assert first.colors is not second.colors and first.card_faces is not second.card_faces
    first.keywords.append('haste')
    first.colors.clear()
    assert second.keywords == ['Flying', 'Haste'] and second.colors == ['R', 'U']
    assert pending.CARDS['Sprite Dragon'] == original


@pytest.mark.parametrize('family', ('pending', 'permanent'))
def test_original_catalog_admission_is_still_required(family, monkeypatch):
    name = 'Sprite Dragon' if family == 'pending' else 'Prodigal Pyromancer'
    monkeypatch.delitem(_table(family), name)
    with pytest.raises(KeyError):
        _call(family, _game(), name, Zone.HAND, 1)


@pytest.mark.parametrize('family', ('pending', 'permanent'))
def test_same_name_protocol_override_is_not_canonicalized(family, monkeypatch):
    name = 'Sprite Dragon' if family == 'pending' else 'Prodigal Pyromancer'
    row = _old_row(family, name)
    row['oracle_text'] = 'Protocol-only altered Oracle, not a canonical positive.'
    monkeypatch.setitem(_table(family), name, row)

    def no_normalizer(*args, **kwargs):
        raise AssertionError('A protocol override must not be normalized as canonical')

    monkeypatch.setattr(ScryfallSyncService, '_normalize_payload', no_normalizer)
    obj = _call(family, _game(), name, Zone.HAND, 1)
    assert obj.oracle_text == row['oracle_text'] and obj.printed_power is None and obj.layout == ''


@pytest.mark.parametrize('family', ('pending', 'permanent'))
def test_unknown_fixture_extension_retains_old_partial_projection(family, monkeypatch):
    name = 'fixture-only-extension'
    row = deepcopy(pending.CARDS['Sprite Dragon'])
    monkeypatch.setitem(_table(family), name, row)

    def no_canonical_guess(*args, **kwargs):
        raise AssertionError('Unknown extension must not acquire canonical facts')

    module = pending if family == 'pending' else permanent
    monkeypatch.setattr(module, 'printed_kwargs', no_canonical_guess)
    obj = _call(family, _game(), name, Zone.HAND, 2)
    assert obj.name == name and obj.oracle_text == row['oracle_text']
    assert obj.printed_power is None and obj.printed_toughness is None and obj.layout == ''
    if family == 'pending':
        assert obj.keywords is row['keywords'] and obj.colors is row['colors']
    else:
        assert obj.keywords == [] and obj.colors is None
