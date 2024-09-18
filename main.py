# main.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from card_factory import CardFactory
from image_loader import load_card_image
from player import Player
from game import Game

class GameGUI:
    def __init__(self):
        # Initialize Tkinter root
        self.root = tk.Tk()
        self.root.title("MTG Game Simulation")
        
        # Initialize card factory
        self.card_factory = CardFactory()

        # Initialize players
        self.player1 = Player(name="Player 1", is_ai=False)
        self.player2 = Player(name="Player 2", is_ai=True)

        # Initialize the game
        self.game = Game(self.player1, self.player2, gui=self)
        self.player1.game = self.game
        self.player2.game = self.game

        # Set up a frame for player's hand display
        self.hand_frame = ttk.Frame(self.root, padding="10")
        self.hand_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Set up the battlefield (future addition)

        # Start the game after deck selection
        self.start_game()

    def start_game(self):
        """
        Starts the game after players have selected their decks.
        """
        self.game.start_game()

    def prompt_selection(self, player, options):
        """
        Prompts the player to select an option from a list (e.g., deck selection).

        Args:
            player (Player): The player making the selection.
            options (list): List of options to choose from.

        Returns:
            str: The selected option.
        """
        choice = simpledialog.askstring("Deck Selection", f"{player.name}, choose an option:\n" + "\n".join(options))
        return choice

    def prompt_target_selection(self, opponent):
        """
        Prompts the player to select a target during combat or spell casting.
        
        Args:
            opponent (Player): The opposing player whose creatures or self are the target options.

        Returns:
            Target: The selected target (either a player or creature).
        """
        options = [opponent.name] + [creature.name for creature in opponent.battlefield]
        choice = simpledialog.askstring("Combat", f"Choose a target:\n" + "\n".join(options))
        
        if choice == opponent.name:
            return opponent
        for creature in opponent.battlefield:
            if creature.name == choice:
                return creature
        return None

    def display_hand(self):
        """
        Displays the player's hand in the GUI with options to play cards.
        """
        for widget in self.hand_frame.winfo_children():
            widget.destroy()

        # Display Player 1's hand
        ttk.Label(self.hand_frame, text=f"{self.player1.name}'s Hand:").pack()

        for idx, card in enumerate(self.player1.hand):
            frame = ttk.Frame(self.hand_frame)
            frame.pack(side=tk.LEFT, padx=5, pady=5)

            # Load and display the card image
            image = load_card_image(card.image_url)
            if image:
                label = ttk.Label(frame, image=image)
                label.image = image
                label.pack()
            else:
                label = ttk.Label(frame, text=card.name)
                label.pack()

            # Add a button to play the card
            play_button = ttk.Button(
                frame,
                text="Play",
                command=lambda idx=idx: self.play_card(idx)
            )
            play_button.pack()

    def play_card(self, card_index):
        """
        Handles the action of playing a card from the player's hand.
        
        Args:
            card_index (int): The index of the card in the player's hand to play.
        """
        card = self.player1.hand[card_index]
        self.game.play_card(card)
        messagebox.showinfo("Card Played", f"{self.player1.name} played {card.name}.")
        del self.player1.hand[card_index]
        self.display_hand()

if __name__ == "__main__":
    try:
        GameGUI()
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
