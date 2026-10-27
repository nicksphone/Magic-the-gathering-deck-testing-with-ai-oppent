"""Explicit, bounded Q/V routing over actor-public features; heuristic default stays off."""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math

from ai.action_contract import complete_action
from ai.declaration_policy import finalize_declaration
from ai.learned_qv import MAX_CHECKPOINT_BYTES, QVPolicy, strict_json
from game_state.state import Step
from rules_engine.action_validation import ActionRejected
from training import decision_frame
from training.dataset import DECISION_DATASET_VERSION
from training.environment import (
    ACTION_PREFIX, _engine_hash, decision_inputs_from_view, require_choices_from_view,
)


def _current_contract():
    return {
        'dataset_version': DECISION_DATASET_VERSION, 'action_version': ACTION_PREFIX,
        'decision_version': decision_frame.CONTEXT_DECISION_VERSION,
        'feature_version': decision_frame.CONTEXT_FEATURE_VERSION,
        'feature_schema_sha256': decision_frame.CONTEXT_FEATURE_SCHEMA_SHA256,
        'engine_hash': _engine_hash(),
    }


@dataclass(frozen=True, slots=True)
class LivePolicyBinding:
    """Trusted in-memory handle, never a filename or snapshot activation request."""
    _policy: QVPolicy
    checkpoint_sha256: str
    _contract: tuple

    @property
    def contract(self):
        return dict(self._contract)


def bind_live_policy(raw_checkpoint_bytes):
    """Validate and identify the SAME bounded buffer; no filesystem authority."""
    if type(raw_checkpoint_bytes) is not bytes or not 1 <= len(raw_checkpoint_bytes) <= MAX_CHECKPOINT_BYTES:
        raise ValueError('A bounded immutable checkpoint buffer is required')
    contract = _current_contract()
    payload = strict_json(raw_checkpoint_bytes)
    policy = QVPolicy(payload, expected=contract)
    provenance = payload['provenance']
    if provenance['updates'] == 0 or provenance['samples'] == 0:
        raise ValueError('Zero-update/sample protocol weights are not live eligible')
    return LivePolicyBinding(policy, sha256(raw_checkpoint_bytes).hexdigest(),
                             tuple(sorted(contract.items())))


def choose_learned_action(binding, agent, view, supplied_moves, seat, *, admit):
    """Rank a checked SUBSET; admission retains the caller's original-state boundary."""
    # The tactical preference corpus does not qualify opening-hand decisions.
    if getattr(view, 'pregame_pending', False):
        return None
    if not isinstance(binding, LivePolicyBinding) or binding.contract != _current_contract():
        return None
    try:
        from ai.pending_effects import unanswered_action_loses, unanswered_action_wins

        observation, prompts, context = decision_inputs_from_view(view, supplied_moves, seat)
        frame, references = decision_frame.build_decision_frame(
            observation, prompts, public_context=context)
        if any(binding.contract[key] != value
               for key, value in decision_frame.feature_contract(frame).items()):
            return None
        proposals = agent._strategic_top_actions(view, supplied_moves, seat, 8)
        # The existing shortlist may retain one extra priority pass. Not exhaustive.
        if not isinstance(proposals, list) or len(proposals) > 9:
            return None
        candidates, seen = [], set()
        for proposal in proposals:
            try:
                action = complete_action(finalize_declaration(view, deepcopy(proposal)))
                require_choices_from_view(view, supplied_moves, action, seat)
                admit(action)
            except (ActionRejected, ValueError):
                continue
            identity = json.dumps(action, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if identity not in seen:
                candidates.append(action)
                seen.add(identity)
        if not candidates:
            return None
        prepared = binding._policy.prepare(decision_frame.encode_state(frame))
        best, best_key = None, None
        known_outcome = False
        for action in candidates:
            result = prepared.predict(decision_frame.encode_action(frame, references.action(action)))
            if (type(result) is not dict or set(result) != {'q', 'v'}
                    or any(type(result[key]) not in (int, float)
                           or not math.isfinite(result[key]) or not -1 <= result[key] <= 1
                           for key in ('q', 'v'))):
                return None
            # Checked terminal forecasts outrank utility, not every possible reply.
            win = unanswered_action_wins(view, seat, action, settle_declared_combat=True)
            loss = (unanswered_action_loses(view, seat, action, settle_declared_combat=True)
                    if win is False else None)
            known_outcome |= win is True or (win is False and (loss is True or loss is False))
            key = (win is True, loss is not True, result['q'])
            if best is None or key > best_key:
                best, best_key = action, key
        if (view.step == Step.DECLARE_BLOCKERS and view.active_player != seat
                and not known_outcome):
            return None
        return deepcopy(best)
    except (ActionRejected, ValueError, OverflowError):
        return None
