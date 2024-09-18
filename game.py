# game.py (updated with deck selection)

import random
from card_factory import CardFactory
from player import Player
from tkinter import filedialog, simpledialog

class Game:
    def __init__(self, player1, player2, gui=None):
        """
        Initializes the game with two players and sets up the game environment.
        """
        self.player1 = player1
        self.player2 = player2
        self.gui = gui
        self.turn = 0
        self.current_phase = 'Main Phase'

        # Initialize the CardFactory to pull cards from the local database or API
        self.card_factory = CardFactory()

        # Prompt players to select decks
        self.player1.deck = self.select_deck(player1)
        self.player2.deck = self.select_deck(player2)

        # Shuffle the decks
        random.shuffle(self.player1.deck)
        random.shuffle(self.player2.deck)

    def select_deck(self, player):
        """
        Allows the player to select a deck, either a pre-built one or a custom deck.

        Args:
            player (Player): The player who is selecting the deck.

        Returns:
            list: A list of cards that form the player's deck.
        """
        print(f"{player.name}, choose your deck:")
        options = ["Pre-built: Red Aggro", "Pre-built: Blue Control", "Custom Deck"]
        selection = self.gui.prompt_selection(player, options)

        if selection == "Pre-built: Red Aggro":
            return self.build_deck("Red Aggro")
        elif selection == "Pre-built: Blue Control":
            return self.build_deck("Blue Control")
        else:
            return self.custom_deck_selection(player)

    def build_deck(self, deck_type):
        """
        Builds a dynamic deck for a player based on deck type.

        Args:
            deck_type (str): The type of deck to build (e.g., 'Red Aggro', 'Blue Control').

        Returns:
            list: A list of cards that form the player's deck.
        """
        deck = []
        card_names = []

        if deck_type == 'Red Aggro':
            card_names = ["Lightning Bolt", "Goblin Guide", "Mountain", "Shock", "Lava Spike"]
        elif deck_type == 'Blue Control':
            card_names = ["Counterspell", "Island", "Opt", "Ponder", "Brainstorm"]

        for card_name in card_names:
            card = self.card_factory.create_card(card_name)
            if card:
                deck.append(card)

        return deck

    def custom_deck_selection(self, player):
        """
        Allows the player to build a custom deck by inputting card names or loading from a file.

        Args:
            player (Player): The player creating the custom deck.

        Returns:
            list: A list of cards that form the player's custom deck.
        """
        deck = []
        print(f"{player.name}, choose how to create your custom deck:")
        options = ["Input cards manually", "Load deck from file"]
        selection = self.gui.prompt_selection(player, options)

        if selection == "Input cards manually":
            while True:
                card_name = simpledialog.askstring("Deck Builder", f"Enter card name for {player.name}'s deck (or 'done' to finish):")
                if card_name.lower() == 'done':
                    break
                card = self.card_factory.create_card(card_name)
                if card:
                    deck.append(card)
                else:
                    print(f"Card '{card_name}' not found.")

        elif selection == "Load deck from file":
            file_path = filedialog.askopenfilename(title="Select Deck File", filetypes=[("Text Files", "*.txt")])
            if file_path:
                with open(file_path, 'r') as file:
                    card_names = file.read().splitlines()
                    for card_name in card_names:
                        card = self.card_factory.create_card(card_name)
                        if card:
                            deck.append(card)
                        else:
                            print(f"Card '{card_name}' not found.")

        return deck

    # Rest of the Game class remains the same, with phases and targeting...
