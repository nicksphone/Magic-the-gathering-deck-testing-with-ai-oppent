"""Canonical estimate transport; inert row lookup, not policy strength or SQL."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from knowledge import service
from knowledge.profiles import _hash, derive_profile, merge_profile_payload, profile_payload
from rules_engine.engine import RulesEngine
from tests.test_ai_knowledge_profile_consumer import RAW, position
from tests import test_ai_knowledge_snapshot_contract as contracts


def api():
    assert callable(getattr(service, 'estimate_for', None)), 'Task2.3 estimate transport/getter absent'
    return service


def sealed(value):
    value['snapshot_sha256'] = _hash({key: item for key, item in value.items() if key != 'snapshot_sha256'})
    return value


def fixture(name='Lightning Bolt'):
    case = contracts.KnowledgeSnapshotContract()
    raw, row, hydrated = case.fixture(name)
    snapshot = api().snapshot_for(row, name, hydrated)
    assert snapshot and 'estimates' in snapshot
    return case.card(raw, hydrated, snapshot), raw, row, hydrated


def selected_fields(profile):
    return {'tier': profile.threat_level,
            'routes': profile_payload(profile)['answer_routes'],
            'limits': sorted(set(profile.limitations) | {'known_gap:' + gap for gap in profile.known_gaps})}


def test_estimate_api_is_present_without_new_agent_weights():
    assert callable(api().estimate_for)


def test_all155_compact_inputs_equal_same_estimator_and_full_raw_is_unchanged():
    import math
    api()
    assert len(RAW) == 155
    original = deepcopy(RAW)
    for name, raw in RAW.items():
        profile = derive_profile(raw)
        row = SimpleNamespace(name=name, scryfall_id=raw['id'], oracle_source='scryfall',
                              profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, profile)))
        surface = raw['card_faces'][0] if raw.get('card_faces') else raw
        hydrated = {'layout': raw['layout'], 'card_faces': deepcopy(raw.get('card_faces', [])),
                    **{key: surface.get(key, '') for key in ('oracle_text', 'type_line', 'mana_cost')}}
        snapshot = service.snapshot_for(row, name, hydrated)
        assert snapshot and 'estimates' in snapshot, name
        namespace = snapshot['estimates']
        assert set(namespace) == {'transport_version', 'root', 'faces', 'context'} and namespace['transport_version'] == 2
        assert type(namespace['context']) is dict and set(namespace['context']) == {
            'mode', 'archetype', 'archetype_verification', 'corpus_fingerprint',
            'curve_nonland_mean', 'deck_analysis_primary_archetype_estimate'}
        assert namespace['context'] == profile.context
        assert len(namespace['faces']) == len(profile.faces)
        for entry, expected in zip([namespace['root'], *namespace['faces']], [profile, *profile.faces]):
            assert set(entry) == {'tier', 'routes', 'limits', 'printed_inputs', 'play_value'}
            assert type(entry['play_value']) is float and math.isfinite(entry['play_value'])
            assert 0 <= entry['play_value'] <= 10 and entry['play_value'] == expected.play_value
            assert set(entry['printed_inputs']) <= {'name', 'oracle_text', 'type_line', 'mana_cost',
                                                    'power', 'toughness', 'layout'}
            actual = {key: entry[key] for key in ('tier', 'routes', 'limits')}
            assert actual == selected_fields(expected), name
            assert actual == selected_fields(derive_profile(entry['printed_inputs'])), name
        assert service.copy_snapshot(snapshot, semantic=True) == snapshot
    assert RAW == original


@pytest.mark.parametrize('field', ['layout', 'power', 'toughness'])
def test_actual_typed_kicker_coverage_requires_retained_printed_fields(field):
    card, raw, _, _ = fixture('Archangel of Wrath')
    retained = card.knowledge_snapshot['estimates']['root']['printed_inputs']
    assert retained[field] == raw[field]
    complete = selected_fields(derive_profile(retained))
    reduced = deepcopy(retained)
    reduced.pop(field)
    incomplete = selected_fields(derive_profile(reduced))
    assert incomplete != complete and 'known_gap:kicker' in incomplete['limits']


def test_tag_only_v1_capsule_keeps_original_tags_and_has_no_numeric_advice():
    card, _, _, _ = fixture()
    card.knowledge_snapshot.pop('estimates')
    sealed(card.knowledge_snapshot)
    assert service.copy_snapshot(card.knowledge_snapshot, semantic=True) == card.knowledge_snapshot
    assert service.tags_for(card).source == 'persisted'
    assert service.estimate_for(card) is None


def test_old_tag_profile_row_without_numeric_fields_retains_legacy_carrier():
    card, raw, row, hydrated = fixture()
    payload = json.loads(row.profiles_json)
    for key in ('threat_level', 'answer_routes', 'known_gaps'):
        payload['tactical_profile'].pop(key)
    row.profiles_json = json.dumps(payload)
    snapshot = service.snapshot_for(row, raw['name'], hydrated)
    assert snapshot and 'estimates' not in snapshot
    card.knowledge_snapshot = snapshot
    assert service.tags_for(card).source == 'persisted' and service.estimate_for(card) is None


@pytest.mark.parametrize('field', ['tier', 'routes'])
def test_corrupt_persisted_row_cannot_mint_estimates(field):
    card, raw, row, hydrated = fixture()
    payload = json.loads(row.profiles_json)
    if field == 'tier':
        payload['tactical_profile']['threat_level'] = (derive_profile(raw).threat_level + 1) % 4
    else:
        payload['tactical_profile']['answer_routes'] = []
    row.profiles_json = json.dumps(payload)
    snapshot = service.snapshot_for(row, raw['name'], hydrated)
    card.knowledge_snapshot = snapshot or {}
    assert service.estimate_for(card) is None


@pytest.mark.parametrize('field', ['tier', 'routes', 'limits'])
def test_resealed_numeric_routes_or_limits_rejected_before_use_and_on_cold_restore(field):
    card, _, _, _ = fixture()
    entry = card.knowledge_snapshot['estimates']['root']
    if field == 'tier':
        entry['tier'] = (entry['tier'] + 1) % 4
    elif field == 'routes':
        entry['routes'] = []
    else:
        entry['limits'] = []
    sealed(card.knowledge_snapshot)
    before = deepcopy(card.knowledge_snapshot)
    assert service.estimate_for(card) is None
    assert service.copy_snapshot(card.knowledge_snapshot, semantic=True) == {}
    assert card.knowledge_snapshot == before


@pytest.mark.parametrize('tier', [True, 1.0, -1, 4, float('nan')])
def test_invalid_tiers_are_not_numbers_or_default_values(tier):
    card, _, _, _ = fixture()
    card.knowledge_snapshot['estimates']['root']['tier'] = tier
    if tier == tier:
        sealed(card.knowledge_snapshot)
    assert service.estimate_for(card) is None
    assert service.copy_snapshot(card.knowledge_snapshot, semantic=True) == {}


def test_name_changes_are_not_policy_dispatch_or_estimate_identity():
    card, _, _, _ = fixture()
    before = service.estimate_for(card)
    assert before is not None
    card.name = 'Unrelated name without a card-name policy'
    assert service.estimate_for(card) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_factory_face_cold_and_opaque_views_keep_estimates_private(seat):
    api()
    state, cid = position(seat)
    estimate = service.estimate_for(state.cards[cid])
    assert estimate is not None
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    assert service.estimate_for(restored.cards[cid]) == estimate
    modal = next(card for card in restored.cards.values() if card.owner == seat and card.name == 'Bonecrusher Giant')
    actor = AIAgent()
    proxy = actor._modal_face_proxy(modal, modal.card_faces[1], face_index=1)
    assert service.estimate_for(proxy) is not None and not hasattr(proxy, 'id')
    assert service.estimate_for(actor._modal_face_proxy(modal, deepcopy(modal.card_faces[1]), face_index=1)) is None
    view, _ = decision_view(restored, seat, RulesEngine().legal_moves(restored, seat))
    for hidden in (view.cards[key] for key in restored.players[3 - seat].hand):
        assert hidden.ai_unknown and hidden.knowledge_snapshot == {}
        assert service.estimate_for(hidden) is None
    public = serialize_match(restored, look_players=[seat])
    assert 'knowledge_snapshot' not in json.dumps(public) and 'estimates' not in json.dumps(public)
    assert serialize_match_snapshot(restored) == saved


def test_opaque_getter_never_reads_carrier_and_routes_are_immutable_records():
    api()

    class Opaque:
        ai_unknown = True
        name = ''
        types = []

        @property
        def knowledge_snapshot(self):
            raise AssertionError('Opaque carrier read')

    assert service.estimate_for(Opaque()) is None
    card, _, _, _ = fixture()
    estimate = service.estimate_for(card)
    assert estimate is not None and type(estimate.routes) is tuple and type(estimate.limits) is tuple
    with pytest.raises((AttributeError, TypeError)):
        estimate.tier = 3
