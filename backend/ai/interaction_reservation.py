"""Shared affordable-hand interaction reservation, not idle-banking preferences."""
from rules_engine.costs import collect_cost_options
from rules_engine.mana import can_pay_with_pool_and_lands


def affordable_interactions(agent, state, player_id):
    answers = []
    for cid in state.players[player_id].hand:
        card = state.cards[cid]
        if {'counter', 'removal'} & agent._spell_tags(card):
            for option in collect_cost_options(state, player_id, card):
                if can_pay_with_pool_and_lands(state, player_id, option.mana_cost,
                                              spell_types=card.types, source_card_id=cid):
                    answers.append((cid, option.mana_cost, card.types))
    return answers


def preserves_interactions(projected, player_id, banked_card_id, answers):
    return all(source != banked_card_id and can_pay_with_pool_and_lands(
        projected, player_id, cost, spell_types=types, source_card_id=source)
        for source, cost, types in answers)
