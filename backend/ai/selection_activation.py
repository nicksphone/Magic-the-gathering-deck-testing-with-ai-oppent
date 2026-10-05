"""Bounded paid-selection priors; no hypothetical cards or executable choices."""
from math import comb
import re
from typing import TypedDict

from ai.heuristics import evaluate_board
from ai.information import draw_resource_forecast, is_unknown
from ai.pending_effects import planning_copy
from card_data.tactical import tactical_tags
from game_state.state import StackItem
from rules_engine.action_validation import ActionRejected
from rules_engine.costs import parse_activated_cost
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands, mana_value
from rules_engine.oracle_effects import extract_activated_abilities, _parse_count_token
from rules_engine.type_effects import effective_types


class SelectionActivationPlan(TypedDict):
    expected_hand_cards: float | None
    population: int | None
    eligible_population: int | None
    inspected_count: int
    public_cost_delta: float
    loses_known_interaction: bool


def _schema(ability):
    match = re.fullmatch(
        r'look at the top (one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards? of your library\. '
        r'you may reveal a creature card with mana value (\d+) or less from among them '
        r'and put it into your hand\. put the rest on the bottom of your library in a random order\.?',
        ability['text'], re.I)
    cost = parse_activated_cost(ability['mana_cost'])
    if (match is None or not cost.supported or cost.pay_life or cost.discard_cards
            or cost.discard_source or cost.sacrifice_creatures or cost.sacrifice_source
            or '{X}' in cost.mana_cost):
        return None
    return {'top_n': _parse_count_token(match[1].lower()), 'mv_max': int(match[2]),
            'optional': True, 'bottom_random': True, 'bottom_any_order': False}


def _prior(state, player_id, payload):
    count = min(payload['top_n'], len(state.players[player_id].library))
    prior = draw_resource_forecast(state, player_id, 0)
    if prior is None:
        return {'expected_hand_cards': None, 'population': None,
                'eligible_population': None, 'inspected_count': count}
    population = prior['population']
    eligible = sum(row['count'] for row in prior['inventory']
                   if 'Creature' in row['type_line'].split()
                   and mana_value(row['mana_cost'] or '') <= payload['mv_max'])
    probability = 1 - comb(population - eligible, count) / comb(population, count) if count else 0.0
    return {'expected_hand_cards': probability, 'population': population,
            'eligible_population': eligible, 'inspected_count': count}


def _payable_interaction(state, player_id, card):
    return (not is_unknown(card) and 'Instant' in effective_types(state, card)
            and bool(tactical_tags(card.oracle_text) & {'counter', 'removal'})
            and can_pay_with_pool_and_lands(state, player_id, card.mana_cost,
                card_name=card.name, spell_types=set(effective_types(state, card)),
                oracle_text=card.oracle_text))


def selection_activation_plan(state, move, player_id) -> SelectionActivationPlan | None:
    """Evaluate an admitted paid action without resolving a hidden inspection.

    None means unsupported/illegal, not a bad card. A None probability means an
    unavailable prior, not zero eligible cards. Costs are actual engine payments.
    """
    if (getattr(state, 'ai_information_player', None) != player_id
            or move.get('type') != 'activate_ability' or state.winner is not None):
        return None
    source = state.cards.get(move.get('card_id'))
    if source is None or is_unknown(source):
        return None
    ability = next((a for a in extract_activated_abilities(source)
                    if a['index'] == move.get('ability_index')), None)
    if ability is None or (move.get('ability_label', ability['label']) != ability['label']
                          or move.get('mana_cost', ability['mana_cost']) != ability['mana_cost']):
        return None
    payload = _schema(ability)
    if payload is None:
        return None
    branch = planning_copy(state)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': ability['index']}
    try:
        RulesEngine().take_action(branch, player_id, action, reject_invalid=True)
    except ActionRejected:
        return None
    item = branch.stack[-1] if branch.stack else None
    if item is None or item.effect_key != 'topdeck_reveal_creature_to_hand' or any(
            item.payload.get(k) != v for k, v in payload.items()):
        return None
    facts = _prior(state, player_id, payload)
    # Unsettled responses need a joint prior; do not grant proactive acquisition value.
    if state.stack or state.pending_mechanic_choice or state.pending_replacement_choice:
        facts['expected_hand_cards'] = None
    responses = [state.cards[c] for c in state.players[player_id].hand
                 if _payable_interaction(state, player_id, state.cards[c])]
    loses = (bool(responses) and not any(_payable_interaction(branch, player_id, c) for c in responses)
             and state.step.value not in {'end_step', 'cleanup'})
    return {**facts, 'public_cost_delta': evaluate_board(branch, player_id) - evaluate_board(state, player_id),
            'loses_known_interaction': loses}


def selection_activation_score(plan, *, hand_value, interaction_reservation):
    """Consumer-weighted marginal value, replacing flat selection bonuses."""
    return (plan['public_cost_delta'] + (plan['expected_hand_cards'] or 0.0) * hand_value
            - (interaction_reservation if plan['loses_known_interaction'] else 0.0))


def pending_selection_expectation(state, player_id) -> float | None:
    """One unresolved own activation's fractional acquisition, never game state."""
    if getattr(state, 'ai_information_player', None) != player_id or state.winner is not None:
        return None
    items = list(state.stack)
    choice = state.pending_mechanic_choice
    if choice:
        if (choice.get('kind') != 'topdeck_reveal_creature' or choice.get('player_id') != player_id
                or not isinstance(choice.get('resolving_item'), dict)
                or any(choice.get(k) for k in ('remaining_effects', 'counter_continuation_queue',
                                              'draw_continuation_queue', 'remaining_draws'))):
            return None
        try:
            items.insert(0, StackItem(**choice['resolving_item']))
        except (TypeError, ValueError):
            return None
    if len(items) != 1 or state.pending_replacement_choice or state.pending_trigger_order:
        return None
    item = items[0]
    if item.controller != player_id or item.effect_key != 'topdeck_reveal_creature_to_hand':
        return None
    source = state.cards.get(item.source_card_id)
    if source is None or is_unknown(source) or item.payload.get('__copied_card'):
        return None
    ability = next((a for a in extract_activated_abilities(source)
                    if a['text'] == item.payload.get('__ability_target_text')), None)
    payload = _schema(ability) if ability else None
    if payload is None or any(item.payload.get(k) != v for k, v in payload.items()):
        return None
    if (item.payload.get('target_restrictions') != {'mana_value_max': payload['mv_max']}
            or any(not k.startswith('__') and k not in {*payload, 'target_restrictions'}
                   for k in item.payload)):
        return None
    return _prior(state, player_id, payload)['expected_hand_cards']
