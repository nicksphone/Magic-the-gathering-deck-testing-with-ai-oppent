"""Complete ownership-conditioned end-step draws with an intervening if."""
import re

from game_state.state import Zone
from rules_engine.spell_cost_clauses import NUMBERS


COUNT = r'(?:[0-9]+|' + '|'.join(NUMBERS) + r')'
CANDIDATE = re.compile(
    r"At the beginning of your end step, if you control [^,\n]*\bpermanents you don't own\b", re.I)
CLAUSE = re.compile(
    rf"At the beginning of your end step, if you control (?P<threshold>{COUNT}) "
    rf"or more permanents you don't own, draw (?P<amount>{COUNT}) cards?\.", re.I)


def compile_clause(text):
    match = CLAUSE.fullmatch(text.strip())
    if match is None:
        return None
    return {key: int(value) if value.isdigit() else NUMBERS[value.lower()]
            for key, value in match.groupdict().items()}


def condition_holds(state, controller, threshold):
    return sum(
        card is not None and card.zone == Zone.BATTLEFIELD and card.controller == controller
        and card.owner in state.players and card.owner != controller
        for cid in set(state.players[controller].battlefield)
        for card in [state.cards.get(cid)]
    ) >= threshold


def collect(state, card, raw_oracle):
    clauses = [line.strip() for line in raw_oracle.splitlines() if CANDIDATE.search(line)]
    if not clauses:
        return None
    triggers = []
    for clause in clauses:
        data = compile_clause(clause)
        key = 'ownership_end_step_draw'
        if data is None:
            key, data = 'noop', {'__unsupported_trigger_instruction': clause}
        elif not condition_holds(state, card.controller, data['threshold']):
            continue
        triggers.append({'source_card_id': card.id, 'controller': card.controller,
                         'label': f'{card.name} end-step trigger', 'effect_key': key,
                         'payload': data})
    return triggers


def resolve(state, controller, payload):
    # Check once on entry; draw_cards owns every per-card replacement/resume.
    if condition_holds(state, controller, payload['threshold']):
        from effects.registry import resolve_effect
        resolve_effect(state, controller, 'draw_cards', {**payload, 'target_player': controller})


def route_end_step(state, card, raw_oracle, active_player):
    paragraphs = [line.strip() for line in raw_oracle.splitlines()]
    if not any(CANDIDATE.search(clause) for clause in paragraphs):
        return None
    triggers, legacy = [], []
    for clause in paragraphs:
        text = clause.lower()
        eligible = (text.startswith(('at the beginning of each end step,',
                                     'at the beginning of end step,'))
                    or text.startswith('at the beginning of your end step,')
                    and card.controller == active_player)
        if not eligible:
            continue
        if CANDIDATE.search(clause):
            triggers.extend(collect(state, card, clause) or [])
        else:
            legacy.append(clause)
    return triggers, legacy
