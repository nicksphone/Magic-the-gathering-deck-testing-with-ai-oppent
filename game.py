# game.py

import random
from logger import Logger
from game_event import GameEvent
from card import Card
from creature_card import CreatureCard

class Game:
    """
    Manages the core game logic, including phases, turns, and interactions between players.
    """

    def __init__(self, player1, player2, gui):
        self.players = [player1, player2]
        self.current_player_index = 0
        self.phase = 'Draw'
        self.turn = 1
        self.stack = []
        self.priority_passed = [False, False]
        self.gui = gui
        self.logger = Logger()
        self.spells_cast_this_turn = []
        self.event_listeners = []
        self.game_over = False
        self.end_of_turn_effects = []  # List to hold effects that last until end of turn

    def start_game(self):
        """
        Starts the game by having each player draw their starting hand and initiating the first phase.
        """
        for player in self.players:
            player.game = self
            player.draw_hand()
        self.current_player_index = 0
        self.phase = 'Draw'
        self.gui.handle_phase()

    def get_current_player(self):
        """
        Returns the current player.

        Returns:
            Player: The player whose turn it currently is.
        """
        return self.players[self.current_player_index]

    def get_opponent(self, player=None):
        """
        Returns the opponent of the given player.

        Args:
            player (Player, optional): The player whose opponent is to be found. Defaults to None.

        Returns:
            Player: The opponent player.
        """
        if player:
            return self.players[1] if self.players[0] == player else self.players[0]
        return self.players[1 - self.current_player_index]

    def next_phase(self):
        """
        Advances the game to the next phase, handling phase transitions and turn changes.
        """
        phases = ['Untap', 'Upkeep', 'Draw', 'Main1', 'Beginning of Combat',
                  'Declare Attackers', 'Declare Blockers', 'Combat Damage', 'End of Combat',
                  'Main2', 'End', 'Cleanup']
        current_index = phases.index(self.phase)
        if current_index == len(phases) - 1:
            self.phase = phases[0]
            self.next_turn()
        else:
            self.phase = phases[current_index + 1]
        self.reset_priority()
        self.gui.update_gui()

    def next_turn(self):
        """
        Proceeds to the next turn, handling end-of-turn effects and resetting turn-based attributes.
        """
        # Apply end-of-turn effects
        for effect in self.end_of_turn_effects:
            try:
                effect()
            except Exception as e:
                self.logger.record(f"Error during end-of-turn effect: {e}")
        self.end_of_turn_effects.clear()

        self.turn += 1
        self.current_player_index = (self.current_player_index + 1) % 2
        self.phase = 'Untap'
        self.reset_turn()
        self.logger.record(f"Turn {self.turn}: {self.get_current_player().name}'s turn")

        # Remove summoning sickness from creatures
        for card in self.get_current_player().battlefield:
            if isinstance(card, CreatureCard):
                card.on_turn_start()

    def reset_turn(self):
        """
        Resets turn-specific attributes and statuses for all players.
        """
        self.spells_cast_this_turn = []
        for player in self.players:
            player.mana_pool = {'White': 0, 'Blue': 0, 'Black': 0, 'Red': 0, 'Green': 0, 'Colorless': 0}
            for card in player.battlefield:
                if hasattr(card, 'tap_status'):
                    card.tap_status = False
            # Reset land play for the new turn
            if hasattr(player, 'land_played_this_turn'):
                player.land_played_this_turn = False
        self.reset_priority()

    def reset_priority(self):
        """
        Resets the priority passed status for both players.
        """
        self.priority_passed = [False, False]

    def add_to_stack(self, item):
        """
        Adds a spell or ability to the stack.

        Args:
            item: The spell or ability to add.
        """
        self.stack.append(item)
        self.logger.record(f"{item.owner.name} adds {item.name} to the stack")
        if isinstance(item, Card):
            self.spells_cast_this_turn.append(item)
        self.reset_priority()
        self.give_priority()

    def give_priority(self):
        """
        Gives priority to the current player to respond to the stack.
        """
        current_player = self.get_current_player()
        if current_player.is_ai:
            current_player.decide_response(self)
        else:
            # For simplicity, auto-pass priority for the player
            self.pass_priority()

    def pass_priority(self):
        """
        Handles the passing of priority between players.
        """
        self.priority_passed[self.current_player_index] = True
        if all(self.priority_passed):
            if self.stack:
                self.resolve_top_of_stack()
                self.reset_priority()
                self.give_priority()
            else:
                self.next_phase()
                self.gui.handle_phase()
        else:
            self.switch_player()
            self.give_priority()

    def switch_player(self):
        """
        Switches the current player index to the next player.
        """
        self.current_player_index = (self.current_player_index + 1) % 2

    def resolve_top_of_stack(self):
        """
        Resolves the top item on the stack.
        """
        try:
            item = self.stack.pop()
            self.logger.record(f"Resolving {item.name}")
            item.resolve(self)
            self.check_state_based_actions()
        except Exception as e:
            self.logger.record(f"Error resolving {item.name}: {e}")

    def check_state_based_actions(self):
        """
        Checks and handles state-based actions like creatures dying due to zero toughness.
        """
        for player in self.players:
            for card in player.battlefield[:]:
                if isinstance(card, CreatureCard) and card.toughness <= 0:
                    player.battlefield.remove(card)
                    player.graveyard.append(card)
                    self.logger.record(f"{card.name} dies due to having 0 toughness")
        for player in self.players:
            if player.life_total <= 0:
                self.end_game(winner=self.get_opponent(player))

    def end_game(self, winner):
        """
        Ends the game and declares the winner.

        Args:
            winner (Player): The player who won the game.
        """
        self.logger.record(f"{winner.name} wins the game!")
        self.game_over = True
        self.gui.end_game(winner)

    def trigger_event(self, event):
        """
        Triggers an event, applying replacement effects and triggering abilities.

        Args:
            event (GameEvent): The event to trigger.
        """
        # Apply replacement effects
        event = self.apply_replacement_effects(event)
        if event:
            # Notify all permanents with triggered abilities
            for player in self.players:
                for permanent in player.battlefield:
                    if hasattr(permanent, 'triggered_abilities'):
                        for ability in permanent.triggered_abilities:
                            if ability.trigger_condition(event, self, permanent):
                                ability.owner = permanent.owner
                                ability.source_card = permanent
                                self.add_to_stack(ability)

    def apply_replacement_effects(self, event):
        """
        Applies any replacement effects to the event.

        Args:
            event (GameEvent): The event to modify.

        Returns:
            GameEvent: The modified event or None if the event is replaced.
        """
        for player in self.players:
            for permanent in player.battlefield:
                if hasattr(permanent, 'replacement_effects'):
                    for effect in permanent.replacement_effects:
                        event = effect.apply(event, self)
                        if event is None:
                            return None
        return event

    def is_game_over(self):
        """
        Checks if the game is over.

        Returns:
            bool: True if the game is over, False otherwise.
        """
        return self.game_over

    def get_valid_targets(self, card):
        """
        Returns a list of valid targets for the given card.

        Args:
            card (Card): The card for which to find valid targets.

        Returns:
            list: A list of valid target objects.
        """
        valid_targets = []
        opponent = self.get_opponent(card.owner)
        if card.name == "Lightning Bolt":
            # Lightning Bolt can target creatures or players
            valid_targets.extend([creature for creature in opponent.battlefield if isinstance(creature, CreatureCard)])
            valid_targets.append(opponent)
        elif card.name == "Counterspell":
            # Counterspell targets spells on the stack
            valid_targets.extend([spell for spell in self.stack if spell.owner != card.owner])
        else:
            # Default to opponent's creatures
            valid_targets.extend([creature for creature in opponent.battlefield if isinstance(creature, CreatureCard)])
        return valid_targets

    def add_end_of_turn_effect(self, effect):
        """
        Adds an effect to be executed at the end of the turn.

        Args:
            effect (function): The effect function to add.
        """
        self.end_of_turn_effects.append(effect)

    def check_for_mana_burn(self):
        """
        Checks for unused mana in the mana pool (mana burn is obsolete but can be implemented if desired).
        """
        pass  # Mana burn is no longer a rule in Magic: The Gathering

