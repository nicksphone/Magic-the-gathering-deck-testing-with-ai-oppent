# game.py

import random
from card_factory import CardFactory
from player import Player

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

    def play_card(self, card):
        """
        Handles playing a card during a player's turn, including handling dual-option cards that can be multiple types.
        
        Args:
            card: The card that is being played.
        """
        player = card.owner

        if isinstance(card, DualOptionCard):
            # Prompt the player or AI to choose how to play the card
            choice = self.gui.prompt_dual_option(card) if not player.is_ai else self.ai_decide_dual_option(card)
            card.play_card(choice, player)
        else:
            # Handle normal card types
            if card.card_type == 'Creature':
                player.battlefield.append(card)
                print(f"{player.name} played {card.name} as a Creature.")
            elif card.card_type == 'Land':
                player.lands.append(card)
                print(f"{player.name} played land {card.name}.")
            elif card.card_type in ['Instant', 'Sorcery']:
                print(f"{player.name} cast {card.name}.")
                self.resolve_spell(card)

        player.hand.remove(card)

        # Update the game state or GUI if needed
        if self.gui:
            self.gui.display_hand()

    def ai_decide_dual_option(self, card):
        """
        AI decides how to play a DualOptionCard based on the game state.
        
        Args:
            card: The DualOptionCard in question.

        Returns:
            str: The chosen option (e.g., "Creature", "Land", etc.).
        """
        # Example logic: If the AI needs lands, play it as a land; otherwise, as a creature
        if len(self.player1.lands) < 3:  # Example condition: If the AI needs more lands
            return "Land"
        return "Creature"  # Default to creature if it doesn't need lands

    def ai_take_turn(self, player):
        """
        AI takes its turn, playing cards and making decisions based on the game state.
        
        Args:
            player (Player): The AI player.
        """
        print(f"{player.name} (AI) is taking its turn.")
        
        # AI plays cards based on hand and game state
        for card in player.hand:
            if isinstance(card, DualOptionCard):
                choice = self.ai_decide_dual_option(card)
                card.play_card(choice, player)
            elif isinstance(card, TriggeredCard):
                print(f"{player.name} (AI) plays {card.name} (triggered effect).")
                card.apply_effect(self)
                player.battlefield.append(card)
            else:
                self.play_card(card)

        # AI ends its turn
        print(f"{player.name} (AI) ends its turn.")

    def resolve_spell(self, spell):
        """
        Handles the resolution of a spell.
        
        Args:
            spell: The spell being cast.
        """
        if spell.name == "Lightning Bolt":
            target = self.choose_target(spell)
            if target:
                print(f"{spell.name} deals 3 damage to {target.name}.")
                target.take_damage(3)

    def choose_target(self, spell):
        """
        Chooses a target for a spell.
        
        Args:
            spell: The spell being cast.
        
        Returns:
            Target (Player or CreatureCard): The chosen target.
        """
        if self.gui:
            # GUI logic to choose a target
            pass
        else:
            # Simulate choosing a random target in a non-GUI environment
            opponent = self.player1 if spell.owner == self.player2 else self.player2
            if opponent.battlefield:
                return random.choice(opponent.battlefield)
            return opponent

    def combat_phase(self, player):
        """
        Handle the combat phase, where creatures can attack.
        """
        if player.battlefield:
            print(f"{player.name}'s creatures prepare to attack.")
            for creature in player.battlefield:
                if creature.can_attack():
                    print(f"{creature.name} is ready to attack.")
                    target = self.choose_combat_target(creature)
                    if target:
                        self.resolve_combat(creature, target)

    def choose_combat_target(self, creature):
        """
        Chooses a target for the attacking creature.
        
        Args:
            creature: The attacking creature.

        Returns:
            Target: The target being attacked.
        """
        opponent = self.player1 if creature.owner == self.player2 else self.player2

        if self.gui:
            return self.gui.prompt_target_selection(opponent)
        else:
            if opponent.battlefield:
                return random.choice(opponent.battlefield)
            return opponent

    def resolve_combat(self, attacker, target):
        """
        Resolves combat between an attacking creature and a target.
        
        Args:
            attacker: The attacking creature.
            target: The target of the attack (either a creature or a player).
        """
        print(f"{attacker.name} attacks {target.name}.")
        if isinstance(target, Player):
            target.take_damage(attacker.power)
            print(f"{target.name} takes {attacker.power} damage.")
        else:
            # Creature vs Creature combat
            attacker.take_damage(target.power)
            target.take_damage(attacker.power)
            print(f"{attacker.name} deals {attacker.power} damage to {target.name}.")
            print(f"{target.name} deals {target.power} damage to {attacker.name}.")
            # Remove dead creatures
            if attacker.toughness <= 0:
                print(f"{attacker.name} dies.")
                attacker.owner.battlefield.remove(attacker)
            if target.toughness <= 0:
                print(f"{target.name} dies.")
                target.owner.battlefield.remove(target)

    def next_turn(self):
        """
        Advances the game to the next turn.
        """
        self.turn += 1
        current_player = self.player1 if self.turn % 2 == 1 else self.player2
        print(f"Turn {self.turn}: {current_player.name}'s turn.")

        self.start_phase(current_player, "Main Phase")
        self.start_phase(current_player, "Combat Phase")
        self.start_phase(current_player, "End Phase")

    def start_phase(self, player, phase):
        """
        Begins a specific phase for the player.
        
        Args:
            player (Player): The player whose turn it is.
            phase (str): The phase of the turn.
        """
        self.current_phase = phase
        print(f"{phase} begins for {player.name}.")

        if phase == "Main Phase":
            self.draw_card(player)
            # Player can play cards during the main phase
            self.play_phase(player)

        elif phase == "Combat Phase":
            # Handle combat logic (attacking, defending, etc.)
            self.combat_phase(player)

        elif phase == "End Phase":
            print(f"{player.name}'s turn ends.")

    def play_phase(self, player):
        """
        Handles the play phase, where the player can play cards.
        """
        if self.gui:
            self.gui.display_hand()  # Allow the player to select cards to play from the GUI
        else:
            # For non-GUI mode, simulate the player playing cards
            if player.hand:
                card_to_play = player.hand[0]
                self.play_card(card_to_play)

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


        return deck

    # Rest of the Game class remains the same, with phases and targeting...
