import sys
from PyQt5.QtWidgets import QApplication
from deck_builder import DeckBuilderApp
from game_play import GamePlayApp

class MagicApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.main_window = None

    def start_deck_builder(self):
        """
        Starts the deck-building phase by launching the DeckBuilderApp.
        """
        self.main_window = DeckBuilderApp(parent=self)
        self.main_window.show()

    def transition_to_game(self, player_deck):
        """
        Transitions from the deck-building phase to the game-play phase.
        """
        # Close the deck builder window
        self.main_window.close()

        # Open the game play window
        self.main_window = GamePlayApp(player_deck=player_deck, ai_deck=self.generate_ai_deck())
        self.main_window.show()

    def generate_ai_deck(self):
        """
        Generates a deck for the AI to play with.
        """
        return [
            Card('AI Warrior', 'creature', mana_cost=2, power=2, toughness=2),
            Card('AI Spell', 'spell', mana_cost=3, ability='deal_damage'),
            Card('AI Fire Elemental', 'creature', mana_cost=5, power=5, toughness=4, abilities=['flying'])
        ]

if __name__ == '__main__':
    app = MagicApp(sys.argv)
    app.start_deck_builder()
    sys.exit(app.exec_())
