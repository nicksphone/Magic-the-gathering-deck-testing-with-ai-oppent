"""Fixed, targetless triggered mana: capture at the mana tap, resolve immediately."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import re

from game_state.state import Zone, object_incarnation

_activation = ContextVar('mana_tap_activation', default=None)


@lru_cache(maxsize=4096)
def fixed_mana_clauses(text):
    from rules_engine.oracle_text import without_reminder_text
    rows = []
    for line in without_reminder_text(text or '').splitlines():
        own = re.fullmatch(r'Whenever you tap (?:a|an) (land|creature|artifact|permanent|Plains|Island|Swamp|Mountain|Forest) for mana, add (?:an additional )?((?:\{[WUBRGC]\})+)\.', line.strip(), re.I)
        aura = re.fullmatch(r'Whenever enchanted land is tapped for mana, its controller adds (?:an additional )?((?:\{[WUBRGC]\})+)\.', line.strip(), re.I)
        if own or aura:
            symbols = re.findall(r'\{([WUBRGC])\}', (own[2] if own else aura[1]).upper())
            rows.append((own[1].lower() if own else 'enchanted land',
                         tuple((color, symbols.count(color)) for color in sorted(set(symbols)))))
    return tuple(rows)


def fixed_mana_triggers(state, tapped):
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.land_types import has_land_type
    from rules_engine.type_effects import effective_types
    from rules_engine.mana import is_snow_source
    triggers = []
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            clauses = fixed_mana_clauses(source.oracle_text)
            if not clauses or source.zone != Zone.BATTLEFIELD:
                continue
            matching = []
            for subject, outputs in clauses:
                if subject == 'enchanted land':
                    match = source.attached_to == tapped.id and 'Land' in effective_types(state, tapped)
                elif source.controller != tapped.controller:
                    match = False
                elif subject in {'plains', 'island', 'swamp', 'mountain', 'forest'}:
                    match = 'Land' in effective_types(state, tapped) and has_land_type(state, tapped, subject)
                else:
                    match = subject == 'permanent' or subject.title() in effective_types(state, tapped)
                if match:
                    matching.append(outputs)
            if matching and not printed_abilities_suppressed(state, cid):
                for outputs in matching:
                    triggers.append((tapped.controller, cid, object_incarnation(source), is_snow_source(source), dict(outputs)))
    return triggers


def has_fixed_mana_triggers(state):
    return any(fixed_mana_clauses(state.cards[cid].oracle_text)
               for player in state.players.values() for cid in player.battlefield)


@contextmanager
def mana_tap_scope(state, card):
    captured = []
    token = _activation.set((state, card.id, object_incarnation(card), captured))
    try:
        yield captured
    finally:
        _activation.reset(token)


def record_mana_tap(state, card):
    scope = _activation.get()
    if scope is not None and scope[0] is state and scope[1:3] == (card.id, object_incarnation(card)):
        scope[3].extend(fixed_mana_triggers(state, card))


def resolve_mana_triggers(state, captured):
    # Captured controller/incarnation/snow provenance survives activation-cost departures.
    for pid, _, _, snow, outputs in captured:
        player = state.players[pid]
        for color, amount in outputs.items():
            player.mana_pool[color] = player.mana_pool.get(color, 0) + amount
            if snow:
                player.snow_mana_pool[color] = player.snow_mana_pool.get(color, 0) + amount
        state.log.append(f'{player.name} adds ' + ', '.join(f'{amount} {color}' for color, amount in outputs.items())
                         + ' from a triggered mana ability.')
