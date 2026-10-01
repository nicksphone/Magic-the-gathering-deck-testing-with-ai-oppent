from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar

from rules_engine.continuous import has_keyword
from rules_engine.replacement import player_cant_lose_life


_damage_counters = ContextVar('damage_counters', default=None)


@contextmanager
def collect_damage_counters(state):
    """Collect simultaneous results without leaking into another match or AI copy."""
    packets = []
    token = _damage_counters.set((state, packets))
    try:
        yield packets
    finally:
        _damage_counters.reset(token)


def flush_damage_counters(state, packets):
    grouped = {}
    for event in packets:
        payload = event['payload']
        key = (event['controller'], event['effect_key'], payload.get('target_player'),
               payload.get('target_card_id'), payload['counter'],
               payload.get('__counter_is_effect', False))
        if key not in grouped:
            grouped[key] = {**event, 'payload': dict(payload)}
        else:
            grouped[key]['payload']['amount'] += payload['amount']
            if grouped[key]['payload'].get('__counter_reason') != payload.get('__counter_reason'):
                grouped[key]['payload']['__counter_reason'] = 'infect/toxic'
    for event in grouped.values():
        queue_damage_counters(state, event['controller'], event['effect_key'], event['payload'])


def source_has_keyword(state, source_id: str | None, keyword: str, source_lki: dict | None = None) -> bool:
    if source_lki is not None:
        return keyword in {str(value).lower() for value in source_lki.get("keywords", [])}
    return source_id in state.cards and has_keyword(state, source_id, keyword)


def damage_controller(state, source_id, source_lki=None, fallback=None):
    if source_lki and source_lki.get('controller') in state.players:
        return source_lki['controller']
    if source_id in state.cards:
        return state.cards[source_id].controller
    return fallback if fallback in state.players else state.active_player


def queue_damage_counters(state, controller, effect_key, payload):
    """Keep damage results inside one deferred-SBA event, preserving each placer."""
    from effects.registry import resolve_effect
    collector = _damage_counters.get()
    if collector is not None and collector[0] is state:
        collector[1].append({'controller': controller, 'effect_key': effect_key, 'payload': payload})
        return
    pending = state.pending_replacement_choice or state.pending_mechanic_choice
    if pending:
        pending.setdefault('counter_continuation_queue', []).append(
            {'controller': controller, 'effect_key': effect_key, 'payload': payload})
    else:
        resolve_effect(state, controller, effect_key, payload)


def apply_player_damage(state, player_id: int, amount: int, source_id: str | None, *, combat: bool = False,
                        source_lki: dict | None = None, controller=None, counter_is_effect=False) -> None:
    """Apply consequences of damage after replacements and prevention."""
    if amount <= 0:
        return
    player = state.players[player_id]
    placer = damage_controller(state, source_id, source_lki, controller)
    infect = source_has_keyword(state, source_id, "infect", source_lki)
    poison = amount if infect else 0
    reason = 'infect' if infect else 'toxic'
    if not infect and not player_cant_lose_life(state, player_id):
        player.life -= amount
    if combat and source_id in state.cards:
        toxic = sum(int(value) for value in re.findall(r"\btoxic\s+(\d+)", state.cards[source_id].oracle_text, re.IGNORECASE))
        if toxic:
            poison += toxic
            if infect:
                reason = 'infect/toxic'
    if poison:
        queue_damage_counters(state, placer, 'add_player_counters', {
            'target_player': player_id, 'counter': 'poison', 'amount': poison,
            '__counter_is_effect': counter_is_effect, '__counter_reason': reason})


def apply_creature_damage(state, card_id: str, amount: int, source_id: str | None,
                          *, source_lki: dict | None = None, controller=None, counter_is_effect=False) -> None:
    if amount <= 0:
        return
    card = state.cards[card_id]
    counter_damage = any(source_has_keyword(state, source_id, keyword, source_lki) for keyword in ("infect", "wither"))
    if counter_damage:
        queue_damage_counters(state, damage_controller(state, source_id, source_lki, controller),
                              'add_counters', {'target_card_id': card_id, 'counter': '-1/-1',
                                               'amount': amount, '__counter_is_effect': counter_is_effect})
    else:
        card.counters['__damage_marked'] = int(card.counters.get('__damage_marked', 0)) + amount
