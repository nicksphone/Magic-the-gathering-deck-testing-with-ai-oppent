"""Opt-in cooperative search limits for interactive autoplay."""
from contextlib import contextmanager
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
    authoritative: object
    player_id: int
    view: object = None
    rank_requested: bool = False
    best_key: tuple | None = None
    best_action: dict | None = None
    pending_key: tuple | None = None

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


@contextmanager
def decision_root(authoritative, view):
    current = _active.get()
    if current is None or current.authoritative is not authoritative or current.view is not None:
        yield
        return
    current.view = view
    try:
        yield
    finally:
        current.view = None


def _root_budget(state):
    current = _active.get()
    if current is not None and state is (current.view if current.view is not None else current.authoritative):
        return current
    return None


def rank_root(state, rank, moves, player_id):
    current = _root_budget(state)
    if current is None:
        return rank(state, moves, player_id)
    current.rank_requested = True
    try:
        return rank(state, moves, player_id)
    finally:
        current.rank_requested = False


def track_rank(state):
    current = _root_budget(state)
    if current is None or not current.rank_requested:
        return False
    current.rank_requested = False
    return True


def remember(state, key, prepare):
    current = _root_budget(state)
    if current is None or current.pending_key is not None:
        return
    if current.best_key is not None and key <= current.best_key:
        return

    current.pending_key = key
    action = _checked(current.authoritative, current.player_id, prepare())
    if action is not None:
        current.best_key = key
        current.best_action = action
    current.pending_key = None


def _limit(name):
    value = os.environ.get(name)
    if value is None:
        return None
    if not value.isascii() or not value.isdecimal():
        raise ValueError(f'{name} must be a nonnegative integer')
    return int(value)


def _checked(state, player_id, action):
    from ai.action_contract import complete_action
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine

    try:
        action = complete_action(action)
        checked_action(state, RulesEngine(), player_id, action)
    except (ActionRejected, TypeError, ValueError):
        return None
    return action


def _after_cutoff(limit, offers):
    from ai.agent import AIDecision

    action = limit.best_action
    # An unfinished better candidate prevents falling through to a scored
    # wait. A previously checked play is still available.
    if action is not None and (limit.pending_key is None or not _empty_action(action)):
        return AIDecision(action=action, reasoning='Best checked move scored within the interactive AI budget')
    if (limit.pending_key is None and len(offers) == 1
            and offers[0].get('type') in {'pass_priority', 'play_land'}):
        action = _checked(limit.authoritative, limit.player_id, offers[0])
        if action is not None:
            return AIDecision(action=action, reasoning='Single checked offer after interactive AI budget exhaustion')
    return None


def _empty_action(action):
    kind = action['type']
    return (kind == 'pass_priority'
            or kind == 'attack' and not action['attackers']
            or kind == 'block' and not any(action['blocks'].values())
            or kind == 'choose_mechanic' and (
                action.get('choice_id') in {'decline', 'skip', 'no', 'none', 'cancel', 'pass'}
                or action.get('card_ids') == []))


def choose_for_autoplay(agent, state, offers, player_id):
    return choose_with_budget(agent, state, offers, player_id,
                              nodes=_limit('MTG_AI_INTERACTIVE_NODES'),
                              milliseconds=_limit('MTG_AI_INTERACTIVE_MS'))


def choose_with_budget(agent, state, offers, player_id, *, nodes, milliseconds, on_cutoff=None):
    if nodes is None and milliseconds is None:
        return agent.choose_action(state, offers, player_id)
    counts = getattr(agent, '_main_pass_signature_counts', None)
    prior_counts = counts.copy() if type(counts) is dict else None
    deadline = None if milliseconds is None else monotonic() + milliseconds / 1000
    limit = _Budget(nodes, deadline, state, player_id)
    token = _active.set(limit)
    try:
        limit.check()
        return agent.choose_action(state, offers, player_id)
    except _Exhausted as exc:
        reason = str(exc)
        if prior_counts is not None:
            counts.clear()
            counts.update(prior_counts)
        _log.debug('Interactive AI stopped at %s', reason)
    finally:
        _active.reset(token)
    decision = _after_cutoff(limit, offers)
    if on_cutoff is not None:
        on_cutoff(reason, limit.best_action is not None)
    return decision
