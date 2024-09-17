# main.py

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from game import Game
from player import Player
from ai_player import AIPlayer
from collection_manager import CollectionManager
from card_pool import CardPool
from card_factory import CardFactory
from creature_card import CreatureCard
from land_card import LandCard
from instant_card import InstantCard
from sorcery_card import SorceryCard

class GameGUI:
    """
    Main GUI class for the Magic: The Gathering game simulation.
    Manages the graphical interface and user interactions.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Magic: The Gathering")

        # Initialize players
        self.player1 = Player(name="Player 1", is_ai=False)
        self.player2 = AIPlayer(name="Computer", is_ai=True)

        # Initialize collection manager
        self.collection_manager = CollectionManager(self.player1.name)

        # Initialize card factory
        self.card_factory = CardFactory()

        # Create widgets
        self.create_widgets()

        # Create game
        self.game = Game(self.player1, self.player2, self)
        self.game_gui_setup()

        # Start the main loop
        self.root.mainloop()

    def create_widgets(self):
        """
        Creates the GUI widgets including frames, labels, buttons, and menus.
        """
        # Create frames
        self.info_frame = ttk.Frame(self.root)
        self.info_frame.pack()
        self.battlefield_frame = ttk.Frame(self.root)
        self.battlefield_frame.pack()
        self.hand_frame = ttk.Frame(self.root)
        self.hand_frame.pack()
        self.stack_frame = ttk.Frame(self.root)
        self.stack_frame.pack()
        self.controls_frame = ttk.Frame(self.root)
        self.controls_frame.pack()

        # Info label
        self.info_label = ttk.Label(self.info_frame, text="Game Information")
        self.info_label.pack()

        # Controls
        self.next_phase_button = ttk.Button(self.controls_frame, text="Next Phase", command=self.next_phase)
        self.next_phase_button.pack(side=tk.LEFT)

        # Menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        game_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Game", menu=game_menu)
        game_menu.add_command(label="Save Game", command=self.save_game)
        game_menu.add_command(label="Load Game", command=self.load_game)
        game_menu.add_separator()
        game_menu.add_command(label="Exit", command=self.root.quit)
        collection_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Collection", menu=collection_menu)
        collection_menu.add_command(label="Open Booster Pack", command=self.open_booster_pack)
        collection_menu.add_command(label="View Collection", command=self.view_collection)
        collection_menu.add_command(label="Deck Builder", command=self.open_deck_builder)

    def game_gui_setup(self):
        """
        Sets up the game GUI and starts the game.
        """
        self.update_gui()
        self.game.start_game()

    def update_gui(self):
        """
        Updates the GUI elements to reflect the current game state.
        """
        # Update info label
        current_player = self.game.get_current_player()
        self.info_label.config(text=f"Current Phase: {self.game.phase} | {current_player.name}'s Turn")

        # Display battlefield
        self.display_battlefield()

        # Display hand
        self.display_hand()

        # Display stack
        self.display_stack()

    def display_battlefield(self):
        """
        Displays the battlefield, including the player's and opponent's cards.
        """
        # Clear previous battlefield display
        for widget in self.battlefield_frame.winfo_children():
            widget.destroy()

        # Display player's life total
        ttk.Label(self.battlefield_frame, text=f"{self.player1.name} - Life: {self.player1.life_total}").pack()

        # Display player's battlefield
        ttk.Label(self.battlefield_frame, text=f"{self.player1.name}'s Battlefield:").pack()

        # Display lands
        ttk.Label(self.battlefield_frame, text="Lands:").pack()
        for card in self.player1.battlefield:
            if card.card_type == 'Land':
                frame = ttk.Frame(self.battlefield_frame)
                frame.pack()
                status = "(Tapped)" if card.tap_status else "(Untapped)"
                label = ttk.Label(frame, text=f"{card.name} {status}")
                label.pack(side=tk.LEFT)
                if not card.tap_status:
                    button = ttk.Button(
                        frame,
                        text="Tap for Mana",
                        command=lambda c=card: self.tap_land(c)
                    )
                    button.pack(side=tk.LEFT)

        # Display creatures
        ttk.Label(self.battlefield_frame, text="Creatures:").pack()
        for card in self.player1.battlefield:
            if isinstance(card, CreatureCard):
                frame = ttk.Frame(self.battlefield_frame)
                frame.pack()
                status = "(Tapped)" if card.tap_status else "(Untapped)"
                abilities = ", ".join(card.abilities)
                label = ttk.Label(frame, text=f"{card.name} {status} [P/T: {card.power}/{card.toughness}] Abilities: {abilities}")
                label.pack(side=tk.LEFT)
                # Add any actions for creatures here

        # Display mana pool
        mana_pool_text = ", ".join([f"{color}: {amount}" for color, amount in self.player1.mana_pool.items() if amount > 0])
        ttk.Label(self.battlefield_frame, text=f"Mana Pool: {mana_pool_text}").pack()

        # Display AI's life total
        ttk.Label(self.battlefield_frame, text=f"{self.player2.name} - Life: {self.player2.life_total}").pack()

        # Display AI's battlefield (simplified)
        ttk.Label(self.battlefield_frame, text=f"{self.player2.name}'s Battlefield:").pack()
        for card in self.player2.battlefield:
            if isinstance(card, CreatureCard):
                abilities = ", ".join(card.abilities)
                ttk.Label(self.battlefield_frame, text=f"{card.name} [P/T: {card.power}/{card.toughness}] Abilities: {abilities}").pack()
            else:
                ttk.Label(self.battlefield_frame, text=card.name).pack()

    def display_hand(self):
        """
        Displays the player's hand with options to play cards.
        """
        # Clear previous hand display
        for widget in self.hand_frame.winfo_children():
            widget.destroy()

        ttk.Label(self.hand_frame, text="Your Hand:").pack()
        for idx, card in enumerate(self.player1.hand):
            frame = ttk.Frame(self.hand_frame)
            frame.pack(side=tk.LEFT)
            image = self.load_card_image(card.name)
            if image:
                label = ttk.Label(frame, image=image)
                label.image = image  # Keep a reference to avoid garbage collection
                label.pack()
            else:
                label = ttk.Label(frame, text=card.name)
                label.pack()
            button = ttk.Button(
                frame,
                text="Play",
                command=lambda idx=idx: self.play_card(idx)
            )
            button.pack()

    def display_stack(self):
        """
        Displays the current stack of spells and abilities.
        """
        # Clear previous stack display
        for widget in self.stack_frame.winfo_children():
            widget.destroy()

        ttk.Label(self.stack_frame, text="Stack:").pack()
        for item in reversed(self.game.stack):
            text = f"{item.name} (Owner: {item.owner.name})"
            if hasattr(item, 'target') and item.target:
                text += f" targeting {item.target.name}"
            ttk.Label(self.stack_frame, text=text).pack()

    def load_card_image(self, card_name):
        """
        Loads the image of a card if available.

        Args:
            card_name (str): The name of the card.

        Returns:
            ImageTk.PhotoImage: The image of the card or None if not found.
        """
        try:
            image = Image.open(f"images/{card_name}.jpg")
            return ImageTk.PhotoImage(image.resize((100, 150)))
        except FileNotFoundError:
            return None

    def tap_land(self, card):
        """
        Taps a land to add mana to the player's mana pool.

        Args:
            card (LandCard): The land card to tap.
        """
        try:
            self.player1.tap_land(card)
            self.update_gui()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while tapping the land: {e}")

    def play_card(self, idx):
        """
        Plays a card from the player's hand.

        Args:
            idx (int): The index of the card in the player's hand.
        """
        try:
            card = self.player1.hand[idx]
            if self.player1.can_play_card(card, self.game):
                self.player1.play_card_from_hand(card, self.game)
                self.update_gui()
            else:
                messagebox.showerror("Play Card", f"You cannot play {card.name} at this time.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while playing the card: {e}")

    def next_phase(self):
        """
        Advances the game to the next phase.
        """
        try:
            self.game.next_phase()
            self.handle_phase()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while advancing the phase: {e}")

    def handle_phase(self):
        """
        Handles the actions required for the current phase.
        """
        if self.game.is_game_over():
            return
        self.update_gui()
        phase = self.game.phase
        try:
            if phase == 'Draw':
                self.game.get_current_player().draw_card()
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'Main1':
                self.game.get_current_player().take_actions(self.game)
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'Declare Attackers':
                self.game.get_current_player().declare_attackers(self.game)
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'Declare Blockers':
                opponent = self.game.get_opponent()
                opponent.declare_blockers(self.game, self.game.get_current_player().attackers)
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'Combat Damage':
                self.game.get_current_player().assign_combat_damage(self.game)
                self.game.get_opponent().assign_combat_damage(self.game)
                self.cleanup_combat()
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'Main2':
                self.game.get_current_player().take_actions(self.game)
                self.game.next_phase()
                self.handle_phase()
            elif phase == 'End':
                self.game.next_turn()
                self.handle_phase()
            else:
                # Other phases
                self.game.next_phase()
                self.handle_phase()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during the {phase} phase: {e}")

    def cleanup_combat(self):
        """
        Cleans up after combat, removing dead creatures and updating the game state.
        """
        self.game.check_state_based_actions()
        self.update_gui()

    def save_game(self):
        """
        Saves the current game state to a file.
        """
        # Implement save functionality
        messagebox.showinfo("Save Game", "Game saving is not yet implemented.")

    def load_game(self):
        """
        Loads a game state from a file.
        """
        # Implement load functionality
        messagebox.showinfo("Load Game", "Game loading is not yet implemented.")

    def end_game(self, winner):
        """
        Ends the game and displays the winner.

        Args:
            winner (Player): The player who won the game.
        """
        messagebox.showinfo("Game Over", f"{winner.name} wins the game!")
        self.root.quit()

    def open_booster_pack(self):
        """
        Opens a booster pack and adds the cards to the player's collection.
        """
        pack_cost = 100  # Example cost
        if self.player1.adjust_currency(-pack_cost):
            card_pool = CardPool()
            pack_contents = card_pool.generate_booster_pack()
            # Update the player's collection
            for card_name in pack_contents:
                self.collection_manager.add_card(card_name)
            # Display the pack contents
            self.display_booster_pack_contents(pack_contents)
        else:
            messagebox.showerror("Booster Pack", "You do not have enough currency to purchase a booster pack.")

    def display_booster_pack_contents(self, pack_contents):
        """
        Displays the contents of the opened booster pack.

        Args:
            pack_contents (list): The list of card names in the booster pack.
        """
        pack_window = tk.Toplevel(self.root)
        pack_window.title("Booster Pack Contents")

        ttk.Label(pack_window, text="You opened a booster pack and received:").pack()

        for card_name in pack_contents:
            frame = ttk.Frame(pack_window)
            frame.pack(side=tk.LEFT)
            image = self.load_card_image(card_name)
            if image:
                label = ttk.Label(frame, image=image)
                label.image = image  # Keep a reference
                label.pack()
            else:
                label = ttk.Label(frame, text=card_name)
                label.pack()

        ttk.Button(pack_window, text="Close", command=pack_window.destroy).pack()

    def open_deck_builder(self):
        """
        Opens the deck builder interface for the player to build or edit their deck.
        """
        deck_builder_window = tk.Toplevel(self.root)
        deck_builder_window.title("Deck Builder")

        # Create frames for card pool and deck
        card_pool_frame = ttk.Frame(deck_builder_window)
        card_pool_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        deck_frame = ttk.Frame(deck_builder_window)
        deck_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Display card pool
        ttk.Label(card_pool_frame, text="Your Collection").pack()
        card_pool_listbox = tk.Listbox(card_pool_frame, selectmode=tk.SINGLE)
        card_pool_listbox.pack(fill=tk.BOTH, expand=True)

        # Display current deck
        ttk.Label(deck_frame, text="Your Deck").pack()
        deck_listbox = tk.Listbox(deck_frame)
        deck_listbox.pack(fill=tk.BOTH, expand=True)

        # Populate card pool
        collection = self.collection_manager.get_collection()
        for card_name, quantity in collection.items():
            card_pool_listbox.insert(tk.END, f"{card_name} (x{quantity})")

        # Add buttons to add/remove cards
        add_button = ttk.Button(deck_builder_window, text="Add Card", command=lambda: self.add_card_to_deck(card_pool_listbox, deck_listbox))
        add_button.pack(side=tk.LEFT)
        remove_button = ttk.Button(deck_builder_window, text="Remove Card", command=lambda: self.remove_cards_from_deck(deck_listbox))
        remove_button.pack(side=tk.RIGHT)

        # Save and load deck buttons
        save_button = ttk.Button(deck_builder_window, text="Save Deck", command=lambda: self.save_deck(deck_listbox))
        save_button.pack(side=tk.LEFT)
        load_button = ttk.Button(deck_builder_window, text="Load Deck", command=lambda: self.load_deck(deck_listbox))
        load_button.pack(side=tk.RIGHT)

        # Store references
        self.deck_listbox = deck_listbox
        self.card_pool_listbox = card_pool_listbox

    def add_card_to_deck(self, card_pool_listbox, deck_listbox):
        """
        Adds a selected card from the collection to the deck.

        Args:
            card_pool_listbox (tk.Listbox): The listbox containing the collection.
            deck_listbox (tk.Listbox): The listbox containing the deck.
        """
        selection = card_pool_listbox.curselection()
        if selection:
            index = selection[0]
            item = card_pool_listbox.get(index)
            card_name = item.split(" (x")[0]
            owned_quantity = self.collection_manager.get_card_quantity(card_name)
            deck_quantity = deck_listbox.get(0, tk.END).count(card_name)
            if deck_quantity < owned_quantity:
                deck_listbox.insert(tk.END, card_name)
            else:
                messagebox.showerror("Deck Builder", f"You do not have more copies of {card_name} to add.")

    def remove_cards_from_deck(self, deck_listbox):
        """
        Removes selected cards from the deck.

        Args:
            deck_listbox (tk.Listbox): The listbox containing the deck.
        """
        selected_indices = list(deck_listbox.curselection())
        selected_indices.sort(reverse=True)  # Remove from the end to avoid index shift
        for index in selected_indices:
            deck_listbox.delete(index)

    def save_deck(self, deck_listbox):
        """
        Saves the current deck to a file.

        Args:
            deck_listbox (tk.Listbox): The listbox containing the deck.
        """
        deck = [deck_listbox.get(idx) for idx in range(deck_listbox.size())]
        try:
            with open(f'{self.player1.name}_deck.txt', 'w') as f:
                for card_name in deck:
                    f.write(f"{card_name}\n")
            messagebox.showinfo("Deck Builder", "Deck saved successfully.")
        except Exception as e:
            messagebox.showerror("Deck Builder", f"An error occurred while saving the deck: {e}")

    def load_deck(self, deck_listbox):
        """
        Loads a deck from a file.

        Args:
            deck_listbox (tk.Listbox): The listbox to populate with the loaded deck.
        """
        try:
            with open(f'{self.player1.name}_deck.txt', 'r') as f:
                deck_listbox.delete(0, tk.END)
                for line in f:
                    card_name = line.strip()
                    deck_listbox.insert(tk.END, card_name)
            messagebox.showinfo("Deck Builder", "Deck loaded successfully.")
        except FileNotFoundError:
            messagebox.showerror("Deck Builder", "No saved deck found.")
        except Exception as e:
            messagebox.showerror("Deck Builder", f"An error occurred while loading the deck: {e}")

    def view_collection(self):
        """
        Displays the player's card collection.
        """
        collection_window = tk.Toplevel(self.root)
        collection_window.title("Your Collection")

        ttk.Label(collection_window, text="Your Card Collection:").pack()

        collection = self.collection_manager.get_collection()
        for card_name, quantity in collection.items():
            frame = ttk.Frame(collection_window)
            frame.pack(side=tk.TOP)
            image = self.load_card_image(card_name)
            if image:
                label = ttk.Label(frame, image=image)
                label.image = image
                label.pack(side=tk.LEFT)
            else:
                label = ttk.Label(frame, text=card_name)
                label.pack(side=tk.LEFT)
            qty_label = ttk.Label(frame, text=f"Quantity: {quantity}")
            qty_label.pack(side=tk.LEFT)

if __name__ == "__main__":
    try:
        GameGUI()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
