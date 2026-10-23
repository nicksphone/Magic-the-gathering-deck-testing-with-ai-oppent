"""Native query-count and exact-wire controls, not a natural-game benchmark."""
from contextlib import ExitStack
import json
from unittest import TestCase
from unittest.mock import patch

from analytics import decision_quality as original
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.continuous import (
    effective_combat_stats, effective_keywords, effective_power, effective_toughness,
)
from rules_engine.engine import RulesEngine
from rules_engine.type_effects import effective_types
from tests.browser_positive83_canonical import card, entry


def scene(empty=False):
    decks = [entry('Island', 60)]
    state = MatchFactory.from_decks(decks, decks, seed=37)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DRAW
    if not empty:
        for identifier, name, owner in (
                ('bear', 'Grizzly Bears', 1), ('island', 'Island', 1),
                ('elf', 'Llanowar Elves', 2), ('copter', "Smuggler's Copter", 2)):
            state.cards[identifier] = card(name, id=identifier, owner=owner,
                                           controller=owner, zone=Zone.BATTLEFIELD,
                                           summoning_sick=False)
            state.players[owner].battlefield.append(identifier)
    return state


def legacy_snapshot(state, pid):
    """Exact original expression sequence, delegated to real rule queries."""
    return [
        {'id': cid, 'name': state.cards[cid].name,
         'types': effective_types(state, cid),
         'tapped': bool(getattr(state.cards[cid], 'tapped', False)),
         'power': effective_power(state, cid),
         'toughness': effective_toughness(state, cid),
         'keywords': effective_keywords(state, cid),
         'damage_marked': int(state.cards[cid].counters.get('__damage_marked', 0))}
        for cid in state.players[pid].battlefield
    ]


def wire_json(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


class SnapshotPairTests(TestCase):
    def instrument(self, stack):
        power = stack.enter_context(patch.object(original, 'effective_power', wraps=effective_power))
        tough = stack.enter_context(patch.object(original, 'effective_toughness', wraps=effective_toughness))
        pair = stack.enter_context(patch.object(original, 'effective_combat_stats',
                                               wraps=effective_combat_stats, create=True))
        return power, tough, pair

    def test_empty_boards_do_not_query_stats(self):
        state = scene(empty=True)
        before = serialize_match_snapshot(state)
        with ExitStack() as stack:
            queries = self.instrument(stack)
            self.assertEqual([original._battlefield_snapshot(state, pid) for pid in (1, 2)], [[], []])
            self.assertEqual(sum(query.call_count for query in queries), 0)
        self.assertEqual(serialize_match_snapshot(state), before)

    def test_two_seats_and_noncreatures_keep_rows_with_one_query_each(self):
        state = scene()
        expected = [legacy_snapshot(state, pid) for pid in (1, 2)]
        before = serialize_match_snapshot(state)
        with ExitStack() as stack:
            power, tough, pair = self.instrument(stack)
            observed = [original._battlefield_snapshot(state, pid) for pid in (1, 2)]
            self.assertEqual(wire_json(observed), wire_json(expected))
            self.assertEqual(serialize_match_snapshot(state), before)
            self.assertEqual(power.call_count + tough.call_count + pair.call_count, 4)
            self.assertEqual(pair.call_count, 4)

    def test_changed_counters_and_modifiers_get_fresh_pairs(self):
        state = scene()
        with ExitStack() as stack:
            power, tough, pair = self.instrument(stack)
            for count in (0, 2):
                state.cards['bear'].counters['+1/+1'] = count
                state.cards['bear'].counters['__eot_power'] = count + 1
                state.cards['elf'].counters['__eot_toughness'] = count + 2
                expected = [legacy_snapshot(state, pid) for pid in (1, 2)]
                before = serialize_match_snapshot(state)
                self.assertEqual(wire_json([original._battlefield_snapshot(state, pid) for pid in (1, 2)]),
                                 wire_json(expected))
                self.assertEqual(serialize_match_snapshot(state), before)
            self.assertEqual(power.call_count + tough.call_count + pair.call_count, 8)
            self.assertEqual(pair.call_count, 8)

    def test_complete_trace_payload_keeps_exact_legacy_bytes(self):
        state = scene()
        state.cards['island'].tapped = True
        state.cards['bear'].counters['__damage_marked'] = 1
        before = serialize_match_snapshot(state)
        legal = RulesEngine().legal_moves(state, 1)
        action = next(move for move in legal if move['type'] == 'pass_priority')
        with patch.object(original, '_battlefield_snapshot', legacy_snapshot):
            expected = original.build_trace_payload(state, 1, legal, action, 'controlled snapshot comparison')
        with ExitStack() as stack:
            power, tough, pair = self.instrument(stack)
            observed = original.build_trace_payload(state, 1, legal, action, 'controlled snapshot comparison')
            self.assertEqual(wire_json(observed), wire_json(expected))
            self.assertEqual(serialize_match_snapshot(state), before)
            self.assertEqual(power.call_count + tough.call_count + pair.call_count, 4)
            self.assertEqual(pair.call_count, 4)
