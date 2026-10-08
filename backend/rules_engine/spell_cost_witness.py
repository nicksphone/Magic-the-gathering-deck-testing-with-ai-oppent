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
    def __init__(self, predicate, valid=True, max_nodes=4096, budget=None, pending=()):
        self.predicate = predicate
        self.valid = valid
        self.max_nodes = max_nodes
        self.budget = budget if budget is not None else {'nodes': 0, 'exhausted': False}
        self.pending = tuple(pending)

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
                                           self.budget, tuple(ids))

    def __call__(self, state):
        return self.valid and self.predicate(state, self.pending)


def escape_payment_condition(player_id, card_id, count, selected=None, *, max_nodes=4096):
    from rules_engine.alternative_casts import validate_escape_exiles
    from rules_engine.zone_actions import is_departed_token

    valid = type(count) is int and count >= 0 and (selected is None or (
        isinstance(selected, list) and len(selected) == count
        and all(isinstance(cid, str) for cid in selected)
        and len(set(selected)) == count and card_id not in selected))
    frozen = tuple(selected) if valid and selected is not None else None

    def viable(state, pending):
        ids = list(frozen) if frozen is not None else [
            cid for cid in state.players[player_id].graveyard
            if cid != card_id and cid not in pending and not is_departed_token(state.cards[cid])][:count]
        return not set(ids).intersection(pending) and validate_escape_exiles(
            state, player_id, card_id, count, ids) is not None

    return _BoundedPaymentPostcondition(viable, valid, max_nodes)
