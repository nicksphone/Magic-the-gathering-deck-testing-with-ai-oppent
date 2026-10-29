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

import ai.agent as agent_module
from ai.agent import AIAgent
from ai.information import decision_view
from ai.suspend_policy import idle_suspend
from analytics.decision_quality import build_trace_payload
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from tests.browser_positive83_canonical import entry


# Current tactical routing, with only Suspend's phase optimization removed.
OLD_FUNCTION_SHA = '95ce2fa7a39e809a07138674715f749ef32d175cca170aaf22f036feece2dac8'
NEW_IF = "if decision.action.get('type') == 'pass_priority' and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:"
OLD_IF = "if decision.action.get('type') == 'pass_priority':"


def legacy_choose_action():
    source = textwrap.dedent(inspect.getsource(AIAgent.choose_action))
    assert source.count(NEW_IF) in {0, 1}
    source = source.replace(NEW_IF, OLD_IF, 1)
    assert hashlib.sha256(source.encode()).hexdigest() == OLD_FUNCTION_SHA
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
