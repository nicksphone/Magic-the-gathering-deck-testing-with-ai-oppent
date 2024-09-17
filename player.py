# player.py

import random
from card import Card
from creature_card import CreatureCard
from land_card import LandCard
from instant_card import InstantCard
from sorcery_card import SorceryCard
from tkinter import messagebox

class Player:
    """
    Represents a player in the game, handling actions like drawing cards, playing cards, and managing resources.
    """
    def __init__(self, name, is_ai=False):
        self.name = name
        self.is_ai = is_ai
        self.library = []
        self.hand = []
        self.battlefield = []
        self.graveyard = []
        self.life_total = 20
        self.mana_pool = {'White': 0, 'Blue': 0, 'Black': 0, 'Red': 0, 'Green': 0, 'Colorless': 0}
        self.attackers = []
        self.blockers = {}
        self.currency = 1000  # Starting in-game currency
        self.game = None

        self.load_deck()
        self.shuffle_library()

    def load_deck(self):
        # For simplicity, load a default deck
        card_names = ["Plains"] * 10 + ["Mountain"] * 10 + ["Savannah Lions"] * 4 + ["Lightning Bolt"] * 4
        for name in card_names:
            card = self.game.gui.card_factory.create_card(name)
            if card:
                card.owner = self
                self.library.append(card)

    def shuffle_library(self):
        random.shuffle(self.library)

    def draw_hand(self):
        for _ in range(7):
            self.draw_card()

    def draw_card(self):
        if self.library:
            card = self.library.pop(0)
            self.hand.append(card)
            card.zone = 'hand'
        else:
            self.life_total = 0  # Lose the game if cannot draw

    def can_pay_mana_cost(self, mana_cost):
        available_mana = self.mana_pool.copy()
        for color, amount in mana_cost.items():
            if available_mana.get(color, 0) < amount:
                return False
            available_mana[color] -= amount
        return True

    def pay_mana_cost(self, mana_cost):
        for color, amount in mana_cost.items():
            self.mana_pool[color] -= amount

    def tap_land(self, land_card):
        if not land_card.tap_status:
            land_card.tap_status = True
            self.mana_pool[land_card.mana_type] += 1

    def can_play_card(self, card, game):
        if card.timing == 'Instant' or 'Flash' in card.keywords:
            return True
        elif card.timing == 'Sorcery' and game.phase in ['Main1', 'Main2'] and self == game.get_current_player() and not game.stack:
            return True
        elif card.timing == 'Land' and game.phase in ['Main1', 'Main2'] and self == game.get_current_player() and not game.stack:
            # Ensure land hasn't been played yet this turn
            return not getattr(self, 'land_played_this_turn', False)
        else:
            return False

    def play_card_from_hand(self, card, game):
        if card.target_required:
            target = self.select_target(card, game)
            if target is None:
                game.logger.record(f"{self.name} could not find a valid target for {card.name}")
                return
        else:
            target = None
        if self.can_pay_mana_cost(card.mana_cost):
            self.pay_mana_cost(card.mana_cost)
            self.hand.remove(card)
            card.owner = self
            card.target = target
            if card.has_keyword("Cascade"):
                self.handle_cascade(card, game)
            game.add_to_stack(card)
            game.logger.record(f"{self.name} casts {card.name}")
        else:
            game.logger.record(f"{self.name} cannot pay the mana cost for {card.name}")

    def handle_cascade(self, source_card, game):
        game.logger.record(f"{self.name} triggers Cascade from {source_card.name}")
        exiled_cards = []
        while True:
            if not self.library:
                game.logger.record(f"{self.name}'s library is empty.")
                break
            exiled_card = self.library.pop(0)
            exiled_cards.append(exiled_card)
            game.logger.record(f"{self.name} exiles {exiled_card.name}")
            if exiled_card.card_type != 'Land' and self.get_converted_mana_cost(exiled_card.mana_cost) < self.get_converted_mana_cost(source_card.mana_cost):
                choice = 'yes'
                if not self.is_ai:
                    choice = messagebox.askyesno("Cascade", f"Do you want to cast {exiled_card.name} without paying its mana cost?")
                if choice == 'yes':
                    game.logger.record(f"{self.name} casts {exiled_card.name} from Cascade")
                    exiled_card.owner = self
                    game.add_to_stack(exiled_card)
                else:
                    game.logger.record(f"{self.name} chooses not to cast {exiled_card.name}")
                break
        random.shuffle(exiled_cards)
        self.library.extend(exiled_cards)
        game.logger.record(f"{self.name} puts exiled cards on the bottom of their library")

    def get_converted_mana_cost(self, mana_cost):
        return sum(mana_cost.values())

    def select_target(self, card, game):
        valid_targets = game.get_valid_targets(card)
        if valid_targets:
            if self.is_ai:
                # Simple AI target selection
                return valid_targets[0]
            else:
                # For simplicity, auto-select the first target
                return valid_targets[0]
        else:
            return None

    def adjust_currency(self, amount):
        if self.currency + amount >= 0:
            self.currency += amount
            return True
        else:
            return False

    def take_actions(self, game):
        # Placeholder for player actions during main phases
        pass

    # Additional methods for actions, combat, abilities, etc.
