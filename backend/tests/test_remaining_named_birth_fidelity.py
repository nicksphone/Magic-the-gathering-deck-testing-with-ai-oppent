"""Tests-first real caller observations; no fixture or engine implementation.

These are declared cases, not an executed acceptance result. Complete source
RAW, projected cache rules, native characteristics, and display pose are separate.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from tests import test_foretell as foretell
from tests import test_modal_spell_faces as modal
from tests import test_ward_resolution as ward
from tests.browser_positive83_canonical import raw_card


CASES = ('modal-archaic', 'ward-trespasser', 'foretell-behold')
NAMES = {
    'modal-archaic': 'Wandering Archaic // Explore the Vastlands',
    'ward-trespasser': 'Graveyard Trespasser // Graveyard Glutton',
    'foretell-behold': 'Behold the Multiverse',
}
LOCAL_RAW = {
    'ward-trespasser': (0, 'daa2a273-488f-4285-a069-ad159ad2d393', 62,
                      '77c9fd283e58c6650278be652c07941bf4a81f257bc3bd68cb430c0c4634d4e9'),
    'foretell-behold': (1, '27855a38-a682-4f97-ad22-ac625e86faec', 67,
                       'f8eecc1825a7f51ad8bfc43a23bea8b9c4697e70cb026f6666e147dd62641646'),
}
RAW_SHA = 'f51e63c91d84cf830281c0db0d1e7a0d4ef7379616475084611fbc0ac5190bec'
COPIABLE = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
            'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
            'keywords', 'colors')
PHYSICAL = (*COPIABLE, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def _raw(case):
    if case == 'modal-archaic':
        return raw_card(NAMES[case])
    body = (Path(__file__).parent / 'fixtures/remaining_named3/canonical.jsonl').read_bytes()
    assert hashlib.sha256(body).hexdigest() == RAW_SHA
    rows = body.splitlines()
    assert len(rows) == 2
    index, printing, fields, digest = LOCAL_RAW[case]
    raw = json.loads(rows[index])
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == digest
    assert (raw['object'], raw['name'], raw['id'], len(raw)) == ('card', NAMES[case], printing, fields)
    return raw


def _strict(actual, expected, field):
    assert type(actual) is type(expected), field + ': type'
    if type(expected) is dict:
        assert actual.keys() == expected.keys(), field + ': keys'
        for key in expected:
            _strict(actual[key], expected[key], field + '.' + key)
    elif type(expected) is list:
        assert len(actual) == len(expected), field + ': length'
        for index, (left, right) in enumerate(zip(actual, expected)):
            _strict(left, right, field + '[' + str(index) + ']')
    else:
        assert actual == expected, field


def _birth(case, seat, monkeypatch):
    module, source_name = {
        'modal-archaic': (modal, modal.ARCHAIC),
        'ward-trespasser': (ward, 'Graveyard Trespasser'),
        'foretell-behold': (foretell, 'Behold the Multiverse'),
    }[case]
    table = modal.DATA if case == 'modal-archaic' else module.CARDS
    admitted, births, projections = [deepcopy(table[source_name])], [], []
    target_names = (NAMES[case], NAMES[case].split(' // ')[0])
    events = []
    receipt = {'normalizer': None, 'rules': None, 'birth_entries': [], 'consumer': None}
    native_normalize = ScryfallSyncService._normalize_payload
    native_rules = ScryfallSyncService._canonical_rule_projection
    native_post_init = CardInstance.__post_init__

    def observe_normalize(cls, raw, image_uri, rulings=None):
        observed = None
        # Select by target name BEFORE validating object, ID or completeness.
        if (receipt['normalizer'] is None and isinstance(raw, dict)
                and raw.get('name') in target_names):
            observed = {'input_ref': raw, 'raw': deepcopy(raw), 'entered': len(events)}
            receipt['normalizer'] = observed
            events.append('normalize-enter')
        result = native_normalize.__func__(cls, raw, image_uri, rulings)
        if observed is not None:
            observed.update(output=result, output_snapshot=deepcopy(result), returned=len(events))
            events.append('normalize-return')
        return result

    def observe_rules(cls, raw, cached=None, *, physical_front=False):
        observed = None
        if (receipt['rules'] is None and isinstance(raw, dict)
                and raw.get('name') in target_names):
            observed = {'input_ref': raw, 'entered': len(events)}
            receipt['rules'] = observed
            events.append('rules-enter')
        result = native_rules.__func__(cls, raw, cached, physical_front=physical_front)
        if observed is not None:
            observed.update(output=result, returned=len(events))
            events.append('rules-return')
        return result

    monkeypatch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalize))
    monkeypatch.setattr(ScryfallSyncService, '_canonical_rule_projection', classmethod(observe_rules))

    def observe_birth(card):
        supplied = {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
        if card.name in target_names:
            receipt['birth_entries'].append({
                'card': card, 'entered': len(events), 'oracle_ref': card.oracle_text,
            })
            events.append('birth-enter')
        result = native_post_init(card)
        births.append((card, supplied))
        return result

    monkeypatch.setattr(CardInstance, '__post_init__', observe_birth)
    if case == 'modal-archaic':
        native_hydrate = modal.hydrate_deck_cards

        def observe_hydrate(repo, rows):
            cache = repo.get_cached_cards_by_names([modal.ARCHAIC])
            row = cache[modal.ARCHAIC.lower()]
            supplied = deepcopy(vars(row))
            receipt['consumer'] = {
                'cache_ref': row, 'faces_ref': row.card_faces_json,
                'values': deepcopy(vars(row)), 'entered': len(events),
            }
            events.append('hydrate-enter')
            supplied['card_faces'] = json.loads(supplied.pop('card_faces_json'))
            projections.append(supplied)
            return native_hydrate(repo, rows)

        monkeypatch.setattr(modal, 'hydrate_deck_cards', observe_hydrate)
        state, _ = modal.fixture(modal.ARCHAIC)
        card = state.cards[state.players[seat].hand[0]]
        assert len(state.cards) == 120
        assert len(state.players[seat].hand) == 7
        assert len(state.players[seat].library) == 53
        assert sum(row['quantity'] for row in state.starting_decks[seat]) == 60
    else:
        module, alias = (ward, 'add_card') if case == 'ward-trespasser' else (foretell, 'raw_add')
        native_add = getattr(module, alias)

        def observe_add(state, name, player=1, zone=Zone.BATTLEFIELD, *, cards):
            supplied = deepcopy(cards[name])
            ids, rng = set(state.cards), state.rng.getstate()
            stock, decks = deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
            card = native_add(state, name, player, zone, cards=cards)
            projections.append(supplied)
            assert set(state.cards) == ids | {card.id}
            assert state.rng.getstate() == rng
            assert state.sideboard_facts == stock and state.starting_decks == decks
            _strict(cards[name], supplied, 'caller table remains unmodified')
            return card

        monkeypatch.setattr(module, alias, observe_add)
        if case == 'ward-trespasser':
            state = ward.clean(seat)
            card = ward.add(state, 'Graveyard Trespasser', seat, Zone.HAND)
        else:
            state, cid = foretell.setup('Behold the Multiverse', seat)
            card = state.cards[cid]
            assert state.players[seat].mana_pool == {'C': 2}
    assert len(admitted) == 1
    assert len(projections) == 1
    _strict(table[source_name], admitted[0], 'source table remains unmodified')
    own_births = [supplied for born, supplied in births if born is card]
    assert len(own_births) == 1, 'The observed caller must execute the genuine native constructor'
    assert state.cards[card.id] is card
    assert (card.owner, card.controller, card.zone) == (seat, seat, Zone.HAND)
    assert state.players[seat].hand.count(card.id) == 1
    return state, card, receipt, own_births[0], projections[0]


def _modal_faces(raw, supplied_faces):
    assert type(supplied_faces) is list
    assert all(type(face) is dict for face in supplied_faces)
    assert len(supplied_faces) == len(raw['card_faces'])
    fields = ('name', 'mana_cost', 'type_line', 'oracle_text', 'power',
              'toughness', 'loyalty', 'colors')
    # Art and opaque cache extensions retain their supplied pose; every rules
    # operand, including explicit absent-stat nulls, comes from independent RAW.
    return [{**deepcopy(supplied), **{key: deepcopy(face.get(key)) for key in fields}}
            for supplied, face in zip(supplied_faces, raw['card_faces'])]


def _assert_modal_cache(raw, supplied):
    front = raw['card_faces'][0]
    expected = {
        'scryfall_id': raw['id'], 'name': raw['name'], 'layout': raw['layout'],
        **{key: raw.get(key) or front.get(key) or ''
           for key in ('oracle_text', 'mana_cost', 'type_line')},
        **{key: raw.get(key) or front.get(key) for key in ('power', 'toughness')},
        'loyalty': raw.get('loyalty') if raw.get('loyalty') is not None else front.get('loyalty'),
        'colors': ','.join(raw.get('colors') or front.get('colors', [])),
    }
    for key, value in expected.items():
        _strict(supplied[key], value, 'modal cache.' + key)
    _strict(supplied['card_faces'], _modal_faces(raw, supplied['card_faces']),
            'modal cache face rules')


def _facts(raw, image_uri, supplied_keywords):
    front = raw['card_faces'][0] if raw.get('card_faces') else raw
    kinds = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    return {
        **{key: front[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text')},
        'types': [word for word in front['type_line'].split('\u2014')[0].split() if word in kinds],
        'power': int(front['power']) if front.get('power') is not None else None,
        'toughness': int(front['toughness']) if front.get('toughness') is not None else None,
        'printed_power': front.get('power'), 'printed_toughness': front.get('toughness'),
        'loyalty': int(front['loyalty']) if front.get('loyalty') is not None else None,
        # Scryfall mechanic tags and native runtime keyword flags have different
        # domains. Admission checks the former; birth/record/reload retain the
        # exact genuine constructor flags, without inventing mechanic support.
        'keywords': deepcopy(supplied_keywords), 'colors': deepcopy(front['colors']),
        'layout': raw['layout'], 'card_faces': deepcopy(raw.get('card_faces', [])),
        'selected_face_index': None, 'image_uri': image_uri,
    }


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('seat', (1, 2))
def test_original_named_caller_admits_full_pinned_source_before_native_birth(case, seat, monkeypatch):
    raw = _raw(case)
    _, _, receipt, _, projection = _birth(case, seat, monkeypatch)
    normalization = receipt['normalizer']
    assert normalization is not None, case + ': original caller never admits target RAW'
    assert 'returned' in normalization, case + ': target normalization did not complete'
    assert receipt['birth_entries'], case + ': target native constructor was not entered'
    first_birth = receipt['birth_entries'][0]
    assert normalization['returned'] < first_birth['entered']
    supplied = normalization['raw']
    assert raw.keys() <= supplied.keys(), case + ': source table drops complete RAW fields'
    for key, value in raw.items():
        if key == 'name' and case == 'ward-trespasser':
            assert type(supplied[key]) is str
            assert supplied[key] in (raw['name'], raw['card_faces'][0]['name'])
        else:
            _strict(supplied[key], value, case + ' admitted RAW.' + key)
    _strict(supplied, raw, case + ' complete pinned parent RAW')
    _strict(normalization['input_ref'], supplied, case + ' RAW remains unmodified')
    if case == 'modal-archaic':
        consumer = receipt['consumer']
        assert consumer is not None
        assert normalization['returned'] < consumer['entered'] < first_birth['entered']
        output = normalization['output']
        assert consumer['cache_ref'].card_faces_json is consumer['faces_ref']
        assert consumer['faces_ref'] is output['card_faces_json']
        _strict({key: consumer['values'][key] for key in output},
                normalization['output_snapshot'], case + ' actual normalized cache fields')
        _assert_modal_cache(raw, projection)
    else:
        rules = receipt['rules']
        assert rules is not None, case + ': missing RAW-linked rules projection'
        assert 'returned' in rules
        assert rules['input_ref'] is normalization['input_ref']
        assert (rules['entered'] < normalization['entered'] < normalization['returned']
                < rules['returned'] < first_birth['entered'])
        assert rules['output']['oracle_text'] is first_birth['oracle_ref']


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('seat', (1, 2))
def test_original_named_caller_retains_native_front_parent_and_snapshot(case, seat, monkeypatch):
    raw = _raw(case)
    state, card, _, supplied_birth, projection = _birth(case, seat, monkeypatch)
    assert type(supplied_birth['keywords']) is list
    assert all(type(keyword) is str for keyword in supplied_birth['keywords'])
    facts = _facts(raw, card.image_uri, supplied_birth['keywords'])
    if case == 'modal-archaic':
        facts['card_faces'] = _modal_faces(raw, projection['card_faces'])
    # Factory completes DFC front selection after __post_init__; its final
    # physical record is authoritative. Direct add has no later face projection.
    if case != 'modal-archaic':
        _strict(supplied_birth, facts, case + ' constructor inputs')
    _strict({key: getattr(card, key) for key in PHYSICAL}, facts, case + ' native front')
    record = {'version': 1, 'physical': facts,
              'values': {key: facts[key] for key in COPIABLE}}
    _strict(card.characteristic_record, record, case + ' retained parent/front')
    before = deepcopy(serialize_match_snapshot(state))
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    _strict(restored.cards[card.id].characteristic_record, record, case + ' restored record')
    _strict({key: getattr(restored.cards[card.id], key) for key in PHYSICAL}, facts,
            case + ' restored native front')
    assert serialize_match_snapshot(restored) == before
