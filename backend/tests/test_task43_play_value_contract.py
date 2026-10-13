"""Real derive/merge/snapshot checks; numeric faults are explicit unsafe inputs."""
from copy import deepcopy
import json
import math
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from knowledge.profiles import _hash, derive_profile, merge_profile_payload
from knowledge.service import estimate_for, snapshot_for, tags_for
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_task43_vanilla_controls import RAW, VANILLA, controlled_pose
from tests.test_ai_knowledge_profile_consumer import position
from tests.test_task23_profile_threat_transport import selected_fields
from rules_engine.card_faces import select_cast_face


def seal(snapshot):
    snapshot['snapshot_sha256'] = _hash({k: v for k, v in snapshot.items() if k != 'snapshot_sha256'})


@pytest.mark.parametrize('value', [True, '4.9', None, -0.1, 10.1, 9.9, 0.0, 10.0, float('inf'), float('nan')])
def test_bad_additive_persisted_values_keep_valid_legacy_tier_routes(value):
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    raw = VANILLA['Watchwolf']
    profile = merge_profile_payload({'card_data': raw}, derive_profile(raw))
    profile['tactical_profile']['play_value'] = value
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall', profiles_json=json.dumps(profile))
    hydrated = {k: raw.get(k, '') for k in ('oracle_text', 'type_line', 'mana_cost', 'layout')}
    hydrated['card_faces'] = []
    state.cards[cid].knowledge_snapshot = snapshot_for(row, raw['name'], hydrated)
    estimate = estimate_for(state.cards[cid])
    assert estimate is not None and estimate.tier == 1 and estimate.routes
    assert getattr(estimate, 'play_value', None) is None
    assert state.cards[cid].knowledge_snapshot['estimates']['transport_version'] == 1


@pytest.mark.parametrize('field,value', [
    ('mode', 'unknown'), ('archetype_verification', 'verified'), ('curve_nonland_mean', True),
    ('curve_nonland_mean', '2.5'), ('curve_nonland_mean', -1.0), ('curve_nonland_mean', float('inf')),
    ('corpus_fingerprint', 'unknown'), ('archetype', 13), ('deck_analysis_primary_archetype_estimate', []),
])
def test_malformed_context_does_not_destroy_legacy_estimate_or_mint_value(field, value):
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    raw = VANILLA['Watchwolf']
    payload = merge_profile_payload({'card_data': raw}, derive_profile(raw))
    payload['tactical_profile']['context'][field] = value
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall', profiles_json=json.dumps(payload))
    hydrated = {k: raw.get(k, '') for k in ('oracle_text', 'type_line', 'mana_cost', 'layout')}
    hydrated['card_faces'] = []
    state.cards[cid].knowledge_snapshot = snapshot_for(row, raw['name'], hydrated)
    estimate = estimate_for(state.cards[cid])
    assert estimate is not None and estimate.tier == 1 and estimate.routes
    assert getattr(estimate, 'play_value', None) is None


@pytest.mark.parametrize('fault', ['value', 'context', 'pt', 'extra_field', 'missing_field', 'face_value'])
def test_semantically_resealed_wrong_scalar_context_printed_inputs_and_face_are_rejected(fault):
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    card = state.cards[cid]
    if fault == 'face_value':
        state, _ = position(1)
        parent = next(c for c in state.cards.values() if c.owner == 1 and c.card_faces)
        card = select_cast_face(parent, 1)
    snapshot = card.knowledge_snapshot
    assert snapshot['estimates']['transport_version'] == 2
    if fault == 'value':
        snapshot['estimates']['root']['play_value'] = 9.9
    elif fault == 'context':
        snapshot['estimates']['context']['curve_nonland_mean'] = 2.5
    elif fault == 'pt':
        snapshot['estimates']['root']['printed_inputs']['power'] = '9'
    elif fault == 'extra_field':
        snapshot['estimates']['context']['unapproved'] = 1
    elif fault == 'missing_field':
        snapshot['estimates']['context'].pop('mode')
    else:
        snapshot['estimates']['faces'][1]['play_value'] = 5.05
    seal(snapshot)
    assert estimate_for(card) is None


def test_returned_existing_context_is_defensively_copied_and_does_not_certify_corpus():
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    card = state.cards[cid]
    before = deepcopy(card.knowledge_snapshot)
    estimate = estimate_for(card)
    assert getattr(estimate, 'play_value', None) == 4.9
    assert estimate.context['archetype_verification'] == 'caller_declared_not_verified'
    estimate.context['curve_nonland_mean'] = 2.5
    assert estimate_for(card).context['curve_nonland_mean'] is None
    assert card.knowledge_snapshot == before


@pytest.mark.parametrize('fault', ['v1', 'changed_pt', 'missing_pt', 'opaque', 'missing_carrier', 'bad_face'])
def test_optional_value_preserves_legacy_printed_face_missing_field_and_unknown_safety(fault):
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    card = state.cards[cid]
    if fault == 'v1':
        estimates = card.knowledge_snapshot['estimates']
        estimates['transport_version'] = 1
        estimates.pop('context')
        for entry in [estimates['root'], *estimates['faces']]:
            entry.pop('play_value')
        seal(card.knowledge_snapshot)
    elif fault == 'changed_pt':
        card.power = 9
    elif fault == 'missing_pt':
        card.power = None
    elif fault == 'opaque':
        card.ai_unknown = True
    elif fault == 'missing_carrier':
        card.knowledge_snapshot = {}
    else:
        card.selected_face_index = 99
    estimate = estimate_for(card)
    assert estimate is None or getattr(estimate, 'play_value', None) is None
    if fault in {'v1', 'changed_pt', 'missing_pt'}:
        assert estimate is not None and estimate.tier == 1 and estimate.routes


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario,want', [('empty', -0.6375), ('stable_low', -0.6375),
    ('urgent_low', 0.6375), ('resource_low', 0.6375), ('tier2', 0.6375), ('tier3', 0.6375)])
def test_actual_profile_advice_is_pure_and_total_clamped_with_real_qualified_public_context(seat, scenario, want):
    state, creature, sweeper, _, _ = controlled_pose(seat, 'Watchwolf', scenario)
    actor = AIAgent(difficulty='strong', archetype='Control')
    advice = getattr(actor, '_profile_cast_advice', None)
    assert callable(advice), 'Shared pure method-local eligibility/contribution helper absent'
    before = serialize_match_snapshot(state)
    # Preserve the engine object's identity; copying an object without __eq__
    # cannot establish whether it changed. Copy mutable policy/counter data.
    actor_before = {key: deepcopy(value) if isinstance(value, (dict, list, set, tuple)) else value
                    for key, value in actor.__dict__.items()}
    legal = RulesEngine().legal_moves(state, seat)
    source_move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == creature)
    sweep_move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == sweeper)
    assert advice(state, source_move, seat) == pytest.approx(0.735)
    assert advice(state, sweep_move, seat) == pytest.approx(want)
    assert all(-1.5 <= advice(state, m, seat) <= 1.5 for m in legal)
    assert serialize_match_snapshot(state) == before and actor.__dict__ == actor_before


@pytest.mark.parametrize('fault', ['opaque', 'missing', 'live_stats', 'alternate_cost', 'pending', 'resource_plan'])
def test_unknown_unsafe_or_other_resource_policy_adds_no_profile_contribution(fault):
    state, creature, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    actor = AIAgent(difficulty='strong', archetype='Control')
    advice = getattr(actor, '_profile_cast_advice', None)
    assert callable(advice), 'Shared advice helper absent'
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m['type'] == 'cast_spell' and m['card_id'] == creature)
    kwargs = {}
    if fault == 'opaque': state.cards[creature].ai_unknown = True
    elif fault == 'missing': state.cards[creature].knowledge_snapshot = {}
    elif fault == 'live_stats': state.cards[creature].power = 9
    elif fault == 'alternate_cost': move['cast_variant'] = 'unreviewed'
    elif fault == 'pending': state.pending_mechanic_choice = {'fixture': 'unresolved'}
    else: kwargs['resource_plan'] = {'score': 1}
    assert advice(state, move, 1, **kwargs) == 0.0
    if fault == 'opaque':
        assert estimate_for(state.cards[creature]) is None and tags_for(state.cards[creature]).source == 'opaque'


@pytest.mark.parametrize('context', ['printed_only', 'actual_known_corpus'])
@pytest.mark.parametrize('name', sorted(RAW))
def test_all155_actual_derived_values_and_declared_context_use_same_canonical_transport(name, context):
    # Explicit supplied standalone own roster, full official objects and actual
    # quantities. This is not inferred from any opponent/private game input.
    raw = RAW[name]
    corpus = [{'card_metadata': item, 'quantity': 1} for item in RAW.values()] if context == 'actual_known_corpus' else []
    profile = derive_profile(raw, corpus)
    row = SimpleNamespace(name=name, scryfall_id=raw['id'], oracle_source='scryfall',
        profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, profile)))
    surface = raw['card_faces'][0] if raw.get('card_faces') else raw
    hydrated = {k: surface.get(k, '') for k in ('oracle_text', 'type_line', 'mana_cost')}
    hydrated.update(layout=raw['layout'], card_faces=deepcopy(raw.get('card_faces', [])))
    snapshot = snapshot_for(row, name, hydrated)
    assert snapshot and snapshot['estimates']['transport_version'] == 2
    estimates = snapshot['estimates']
    assert estimates['context'] == profile.context
    for entry, expected in zip([estimates['root'], *estimates['faces']], [profile, *profile.faces]):
        assert type(entry['play_value']) is float and math.isfinite(entry['play_value'])
        assert entry['play_value'] == expected.play_value and 0 <= entry['play_value'] <= 10


def test_all155_real_legacy_rows_without_additive_fields_still_emit_exact_v1_semantics():
    for name, raw in RAW.items():
        profile = derive_profile(raw)
        payload = merge_profile_payload({'card_data': raw}, profile)
        payload['tactical_profile'].pop('play_value')
        payload['tactical_profile'].pop('context')
        row = SimpleNamespace(name=name, scryfall_id=raw['id'], oracle_source='scryfall', profiles_json=json.dumps(payload))
        surface = raw['card_faces'][0] if raw.get('card_faces') else raw
        hydrated = {k: surface.get(k, '') for k in ('oracle_text', 'type_line', 'mana_cost')}
        hydrated.update(layout=raw['layout'], card_faces=deepcopy(raw.get('card_faces', [])))
        snapshot = snapshot_for(row, name, hydrated)
        assert snapshot and snapshot['estimates']['transport_version'] == 1
        assert set(snapshot['estimates']) == {'transport_version', 'root', 'faces'}
        for entry, expected in zip([snapshot['estimates']['root'], *snapshot['estimates']['faces']], [profile, *profile.faces]):
            assert set(entry) == {'tier', 'routes', 'limits', 'printed_inputs'}
            assert {key: entry[key] for key in ('tier', 'routes', 'limits')} == selected_fields(expected)


@pytest.mark.parametrize('kind,archetype,expected', [('empty_with_label', 'Control', 4.9),
    ('supplied_archetype', 'Caller label', 5.4), ('land_only', None, 4.9)])
def test_legitimate_existing_context_forms_are_not_discarded_or_inferred(kind, archetype, expected):
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    raw = VANILLA['Watchwolf']
    corpus = [] if kind == 'empty_with_label' else [{'card_metadata': RAW['Forest'], 'quantity': 1}] if kind == 'land_only' else [
        {'card_metadata': raw, 'quantity': 3}, {'card_metadata': RAW['Supreme Verdict'], 'quantity': 1}]
    profile = derive_profile(raw, corpus, archetype=archetype)
    assert profile.play_value == expected
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
        profiles_json=json.dumps(merge_profile_payload({'card_data': raw}, profile)))
    hydrated = {k: raw.get(k, '') for k in ('oracle_text', 'type_line', 'mana_cost', 'layout')}
    hydrated['card_faces'] = []
    state.cards[cid].knowledge_snapshot = snapshot_for(row, raw['name'], hydrated)
    estimate = estimate_for(state.cards[cid])
    assert getattr(estimate, 'play_value', None) == expected
    assert estimate.context == profile.context and estimate.context['archetype_verification'] == 'caller_declared_not_verified'


def test_resealed_consistent_changed_pt_and_value_still_cannot_override_live_printed_pt():
    state, cid, _, _, _ = controlled_pose(1, 'Watchwolf', 'empty')
    card = state.cards[cid]
    snapshot = card.knowledge_snapshot
    snapshot['estimates']['root']['printed_inputs']['power'] = '9'
    snapshot['estimates']['root']['play_value'] = 5.8
    seal(snapshot)
    estimate = estimate_for(card)
    assert estimate is not None and estimate.tier == 1
    assert getattr(estimate, 'play_value', None) is None and card.power == 3
