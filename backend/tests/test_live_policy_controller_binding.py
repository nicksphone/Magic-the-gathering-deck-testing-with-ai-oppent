"""Actual binding eligibility protocols; synthetic weights do not prove training."""
from copy import deepcopy
from hashlib import sha256

from tests.test_live_policy_controller_protocol import (
    api, checkpoint_binding, scene, restore, saved_record, stored_row, trusted_binding,
)


def test_plain_agent_with_matching_metadata_cannot_claim_learned(api, scene):
    from ai.agent import AIAgent

    agent = AIAgent(difficulty='strong', archetype='Control')
    binding = {'agent': agent, 'provenance': deepcopy(scene.record)}
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: binding})
    assert restored.ai[scene.seat] is not agent
    assert restored.ai[scene.seat].learned_binding is None
    assert (restored.ai[scene.seat].difficulty, restored.ai[scene.seat].archetype) == ('strong', 'Control')
    assert saved_record(api, restored, scene.seat) == {
        **scene.record, 'effective': 'heuristic', 'fallback_reason': 'restore_requires_opt_in',
    }


def test_agent_bound_to_different_buffer_cannot_borrow_matching_receipt(api, scene):
    from ai.agent import AIAgent
    from ai.learned_policy import bind_live_policy

    # Same JSON model/contract, different real buffer identity, not fabricated metadata.
    alternate = bind_live_policy(scene.raw_checkpoint + b'\n')
    assert alternate.contract == scene.binding.contract
    assert alternate.checkpoint_sha256 != scene.binding.checkpoint_sha256
    agent = AIAgent(difficulty='strong', archetype='Control', learned_binding=alternate)
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: {'agent': agent, 'provenance': deepcopy(scene.record)}})
    assert restored.ai[scene.seat] is not agent
    assert saved_record(api, restored, scene.seat) == {
        **scene.record, 'effective': 'heuristic', 'fallback_reason': 'restore_requires_opt_in',
    }


def test_real_same_buffer_binding_restores_identity_and_registered_model(api, scene):
    from ai.learned_qv import VERSION

    binding = trusted_binding(scene)
    row = stored_row(api, scene.controller, {scene.seat: scene.record})
    restored = restore(api, row, {scene.seat: binding})
    assert restored.ai[scene.seat] is binding['agent']
    assert restored.ai[scene.seat].learned_binding is scene.binding
    assert scene.binding.checkpoint_sha256 == sha256(scene.raw_checkpoint).hexdigest()
    assert scene.binding._policy.payload()['version'] == VERSION == 'mtg.qv.v1'
    assert scene.record['version'] == 'mtg.live-policy.v1'
    assert saved_record(api, restored, scene.seat) == scene.record
    assert (restored.ai[scene.seat].difficulty, restored.ai[scene.seat].archetype) == ('strong', 'Control')
