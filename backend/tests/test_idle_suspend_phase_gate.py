"""Skip only ineligible Suspend work; retain the original decision and trace."""
import ast
from dataclasses import asdict
import hashlib
import inspect
import json
import pickle
import random
import sys
import textwrap
from types import MethodType
from unittest import TestCase
from unittest.mock import patch

import ai.agent as agent_module
from ai.agent import AIAgent
from ai.information import decision_view
from ai.suspend_policy import idle_suspend
from analytics.decision_quality import build_trace_payload
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from tests.browser_positive83_canonical import entry


# Current tactical routing, with only Suspend's phase optimization removed.
# The edd74a5f routing/encoder changes remain in both comparison arms. The
# earlier 95ce2fa7... reference predates those changes, not just the phase gate.
# Invert f9b3d123's budget hunk only for the c5a8a540 historical source check;
# both executed arms retain the current combat-expansion budget.
REFERENCE_FUNCTION_SHA = '1c6eea245223f88d6e89361d5a540da8ba9c64c3ff9103969b9f791a4bb24b77'
NEW_IF = "if decision.action.get('type') == 'pass_priority' and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:"
OLD_IF = "if decision.action.get('type') == 'pass_priority':"
PRE_BUDGET_SCOPE = '            with decision_projection_scope(state, player_id):'
BUDGET_SCOPE = (
    '            with decision_projection_scope(state, player_id,\n'
    "                    {'master': 128, 'master_plus': 256}.get(self.difficulty)):")

# Deferred-payment routing stays in both executed comparison arms. Only
# the historical source check reverses these exact reviewed public hunks.
CURRENT_ROUTING_REFERENCE_SHA = '5c59d440338349eb3b19c46ab37549ba43e28c40d60db4497830511ef9dcb92f'
DEFERRED_PAYMENT_REFERENCE_HUNKS = (("                                reasoning='Checked current-turn damage sequence if unanswered',\n                                knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                from ai.deferred_payment_policy import DeferredPaymentPolicy\n                payments = DeferredPaymentPolicy(self, state, player_id)\n                if win is not True:\n                    financing = payments.financing_action()\n                    if financing is not None:\n                        from rules_engine.action_validation import ActionRejected, checked_action\n                        try:\n                            checked_action(authoritative_state, self.engine, player_id, financing)\n                        except ActionRejected:\n                            pass\n                        else:\n                            return AIDecision(action=financing,\n                                reasoning='Execute native financing before the deferred payment deadline',\n                                knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                    legal_moves = payments.filter(legal_moves)\n                    if action is not None and not payments.permits(action):\n                        action = None\n                def funded_decision(proposed, reasoning):\n                    alternative = payments.funded_alternative(proposed, legal_moves) if win is not True else None\n                    if alternative is not None:\n                        from rules_engine.action_validation import ActionRejected, checked_action\n                        try:\n                            checked_action(authoritative_state, self.engine, player_id, alternative)\n                        except ActionRejected:\n                            pass\n                        else:\n                            proposed = alternative\n                            reasoning = 'Keep a proved payment continuation before borrowing again'\n                    return AIDecision(action=proposed, reasoning=reasoning,\n                        knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                if action is not None:\n                    if (win is not True and (replacement := self._early_prowess_burn_action(state, action, player_id))\n                            and payments.permits(replacement)):\n                        from rules_engine.action_validation import ActionRejected, checked_action\n                        try:\n", "                                reasoning='Checked current-turn damage sequence if unanswered',\n                                knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                if action is not None:\n                    if win is not True and (replacement := self._early_prowess_burn_action(state, action, player_id)):\n                        from rules_engine.action_validation import ActionRejected, checked_action\n                        try:\n"), ("                            pass\n                        else:\n                            return funded_decision(replacement,\n                                'Develop a checked main-phase prowess sequence before nonlethal burn')\n                    return funded_decision(action,\n                        'Tactical-safeguarded Q ranking over a checked heuristic subset')\n                decision = self._choose_action(state, [move for move in legal_moves if move['type'] not in {'foretell', 'suspend'}], player_id)\n                if ((replacement := self._early_prowess_burn_action(state, decision.action, player_id))\n                        and payments.permits(replacement)):\n                    from rules_engine.action_validation import ActionRejected, checked_action\n                    try:\n", "                            pass\n                        else:\n                            return AIDecision(action=replacement,\n                                reasoning='Develop a checked main-phase prowess sequence before nonlethal burn',\n                                knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                    return AIDecision(action=action,\n                        reasoning='Tactical-safeguarded Q ranking over a checked heuristic subset',\n                        knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n                decision = self._choose_action(state, [move for move in legal_moves if move['type'] not in {'foretell', 'suspend'}], player_id)\n                if replacement := self._early_prowess_burn_action(state, decision.action, player_id):\n                    from rules_engine.action_validation import ActionRejected, checked_action\n                    try:\n"), ("                        decision = AIDecision(action=action, reasoning='Invest idle mana in supported Suspend without spending a known answer')\n                from ai.declaration_policy import finalize_declaration\n                return funded_decision(finalize_declaration(state, decision.action), decision.reasoning)\n        finally:\n            self._knowledge_usage = previous_usage\n", "                        decision = AIDecision(action=action, reasoning='Invest idle mana in supported Suspend without spending a known answer')\n                from ai.declaration_policy import finalize_declaration\n                return AIDecision(action=finalize_declaration(state, decision.action), reasoning=decision.reasoning,\n                                  knowledge_usage=copy.deepcopy(self._knowledge_usage['counts']))\n        finally:\n            self._knowledge_usage = previous_usage\n"))


def legacy_choose_action():
    source = textwrap.dedent(inspect.getsource(AIAgent.choose_action))
    assert source.count(NEW_IF) == 1
    source = source.replace(NEW_IF, OLD_IF, 1)
    assert source.count(BUDGET_SCOPE) == 1
    historical = source.replace(BUDGET_SCOPE, PRE_BUDGET_SCOPE, 1)
    assert hashlib.sha256(historical.encode()).hexdigest() == CURRENT_ROUTING_REFERENCE_SHA
    for current_block, reference_block in DEFERRED_PAYMENT_REFERENCE_HUNKS:
        assert historical.count(current_block) == 1
        historical = historical.replace(current_block, reference_block, 1)
    assert hashlib.sha256(historical.encode()).hexdigest() == REFERENCE_FUNCTION_SHA
    tree = ast.parse(source)
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
    namespace = vars(agent_module).copy()
    exec(compile(tree, '<exact-original-choose-action>', 'exec'), namespace)
    return namespace['choose_action']


def wire(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


def scene(pid, step):
    deck = [entry('Island', 40), entry('Forest', 8), entry('Grizzly Bears', 4),
            entry('Llanowar Elves', 4), entry("Smuggler's Copter", 4)]
    state = MatchFactory.from_decks(deck, deck, seed=37)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 4
    state.active_player = state.priority_player = pid
    state.step = step
    for owner in (1, 2):
        card = next(card for card in state.cards.values() if card.owner == owner
                    and card.name == 'Grizzly Bears' and card.zone in {Zone.HAND, Zone.LIBRARY})
        getattr(state.players[owner], card.zone.value).remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        state.players[owner].battlefield.append(card.id)
        card.summoning_sick = False
        state.players[owner].lands_played_this_turn = 1
        state.players[owner].land_plays_recorded_on_turn = 1
        state.players[owner].last_land_play_turn = state.turn
    assert len(state.cards) == 120
    return state, RulesEngine().legal_moves(state, pid)


class IdleSuspendPhaseGate(TestCase):
    def test_reference_rejects_unrelated_routing_changes(self):
        source = inspect.getsource(AIAgent.choose_action)
        changed = source.replace('decision = self._choose_action(',
                                 'decision = self._different_action(', 1)
        self.assertNotEqual(source, changed)
        with patch.object(inspect, 'getsource', return_value=changed):
            with self.assertRaises(AssertionError):
                legacy_choose_action()

    def test_reference_requires_the_exact_phase_gate(self):
        source = inspect.getsource(AIAgent.choose_action)
        with patch.object(inspect, 'getsource', return_value=source.replace(NEW_IF, OLD_IF, 1)):
            with self.assertRaises(AssertionError):
                legacy_choose_action()

    def test_reference_rejects_changed_or_missing_combat_budget(self):
        source = textwrap.dedent(inspect.getsource(AIAgent.choose_action))
        for before, after in (
            ("'master': 128", "'master': 127"),
            ("'master_plus': 256", "'master_plus': 257"),
            (BUDGET_SCOPE, PRE_BUDGET_SCOPE),
            (BUDGET_SCOPE, BUDGET_SCOPE + '\n' + BUDGET_SCOPE),
        ):
            with self.subTest(replacement=after):
                changed = source.replace(before, after, 1)
                self.assertNotEqual(source, changed)
                with patch.object(inspect, 'getsource', return_value=changed):
                    with self.assertRaises(AssertionError):
                        legacy_choose_action()

    def compare(self, pid, step):
        state, moves = scene(pid, step)
        self.assertEqual(moves, [{'type': 'pass_priority'}])
        initial = pickle.dumps((state, moves), protocol=5)
        rows, calls = [], []
        for original in (True, False):
            current, offered = pickle.loads(initial)
            agent = AIAgent('strong', 'Midrange', 'Midrange')
            if original:
                agent.choose_action = MethodType(legacy_choose_action(), agent)
            before = pickle.dumps((current, offered), protocol=5)
            rng = random.getstate()
            count = {'projection': 0, 'idle_suspend': 0}

            def observe(frame, event, _):
                if event == 'call':
                    if frame.f_code is decision_view.__code__:
                        count['projection'] += 1
                    elif frame.f_code is idle_suspend.__code__:
                        count['idle_suspend'] += 1

            previous = sys.getprofile()
            sys.setprofile(observe)
            try:
                decision = agent.choose_action(current, offered, pid)
            finally:
                sys.setprofile(previous)
            payload = build_trace_payload(current, pid, offered, decision.action,
                                          decision.reasoning, knowledge_usage=decision.knowledge_usage)
            self.assertEqual(pickle.dumps((current, offered), protocol=5), before)
            self.assertEqual(random.getstate(), rng)
            if original:
                del agent.choose_action
            rows.append((wire(asdict(decision)), wire(payload), pickle.dumps(agent.__dict__, protocol=5)))
            calls.append(count)
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(calls[0], {'projection': 2, 'idle_suspend': 1})
        if step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:
            self.assertEqual(calls[1], calls[0])
        else:
            self.assertEqual(calls[1], {'projection': 1, 'idle_suspend': 0})

    def test_seat1_draw(self):
        self.compare(1, Step.DRAW)

    def test_seat2_draw(self):
        self.compare(2, Step.DRAW)

    def test_seat1_end_step(self):
        self.compare(1, Step.END_STEP)

    def test_seat2_end_step(self):
        self.compare(2, Step.END_STEP)

    def test_seat1_main_still_scans_hand(self):
        self.compare(1, Step.PRECOMBAT_MAIN)

    def test_seat2_main_still_scans_hand(self):
        self.compare(2, Step.POSTCOMBAT_MAIN)
