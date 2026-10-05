"""Resource transitions shared by costs, combat, and resolving effects."""
from copy import copy
import re

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text


def tap_permanents(state, card_ids):
    """Entering tapped is not a tap event; only an untapped battlefield object changes."""
    changed = []
    for cid in dict.fromkeys(card_ids):
        card = state.cards.get(cid)
        if card is not None and card.zone == Zone.BATTLEFIELD and not card.tapped:
            from rules_engine.mana_triggers import record_mana_tap
            record_mana_tap(state, card)
            card.tapped = True
            changed.append({'card_id': cid, 'controller': card.controller})
    if changed:
        from rules_engine.events import emit_event_batch
        emit_event_batch(state, 'becomes_tapped', changed)


def collect_tap_triggers(state, payload):
    card = state.cards.get(payload.get('card_id'))
    if card is None or card.zone != Zone.BATTLEFIELD:
        return []
    # Check the clause before querying layers: basic land mana taps are the hot path.
    names = [card.name, card.name.split(',')[0], 'this creature', 'this artifact', 'this permanent']
    subject = '|'.join(re.escape(name) for name in names)
    clauses = re.findall(r'(?:^|\n)Whenever (?:' + subject + r') becomes tapped, ([^\n]+)',
                         without_reminder_text(card.oracle_text or ''), re.I)
    if not clauses:
        return []
    from rules_engine.continuous import printed_abilities_suppressed
    if printed_abilities_suppressed(state, card.id):
        return []
    from rules_engine.oracle_effects import infer_effect_from_oracle
    triggers = []
    for instruction in clauses:
        proxy = copy(card)
        proxy.oracle_text, proxy.card_faces, proxy.types = instruction, [], []
        key, data = infer_effect_from_oracle(state, proxy, card.controller)
        triggers.append({'source_card_id': card.id, 'controller': card.controller,
                         'label': f'{card.name} tap trigger', 'effect_key': key, 'payload': data})
    return triggers


GRAVEYARD_LEAVE_RE = re.compile(
    r'(?:^|\n)Whenever (one or more|a|an) (creature )?cards? leaves? your graveyard, ([^\n]+)', re.I)


def capture_graveyard_departures(state, card_ids):
    """Look back before movement, including which battlefield abilities existed then."""
    from rules_engine.card_types import is_token_card
    from rules_engine.type_effects import effective_types
    from rules_engine.continuous import printed_abilities_suppressed
    departed = [state.cards[cid] for cid in dict.fromkeys(card_ids)
                if cid in state.cards and state.cards[cid].zone == Zone.GRAVEYARD
                and cid in state.players[state.cards[cid].owner].graveyard
                and not is_token_card(state.cards[cid])]
    if not departed:
        return []
    captured = []
    for player in state.players.values():
        for cid in player.battlefield:
            card = state.cards[cid]
            clauses = list(GRAVEYARD_LEAVE_RE.finditer(without_reminder_text(card.oracle_text or '')))
            if not clauses or printed_abilities_suppressed(state, cid):
                continue
            for clause in clauses:
                matching = [other for other in departed if other.owner == card.controller
                            and (not clause[2] or 'Creature' in effective_types(state, other))]
                count = min(1, len(matching)) if clause[1].lower() == 'one or more' else len(matching)
                for _ in range(count):
                    proxy = copy(card)
                    proxy.oracle_text, proxy.card_faces, proxy.types = clause[3], [], []
                    captured.append(proxy)
    return captured


def emit_graveyard_departures(state, captured):
    from rules_engine.oracle_effects import infer_effect_from_oracle
    from rules_engine.events import _push_triggers
    triggers = []
    for proxy in captured:
        key, data = infer_effect_from_oracle(state, proxy, proxy.controller)
        triggers.append({'source_card_id': proxy.id, 'controller': proxy.controller,
                         'label': f'{proxy.name} graveyard departure trigger',
                         'effect_key': key, 'payload': data})
    _push_triggers(state, 'leaves_graveyard', triggers)
