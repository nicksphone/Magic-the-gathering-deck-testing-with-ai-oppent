"""Role-specific entry and deterministic random-offer policy for the strength run."""
import random
from types import SimpleNamespace

from scripts.archetype_trace_v3 import digest
from scripts.archetype_worker_v3 import main


def random_action(state, offers, player_id, *, rng, materialize, rules):
    from ai.action_contract import complete_action
    from rules_engine.action_validation import ActionRejected, checked_action

    candidates = {}
    for offer in offers:
        try:
            for proposed in materialize(offer):
                try:
                    action = complete_action(proposed)
                    checked_action(state, rules, player_id, action)
                except ActionRejected:
                    continue
                candidates.setdefault(digest(action), action)
        except ActionRejected:
            continue
    if not candidates:
        raise ActionRejected('Random-offer baseline has no complete checked action')
    return SimpleNamespace(action=rng.choice(list(candidates.values())),
                           reasoning='uniform over unique checked offer completions')


def choose_for_cell(decks, cell):
    from ai.agent import AIAgent
    from ai.deck_analysis import guess_archetype
    from ai.declaration_policy import finalize_declaration
    from ai.information import decision_view
    from rules_engine.engine import RulesEngine

    candidate = cell['deck_a_seat']
    opponent = cell['opponent']
    profiles = [guess_archetype(deck) for deck in decks]
    agents = {
        seat: AIAgent(difficulty='master' if seat == candidate else ('casual' if opponent == 'random' else opponent),
                      archetype=profiles[seat-1], opponent_archetype=profiles[2-seat])
        for seat in (1, 2)
    }
    rng = random.Random(int(digest({'seed': cell['seed'], 'deck': cell['deck_a'],
                                   'role': 'random_offer_v1'}), 16))
    rules = RulesEngine()

    def choose(state, offers, player_id):
        agent = agents[player_id]
        if opponent == 'random' and player_id != candidate:
            view, visible_offers = decision_view(state, player_id, offers)

            def complete_offer(offer):
                if offer['type'] == 'choose_mechanic':
                    # Some offers supply selectors rather than an action.
                    # Complex multi-card choices also get the built-in completion.
                    yield {'type': 'choose_mechanic', 'card_ids': []}
                    for option in offer.get('options', []):
                        if type(option) is str:
                            yield {'type': 'choose_mechanic', 'card_ids': [option]}
                            yield {'type': 'choose_mechanic', 'choice_id': option}
                    choice = agent.choose_action(state, [offer], player_id).action
                    if choice.get('type') == 'choose_mechanic':
                        yield choice
                else:
                    yield finalize_declaration(view, agent._materialize_action(view, offer, player_id))

            return random_action(state, visible_offers, player_id, rng=rng,
                                 materialize=complete_offer, rules=rules)
        return agent.choose_action(state, offers, player_id)

    return choose


if __name__ == '__main__':
    raise SystemExit(main(kind='strength'))
