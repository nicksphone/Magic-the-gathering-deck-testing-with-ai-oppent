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
