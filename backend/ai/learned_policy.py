"""Explicit, bounded Q/V routing over actor-public features; heuristic default stays off."""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math

from ai.action_contract import complete_action
from ai.declaration_policy import finalize_declaration
from ai.interaction_reservation import affordable_interactions, preserves_interactions
from ai.learned_qv import MAX_CHECKPOINT_BYTES, QVPolicy, strict_json
from game_state.state import Step
from rules_engine.action_validation import ActionRejected, checked_action
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


def _public_cost_option(action, supplied_moves):
    """Retain one authentic offered option, never rehydrate a stripped action."""
    if not isinstance(action, dict) or action.get('type') != 'cast_spell':
        return None
    choice = action.get('cost_choice')
    if not isinstance(choice, dict) or type(choice.get('id')) is not str or not choice['id']:
        return None
    selected = choice['id']
    selectors = ('card_id', 'selected_face_index', 'cast_variant', 'graveyard_permission_key')
    origins = ('from_graveyard', 'from_exile', 'from_library')
    options = []
    for move in supplied_moves:
        if (move.get('type') != 'cast_spell'
                or any(move.get(key) != action.get(key) for key in selectors)
                or any(bool(move.get(key)) != bool(action.get(key)) for key in origins)):
            continue
        offered = move.get('cost_options')
        if (type(offered) is not list or not offered
                or any(type(option) is not dict or type(option.get('id')) is not str
                       or not option['id'] for option in offered)):
            return None
        options.extend(option for option in offered if option['id'] == selected)
    return deepcopy(options[0]) if len(options) == 1 else None


def _prefer_pass_to_paid_draw(agent, view, action, seat, option):
    """Narrow conditional preference; unresolved payoff contexts retain Q ordering."""
    if (option is None or action.get('type') != 'cast_spell'
            or action.get('selected_face_index') is not None or action.get('cast_variant') is not None
            or agent.archetype not in {'Control', 'Counter-heavy', 'Tempo'}
            or view.priority_player != seat or view.active_player == seat or view.step != Step.END_STEP
            or view.stack or view.pending_trigger_order or view.pending_mechanic_choice
            or view.pending_replacement_choice or view.delayed_triggers or view.staged_triggers
            or view.emblems):
        return False
    from ai.information import is_unknown
    from rules_engine.continuous import effective_keywords
    import re
    # Public text/keyword matches only abstain; they do not certify any payoff.
    for player in view.players.values():
        for cid in player.battlefield:
            public_card = view.cards.get(cid)
            if public_card is None or is_unknown(public_card):
                return False
            text = (public_card.oracle_text or '').lower()
            if ('instead' in text or re.search(r'\b(?:when|whenever|at the beginning)\b', text)
                    or any(keyword.split()[0] in {'prowess', 'training', 'undying', 'decayed',
                                                  'exalted', 'bushido', 'rampage', 'flanking'}
                           for keyword in effective_keywords(view, cid) if keyword.split())):
                return False
    from rules_engine.type_effects import effective_types
    card = view.cards[action['card_id']]
    if ('Instant' not in effective_types(view, card)
            or ('draw' not in agent._spell_tags(card)
                and not any(word in (card.oracle_text or '').lower() for word in ('scry', 'surveil')))):
        return False
    if not all(type(option.get(key)) is int for key in ('pay_life', 'discard_cards', 'sacrifice_creatures')):
        return False
    loss, prefer_pass = agent._endstep_draw_payment_preference(view, action, seat, option)
    return math.isfinite(loss) and prefer_pass


def choose_learned_action(binding, agent, view, supplied_moves, seat, *, admit, _terminal_win=None):
    """Rank a checked SUBSET; admission retains the caller's original-state boundary."""
    # The tactical preference corpus does not qualify opening-hand decisions.
    if getattr(view, 'pregame_pending', False):
        return None
    if not isinstance(binding, LivePolicyBinding) or binding.contract != _current_contract():
        return None
    try:
        from ai.pending_effects import unanswered_action_classification

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
        candidates, seen, public_costs = [], set(), {}
        for proposal in proposals:
            try:
                intent = finalize_declaration(view, deepcopy(proposal))
                offered_cost = _public_cost_option(intent, supplied_moves)
                action = complete_action(intent)
                require_choices_from_view(view, supplied_moves, action, seat)
                admit(action)
            except (ActionRejected, ValueError):
                continue
            draw_loss = getattr(agent, '_draw_cast_loses', None)
            if callable(draw_loss) and draw_loss(view, action, seat):
                continue
            identity = json.dumps(action, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if identity not in seen:
                candidates.append(action)
                seen.add(identity)
                public_costs[identity] = offered_cost
        if not candidates:
            return None
        prepared = binding._policy.prepare(decision_frame.encode_state(frame))

        def own_choice(projected, moves, actor):
            from ai.agent import AIAgent
            # Follow public continuations without recursively invoking learned ranking.
            chooser = AIAgent(difficulty=getattr(agent, 'difficulty', 'master'),
                              archetype=getattr(agent, 'archetype', 'Midrange'),
                              opponent_archetype=getattr(agent, 'opponent_archetype', None))
            return chooser.choose_action(projected, moves, actor).action

        best, best_key = None, None
        terminal_classes = []
        ranked = []
        known_outcome = False
        answers = None
        for action in candidates:
            result = prepared.predict(decision_frame.encode_action(frame, references.action(action)))
            if (type(result) is not dict or set(result) != {'q', 'v'}
                    or any(type(result[key]) not in (int, float)
                           or not math.isfinite(result[key]) or not -1 <= result[key] <= 1
                           for key in ('q', 'v'))):
                return None
            # Checked terminal forecasts outrank utility, not every possible reply.
            win, loss = unanswered_action_classification(
                view, seat, action, settle_declared_combat=True, own_choice_action=own_choice)
            if action['type'] in {'foretell', 'suspend'} and win is not True:
                if answers is None:
                    answers = affordable_interactions(agent, view, seat)
                # Preserve known wins; reserve answers using only the actor projection.
                if answers and not preserves_interactions(
                        checked_action(view, agent.engine, seat, action),
                        seat, action['card_id'], answers):
                    continue
            known_outcome |= win is True or (win is False and (loss is True or loss is False))
            key = (win is True, loss is not True, result['q'])
            terminal_classes.append((action, key[:2]))
            ranked.append((action, key))
            if best is None or key > best_key:
                best, best_key = action, key
        if best is None:
            return None
        if (view.step == Step.DECLARE_BLOCKERS and view.active_player != seat
                and not known_outcome):
            return None
        while best['type'] != 'pass_priority' and not best_key[0]:
            if not any(action['type'] == 'pass_priority' and key[:2] >= best_key[:2]
                       for action, key in ranked):
                break
            identity = json.dumps(best, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if not _prefer_pass_to_paid_draw(agent, view, best, seat, public_costs[identity]):
                break
            ranked = [(action, key) for action, key in ranked if action != best]
            best, best_key = max(ranked, key=lambda item: item[1])
        if best.get('type') == 'play_land' and not best_key[0]:
            from ai.mana_resource_policy import prefer_nonregressive_land
            alternatives = [action for action, prefix in terminal_classes
                            if action.get('type') == 'play_land' and prefix >= best_key[:2]]
            best = prefer_nonregressive_land(agent, view, seat, best, alternatives)
        if best.get('type') == 'pass_priority' and not best_key[0]:
            stall = getattr(agent, '_should_break_stall', None)
            proactive = getattr(agent, '_best_proactive_non_pass', None)
            unplayable_x = getattr(agent, '_is_unplayable_x_action', None)
            if (callable(stall) and callable(proactive) and callable(unplayable_x)
                    and stall(view, supplied_moves, seat)):
                # Only an equal-or-better checked unanswered terminal class;
                # this is not a safety claim about unknown future replies.
                eligible = {
                    json.dumps(action, sort_keys=True, separators=(',', ':'), allow_nan=False): action
                    for action, terminal_class in terminal_classes
                    if terminal_class >= best_key[:2]
                    and action.get('type') not in {'pass_priority', 'tap_land_for_mana', 'tap_lands_bulk',
                                                  'activate_mana_ability', 'tap_nonland_for_mana',
                                                  'foretell', 'suspend'}
                    and not action.get('_invalid_ai_choice') and not unplayable_x(action)
                    and (action.get('type') != 'attack' or bool(action.get('attackers')))
                }
                if eligible:
                    proposed = proactive(deepcopy(list(eligible.values())), view, seat)
                    if type(proposed) is dict:
                        try:
                            identity = json.dumps(proposed, sort_keys=True, separators=(',', ':'), allow_nan=False)
                        except (TypeError, ValueError, OverflowError):
                            identity = None
                        if identity in eligible:
                            best = eligible[identity]
            if best.get('type') == 'pass_priority':
                idle = {
                    json.dumps(action, sort_keys=True, separators=(',', ':'), allow_nan=False): action
                    for action, terminal_class in terminal_classes
                    if terminal_class >= best_key[:2] and action.get('type') in {'foretell', 'suspend'}
                }
                if idle:
                    from ai.foretell_policy import idle_foretell_action
                    from ai.suspend_policy import idle_suspend
                    # Preserve full-move reservation/timing checks, but never
                    # let a helper add an action outside the admitted subset.
                    for kind, helper in (('foretell', idle_foretell_action), ('suspend', idle_suspend)):
                        if not any(action['type'] == kind for action in idle.values()):
                            continue
                        try:
                            proposed = helper(agent, deepcopy(view), deepcopy(supplied_moves), seat)
                            identity = (json.dumps(proposed, sort_keys=True, separators=(',', ':'), allow_nan=False)
                                        if type(proposed) is dict else None)
                        except (ActionRejected, TypeError, ValueError, OverflowError):
                            identity = None
                        selected = idle.get(identity)
                        if selected is not None and selected['type'] == kind:
                            best = selected
                            break
        if (_terminal_win is not None
                and not (view.step == Step.DECLARE_BLOCKERS and view.active_player != seat)):
            # The caller asks only "is a win?". Defensive combat used a different horizon.
            _terminal_win.extend(prefix[0] for candidate, prefix in terminal_classes if candidate == best)
        return deepcopy(best)
    except (ActionRejected, ValueError, OverflowError):
        return None
