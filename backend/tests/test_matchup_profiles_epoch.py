"""Synthetic loader protocol ONLY: not native data, profiles or epoch authority."""
from copy import deepcopy
import json

import pytest

from ai import matchup_profiles as consumer
from decks.builtin_decks import BUILTIN_DECKS


MEASURED_EPOCH = {
    'source_base_commit': '7c5e933a73755b53da5efd50159c1bb248cf4906',
    'backend_sha256': '9a9b0bd326a05e05b36ac3a01819f9d22709586a78da3c2a50352cf40f78da67',
    'source_binding_sha256': '123b889fbe544bac3dd31689baf793be55daac1da1976210cf034bc41ac212fa',
}
PREVIOUS_EPOCH = {
    'source_base_commit': '7c5e933a73755b53da5efd50159c1bb248cf4906',
    'backend_sha256': '57b0b0e28dfa2896b14b52505e8b978da4a6cc3c65202a86b738419101c9003c',
    'source_binding_sha256': '7059b869b0a7693a8d4a463dffc44e39e45708280e56854c499218f2dedd59ce',
}


def protocol_packet():
    # Hand-checked balanced single-bucket protocol. No derivation or native run.
    return {
        'schema_version': 1, 'qualified': True, 'lineage': deepcopy(MEASURED_EPOCH),
        'coverage': {'builtin_decks': 11, 'builtin_pairs': 55, 'seed_tokens': 1,
                     'roster_schema_version': 1,
                     'roster_archetypes': dict.fromkeys(BUILTIN_DECKS, 'control')},
        'counts': {'resolved_series': 110, 'resolved_games': 220},
        'profiles': {'control': {'control': {'proactive_bias': 0.8, 'holdup_bias': 0.8,
                                            'risk_tolerance': 0.0}}},
        'samples': {'control': {'control': {'series': 220, 'wins': 110, 'games': 440,
            'quality': dict.fromkeys(consumer.QUALITY_KEYS, 0),
            'opponent_quality': dict.fromkeys(consumer.QUALITY_KEYS, 0)}}},
    }


def write_protocol(tmp_path, payload):
    data = deepcopy(payload)
    data['artifact_sha256'] = consumer.artifact_digest(data)
    path = tmp_path / 'synthetic-epoch-protocol.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_default_loader_accepts_current_measured_epoch_protocol(tmp_path):
    payload = protocol_packet()
    before = deepcopy(payload)
    path = write_protocol(tmp_path, payload)
    assert consumer.load_profiles(path) == {'control': {'control': {
        'proactive_bias': 0.8, 'holdup_bias': 0.8, 'risk_tolerance': 0.0}}}
    assert payload == before


def test_process_cache_uses_current_epoch_without_lineage_override(tmp_path, monkeypatch):
    payload = protocol_packet()
    monkeypatch.setattr(consumer, 'PROFILE_PATH', write_protocol(tmp_path, payload))
    consumer._load_profile_table.cache_clear()
    try:
        assert consumer._load_profile_table() == payload['profiles']
        row = consumer.profile_for('Control', 'Control')
        row['holdup_bias'] = 999.0
        assert consumer.profile_for('Control', 'Control')['holdup_bias'] == 0.8
    finally:
        consumer._load_profile_table.cache_clear()


@pytest.mark.parametrize('wrong', ['previous_tuple', 'previous_backend', 'previous_binding',
    'consumer_commit', 'foreign_base', 'missing_binding', 'extra_epoch', 'null_backend'])
def test_resealed_wrong_epoch_protocol_is_rejected(tmp_path, wrong):
    payload = protocol_packet()
    if wrong == 'previous_tuple': payload['lineage'] = deepcopy(PREVIOUS_EPOCH)
    elif wrong == 'previous_backend': payload['lineage']['backend_sha256'] = PREVIOUS_EPOCH['backend_sha256']
    elif wrong == 'previous_binding': payload['lineage']['source_binding_sha256'] = PREVIOUS_EPOCH['source_binding_sha256']
    elif wrong == 'consumer_commit': payload['lineage']['source_base_commit'] = '2f42a6eb352480fae1940018b70f4395c478c38e'
    elif wrong == 'foreign_base': payload['lineage']['source_base_commit'] = 'a' * 40
    elif wrong == 'missing_binding': del payload['lineage']['source_binding_sha256']
    elif wrong == 'extra_epoch': payload['lineage']['producer_epoch'] = '9061'
    else: payload['lineage']['backend_sha256'] = None
    assert consumer.load_profiles(write_protocol(tmp_path, payload)) == {}


def test_wrong_epoch_preserves_original_fallback_and_input_bytes(tmp_path, monkeypatch):
    payload = protocol_packet()
    payload['lineage'] = deepcopy(PREVIOUS_EPOCH)
    path = write_protocol(tmp_path, payload)
    before = path.read_bytes()
    monkeypatch.setattr(consumer, 'PROFILE_PATH', path)
    consumer._load_profile_table.cache_clear()
    try:
        assert consumer._load_profile_table() == {}
        assert consumer.profile_for('Control', 'Aggro') == {
            'proactive_bias': 0.0, 'holdup_bias': 1.3, 'risk_tolerance': -0.1}
    finally:
        consumer._load_profile_table.cache_clear()
    assert path.read_bytes() == before


def test_current_epoch_does_not_admit_unqualified_or_malformed_table(tmp_path):
    payload = protocol_packet()
    payload['qualified'] = False
    assert consumer.load_profiles(write_protocol(tmp_path, payload)) == {}
    payload['qualified'] = True
    payload['counts']['resolved_series'] = 109
    assert consumer.load_profiles(write_protocol(tmp_path, payload)) == {}
