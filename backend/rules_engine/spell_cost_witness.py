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
            selected = additional_cost_selection(state, player_id, option, card_id, choice, x_value=x_value)
            if selected is not None:
                # Validation reuses the same candidates/prohibitions as payment,
                # but exhaustive resources must not be reserved before mana.
                yield {key: [] if exhaustive else selected[key] for key, exhaustive in (
                    ('discard_card_ids', option.discard_all), ('sacrifice_card_ids', option.sacrifice_all))}
