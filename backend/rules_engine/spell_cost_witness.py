"""Lazy fixed additional-cost selections; exhaustive payments stay post-mana."""
from itertools import combinations


def fixed_cost_selections(state, player_id, card_id, option, x_value=0):
    from rules_engine.costs import additional_cost_candidates, additional_cost_selection

    candidates = additional_cost_candidates(state, player_id, card_id, option)
    discard_count = 0 if option.discard_all else option.discard_cards + (x_value if option.discard_x else 0)
    sacrifice_count = 0 if option.sacrifice_all else option.sacrifice_creatures
    if discard_count < 0 or sacrifice_count < 0:
        return
    for discards in combinations(candidates['discard_card_ids'], discard_count):
        for sacrifices in combinations(candidates['sacrifice_card_ids'], sacrifice_count):
            choice = {'discard_card_ids': list(discards), 'sacrifice_card_ids': list(sacrifices)}
            exiles = [cid for cid in candidates.get('exile_card_ids', []) if cid not in discards and cid not in sacrifices]
            # This closed family has no mandatory hand/type cost; count prefixes bound
            # price witnesses, while exact supplied IDs are validated independently.
            counts = range(min(len(exiles), 250) + 1) if option.hand_exile_color else range(1)
            for count in counts:
                if option.hand_exile_color:
                    choice['exile_card_ids'] = exiles[:count]
                selected = additional_cost_selection(state, player_id, option, card_id, choice, x_value=x_value)
                if selected is None:
                    continue
                # Validation reuses the same candidates/prohibitions as payment,
                # but exhaustive resources must not be reserved before mana.
                witness = {key: [] if exhaustive else selected[key] for key, exhaustive in (
                    ('discard_card_ids', option.discard_all), ('sacrifice_card_ids', option.sacrifice_all))}
                if option.hand_exile_color:
                    witness['exile_card_ids'] = selected['exile_card_ids']
                yield witness


class _BoundedPaymentPostcondition:
    def __init__(self, predicate, valid=True, max_nodes=4096, budget=None, pending=(), recipe=None):
        self.predicate = predicate
        self.valid = valid
        self.max_nodes = max_nodes
        self.budget = budget if budget is not None else {'nodes': 0, 'exhausted': False}
        self.pending = tuple(pending)
        self.recipe = recipe

    def visit(self):
        if not self.valid:
            return False
        if self.budget['nodes'] >= self.max_nodes:
            self.budget['exhausted'] = True
            return False
        self.budget['nodes'] += 1
        return True

    def with_pending(self, ids):
        return _BoundedPaymentPostcondition(self.predicate, self.valid, self.max_nodes,
                                           self.budget, tuple(ids), self.recipe)

    def __call__(self, state):
        if self.recipe is not None:
            return self.valid and _escape_viable(state, self.recipe, self.pending)
        return self.valid and self.predicate(state, self.pending)


def escape_payment_condition(player_id, card_id, count, selected=None, *, max_nodes=4096):
    valid = type(count) is int and count >= 0 and (selected is None or (
        isinstance(selected, list) and len(selected) == count
        and all(isinstance(cid, str) for cid in selected)
        and len(set(selected)) == count and card_id not in selected))
    frozen = tuple(selected) if valid and selected is not None else None

    return _BoundedPaymentPostcondition(None, valid, max_nodes, recipe={
        'kind': 'escape', 'player_id': player_id, 'card_id': card_id,
        'count': count, 'selected': frozen})


def _escape_viable(state, recipe, pending):
    from rules_engine.alternative_casts import validate_escape_exiles
    from rules_engine.zone_actions import is_departed_token
    player_id, card_id, count = recipe['player_id'], recipe['card_id'], recipe['count']
    frozen = recipe['selected']
    ids = list(frozen) if frozen is not None else [
        cid for cid in state.players[player_id].graveyard
        if cid != card_id and cid not in pending and not is_departed_token(state.cards[cid])][:count]
    return not set(ids).intersection(pending) and validate_escape_exiles(
        state, player_id, card_id, count, ids) is not None


def escape_fuel_proven_impossible(state, player_id, condition):
    """Negative proof for closed boards where paying mana cannot add fuel."""
    from game_state.state import CardInstance, MatchState, Zone
    from rules_engine.costs import parse_activated_cost
    from rules_engine.mana import _nonland_mana_effect_outputs
    from rules_engine.oracle_effects import ACTIVATED_ABILITY_RE
    from rules_engine.oracle_text import without_reminder_text
    from rules_engine.state_based_actions import _is_legendary
    from rules_engine.zone_actions import is_departed_token

    if (type(condition) is not _BoundedPaymentPostcondition
            or condition.predicate is not None or condition.valid is not True
            or type(condition.recipe) is not dict
            or set(condition.recipe) != {'kind', 'player_id', 'card_id', 'count', 'selected'}
            or type(state) is not MatchState):
        return False
    recipe = condition.recipe
    if (recipe['kind'] != 'escape' or type(player_id) is not int
            or type(recipe['player_id']) is not int or type(recipe['card_id']) is not str
            or recipe['player_id'] != player_id or player_id not in state.players
            or type(recipe['count']) is not int or recipe['count'] < 0
            or type(condition.pending) is not tuple
            or any(type(cid) is not str for cid in condition.pending)
            or recipe['selected'] is not None and (
                type(recipe['selected']) is not tuple
                or any(type(cid) is not str for cid in recipe['selected']))
            or recipe['card_id'] not in state.players[player_id].graveyard):
        return False
    pending = set(condition.pending)
    eligible = sum(cid != recipe['card_id'] and cid not in pending
                   and not is_departed_token(state.cards[cid])
                   for cid in state.players[player_id].graveyard)
    if eligible >= recipe['count']:
        return False
    if any(getattr(state, field) for field in (
            'stack', 'delayed_triggers', 'staged_triggers', 'trigger_staging',
            'pending_trigger_order', 'pending_mechanic_choice', 'pending_replacement_choice',
            'mana_continuation', 'emblems', 'temporary_control_changes', 'linked_exiles',
            'pending_entry_counters', 'retained_counter_prohibitions', 'combat_cost_effects',
            'cleanup_deferred_triggers')):
        return False
    for player in state.players.values():
        if player.life <= 0 or player.poison >= 10 or player.counters:
            return False
        for cid in player.battlefield:
            card = state.cards[cid]
            if (type(card) is not CardInstance or card.zone != Zone.BATTLEFIELD
                    or card.controller != player.id or _is_legendary(card)
                    or set(card.types) - {'Artifact', 'Creature', 'Land', 'Token', 'Basic', 'Snow'}
                    or any(type(keyword) is not str or keyword.lower() not in {'flying', 'haste'}
                           for keyword in card.keywords)
                    or card.layout not in ('', 'normal', 'token')
                    or card.control_effect_base is not None or card.type_effect_base is not None
                    or any(getattr(card, field) for field in (
                        'counters', 'type_effects', 'keyword_effects', 'base_stat_effects',
                        'control_effects', 'printed_characteristics', 'bestow_characteristics',
                        'attached_to', 'card_faces', 'suspend_haste', 'granted_flashback'))
                    or 'Creature' in card.types and (
                        type(card.toughness) is not int or card.toughness <= 0
                        or card.printed_toughness not in (None, str(card.toughness)))):
                return False
            # Inspect every clause, not just the subset recognized as mana abilities.
            # Empty land text retains the native intrinsic tap-mana abilities.
            for line in without_reminder_text(card.oracle_text).splitlines():
                line = line.strip()
                if not line or line.lower() in {'flying', 'haste'}:
                    continue
                match = ACTIVATED_ABILITY_RE.fullmatch(line)
                if match is None:
                    return False
                cost = parse_activated_cost(match[1])
                if (not cost.supported or cost.pay_life or cost.discard_cards
                        or cost.discard_source or cost.remove_source_counters
                        or (cost.sacrifice_source or cost.sacrifice_creatures) and not (
                            card.is_token and cost.sacrifice_source
                            and cost.sacrifice_creatures <= 1)
                        or not _nonland_mana_effect_outputs(match[2], state=state, card=card)):
                    return False
    return True


def export_payment_condition(condition):
    if (type(condition) is not _BoundedPaymentPostcondition
            or condition.predicate is not None or condition.recipe is None):
        raise ValueError('Payment condition has no native transport')
    value = {**condition.recipe, 'selected': (list(condition.recipe['selected'])
             if condition.recipe['selected'] is not None else None),
             'pending': list(condition.pending), 'valid': condition.valid,
             'max_nodes': condition.max_nodes, 'budget': dict(condition.budget)}
    restore_payment_condition(value)
    return value


def restore_payment_condition(value):
    if (type(value) is not dict or set(value) != {
            'kind', 'player_id', 'card_id', 'count', 'selected', 'pending',
            'valid', 'max_nodes', 'budget'} or value['kind'] != 'escape'
            or type(value['player_id']) is not int
            or type(value['card_id']) is not str or not value['card_id']
            or type(value['count']) is not int or value['count'] < 0
            or type(value['valid']) is not bool
            or type(value['max_nodes']) is not int or value['max_nodes'] < 0
            or type(value['budget']) is not dict
            or set(value['budget']) != {'nodes', 'exhausted'}
            or type(value['budget']['nodes']) is not int
            or not 0 <= value['budget']['nodes'] <= value['max_nodes']
            or type(value['budget']['exhausted']) is not bool
            or value['budget']['exhausted'] and value['budget']['nodes'] != value['max_nodes']):
        raise ValueError('Invalid native payment condition')
    for ids in (value['selected'], value['pending']):
        if ids is not None and (type(ids) is not list
                or any(type(cid) is not str or not cid for cid in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('Invalid native payment recipe')
    if (value['pending'] is None or value['selected'] is not None and (
            len(value['selected']) != value['count'] or value['card_id'] in value['selected'])):
        raise ValueError('Invalid native escape selection')
    recipe = {key: value[key] for key in ('kind', 'player_id', 'card_id', 'count')}
    recipe['selected'] = tuple(value['selected']) if value['selected'] is not None else None
    return _BoundedPaymentPostcondition(None, value['valid'], value['max_nodes'],
        dict(value['budget']), tuple(value['pending']), recipe)
