"""Pure block-intent query batches preserve canonical combat semantics."""
import cProfile
import pickle
import pstats
import unittest
from unittest.mock import patch

from ai import block_search as candidate
from ai.agent import AIAgent
from ai import agent as agent_module
from effects.registry import resolve_effect
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine import mana
from rules_engine.query_context import query_cache, rule_query_scope
from tests.combat_canonical_022 import canonical_card, canonical_entry
baseline = candidate._block_intents


def add(state, name, seat):
    card = canonical_card(name, id=state.allocate_object_id(), owner=seat,
                          controller=seat, zone=Zone.BATTLEFIELD, summoning_sick=False)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def board(seat=1, count=3, guards=3, guard_name='Grizzly Bears'):
    deck = [canonical_entry('Forest', 20)]
    state = MatchFactory.from_decks(deck, deck, seed=716)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 10
    state.step = Step.DECLARE_ATTACKERS
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    attackers = [add(state, 'Grizzly Bears', seat) for _ in range(count)]
    blockers = [add(state, guard_name, 3-seat) for _ in range(guards)]
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': attackers})
    RulesEngine().next_step(state)
    assert state.step == Step.DECLARE_BLOCKERS
    return state, attackers, blockers


def measured(function, state, attackers, blockers):
    profiler = cProfile.Profile()
    result = profiler.runcall(function, state, attackers, blockers)
    stats = pstats.Stats(profiler).stats
    calls = sum(v[1] for k, v in stats.items() if k[2] == '_printed_suppression_result')
    return result, calls


class QueryBatchTests(unittest.TestCase):
    def test_ordered_intents_purity_and_measured_query_reduction_both_seats(self):
        for seat in (1, 2):
            with self.subTest(seat=seat):
                state, attackers, blockers = board(seat)
                before = pickle.dumps(state, protocol=5)
                expected, old_calls = measured(baseline, state, attackers, blockers)
                actual, new_calls = measured(candidate.block_intents, state, attackers, blockers)
                self.assertEqual(actual, expected)
                self.assertEqual(len(actual), 64)
                self.assertEqual(pickle.dumps(state, protocol=5), before)
                self.assertIsNone(query_cache(state))
                self.assertGreater(old_calls, 0)
                self.assertLess(new_calls, old_calls / 2)

    def test_payment_probes_mutate_only_detached_clones(self):
        for seat in (1, 2):
            with self.subTest(seat=seat):
                state, attackers, blockers = board(seat, count=1, guards=2)
                for _ in range(2):
                    add(state, 'Forest', 3-seat)
                # Explicit unit tax effect, not a claimed paid canonical card sequence.
                resolve_effect(state, seat, 'set_combat_cost', dict(kind='block', mana_cost='{1}',
                    clause="This turn, creatures can't block unless their controller pays {1} for each blocking creature they control."))
                before = pickle.dumps(state, protocol=5)
                expected = baseline(state, attackers, blockers)
                payment = candidate.block_payment_state
                auto_pay = mana.auto_pay_cost
                observations = []
                def probe(root, *args, **kwargs):
                    self.assertIs(root, state)
                    self.assertIsNotNone(query_cache(root))
                    paid = payment(root, *args, **kwargs)
                    self.assertEqual(pickle.dumps(root, protocol=5), before)
                    if args[0]:
                        self.assertIsNot(paid, root)
                    return paid
                def spend(paid, *args, **kwargs):
                    self.assertIsNot(paid, state)
                    self.assertIsNone(query_cache(paid))
                    prior = pickle.dumps(paid, protocol=5)
                    result = auto_pay(paid, *args, **kwargs)
                    observations.append(prior != pickle.dumps(paid, protocol=5))
                    self.assertEqual(pickle.dumps(state, protocol=5), before)
                    return result
                with patch.object(candidate, 'block_payment_state', probe), patch.object(mana, 'auto_pay_cost', spend):
                    self.assertEqual(candidate.block_intents(state, attackers, blockers), expected)
                self.assertTrue(any(observations))
                self.assertIsNone(query_cache(state))

    def test_scope_cleanup_on_exception_and_existing_outer_scope(self):
        state, attackers, blockers = board(count=1, guards=1)
        error = ValueError('pure query failure')
        def fail(*_):
            self.assertIsNotNone(query_cache(state))
            raise error
        with patch.object(candidate.combat, '_minimum_blockers_required', fail):
            with self.assertRaises(ValueError) as caught:
                candidate.block_intents(state, attackers, blockers)
        self.assertIs(caught.exception, error)
        self.assertIsNone(query_cache(state))
        with rule_query_scope(state):
            outer = query_cache(state)
            candidate.block_intents(state, attackers, blockers)
            self.assertIs(query_cache(state), outer)
        self.assertIsNone(query_cache(state))

    def test_no_cache_survives_real_keyword_mutation_or_budget_exhaustion(self):
        state, attackers, blockers = board(count=1, guards=2)
        first = candidate.block_intents(state, attackers, blockers)
        resolve_effect(state, 1, 'grant_keyword', dict(target_card_id=attackers[0], keyword='menace'))
        changed = candidate.block_intents(state, attackers, blockers)
        self.assertNotEqual(first, changed)
        self.assertEqual(changed, baseline(state, attackers, blockers))
        self.assertIsNone(query_cache(state))
        self.assertIsNone(candidate.block_intents(state, attackers, blockers, node_budget=1))
        self.assertIsNone(baseline(state, attackers, blockers, node_budget=1))
        with self.assertRaises(ValueError):
            candidate.block_intents(state, attackers, blockers, node_budget=0)
        self.assertIsNone(query_cache(state))

    def test_real_block_search_scores_winners_order_and_states_unchanged(self):
        for seat in (1, 2):
            with self.subTest(seat=seat):
                state, attackers, blockers = board(seat, count=2, guards=2)
                state.players[3-seat].life = 2
                before = pickle.dumps(state, protocol=5)
                ai = AIAgent('master')
                outcomes = []
                score = agent_module.evaluate_board
                def scored(position, actor):
                    value = score(position, actor)
                    outcomes.append((value, position.winner, serialize_match_snapshot(position)))
                    return value
                args = (state, [{'id': cid} for cid in attackers], [{'id': cid} for cid in blockers])
                with patch.object(candidate, 'block_intents', baseline), patch.object(agent_module, 'evaluate_board', scored):
                    expected = ai._search_block_assignments(*args, consider_next_combat=False)
                expected_outcomes = outcomes[:]
                outcomes.clear()
                with patch.object(agent_module, 'evaluate_board', scored):
                    actual = ai._search_block_assignments(*args, consider_next_combat=False)
                self.assertEqual(actual, expected)
                self.assertEqual(outcomes, expected_outcomes)
                self.assertTrue(outcomes)
                self.assertEqual(pickle.dumps(state, protocol=5), before)
                self.assertIsNone(query_cache(state))
