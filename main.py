import wx
from deck_builder import DeckBuilderApp
from game_play import GamePlayApp
from db_utils import initialize_database


class MagicApp(wx.App):
    def OnInit(self):
        """
        This method is called when the wxPython application starts.
        We start by initializing the database and then opening the deck builder.
        """
        # Step 1: Initialize the database
        initialize_database()

        # Step 2: Launch the DeckBuilder GUI
        self.frame = DeckBuilderApp(None, "Magic: The Gathering Deck Tester")
        self.frame.Show()

        return True

    def transition_to_game(self, player_deck):
        """
        Transition from deck building to the game play screen.
        This method is called when the user is ready to start the game.
        """
        self.frame.Destroy()  # Close the DeckBuilder frame
        self.frame = GamePlayApp(None, "Magic: The Gathering - Game Play", player_deck)
        self.frame.Show()


if __name__ == "__main__":
    app = MagicApp(False)
    app.MainLoop()
