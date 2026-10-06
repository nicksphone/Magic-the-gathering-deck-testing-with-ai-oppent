"""Fixed, targetless triggered mana: capture at the mana tap, resolve immediately."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import re

from game_state.state import Zone, object_incarnation

_activation = ContextVar('mana_tap_activation', default=None)


@lru_cache(maxsize=4096)
def produced_type_clauses(text):
    from rules_engine.oracle_text import without_reminder_text
    return sum(bool(re.fullmatch(
        r'Whenever (?:a player taps a land|a land is tapped) for mana, '
        r'(?:that player|its controller) adds (?:an additional )?one mana '
        r'of any type that land produced\.', line.strip(), re.I))
        for line in without_reminder_text(text or '').splitlines())


def _proven_tap_type(state, tapped):
    from rules_engine.costs import ActivatedCost, parse_activated_cost
    from rules_engine.mana_abilities import ability_outputs, mana_ability_specs
    colors = set()
    for spec in mana_ability_specs(tapped, state):
        cost = parse_activated_cost(spec[1])
        if not cost.tap_source:
            continue
        # Without the selected activation context, every possible tap must agree.
        # Departure costs and zero/unsupported outputs cannot prove production.
        if cost != ActivatedCost(tap_source=True):
            return None
        outputs = ability_outputs(state, tapped, spec)
        if len(outputs) != 1 or next(iter(outputs.values())) <= 0:
            return None
        colors.update(outputs)
    return next(iter(colors)) if len(colors) == 1 else None


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
    produced_type = None
    type_checked = False
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            clauses = fixed_mana_clauses(source.oracle_text)
            produced = produced_type_clauses(source.oracle_text)
            if not (clauses or produced) or source.zone != Zone.BATTLEFIELD:
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
            if (produced and 'Land' in effective_types(state, tapped)
                    and not printed_abilities_suppressed(state, cid)):
                if not type_checked:
                    produced_type = _proven_tap_type(state, tapped)
                    type_checked = True
                if produced_type is not None:
                    matching.extend([((produced_type, 1),)] * produced)
            if matching and not printed_abilities_suppressed(state, cid):
                for outputs in matching:
                    triggers.append((tapped.controller, cid, object_incarnation(source), is_snow_source(source), dict(outputs)))
    return triggers


def has_fixed_mana_triggers(state):
    return any(fixed_mana_clauses(state.cards[cid].oracle_text)
               or produced_type_clauses(state.cards[cid].oracle_text)
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
