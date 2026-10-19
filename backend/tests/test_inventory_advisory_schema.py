"""Advisory field qualification; row projections are not SQL/source authority.

Canonical RAWs and the existing snapshot serializer/validator are reused. No
permission is supplied by knowledge_snapshot; genuine permission fields remain
separate vetoes. Hidden advisory carriers are not inspected as public facts.
"""
from copy import deepcopy
from dataclasses import field, make_dataclass
import json
from types import SimpleNamespace

import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from knowledge.profiles import _hash, derive_profile, merge_profile_payload
from knowledge.service import copy_snapshot, snapshot_for, tags_for
from rules_engine import graveyard_inventory as inventory
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_numeric_inventory_adapter import positive, pure_inventory


def public_grave(state, seat):
    return state.cards[state.players[3 - seat].graveyard[0]]


def qualified(card):
    raw = RAW[card.name]
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
        profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, derive_profile(raw))))
    hydrated = {key: getattr(card, key) for key in ('oracle_text', 'type_line', 'mana_cost', 'layout', 'card_faces')}
    snapshot = snapshot_for(row, card.name, hydrated)
    assert snapshot and copy_snapshot(snapshot, semantic=True) == snapshot
    return snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('carrier', ['empty', 'validated'])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_reviewed_advisory_field_preserves_actual_public_inventory(seat, carrier, roundtrip):
    state = positive(seat)
    card = public_grave(state, seat)
    if carrier == 'validated':
        card.knowledge_snapshot = qualified(card)
        assert tags_for(card).source == 'persisted'
    original = serialize_match_snapshot(state)
    if roundtrip:
        state = deserialize_match_snapshot(deepcopy(original))
        assert serialize_match_snapshot(state) == original
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    projected, _ = decision_view(state, seat, [])
    assert pure_inventory(projected, seat) == expected
    assert 'knowledge_snapshot' not in json.dumps(serialize_match(state, look_players=[seat]))
    assert serialize_match_snapshot(state) == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['wrong-type', 'unknown-schema', 'bad-digest', 'forged-semantics'])
def test_unreviewed_public_advisory_carrier_is_unknown_without_mutation(seat, fault):
    state = positive(seat)
    card = public_grave(state, seat)
    if fault == 'wrong-type':
        card.knowledge_snapshot = []
    elif fault == 'unknown-schema':
        card.knowledge_snapshot = {'future_permission': []}
    else:
        card.knowledge_snapshot = qualified(card)
        if fault == 'bad-digest':
            card.knowledge_snapshot['snapshot_sha256'] = '0' * 64
        else:
            card.knowledge_snapshot['root']['tags'] = ['counter_spell']
            card.knowledge_snapshot['snapshot_sha256'] = _hash({
                key: value for key, value in card.knowledge_snapshot.items() if key != 'snapshot_sha256'})
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_advisory_changes_never_create_public_receipts(seat):
    state = positive(seat)
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    changed = deepcopy(state)
    hidden = changed.cards[changed.players[3 - seat].library[0]]
    hidden.name = 'Opaque identity protocol fault'
    hidden.knowledge_snapshot = {'private_future': 'not public permission'}
    projected, _ = decision_view(changed, seat, [])
    assert pure_inventory(projected, seat) == expected
    assert hidden.id not in {r['reference']['id'] for r in expected['receipts']}
    assert 'private_future' not in json.dumps(serialize_match(projected, look_players=[seat]))


@pytest.mark.parametrize('seat', [1, 2])
def test_valid_advice_does_not_cover_actual_graveyard_permission(seat):
    state = positive(seat)
    card = public_grave(state, seat)
    card.knowledge_snapshot = qualified(card)
    assert pure_inventory(state, seat)['status'] == 'inert'
    card.granted_flashback = {'turn': state.turn, 'zone_sequence': card.zone_change_sequence}
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['runtime', 'declared'])
def test_unreviewed_future_card_field_stays_unknown(seat, kind, monkeypatch):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    if kind == 'runtime':
        public_grave(state, seat).future_permission = []
    else:
        real_fields = inventory.fields
        extra = make_dataclass('FutureField', [('future_permission', list, field(default_factory=list))])
        monkeypatch.setattr(inventory, 'fields', lambda cls:
            real_fields(cls) + real_fields(extra) if cls is CardInstance else real_fields(cls))
    assert pure_inventory(state, seat)['status'] == 'unknown'
