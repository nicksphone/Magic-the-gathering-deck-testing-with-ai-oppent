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
        self.main_window = GamePlayApp(player_deck=player_deck)
        self.main_window.show()

if __name__ == '__main__':
    app = MagicApp(sys.argv)
    app.start_deck_builder()
    sys.exit(app.exec_())
