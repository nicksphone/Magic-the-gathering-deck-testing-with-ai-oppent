"""Full canonical native exile/life lifecycle; no invented stack objects."""
import json
from pathlib import Path
import unittest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.pending_permanent_fullraw import raw_card
from tests.test_ai_recurring_engines import add, fixture
from tests.test_any_player_cast_damage import checked, settle

RAW = {'Monastery Swiftspear': raw_card('Monastery Swiftspear')}
RAW['Swords to Plowshares'] = next(row for row in json.loads(
    (Path(__file__).parent/'fixtures/hexproof_variants.json').read_bytes())
    if row['name'] == 'Swords to Plowshares')
RECEIPTS = []


class ExilePowerLifeTests(unittest.TestCase):
    def native_exile(self, target_seat, caster):
        state = fixture()
        state.active_player = state.priority_player = target_seat
        for player in state.players.values():
            player.mana_pool = {color: 20 for color in ('W', 'U', 'B', 'R', 'G', 'C')}
            player.snow_mana_pool.clear()
        target = add(state, 'Monastery Swiftspear', target_seat, Zone.HAND, cards=RAW)
        state = checked(state, target_seat, {'type': 'cast_spell', 'card_id': target.id, 'targets': {}})
        state = settle(state)
        self.assertEqual(state.cards[target.id].zone, Zone.BATTLEFIELD)
        spell = add(state, 'Swords to Plowshares', caster, Zone.HAND, cards=RAW)
        if state.priority_player != caster:
            state = checked(state, state.priority_player, {'type': 'pass_priority'})
        initial = serialize_match_snapshot(state)
        state = checked(state, caster, {'type': 'cast_spell', 'card_id': spell.id,
                                        'targets': {'target_card_id': target.id}})
        announced = serialize_match_snapshot(state)
        state = settle(state)
        expected = {1: 20, 2: 20}
        # A self-cast noncreature spell first resolves the target's real prowess trigger.
        expected[target_seat] += 2 if caster == target_seat else 1
        actual = {pid: player.life for pid, player in state.players.items()}
        RECEIPTS.append({'case': self.id(), 'target_controller': target_seat,
                         'spell_controller': caster, 'initial': initial, 'announced': announced,
                         'final': serialize_match_snapshot(state), 'actual_life': actual,
                         'expected_life': expected})
        self.assertFalse(state.stack or state.pending_mechanic_choice
                         or state.pending_replacement_choice or state.pending_trigger_order)
        self.assertEqual(state.cards[target.id].zone, Zone.EXILE)
        self.assertIn(target.id, state.players[target_seat].exile)
        self.assertEqual(state.cards[spell.id].zone, Zone.GRAVEYARD)
        self.assertEqual(actual, expected)

    def test_opponent_target_seat1(self):
        self.native_exile(1, 2)

    def test_opponent_target_seat2(self):
        self.native_exile(2, 1)

    def test_own_target_seat1_with_native_prowess(self):
        self.native_exile(1, 1)

    def test_own_target_seat2_with_native_prowess(self):
        self.native_exile(2, 2)
