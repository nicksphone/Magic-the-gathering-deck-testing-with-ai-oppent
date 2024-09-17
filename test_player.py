# test_player.py

import unittest
from player import Player
from land_card import LandCard
from creature_card import CreatureCard
from game import Game

class TestPlayer(unittest.TestCase):
    """
    Unit tests for the Player class.
    """

    def setUp(self):
        self.player = Player(name="Test Player")
        self.opponent = Player(name="Opponent")
        self.game = Game(self.player, self.opponent, None)
        self.player.game = self.game
        self.opponent.game = self.game

    def test_draw_card(self):
        # Ensure the player can draw a card
        initial_hand_size = len(self.player.hand)
        self.player.draw_card()
        self.assertEqual(len(self.player.hand), initial_hand_size + 1)

    def test_pay_mana_cost(self):
        # Add mana to the player's mana pool
        self.player.mana_pool['Red'] = 3
        mana_cost = {'Red': 2}
        can_pay = self.player.can_pay_mana_cost(mana_cost)
        self.assertTrue(can_pay)
        self.player.pay_mana_cost(mana_cost)
        self.assertEqual(self.player.mana_pool['Red'], 1)

    def test_tap_land(self):
        # Test tapping a land card
        mountain = LandCard(name="Mountain", mana_type="Red")
        self.player.battlefield.append(mountain)
        self.player.tap_land(mountain)
        self.assertTrue(mountain.tap_status)
        self.assertEqual(self.player.mana_pool['Red'], 1)

    def test_play_card_from_hand(self):
        # Test playing a creature card from hand
        savannah_lions = CreatureCard(
            name="Savannah Lions",
            mana_cost={'White': 1},
            power=2,
            toughness=1,
            description="A quick and aggressive creature.",
            abilities=[]
        )
        self.player.hand.append(savannah_lions)
        self.player.mana_pool['White'] = 1
        self.player.play_card_from_hand(savannah_lions, self.game)
        self.assertIn(savannah_lions, self.game.stack)
        self.assertNotIn(savannah_lions, self.player.hand)

    def test_adjust_currency(self):
        # Test adjusting currency
        self.assertTrue(self.player.adjust_currency(-500))
        self.assertEqual(self.player.currency, 500)
        self.assertFalse(self.player.adjust_currency(-600))
        self.assertEqual(self.player.currency, 500)

if __name__ == '__main__':
    unittest.main()
