"""Opt-in cooperative search limits for interactive autoplay."""
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import os
from time import monotonic


class _Exhausted(BaseException):
    """Unwind speculative branches that catch ordinary action failures."""


@dataclass
class _Budget:
    remaining: int | None
    deadline: float | None

    def check_deadline(self):
        if self.deadline is not None and monotonic() >= self.deadline:
            raise _Exhausted('deadline')

    def check(self):
        self.check_deadline()
        if self.remaining == 0:
            raise _Exhausted('node limit')


_active = ContextVar('interactive_ai_budget', default=None)
_log = logging.getLogger(__name__)


def checkpoint():
    current = _active.get()
    if current is not None:
        current.check()
        if current.remaining is not None:
            current.remaining -= 1


def _limit(name):
    value = os.environ.get(name)
    if value is None:
        return None
    if not value.isascii() or not value.isdecimal():
        raise ValueError(f'{name} must be a nonnegative integer')
    return int(value)


def _checked_fallback(state, offers, player_id):
    from ai.action_contract import complete_action
    from ai.agent import AIDecision
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine

    if not offers:
        return None
    offer = next((offer for offer in offers if offer.get('type') == 'pass_priority'), offers[0])
    try:
        action = complete_action(offer)
        checked_action(state, RulesEngine(), player_id, action)
    except (ActionRejected, TypeError, ValueError):
        return None
    return AIDecision(action=action, reasoning='Checked fallback after interactive AI budget exhaustion')


def choose_for_autoplay(agent, state, offers, player_id):
    nodes = _limit('MTG_AI_INTERACTIVE_NODES')
    milliseconds = _limit('MTG_AI_INTERACTIVE_MS')
    if nodes is None and milliseconds is None:
        return agent.choose_action(state, offers, player_id)
    counts = getattr(agent, '_main_pass_signature_counts', None)
    prior_counts = counts.copy() if type(counts) is dict else None
    deadline = None if milliseconds is None else monotonic() + milliseconds / 1000
    limit = _Budget(nodes, deadline)
    token = _active.set(limit)
    try:
        limit.check()
        decision = agent.choose_action(state, offers, player_id)
        limit.check_deadline()
        return decision
    except _Exhausted as exc:
        if prior_counts is not None:
            counts.clear()
            counts.update(prior_counts)
        _log.debug('Interactive AI stopped at %s', exc)
    finally:
        _active.reset(token)
    return _checked_fallback(state, offers, player_id)
