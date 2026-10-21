"""Real public native components, not played games or learned-prior evidence.

Complete pinned RAW is projected before Factory capture. Floating mana and
opening zones are controlled poses; costs, announcements, activation markers
and spell copies must all be produced by the actual checked engine boundary.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from ai.action_contract import complete_action
from analytics.decision_quality import build_trace_payload
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from scripts.regression_matrix_replay import contextual_trace


FIXTURES = Path(__file__).parent / 'fixtures'
PINS = {
    'knowledge_profiles/seed155-scryfall.jsonl':
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
    'knowledge_profiles/PROVENANCE.json':
        'f15047f1ecb06fdaa985a58537d01b6497683637d7caf88db518dea469fc1ca2',
    'canonical_hydration/valki-scryfall-raw.json':
        'ae2bb42378419e9b961eff2f27c7a4c2b7b4ec4af0b72dc3ce7bf4b8a7f87f86',
    'canonical_hydration/PROVENANCE.json':
        '22e0bf7a5c287f4c0e803513cd8c7a7f77bc41d6810eeca156e5dc582a9d04ac',
    'cast_alias_publication_549/steel-seraph.raw.json':
        '72eab5073b2ae6ae683cfd7c6d3cb8d052b69577184ec5086518f58acc8047f7',
    'cast_alias_publication_549/PROVENANCE.json':
        'f9fce5dd4f1474b72bb91ffcb8774fe468dba33962c599b874b9e19734884917',
    'mana_canonical_76/official-bulk13.jsonl':
        'd2dd8459b2d07db047372eb7493cc7e40f243d40b7e8901b4b70a3e8c39624de',
    'mana_canonical_76/PROVENANCE.json':
        '74a347ae0ab1ff7a1876c9a31a2c7543d222fb6dc7af516827dfb9962e63537a',
    'multicast_audit/canonical.jsonl':
        '684a4f7215a8d3020a3d8993b2c9a37eff851860e5650c9307af905307735d99',
    'multicast_audit/provenance.json':
        '7b9ebcfa65028bb5f152b033366447f337f82f65c302a9a44a834067d3d96a40',
}
CONTEXT = {1: 'Control', 2: 'Aggro'}
DELVER = 'Delver of Secrets // Insectile Aberration'
KUMANO = 'Kumano Faces Kakkazan // Etching of Kumano'
ADVENTURE = 'Bonecrusher Giant // Stomp'
MDFC = 'Valki, God of Lies // Tibalt, Cosmic Impostor'


def _pinned(relative):
    body = (FIXTURES / relative).read_bytes()
    assert hashlib.sha256(body).hexdigest() == PINS[relative]
    return body


def _raw(name):
    if name in {'Steel Seraph', MDFC}:
        relative = ('cast_alias_publication_549/steel-seraph.raw.json'
                    if name == 'Steel Seraph' else 'canonical_hydration/valki-scryfall-raw.json')
        raw = json.loads(_pinned(relative))
        if name == 'Steel Seraph':
            proof = json.loads(_pinned('cast_alias_publication_549/PROVENANCE.json'))
            assert proof['raw_file_sha256'] == PINS[relative]
            assert (raw['id'], raw['oracle_id']) == (proof['id'], proof['oracle_id'])
        else:
            proof = json.loads(_pinned('canonical_hydration/PROVENANCE.json'))
            row = next(row for row in proof['records'] if row['canonical_parent'] == name)
            assert row['sha256'] == PINS[relative] and row['http_status'] == 200
            assert (raw['id'], raw['oracle_id']) == (row['scryfall_id'], row['oracle_id'])
    else:
        relative = ('mana_canonical_76/official-bulk13.jsonl' if name == 'Mind Stone'
                    else 'multicast_audit/canonical.jsonl' if name == 'Reverberate'
                    else 'knowledge_profiles/seed155-scryfall.jsonl')
        raw = next(row for row in map(json.loads, _pinned(relative).splitlines())
                   if row['name'] == name)
        if name == 'Mind Stone':
            proof = json.loads(_pinned('mana_canonical_76/PROVENANCE.json'))
            source = proof['objects'][name]
            assert proof['source_files'][source['file']] == PINS[relative]
            assert (raw['id'], raw['oracle_id']) == (source['id'], source['oracle_id'])
            assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=False).encode()).hexdigest() == source['object_sha256']
        elif name == 'Reverberate':
            proof = json.loads(_pinned('multicast_audit/provenance.json'))
            assert proof['fixture_sha256'] == PINS[relative]
            row = next(row for row in proof['rows'] if row['name'] == name)
            assert (raw['id'], raw['oracle_id']) == (row['id'], row['oracle_id'])
        else:
            proof = json.loads(_pinned('knowledge_profiles/PROVENANCE.json'))
            assert proof['snapshot_sha256'] == PINS[relative]
    assert raw['object'] == 'card' and raw['name'] == name
    assert type(raw['id']) is str and type(raw['oracle_id']) is str
    return raw


def _entry(raw, quantity):
    before = deepcopy(raw)
    rules = ScryfallSyncService._canonical_rule_projection(raw, physical_front=True)
    faces = json.loads(rules.pop('card_faces_json'))
    front = raw['card_faces'][0] if raw.get('card_faces') else raw
    row = {**deepcopy(raw), **rules, 'card_name': raw['name'], 'quantity': quantity,
           'card_faces': faces, 'colors': deepcopy(front.get('colors')),
           'image_uri': ScryfallSyncService._extract_remote_image_uri(raw)}
    assert raw == before
    for key in ('oracle_text', 'mana_cost', 'type_line'):
        assert row[key] == (front.get(key) or '')
    assert row['layout'] == raw['layout']
    for supplied, projected in zip(raw.get('card_faces') or [], faces):
        for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors'):
            if key in supplied:
                assert projected[key] == supplied[key]
    return row


def _position(seat, names, pool, *, battlefield=()):
    raws = {name: _raw(name) for name in ('Forest', *names)}
    deck = [_entry(raws['Forest'], 24), *(_entry(raws[name], 1) for name in names)]
    source_deck = deepcopy(deck)
    state = MatchFactory.from_decks(deepcopy(deck), deepcopy(deck), seed=731,
                                    game_id='task33-native-style-public')
    assert deck == source_deck
    stock, starting = deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    physical = {cid: deepcopy(card.characteristic_record['physical'])
                for cid, card in state.cards.items()}
    rng = state.rng.getstate()
    selected = {}
    for name in names:
        cid = next(cid for cid, row in stock['inventory'].items()
                   if row['owner'] == seat and row['stock_key'] == name)
        card = state.cards[cid]
        zone = Zone.BATTLEFIELD if name in battlefield else Zone.HAND
        getattr(state.players[seat], card.zone.value).remove(cid)
        card.move_to_zone(zone)
        getattr(state.players[seat], zone.value).append(cid)
        selected[name] = cid
        front = raws[name]['card_faces'][0] if raws[name].get('card_faces') else raws[name]
        assert card.owner == card.controller == seat and card.zone == zone
        assert card.oracle_text == front['oracle_text']
        assert card.mana_cost == front['mana_cost'] and card.type_line == front['type_line']
        assert card.colors == front.get('colors') and card.layout == raws[name]['layout']
        assert len(card.card_faces) == len(raws[name].get('card_faces') or [])
        assert card.image_uri == ScryfallSyncService._extract_remote_image_uri(raws[name])
        for supplied, born in zip(raws[name].get('card_faces') or [], card.card_faces):
            for field in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors'):
                if field in supplied:
                    assert born[field] == supplied[field]
        for field in ('power', 'toughness', 'loyalty'):
            value = front.get(field)
            assert getattr(card, field) == (int(value) if value is not None else None)
        assert stock['inventory'][cid] == {'owner': seat, 'stock_key': name}
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = {1, 2}
    state.players[seat].mana_pool = deepcopy(pool)
    assert state.sideboard_facts == stock and state.starting_decks == starting
    assert {cid: card.characteristic_record['physical'] for cid, card in state.cards.items()} == physical
    assert state.rng.getstate() == rng
    return state, selected, raws


def _native_step(state, seat, intent, index=0):
    root = deepcopy(serialize_match_snapshot(state))
    rng, original_intent = state.rng.getstate(), deepcopy(intent)
    engine = RulesEngine()
    action = complete_action(intent)
    before_action = deepcopy(action)
    legal = engine.legal_moves(state, seat)
    assert serialize_match_snapshot(state) == root
    if action['type'] in {'cast_spell', 'activate_ability'}:
        assert any(move['type'] == action['type'] and move.get('card_id') == action['card_id']
                   for move in legal)
    trace = contextual_trace(build_trace_payload, CONTEXT)
    raw = trace(state, seat, legal, action, 'public native component control')
    original_raw, original_legal = deepcopy(raw), deepcopy(legal)
    assert raw['action']['type'] == action['type']
    assert raw['hand'] == sorted(state.cards[cid].name for cid in state.players[seat].hand)
    assert raw['opp_hand'] == sorted(state.cards[cid].name for cid in state.players[3-seat].hand)
    bound = trace.bind_native_action(raw, state, seat, action, index)
    candidate = checked_action(state, engine, seat, action)
    native = deepcopy(serialize_match_snapshot(candidate))
    final = trace.confirm_native_action(bound, raw, state, candidate, seat, action)
    assert serialize_match_snapshot(state) == root and state.rng.getstate() == rng
    assert serialize_match_snapshot(candidate) == native
    assert intent == original_intent and action == before_action
    assert raw == original_raw and legal == original_legal
    return candidate, raw, bound, final, action


def _unchanged_payload(raw, final, state, seat, index, *, announcement=None):
    expected = deepcopy(raw)
    expected.update(pid=seat, action_index=index, player_name=state.players[seat].name,
                    opponent_archetype=CONTEXT[seat].lower())
    if announcement is not None:
        expected['action']['card_name'] = announcement
    assert final == expected


CASTS = [
    pytest.param(DELVER, None, {'U': 1}, None, id='delver-default-front'),
    pytest.param(KUMANO, None, {'R': 1}, None, id='kumano-default-front'),
    pytest.param(DELVER, 0, {'U': 1}, None, id='delver-explicit-front'),
    pytest.param(KUMANO, 0, {'R': 1}, None, id='kumano-explicit-front'),
    pytest.param(ADVENTURE, 1, {'C': 1, 'R': 1}, None, id='selected-adventure-stomp'),
    pytest.param(MDFC, 1, {'C': 5, 'B': 1, 'R': 1}, None, id='selected-mdfc-tibalt'),
    pytest.param('Steel Seraph', None, {'C': 6}, None, id='prototype-card-base'),
    pytest.param('Steel Seraph', None, {'C': 1, 'W': 2}, 'prototype', id='selected-prototype'),
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,face,pool,cost', CASTS)
def test_real_native_cast_styles_retain_builder_and_confirmed_context(seat, name, face, pool, cost):
    root, ids, raws = _position(seat, [name], pool)
    cid, raw_card = ids[name], raws[name]
    assert root.cards[cid].selected_face_index is None
    intent = {'type': 'cast_spell', 'card_id': cid}
    if face is not None:
        intent['selected_face_index'] = face
    if name == ADVENTURE:
        intent['targets'] = {'target_player': 3-seat}
    if cost is not None:
        move = next(move for move in RulesEngine().legal_moves(root, seat)
                    if move['type'] == 'cast_spell' and move.get('card_id') == cid)
        option = next(option for option in move['cost_options'] if option['id'] == cost)
        assert option['mana_cost'] == '{1}{W}{W}'
        intent['cost_choice'] = {'id': option['id']}
    before = root.spells_cast_this_turn[seat]
    candidate, raw, bound, final, action = _native_step(root, seat, intent)
    items = [item for item in candidate.stack if item.id not in {old.id for old in root.stack}]
    assert len(items) == 1
    item = items[0]
    surface = raw_card['card_faces'][face or 0] if raw_card.get('card_faces') else raw_card
    card = candidate.cards[cid]
    assert item.source_card_id == cid and item.controller == seat and item.label == surface['name']
    assert item.payload['__announced_stack_kind'] == 'spell'
    assert not item.payload.get('__stack_copy_kind') and not item.payload.get('__trigger_event')
    assert candidate.spells_cast_this_turn[seat] == before + 1
    assert candidate.spells_cast_this_turn[3-seat] == root.spells_cast_this_turn[3-seat]
    assert card.zone == Zone.STACK and cid not in candidate.players[seat].hand
    assert card.oracle_text == surface['oracle_text'] and card.type_line == surface['type_line']
    assert card.characteristic_record['physical'] == root.cards[cid].characteristic_record['physical']
    assert candidate.starting_decks == root.starting_decks
    assert candidate.sideboard_facts['inventory'] == root.sideboard_facts['inventory']
    assert item.payload['mana_spent'] == sum(pool.values())
    assert not any(candidate.players[seat].mana_pool.values())
    if cost == 'prototype':
        reduced = re.search(r'Prototype ((?:\{[^}]+\})+) [\u2014-] (\d+)/(\d+)', raw_card['oracle_text'])
        assert reduced and (card.mana_cost, card.power, card.toughness, card.colors) == (
            reduced[1], int(reduced[2]), int(reduced[3]), ['W'])
        assert card.characteristic_record['values']['power'] == int(reduced[2])
    else:
        assert card.mana_cost == surface['mana_cost'] and card.colors == surface.get('colors')
    if face is None:
        assert 'selected_face_index' not in action
        assert 'selected_face_index' not in raw['action']
    else:
        assert action['selected_face_index'] == raw['action']['selected_face_index'] == face
    assert 'card_name' not in raw['action']
    _unchanged_payload(raw, final, root, seat, 0, announcement=item.label)
    assert bound['action'].get('selected_face_index') == raw['action'].get('selected_face_index')


@pytest.mark.parametrize('seat', [1, 2])
def test_real_nonmana_sacrifice_completion_qualifies_actual_ability(seat):
    root, ids, _ = _position(seat, ['Mind Stone'], {'C': 1}, battlefield=('Mind Stone',))
    cid = ids['Mind Stone']
    move = next(move for move in RulesEngine().legal_moves(root, seat)
                if move['type'] == 'activate_ability' and move.get('card_id') == cid)
    candidate, raw, _, final, _ = _native_step(root, seat, {
        'type': 'activate_ability', 'card_id': cid, 'ability_index': move['ability_index']})
    assert len(candidate.stack) == 1
    item = candidate.stack[0]
    assert item.source_card_id == cid and item.controller == seat
    assert item.label == 'Mind Stone ability' and item.effect_key == 'draw_cards'
    assert item.payload['__announced_stack_kind'] == 'activated'
    assert item.payload['__completed_nonmana_activation'] is True
    assert item.payload['__activation_source_origin'] == Zone.BATTLEFIELD.value
    assert item.payload['__activation_source_reference'] == {
        'incarnation': object_incarnation(root.cards[cid]),
        'zone_change_sequence': root.cards[cid].zone_change_sequence}
    assert candidate.cards[cid].zone == Zone.GRAVEYARD and cid in candidate.players[seat].graveyard
    assert cid not in candidate.players[seat].battlefield
    assert not root.cards[cid].tapped and root.cards[cid].zone == Zone.BATTLEFIELD
    assert not any(candidate.players[seat].mana_pool.values())
    assert candidate.spells_cast_this_turn == root.spells_cast_this_turn
    assert candidate.cards[cid].characteristic_record['physical'] == root.cards[cid].characteristic_record['physical']
    _unchanged_payload(raw, final, root, seat, 0, announcement=item.label)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_reverberate_copy_is_not_a_third_cast_or_activation_credit(seat):
    root, ids, _ = _position(seat, ['Lightning Bolt', 'Reverberate'], {'R': 3})
    state, raw, _, final, _ = _native_step(root, seat, {
        'type': 'cast_spell', 'card_id': ids['Lightning Bolt'],
        'targets': {'target_player': 3-seat}})
    original = state.stack[-1]
    _unchanged_payload(raw, final, root, seat, 0, announcement=original.label)
    state, raw, _, final, _ = _native_step(state, seat, {
        'type': 'cast_spell', 'card_id': ids['Reverberate'],
        'targets': {'target_stack_id': original.id}}, 1)
    assert state.stack[-1].effect_key == 'copy_spell'
    _unchanged_payload(raw, final, state, seat, 1, announcement='Reverberate')
    paid_counts = deepcopy(state.spells_cast_this_turn)
    assert state.spells_cast_this_turn[seat] == root.spells_cast_this_turn[seat] + 2
    assert not any(state.players[seat].mana_pool.values())
    rows = []
    for index in range(2, 14):
        copies = [item for item in state.stack if item.payload.get('__stack_copy_kind') == 'spell']
        if copies and not state.pending_mechanic_choice:
            break
        previous = state
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['kind'] == 'copy_target' and 'keep' in pending['options']
            actor, intent = pending['player_id'], {'type': 'choose_mechanic', 'card_ids': ['keep']}
        else:
            actor, intent = state.priority_player, {'type': 'pass_priority'}
        state, raw, _, final, action = _native_step(state, actor, intent, index)
        assert action['type'] not in {'cast_spell', 'activate_ability'}
        assert 'card_name' not in final['action']
        _unchanged_payload(raw, final, previous, actor, index)
        assert state.spells_cast_this_turn == previous.spells_cast_this_turn
        rows.append(final)
    else:
        pytest.fail('Actual checked Reverberate continuation did not produce a spell copy')
    assert rows and len(copies) == 1
    copy = copies[0]
    assert copy.id != original.id and copy.controller == seat
    assert copy.label == original.label + ' (copy)'
    assert copy.source_card_id == original.source_card_id
    assert copy.payload['__copied_from_stack_id'] == original.id
    assert copy.payload['__announced_stack_kind'] == 'spell'
    assert copy.payload['__stack_copy_kind'] == 'spell'
    assert copy.payload['__copied_card']['oracle_text'] == _raw('Lightning Bolt')['oracle_text']
    assert any(item.id == original.id for item in state.stack)
    assert state.spells_cast_this_turn == paid_counts
    assert not any(row['action']['type'] in {'cast_spell', 'activate_ability'} for row in rows)
    assert state.players[3-seat].life == root.players[3-seat].life
    assert root.spells_cast_this_turn[seat] == 0
