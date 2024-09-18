# game.py

from card_factory import CardFactory
from player import Player
import random

class Game:
    def __init__(self, player1, player2, gui=None):
        """
        Initializes the game with two players and sets up the game environment.

        Args:
            player1 (Player): The first player in the game.
            player2 (Player): The second player in the game.
            gui: Optional GUI reference for updating the interface during the game.
        """
        self.player1 = player1
        self.player2 = player2
        self.gui = gui
        self.turn = 0

        # Initialize the CardFactory to pull cards from the local database or API
        self.card_factory = CardFactory()

        # Initialize the decks for both players
        self.player1.deck = self.build_deck(player1)
        self.player2.deck = self.build_deck(player2)

        # Shuffle the decks
        random.shuffle(self.player1.deck)
        random.shuffle(self.player2.deck)

    def build_deck(self, player):
        """
        Builds a dynamic deck for a player by pulling cards from the database.

        Args:
            player (Player): The player for whom the deck is being built.

        Returns:
            list: A list of cards that form the player's deck.
        """
        deck = []

        # Example list of card names; this could be replaced by a more advanced query or random selection.
        card_names = ["Lightning Bolt", "Serra Angel", "Forest", "Mountain", "Island", "Counterspell", "Llanowar Elves"]

        for card_name in card_names:
            card = self.card_factory.create_card(card_name)
            if card:
                deck.append(card)

        return deck

    def play_card(self, card):
        """
        Handles playing a card during a player's turn.
        
        Args:
            card: The card that is being played.
        """
        player = card.owner

        # Example logic: for a creature card, summon it to the battlefield
        if card.card_type == 'Creature':
            player.battlefield.append(card)
            print(f"{player.name} played {card.name}.")

        # Example logic: for a spell card, cast it and apply its effects
        elif card.card_type in ['Instant', 'Sorcery']:
            print(f"{player.name} cast {card.name}.")
            # Here you would implement the spell's effect based on its description or abilities
            # For simplicity, we are just printing that the spell was cast.

        # Example logic for lands: put the land into play
        elif card.card_type == 'Land':
            player.lands.append(card)
            print(f"{player.name} played land {card.name}.")

        # Remove the card from the player's hand after it's played
        player.hand.remove(card)

        # Update the game state or GUI if needed
        if self.gui:
            self.gui.display_hand()

    def start_game(self):
        """
        Starts the game and initializes the game loop.
        """
        print("The game begins!")
        # Draw initial hands for both players
        self.draw_initial_hands(self.player1)
        self.draw_initial_hands(self.player2)

        # Start the main game loop
        while not self.is_game_over():
            self.next_turn()

    def draw_initial_hands(self, player):
        """
        Draws an initial hand of cards for a player at the start of the game.

        Args:
            player (Player): The player who is drawing cards.
        """
        for _ in range(7):  # Draw 7 cards to start
            self.draw_card(player)

    def draw_card(self, player):
        """
        Draws a card from the player's deck and adds it to their hand.
        
        Args:
            player (Player): The player drawing the card.
        """
        if player.deck:
            card = player.deck.pop(0)
            player.hand.append(card)
            print(f"{player.name} draws {card.name}.")
        else:
            print(f"{player.name} has no cards left to draw!")

    def next_turn(self):
        """
        Advances the game to the next turn.
        """
        self.turn += 1
        current_player = self.player1 if self.turn % 2 == 1 else self.player2
        print(f"Turn {self.turn}: {current_player.name}'s turn.")
        
        # For now, we'll just have the current player draw a card
        self.draw_card(current_player)

    def is_game_over(self):
        """
        Determines if the game is over (e.g., if a player has no cards left or has lost).
        
        Returns:
            bool: True if the game is over, False otherwise.
        """
        if not self.player1.deck and not self.player2.deck:
            print("Both players are out of cards! The game is a draw.")
            return True
        return False
