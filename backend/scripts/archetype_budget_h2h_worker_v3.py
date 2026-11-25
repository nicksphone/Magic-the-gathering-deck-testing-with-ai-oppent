"""Private worker role for the seat-specific Master budget experiment."""
from scripts.archetype_plan_v3 import BUDGET_H2H_KIND, BUDGET_H2H_LIMITS


def choose_for_cell(decks, cell):
    from ai.agent import AIAgent
    from ai.deck_analysis import guess_archetype
    from ai.interactive_budget import choose_with_budget
    from scripts.archetype_game_v3 import BudgetDecision

    profiles = [guess_archetype(deck) for deck in decks]
    agents = {seat: AIAgent(difficulty='master', archetype=profiles[seat-1], opponent_archetype=profiles[2-seat])
              for seat in (1, 2)}

    def choose(state, offers, player_id):
        agent = agents[player_id]
        if player_id != cell['deck_a_seat']:
            return BudgetDecision(agent.choose_action(state, offers, player_id))
        cutoff = []

        def record(reason, retained):
            cutoff.extend((reason, retained))

        result = choose_with_budget(agent, state, offers, player_id, **BUDGET_H2H_LIMITS, on_cutoff=record)
        return BudgetDecision(result, *cutoff)

    return choose


if __name__ == '__main__':
    from scripts.archetype_worker_v3 import main
    raise SystemExit(main(kind=BUDGET_H2H_KIND))
