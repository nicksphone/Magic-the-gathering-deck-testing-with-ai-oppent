"""Whole-clause Revolt destruction and Delirium damage, not a general if parser."""
import re

from game_state.state import Zone, object_incarnation
from rules_engine.card_types import graveyard_card_types
from rules_engine.mana import mana_value
from rules_engine.oracle_text import without_reminder_text


DESTRUCTION = re.compile(
    r'Destroy target creature if it has mana value (\d+) or less\.\s*'
    r'Revolt\s*[\u2014-]\s*Destroy that creature if it has mana value (\d+) or less '
    r'instead if a permanent left the battlefield under your control this turn\.', re.I)
DAMAGE = re.compile(
    r"(?P<subject>[\w ,'-]+) deals (?P<normal>\d+) damage to target creature or planeswalker\.\s*"
    r'Delirium\s*[\u2014-]\s*(?P=subject) deals (?P<enhanced>\d+) damage instead '
    r'if there are four or more card types among cards in your graveyard\.', re.I)
MARKER = re.compile(
    r'(?:^|\n)\s*(?:Revolt\s*[\u2014-]\s*Destroy\b|'
    r'Delirium\s*[\u2014-][^\n]*\bdeals?\b[^\n]*\bdamage\b)', re.I)


def parse_instruction(text, card_name=''):
    text = without_reminder_text(text or '').strip()
    match = DESTRUCTION.fullmatch(text)
    if match:
        return {'condition': 'permanent_departure', 'effect_key': 'destroy_permanent',
                'normal': int(match[1]), 'enhanced': int(match[2])}
    match = DAMAGE.fullmatch(text)
    if match and (not card_name or match['subject'].casefold() in {card_name.casefold(), 'this spell'}):
        return {'condition': 'graveyard_types', 'effect_key': 'deal_damage',
                'normal': int(match['normal']), 'enhanced': int(match['enhanced'])}
    return None


def instruction_gaps(text, card_name=''):
    if MARKER.search(without_reminder_text(text or '')) and parse_instruction(text, card_name) is None:
        return ['unsupported resolution conditional instruction']
    return []


def conditional_effect(state, text, card_name, targets):
    instruction = parse_instruction(text, card_name)
    if instruction is None:
        return None
    payload = {**instruction, 'target_card_id': targets.get('target_card_id')}
    capture_target(state, payload)
    return 'conditional_instruction', payload


def capture_target(state, payload):
    target = state.cards.get(payload.get('target_card_id'))
    if target is not None:
        payload['__conditional_target_reference'] = [target.id, object_incarnation(target), target.zone_change_sequence]


def target_is_current(state, payload):
    target = state.cards.get(payload.get('target_card_id'))
    return (target is not None and target.zone == Zone.BATTLEFIELD
            and payload.get('__conditional_target_reference') ==
            [target.id, object_incarnation(target), target.zone_change_sequence])


def selected_instruction(state, controller, payload):
    condition = payload['condition']
    if condition == 'permanent_departure':
        enhanced = controller in state.players_with_permanent_departure
    elif condition == 'graveyard_types':
        enhanced = len(graveyard_card_types(state, [controller])) >= 4
    else:
        raise ValueError('Unknown resolution condition')
    value = payload['enhanced' if enhanced else 'normal']
    key = payload['effect_key']
    data = {name: value for name, value in payload.items()
            if name not in {'condition', 'effect_key', 'normal', 'enhanced'}}
    if key == 'destroy_permanent':
        target = state.cards.get(payload.get('target_card_id'))
        if target is None or target.zone != Zone.BATTLEFIELD or mana_value(target.mana_cost) > value:
            return 'noop', data
    elif key == 'deal_damage':
        data['amount'] = value
    else:
        raise ValueError('Unknown conditional instruction')
    return key, data


def resolve_instruction(state, controller, payload):
    from effects.registry import resolve_effect
    if not target_is_current(state, payload):
        return
    key, data = selected_instruction(state, controller, payload)
    resolve_effect(state, controller, key, data)
