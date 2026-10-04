"""Bank idle main-phase mana without displacing a chosen play or known answer."""
from game_state.state import Step
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.costs import collect_cost_options
from rules_engine.foretell import take_special_action
from ai.pending_effects import planning_copy


def idle_foretell_action(agent, state, moves, player_id):
    moves = [move for move in moves if move['type'] == 'foretell']
    if not moves:
        return None
    if (state.stack or state.active_player != player_id
            or state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}):
        return None
    answers = []
    for cid in state.players[player_id].hand:
        card = state.cards[cid]
        if {'counter', 'removal'} & agent._spell_tags(card):
            for option in collect_cost_options(state, player_id, card):
                if can_pay_with_pool_and_lands(state, player_id, option.mana_cost,
                                              spell_types=card.types, source_card_id=cid):
                    answers.append((cid, option.mana_cost, card.types))
    candidates = []
    for move in moves:
        if move['type'] != 'foretell':
            continue
        cid = move['card_id']
        if any(answer[0] == cid for answer in answers):
            continue
        sim = planning_copy(state)
        if not take_special_action(sim, player_id, cid):
            continue
        if any(not can_pay_with_pool_and_lands(sim, player_id, cost, spell_types=types, source_card_id=source)
               for source, cost, types in answers):
            continue
        sim.turn += 1
        from rules_engine.mana import mana_value
        options = collect_cost_options(sim, player_id, sim.cards[cid])
        # X spells need tactical sizing; do not bank them by treating X as zero.
        prices = [option.mana_cost for option in options if '{X}' not in option.mana_cost.upper()]
        if not prices:
            continue
        saving = mana_value(state.cards[cid].mana_cost) - min(map(mana_value, prices))
        if saving > 0:
            candidates.append((saving, state.cards[cid].name, cid))
    if not candidates:
        return None
    _, _, cid = max(candidates)
    return {'type': 'foretell', 'card_id': cid}
