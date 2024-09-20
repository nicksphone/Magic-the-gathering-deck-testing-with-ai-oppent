import wx
from deck_builder import DeckBuilderApp
from db_utils import initialize_database  # Assuming db_utils manages the database

if __name__ == "__main__":
    # Step 1: Initialize the database
    initialize_database()

    # Step 2: Launch the wxPython DeckBuilder GUI
    app = wx.App(False)
    frame = DeckBuilderApp(None, "Magic: The Gathering Deck Tester")
    app.MainLoop()
