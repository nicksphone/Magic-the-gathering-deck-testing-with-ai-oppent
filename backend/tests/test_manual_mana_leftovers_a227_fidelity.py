"""Unexecuted PREP: real inline consumers, native token births, full card RAW."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai import sideboard_facts
from card_data.token_definitions import named_artifact_token
from effects import handlers
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands, nonland_mana_outputs
from tests import test_manual_mana_tap as original


BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / 'tests/fixtures/manual_mana_leftovers_a227'
SOURCE_SHA = '2605e1204bf1b414d98799f0f9eaac73a10ffd41c13f116217513250e36f1cdf'
NAMES = ('Treasure', 'Llanowar Elves')
SCENES = ('treasure_pool', 'treasure_flexible', 'mana_creature')


def official(name):
    wire = (DATA / 'SOURCES.json').read_bytes()
    assert hashlib.sha256(wire).hexdigest() == SOURCE_SHA
    sources = json.loads(wire)
    assert hashlib.sha256((BACKEND / sources['provenance_file']).read_bytes()).hexdigest() == sources['provenance_sha256']
    row = sources['objects'][name]
    body = (BACKEND / row['file']).read_bytes()
    assert len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256']
    raw = json.loads(body)
    assert raw['object'] == 'card' and raw['name'] == name and len(raw) == row['fields']
    assert raw['id'] == row['id'] and raw['oracle_id'] == row['oracle_id']
    assert {'uri', 'image_uris', 'legalities', 'colors', 'keywords'} <= raw.keys()
    return raw


def expected(name):
    raw = official(name)
    token = raw['layout'] == 'token'
    assert raw['layout'] in ('normal', 'token') and not raw.get('card_faces')
    head = raw['type_line'].partition(' \u2014 ')[0].split()
    kinds = [word for word in head if word in {'Artifact', 'Creature', 'Land'}]
    assert kinds and raw['keywords'] == []
    values = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text')}
    values.update(types=kinds, keywords=[], colors=raw['colors'], loyalty=None)
    for key in ('power', 'toughness'):
        text = raw.get(key)
        assert text is None or type(text) is str and text.isdecimal()
        values[key] = None if text is None else int(text)
        values['printed_' + key] = text
    # Token is the native instance marker, not a copiable card type.
    physical = {**deepcopy(values), 'types': [*kinds, *(['Token'] if token else [])],
                'card_faces': [], 'layout': raw['layout'], 'selected_face_index': None,
                'image_uri': raw['image_uris']['normal']}
    return values, physical, token


def assert_complete(card, name):
    values, physical, token = expected(name)
    record = card.characteristic_record
    assert type(record) is dict and set(record) == {'version', 'physical', 'values'}
    assert type(record['version']) is int and record['version'] == 1
    assert set(record['physical']) == set(physical) and set(record['values']) == set(values)
    for actual, wanted in ((vars(card), physical), (record['physical'], physical),
                           (record['values'], values)):
        for key, value in wanted.items():
            assert type(actual[key]) is type(value), key
            assert actual[key] == value, key
    assert card.is_token is token


def native_state(owner=1, creature=False):
    raw_forest = official('Forest')
    forest = {**raw_forest, 'card_name': 'Forest', 'quantity': 60,
              'image_uri': raw_forest['image_uris']['normal']}
    decks = [deepcopy([forest]), deepcopy([forest])]
    if creature:
        elf = official('Llanowar Elves')
        decks[owner-1] = [{**elf, 'card_name': elf['name'], 'quantity': 1,
                           'image_uri': elf['image_uris']['normal']},
                          {**forest, 'quantity': 59}]
    state = MatchFactory.from_decks(*decks, seed=8)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = owner
    return state


def native_treasure(owner=1):
    state = native_state(owner)
    raw = official('Treasure')
    seed = named_artifact_token('Treasure')
    assert seed['scryfall_id'] == raw['id']
    assert {key: seed[key] for key in ('name', 'type_line', 'oracle_text')} == {
        key: raw[key] for key in ('name', 'type_line', 'oracle_text')}
    payload = {**seed, 'amount': 1, 'types': ['Artifact', 'Token'],
               'power': None, 'toughness': None, 'printed_power': None,
               'printed_toughness': None, 'mana_cost': raw['mana_cost'],
               'keywords': raw['keywords'], 'colors': raw['colors'],
               'layout': raw['layout'], 'card_faces': [],
               'image_uri': raw['image_uris']['normal']}
    before_ids = set(state.cards)
    stock = deepcopy(state.sideboard_facts['inventory'])
    # This is the real primitive, including its own entry continuation/events.
    handlers.create_token(state, owner, payload)
    added = set(state.cards)-before_ids
    assert len(added) == 1 and state.sideboard_facts['inventory'] == stock
    return state, added.pop()


def native_elf(owner=1):
    state = native_state(owner, creature=True)
    cid = next(cid for cid, card in state.cards.items()
               if card.owner == owner and card.name == 'Llanowar Elves')
    card = state.cards[cid]
    for field in ('hand', 'library'):
        if cid in getattr(state.players[owner], field):
            getattr(state.players[owner], field).remove(cid)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[owner].battlefield.append(cid)
    return state, cid


def invoke(scene):
    return {
        'treasure_pool': original.test_manual_treasure_mana_sacrifices_token_and_persists_pool,
        'treasure_flexible': original.test_one_flexible_source_cannot_pay_two_distinct_colored_pips,
        'mana_creature': original.test_manual_creature_mana_requires_ready_source_and_valid_color,
    }[scene]()


class ConsumerReached(BaseException):
    """Stop only the observer probe before its real consumer, not a game result."""


def capture(scene):
    seen = {'births': [], 'token_calls': []}
    initialize, create = sideboard_facts.initialize, handlers.create_token
    depth = 0

    def birth(state, inventory):
        result = initialize(state, inventory)
        seen['births'].append(deepcopy(state))
        return result

    def token(state, owner, payload):
        nonlocal depth
        outer = depth == 0
        before = set(state.cards)
        depth += 1
        try:
            result = create(state, owner, payload)
        finally:
            depth -= 1
        if outer:
            seen['token_calls'].append({'owner': owner, 'before_ids': before,
                                       'added_ids': set(state.cards)-before})
        return result

    def observe(state, *args, **kwargs):
        if scene == 'treasure_pool':
            cid = args[0]
        elif scene == 'mana_creature':
            cid = args[2]['card_id']
        else:
            assert len(state.players[1].battlefield) == 1
            cid = state.players[1].battlefield[0]
        seen.update(state=state, cid=cid)
        raise ConsumerReached

    symbol = {'treasure_pool': 'serialize_card_view',
              'treasure_flexible': 'can_pay_with_pool_and_lands',
              'mana_creature': 'checked_action'}[scene]
    with patch.object(sideboard_facts, 'initialize', birth), \
            patch.object(handlers, 'create_token', token), patch.object(original, symbol, observe):
        with pytest.raises(ConsumerReached):
            invoke(scene)
    assert 'state' in seen
    return seen


@pytest.mark.parametrize('name', ['Forest', 'Treasure', 'Llanowar Elves'])
def test_complete_RAW_is_pinned_and_reader_results_are_independent(name):
    first, second = official(name), official(name)
    first['legalities'].clear()
    assert second == official(name)


def test_native_Treasure_seed_agrees_with_full_response_not_projection_only():
    sources = json.loads((DATA / 'SOURCES.json').read_bytes())
    wire = (BACKEND / sources['native_seed_file']).read_bytes()
    assert hashlib.sha256(wire).hexdigest() == sources['native_seed_sha256']
    seed, raw = named_artifact_token('Treasure'), official('Treasure')
    assert seed['scryfall_id'] == raw['id']
    for key in ('name', 'type_line', 'oracle_text'):
        assert seed[key] == raw[key]


@pytest.mark.parametrize('owner', [1, 2])
def test_native_Treasure_allocates_new_object_without_consuming_original_stock(owner):
    state, cid = native_treasure(owner)
    assert_complete(state.cards[cid], 'Treasure')
    assert state.cards[cid].owner == state.cards[cid].controller == owner
    assert state.cards[cid].zone == Zone.BATTLEFIELD and len(state.cards) == 121
    assert cid not in state.sideboard_facts['inventory']
    assert len(state.sideboard_facts['inventory']) == 120
    for player in state.players.values():
        assert len(player.hand) == 7 and len(player.library) == 53


@pytest.mark.parametrize('owner', [1, 2])
def test_native_Elves_birth_has_full_traits_and_retained_stock_binding(owner):
    state, cid = native_elf(owner)
    assert_complete(state.cards[cid], 'Llanowar Elves')
    assert state.cards[cid].owner == state.cards[cid].controller == owner
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert len(state.cards) == len(state.sideboard_facts['inventory']) == 120
    assert state.sideboard_facts['inventory'][cid] == {
        'owner': owner, 'stock_key': 'Llanowar Elves'}


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('field', ['types', 'keywords', 'printed_power'])
def test_independent_RAW_oracle_rejects_coherent_three_slot_corruption(name, field):
    state, cid = native_treasure() if name == 'Treasure' else native_elf()
    card = state.cards[cid]
    assert_complete(card, name)
    bad = {'types': ['Battle'], 'keywords': ['flying'], 'printed_power': '99'}[field]
    setattr(card, field, deepcopy(bad))
    for record in (card.characteristic_record['physical'], card.characteristic_record['values']):
        record[field] = deepcopy(bad)
    before = deepcopy(vars(card))
    with pytest.raises(AssertionError, match=field):
        assert_complete(card, name)
    assert vars(card) == before


@pytest.mark.parametrize('scene', SCENES)
def test_actual_original_inline_first_consumer_receives_complete_canonical_source(scene):
    observed = capture(scene)
    name = 'Llanowar Elves' if scene == 'mana_creature' else 'Treasure'
    assert_complete(observed['state'].cards[observed['cid']], name)


@pytest.mark.parametrize('scene', SCENES)
def test_actual_original_inline_has_normal_birth_or_native_token_not_retagged_Forest(scene):
    observed = capture(scene)
    assert len(observed['births']) == 1
    birth, state, cid = observed['births'][0], observed['state'], observed['cid']
    assert birth.sideboard_facts['capture_version'] == 3
    assert birth.sideboard_facts['coverage_ok'] is True
    assert len(birth.sideboard_facts['inventory']) == 120
    if scene == 'mana_creature':
        assert_complete(birth.cards[cid], 'Llanowar Elves')
        assert birth.sideboard_facts['inventory'][cid] == {
            'owner': 1, 'stock_key': 'Llanowar Elves'}
        assert not observed['token_calls']
    else:
        assert len(observed['token_calls']) == 1
        call = observed['token_calls'][0]
        assert call['owner'] == 1 and call['added_ids'] == {cid}
        assert cid not in birth.cards and cid not in birth.sideboard_facts['inventory']
        assert set(state.cards) == set(birth.cards) | {cid}
        for player in state.players.values():
            assert len(player.hand) == 7 and len(player.library) == 53
    for owner in (1, 2):
        stock = Counter(row['stock_key'] for row in birth.sideboard_facts['inventory'].values()
                        if row['owner'] == owner)
        assert stock == Counter({row['card_name']: sum(item['quantity'] for item in state.starting_decks[owner]
                               if item['card_name'] == row['card_name'])
                                for row in state.starting_decks[owner]})
        assert sum(stock.values()) == 60


def test_original_entire_generic_creature_contract_executes_with_real_Elves():
    real, seen = original.checked_action, []

    def forward(state, engine, actor, action):
        card = state.cards[action['card_id']]
        assert_complete(card, 'Llanowar Elves')
        row = (actor, action['color'], card.summoning_sick)
        try:
            result = real(state, engine, actor, action)
        except ActionRejected:
            seen.append((*row, 'rejected'))
            raise
        seen.append((*row, 'accepted'))
        assert state.players[1].mana_pool['G'] == 0 and not card.tapped
        assert result.players[1].mana_pool['G'] == 1 and result.cards[card.id].tapped
        return result

    with patch.object(original, 'checked_action', forward):
        invoke('mana_creature')
    assert seen == [(1, 'G', True, 'rejected'), (1, 'U', False, 'rejected'),
                    (2, 'G', False, 'rejected'), (1, 'G', False, 'accepted')]


@pytest.mark.parametrize('scene', ['treasure_pool', 'treasure_flexible'])
def test_original_Treasure_outcomes_use_real_commands_and_complete_source(scene):
    symbol = 'checked_action' if scene == 'treasure_pool' else 'auto_pay_cost'
    real, seen = getattr(original, symbol), []

    def forward(state, *args, **kwargs):
        cid = next(cid for cid in state.players[1].battlefield if state.cards[cid].name == 'Treasure')
        assert_complete(state.cards[cid], 'Treasure')
        result = real(state, *args, **kwargs)
        seen.append(cid)
        return result

    with patch.object(original, symbol, forward):
        invoke(scene)
    assert len(seen) == 1


@pytest.mark.parametrize('owner', [1, 2])
def test_native_Treasure_sacrifice_pool_and_original_root_are_preserved(owner):
    state, cid = native_treasure(owner)
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), owner,
                            {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'U'})
    assert result.players[owner].mana_pool['U'] == 1
    assert result.cards[cid].zone == Zone.CEASED
    assert cid not in result.players[owner].battlefield
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('owner', [1, 2])
def test_native_single_Treasure_is_not_two_colored_payments(owner):
    state, cid = native_treasure(owner)
    before = serialize_match_snapshot(state)
    assert not can_pay_with_pool_and_lands(state, owner, '{R}{G}')
    assert not auto_pay_cost(state, owner, '{R}{G}')
    assert serialize_match_snapshot(state) == before
    assert can_pay_with_pool_and_lands(state, owner, '{R}')


@pytest.mark.parametrize('owner', [1, 2])
def test_real_Elves_preserves_all_generic_readiness_color_actor_and_pool_checks(owner):
    state, cid = native_elf(owner)
    card = state.cards[cid]
    card.summoning_sick = True
    action = {'type': 'tap_nonland_for_mana', 'card_id': cid, 'color': 'G'}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), owner, action)
    assert serialize_match_snapshot(state) == before
    card.summoning_sick = False
    for actor, color in ((owner, 'U'), (3-owner, 'G')):
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), actor, {**action, 'color': color})
        assert serialize_match_snapshot(state) == before
    assert nonland_mana_outputs(state, cid, card) == {'G': 1}
    result = checked_action(state, RulesEngine(), owner, action)
    assert result.players[owner].mana_pool['G'] == 1 and result.cards[cid].tapped
    assert state.players[owner].mana_pool['G'] == 0 and not card.tapped


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('owner', [1, 2])
def test_native_snapshot_keeps_full_facts_and_stock_tamper_fails_without_root_change(name, owner):
    state, cid = native_treasure(owner) if name == 'Treasure' else native_elf(owner)
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert serialize_match_snapshot(restored) == before
    assert_complete(restored.cards[cid], name)
    bad = deepcopy(state)
    stock_cid = next(iter(bad.sideboard_facts['inventory']))
    bad.cards[stock_cid].name = 'Noncard corrupted stock'
    with pytest.raises(ValueError, match='Sideboard stock'):
        serialize_match_snapshot(bad)
    assert serialize_match_snapshot(state) == before
