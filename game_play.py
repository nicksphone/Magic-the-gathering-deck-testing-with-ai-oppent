# game_play.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QHBoxLayout, QScrollArea, QInputDialog
)
from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtCore import Qt, QSize, pyqtSignal
import os
import re

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
    def mousePressEvent(self, event):
        self.clicked.emit()



class Card:
    def __init__(self, name, power, toughness, abilities=None):
        self.name = name
        self.power = power
        self.toughness = toughness
        self.abilities = abilities or []

    def __str__(self):
        return f"{self.name} (Power: {self.power}, Toughness: {self.toughness}, Abilities: {self.abilities})"

    def display_info(self):
        print(f"Card Name: {self.name}")
        print(f"Power: {self.power}, Toughness: {self.toughness}")
        if self.abilities:
            print(f"Abilities: {', '.join(self.abilities)}")
class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None, ai_deck=None):
        super().__init__(parent)
        self.player_deck = [Card(card_data) for card_data in player_deck] or []
        self.ai_deck = [Card(card_data) for card_data in ai_deck] or []
        self.player_hand = []
        self.player_battlefield = []
        self.player_lands = []
        self.ai_hand = []
        self.ai_battlefield = []
        self.ai_lands = []
        self.life_total = 20
        self.ai_life_total = 20

        # Initialize the player's mana pool as a dictionary of mana types
        self.player_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        self.ai_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}

        self.selected_card = None  # Initialize selected card
        self.land_played_this_turn = False  # Track if the player has played a land this turn
        self.turn_phase = 'begin'  # Tracks the current phase of the turn
        self.turn_player = 'player'  # Whose turn it is

        self.attacking_creatures = []  # Player's attacking creatures
        self.blocking_creatures = {}  # AI's blockers: {attacker: blocker}

        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering')
        self.setGeometry(300, 300, 800, 600)

        self.main_layout = QVBoxLayout()

        # Life totals
        life_layout = QHBoxLayout()
        self.life_label = QLabel(f"Your Life Total: {self.life_total}", self)
        self.ai_life_label = QLabel(f"AI Life Total: {self.ai_life_total}", self)
        life_layout.addWidget(self.life_label)
        life_layout.addWidget(self.ai_life_label)
        self.main_layout.addLayout(life_layout)

        # AI Battlefield display
        ai_battlefield_layout = QVBoxLayout()
        self.ai_battlefield_label = QLabel("AI's Battlefield:", self)
        ai_battlefield_layout.addWidget(self.ai_battlefield_label)

        self.ai_battlefield_area = QScrollArea()
        self.ai_battlefield_widget = QWidget()
        self.ai_battlefield_layout = QHBoxLayout()
        self.ai_battlefield_widget.setLayout(self.ai_battlefield_layout)
        self.ai_battlefield_area.setWidget(self.ai_battlefield_widget)
        self.ai_battlefield_area.setWidgetResizable(True)
        ai_battlefield_layout.addWidget(self.ai_battlefield_area)

        self.main_layout.addLayout(ai_battlefield_layout)

        # Player Battlefield display
        battlefield_layout = QVBoxLayout()
        self.battlefield_label = QLabel("Your Battlefield:", self)
        battlefield_layout.addWidget(self.battlefield_label)

        self.battlefield_area = QScrollArea()
        self.battlefield_widget = QWidget()
        self.battlefield_layout = QHBoxLayout()
        self.battlefield_widget.setLayout(self.battlefield_layout)
        self.battlefield_area.setWidget(self.battlefield_widget)
        self.battlefield_area.setWidgetResizable(True)
        battlefield_layout.addWidget(self.battlefield_area)

        self.main_layout.addLayout(battlefield_layout)

        # Mana pool label
        self.mana_label = QLabel(f"Your Mana Pool: {self.player_mana_pool}", self)
        self.main_layout.addWidget(self.mana_label)

        # Lands in play label
        self.lands_label = QLabel(f"Lands in Play: {len(self.player_lands)}", self)
        self.main_layout.addWidget(self.lands_label)

        # Hand display
        hand_layout = QVBoxLayout()
        self.hand_label = QLabel(f"Your Hand:", self)
        hand_layout.addWidget(self.hand_label)

        self.hand_area = QScrollArea()
        self.hand_widget = QWidget()
        self.hand_layout = QHBoxLayout()
        self.hand_widget.setLayout(self.hand_layout)
        self.hand_area.setWidget(self.hand_widget)
        self.hand_area.setWidgetResizable(True)
        hand_layout.addWidget(self.hand_area)

        self.main_layout.addLayout(hand_layout)

        # Buttons
        button_layout = QHBoxLayout()
        play_land_btn = QPushButton('Play Land', self)
        play_land_btn.clicked.connect(self.play_land)
        button_layout.addWidget(play_land_btn)

        play_btn = QPushButton('Play Spell', self)
        play_btn.clicked.connect(self.play_card)
        button_layout.addWidget(play_btn)

        attack_btn = QPushButton('Attack', self)
        attack_btn.clicked.connect(self.attack)
        button_layout.addWidget(attack_btn)

        # Add Proceed to Combat Button
        self.proceed_to_combat_btn = QPushButton('Proceed to Combat', self)
        self.proceed_to_combat_btn.clicked.connect(self.combat_phase)
        self.proceed_to_combat_btn.setEnabled(False)  # Disabled by default
        button_layout.addWidget(self.proceed_to_combat_btn)

        end_turn_btn = QPushButton('End Turn', self)
        end_turn_btn.clicked.connect(self.end_turn)
        button_layout.addWidget(end_turn_btn)

        self.main_layout.addLayout(button_layout)

        self.setLayout(self.main_layout)

        self.draw_initial_hand()
        self.ai_draw_initial_hand()

        self.start_turn()

    def resizeEvent(self, event):
        """
        Overrides the resize event to adjust the card image sizes when the window is resized.
        """
        super().resizeEvent(event)
        self.update_hand_display()
        self.update_battlefield_display()
        self.update_ai_battlefield_display()

    def calculate_card_size(self, scroll_area, num_cards):
        """
        Calculates the appropriate card size based on the scroll area size and number of cards.
        """
        if num_cards == 0:
            return QSize(0, 0)

        # Get the available width in the scroll area
        viewport = scroll_area.viewport()
        available_width = viewport.width() - scroll_area.verticalScrollBar().sizeHint().width()
        available_height = viewport.height()

        # Calculate max card width
        max_card_width = available_width / num_cards
        # Maintain aspect ratio (approximately 2:3 for Magic cards)
        card_width = max_card_width * 0.9  # Slightly reduce to add spacing
        card_height = card_width * 1.4

        # Limit card size to reasonable bounds
        card_width = min(card_width, 200)
        card_height = min(card_height, 280)

        return QSize(int(card_width), int(card_height))

    def draw_initial_hand(self):
        for _ in range(7):
            if self.player_deck:
                card = self.player_deck.pop(0)
                self.player_hand.append(card)
        self.update_hand_display()

    def ai_draw_initial_hand(self):
        for _ in range(7):
            if self.ai_deck:
                card = self.ai_deck.pop(0)
                self.ai_hand.append(card)

    def update_hand_display(self):
        # Clear current hand display
        for i in reversed(range(self.hand_layout.count())):
            widget = self.hand_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        num_cards = len(self.player_hand)
        card_size = self.calculate_card_size(self.hand_area, num_cards)

        # Display cards in hand
        for card in self.player_hand:
            card_label = ClickableLabel()
            pixmap = card.get_pixmap().scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            card_label.setObjectName(card.name)
            card_label.clicked.connect(lambda c=card: self.hand_card_clicked(c))
            self.hand_layout.addWidget(card_label)

        # Update the layout
        self.hand_layout.addStretch()

    def update_battlefield_display(self):
        # Clear current battlefield display
        for i in reversed(range(self.battlefield_layout.count())):
            widget = self.battlefield_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        num_cards = len(self.player_battlefield) + len(self.player_lands)
        card_size = self.calculate_card_size(self.battlefield_area, num_cards)

        # Display lands first
        for land in self.player_lands:
            card_label = ClickableLabel()
            pixmap = land.get_pixmap()
            if land.is_tapped:
                pixmap = pixmap.transformed(QTransform().rotate(90))
            pixmap = pixmap.scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            card_label.clicked.connect(lambda l=land: self.land_clicked(l, 'player'))
            self.battlefield_layout.addWidget(card_label)

        # Display other permanents
        for card in self.player_battlefield:
            card_label = ClickableLabel()
            pixmap = card.get_pixmap()
            if card.is_tapped:
                pixmap = pixmap.transformed(QTransform().rotate(90))
            pixmap = pixmap.scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            card_label.clicked.connect(lambda c=card: self.battlefield_card_clicked(c))
            self.battlefield_layout.addWidget(card_label)

        # Update the layout
        self.battlefield_layout.addStretch()

    def update_ai_battlefield_display(self):
        # Clear current AI battlefield display
        for i in reversed(range(self.ai_battlefield_layout.count())):
            widget = self.ai_battlefield_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        num_cards = len(self.ai_battlefield) + len(self.ai_lands)
        card_size = self.calculate_card_size(self.ai_battlefield_area, num_cards)

        # Display AI's lands
        for land in self.ai_lands:
            card_label = QLabel()
            pixmap = land.get_pixmap()
            if land.is_tapped:
                pixmap = pixmap.transformed(QTransform().rotate(90))
            pixmap = pixmap.scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            self.ai_battlefield_layout.addWidget(card_label)

        # Display AI's other permanents
        for card in self.ai_battlefield:
            card_label = QLabel()
            pixmap = card.get_pixmap()
            if card.is_tapped:
                pixmap = pixmap.transformed(QTransform().rotate(90))
            pixmap = pixmap.scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            self.ai_battlefield_layout.addWidget(card_label)

        # Update the layout
        self.ai_battlefield_layout.addStretch()

    def hand_card_clicked(self, card):
        self.selected_card = card
        QMessageBox.information(self, "Card Selected", f"You selected {card.name}.")

    def land_clicked(self, land, owner):
        if owner == 'player':
            if not land.is_tapped:
                mana_types = land.get_mana_types()
                if len(mana_types) == 1:
                    mana_type = mana_types[0]
                else:
                    # Prompt the player to choose a mana type
                    mana_type, ok = QInputDialog.getItem(self, "Choose Mana Type", f"Choose mana from {land.name}:", mana_types, 0, False)
                    if not ok:
                        return  # Player canceled the selection

                land.tap()
                self.player_mana_pool[mana_type] += 1
                self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")
                self.update_battlefield_display()
                QMessageBox.information(self, "Land Tapped", f"{land.name} tapped for {mana_type} mana.")
            else:
                QMessageBox.warning(self, "Land Already Tapped", f"{land.name} is already tapped.")

    def battlefield_card_clicked(self, card):
        if self.turn_phase == 'attack':
            if card in self.player_battlefield and not card.is_tapped and not card.summoning_sickness:
                if card in self.attacking_creatures:
                    self.attacking_creatures.remove(card)
                    QMessageBox.information(self, "Attack", f"{card.name} removed from attackers.")
                else:
                    self.attacking_creatures.append(card)
                    QMessageBox.information(self, "Attack", f"{card.name} added to attackers.")
            else:
                QMessageBox.warning(self, "Cannot Attack", f"{card.name} cannot attack.")

    def play_land(self):
        if self.land_played_this_turn:
            QMessageBox.warning(self, "Land Play", "You have already played a land this turn.")
            return
        if self.selected_card and self.selected_card in self.player_hand:
            if self.selected_card.is_land():
                land = self.selected_card
                if land.mana_cost and land.mana_cost != '':
                    # Land has a mana cost, check if player has enough mana
                    mana_cost = self.parse_mana_cost(land.mana_cost)
                    if self.has_enough_mana(mana_cost, self.player_mana_pool):
                        self.pay_mana_cost(mana_cost, self.player_mana_pool)
                        self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")
                    else:
                        QMessageBox.warning(self, "Not Enough Mana", f"You don't have enough mana to play {land.name}.")
                        return
                # Proceed to play the land
                self.player_hand.remove(land)
                self.player_lands.append(land)
                self.update_hand_display()
                self.update_battlefield_display()
                self.lands_label.setText(f"Lands in Play: {len(self.player_lands)}")
                self.selected_card = None
                self.land_played_this_turn = True
                QMessageBox.information(self, "Land Played", f"You played {land.name}.")
            else:
                QMessageBox.warning(self, "Invalid Card", "Selected card is not a land.")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a land card to play.")

    def reset_all_permanents(self):
        # Reset lands
        for land in self.player_lands:
            land.untap()
        # Reset creatures and other permanents
        for card in self.player_battlefield:
            card.untap()
            card.can_attack = True
            card.summoning_sickness = False  # Creatures lose summoning sickness after one turn

        # Reset AI's lands and permanents
        for land in self.ai_lands:
            land.untap()
        for card in self.ai_battlefield:
            card.untap()
            card.can_attack = True
            card.summoning_sickness = False

    def apply_unused_mana_penalty(self):
        # Calculate total unused mana
        unused_mana = sum(self.player_mana_pool.values())
        if unused_mana > 0:
            self.life_total -= unused_mana
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.warning(self, "Unused Mana Burn", f"You take {unused_mana} damage from unused mana!")
        # Reset mana pool
        self.player_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")

    def parse_mana_cost(self, mana_cost_str):
        """
        Parses mana cost string and returns a dictionary of required mana types.
        """
        mana_cost = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        # Find numbers (colorless mana)
        numbers = re.findall(r'\d+', mana_cost_str)
        if numbers:
            mana_cost['C'] = int(numbers[0])

        # Find colored mana symbols
        colored_mana = re.findall(r'\{([WUBRG])\}', mana_cost_str)
        for symbol in colored_mana:
            mana_cost[symbol] += 1

        return mana_cost

    def has_enough_mana(self, mana_cost, mana_pool):
        """
        Checks if the player has enough mana in their pool to pay the mana cost.
        """
        temp_pool = mana_pool.copy()
        # First, pay colored mana
        for color in ['W', 'U', 'B', 'R', 'G']:
            if mana_cost[color] > temp_pool[color]:
                return False  # Not enough colored mana
            else:
                temp_pool[color] -= mana_cost[color]

        # Then, pay colorless mana
        total_available = sum(temp_pool.values())
        if mana_cost['C'] > total_available:
            return False  # Not enough mana
        else:
            # Subtract colorless mana cost from available mana
            mana_needed = mana_cost['C']
            for mana_type in ['C', 'W', 'U', 'B', 'R', 'G']:
                if temp_pool[mana_type] >= mana_needed:
                    temp_pool[mana_type] -= mana_needed
                    mana_needed = 0
                    break
                else:
                    mana_needed -= temp_pool[mana_type]
                    temp_pool[mana_type] = 0
            if mana_needed > 0:
                return False  # Not enough mana

        return True

    def pay_mana_cost(self, mana_cost, mana_pool):
        """
        Subtracts the mana cost from the player's mana pool.
        """
        for mana_type in ['W', 'U', 'B', 'R', 'G', 'C']:
            mana_pool[mana_type] -= mana_cost.get(mana_type, 0)

    def play_card(self):
        if self.selected_card and self.selected_card in self.player_hand:
            card = self.selected_card
            if card.is_land():
                QMessageBox.warning(self, "Cannot Play Land", "Use 'Play Land' button to play lands.")
                return
            mana_cost = self.parse_mana_cost(card.mana_cost)
            if self.has_enough_mana(mana_cost, self.player_mana_pool):
                # Subtract the mana cost from the player's mana pool
                self.pay_mana_cost(mana_cost, self.player_mana_pool)
                self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")
                # Handle card types and play accordingly
                if 'Creature' in card.type_line:
                    card.summoning_sickness = True
                    self.player_battlefield.append(card)
                    self.update_battlefield_display()
                elif 'Instant' in card.type_line or 'Sorcery' in card.type_line:
                    self.cast_spell(card)
                # Remove card from hand
                self.player_hand.remove(card)
                self.update_hand_display()
                self.hand_label.setText(f"Your Hand:")
                self.selected_card = None  # Reset selected card
            else:
                QMessageBox.warning(self, "Not Enough Mana", f"You don't have enough mana to play {card.name}.")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def cast_spell(self, card):
        QMessageBox.information(self, "Spell Cast", f"You cast {card.name}.")
        # Implement spell effects as needed

    def attack(self):
        self.turn_phase = 'attack'
        # Allow player to select attackers
        QMessageBox.information(self, "Attack Phase", "Select attackers by clicking on your creatures. When ready, click 'Proceed to Combat'.")
        self.proceed_to_combat_btn.setEnabled(True)

    def combat_phase(self):
        self.proceed_to_combat_btn.setEnabled(False)
        # AI chooses blockers
        self.blocking_creatures = {}
        for creature in self.ai_battlefield:
            # Simple logic: Block the first attacker if possible
            if creature.power.isdigit() and self.attacking_creatures:
                attacker = self.attacking_creatures.pop(0)
                self.blocking_creatures[attacker] = creature
        # Calculate combat damage
        self.resolve_combat()

    def resolve_combat(self):
        # Damage assignment
        # For each attacker, check if it was blocked
        total_damage_to_ai = 0
        total_damage_to_player = 0

        # Resolve blocked attackers
        for attacker, blocker in self.blocking_creatures.items():
            attacker_power = int(attacker.power) if attacker.power.isdigit() else 0
            attacker_toughness = int(attacker.toughness) if attacker.toughness.isdigit() else 0
            blocker_power = int(blocker.power) if blocker.power.isdigit() else 0
            blocker_toughness = int(blocker.toughness) if blocker.toughness.isdigit() else 0

            # Deal damage to each other
            attacker_damage = blocker_power
            blocker_damage = attacker_power

            # Check if attacker is destroyed
            if attacker_damage >= attacker_toughness:
                self.player_battlefield.remove(attacker)
                QMessageBox.information(self, "Combat", f"Your {attacker.name} was destroyed by {blocker.name}.")

            # Check if blocker is destroyed
            if blocker_damage >= blocker_toughness:
                self.ai_battlefield.remove(blocker)
                QMessageBox.information(self, "Combat", f"AI's {blocker.name} was destroyed by {attacker.name}.")

        # Unblocked attackers deal damage to AI
        for attacker in self.attacking_creatures:
            attacker_power = int(attacker.power) if attacker.power.isdigit() else 0
            total_damage_to_ai += attacker_power

        if total_damage_to_ai > 0:
            self.ai_life_total -= total_damage_to_ai
            self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
            QMessageBox.information(self, "Combat", f"You dealt {total_damage_to_ai} damage to the AI!")

        self.check_win_loss_condition()

        # Reset for next turn
        self.attacking_creatures = []
        self.blocking_creatures = {}
        self.turn_phase = 'main2'  # Proceed to second main phase

    def end_turn(self):
        self.apply_unused_mana_penalty()
        self.land_played_this_turn = False  # Reset land play for next turn
        self.turn_phase = 'end'
        self.turn_player = 'ai'
        self.ai_take_turn()
        self.start_turn()

    def start_turn(self):
        if self.turn_player == 'player':
            self.reset_all_permanents()
            self.draw_card()
            self.turn_phase = 'main1'
        else:
            self.turn_phase = 'main1'

    def draw_card(self):
        if self.player_deck:
            card = self.player_deck.pop(0)
            self.player_hand.append(card)
            self.update_hand_display()
            self.hand_label.setText(f"Your Hand:")
        else:
            QMessageBox.warning(self, "No Cards", "Your deck is empty!")

    def ai_take_turn(self):
        # AI's turn logic
        self.reset_all_permanents()
        # AI draws a card
        if self.ai_deck:
            card = self.ai_deck.pop(0)
            self.ai_hand.append(card)

        # AI plays a land if it hasn't already
        if len(self.ai_lands) < self.turn_number():
            for card in self.ai_hand:
                if card.is_land():
                    if card.mana_cost and card.mana_cost != '':
                        # Land has a mana cost, check if AI has enough mana
                        # AI cannot tap lands to generate mana to play lands
                        # So we check if AI has mana in its mana pool (from other sources)
                        if self.has_enough_mana(self.parse_mana_cost(card.mana_cost), self.ai_mana_pool):
                            self.pay_mana_cost(self.parse_mana_cost(card.mana_cost), self.ai_mana_pool)
                        else:
                            # AI cannot play this land, not enough mana
                            continue
                    # AI can play the land
                    self.ai_hand.remove(card)
                    self.ai_lands.append(card)
                    self.update_ai_battlefield_display()
                    QMessageBox.information(self, "AI Plays Land", f"AI played {card.name}")
                    break  # AI plays one land per turn

        # AI taps lands to generate mana
        self.ai_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        for land in self.ai_lands:
            if not land.is_tapped:
                land.tap()
                mana_types = land.get_mana_types()
                # For simplicity, AI chooses the first mana type
                if mana_types:
                    mana_type = mana_types[0]
                else:
                    mana_type = 'C'  # Default to colorless
                self.ai_mana_pool[mana_type] += 1
        self.update_ai_battlefield_display()

        print(f"AI Mana Pool after tapping lands: {self.ai_mana_pool}")
        print("AI Hand:")
        for card in self.ai_hand:
            print(f"{card.name}, Cost: {card.mana_cost}")

        # AI plays spells if it has enough mana
        for card in self.ai_hand[:]:
            if not card.is_land():
                mana_cost = self.parse_mana_cost(card.mana_cost)
                if self.has_enough_mana(mana_cost, self.ai_mana_pool):
                    print(f"AI has enough mana to play {card.name}")
                    # Subtract mana cost from AI's mana pool
                    self.pay_mana_cost(mana_cost, self.ai_mana_pool)
                    # Play the card
                    if 'Creature' in card.type_line:
                        card.summoning_sickness = True
                        self.ai_battlefield.append(card)
                        self.update_ai_battlefield_display()
                    elif 'Instant' in card.type_line or 'Sorcery' in card.type_line:
                        # Implement spell effects
                        pass
                    self.ai_hand.remove(card)
                    QMessageBox.information(self, "AI Plays Spell", f"AI played {card.name}")
                    # AI may play multiple spells, so we don't break here
                else:
                    print(f"AI does not have enough mana to play {card.name}")

        # AI attacks if it has creatures that can attack
        attacking_ai_creatures = [creature for creature in self.ai_battlefield if not creature.is_tapped and not creature.summoning_sickness]
        if attacking_ai_creatures:
            total_ai_damage = 0
            for creature in attacking_ai_creatures:
                creature.tap()
                creature_power = int(creature.power) if creature.power.isdigit() else 0
                total_ai_damage += creature_power
            self.life_total -= total_ai_damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Attacks", f"The AI attacks and deals {total_ai_damage} damage to you!")
            self.check_win_loss_condition()

        # Reset AI's mana pool
        self.ai_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        self.turn_player = 'player'

    def turn_number(self):
        """
        Returns the current turn number based on the number of times end_turn has been called.
        """
        return len(self.player_lands) + 1

    def check_win_loss_condition(self):
        if self.ai_life_total <= 0:
            QMessageBox.information(self, "Victory", "You defeated the AI!")
            self.close()
        elif self.life_total <= 0:
            QMessageBox.critical(self, "Defeat", "You have been defeated by the AI.")
            self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Updated player_deck and ai_deck with more cards
    player_deck = [
        # (id, name, mana_cost, type_line, power, toughness, abilities, image_path)
        (1, 'Forest', '', 'Basic Land — Forest', '', '', '', 'forest.jpg'),
        (2, 'Llanowar Elves', '{G}', 'Creature — Elf Druid', '1', '1', 'Tap: Add {G}.', 'llanowar_elves.jpg'),
        (3, 'Giant Growth', '{G}', 'Instant', '', '', 'Target creature gets +3/+3 until end of turn.', 'giant_growth.jpg'),
        (4, 'Grizzly Bears', '{1}{G}', 'Creature — Bear', '2', '2', '', 'grizzly_bears.jpg'),
        # Add more cards as needed
    ]
    ai_deck = [
        (1, 'Mountain', '', 'Basic Land — Mountain', '', '', '', 'mountain.jpg'),
        (2, 'Goblin Guide', '{R}', 'Creature — Goblin Scout', '2', '2', 'Haste', 'goblin_guide.jpg'),
        (3, 'Shock', '{R}', 'Instant', '', '', 'Shock deals 2 damage to any target.', 'shock.jpg'),
        (4, 'Lightning Bolt', '{R}', 'Instant', '', '', 'Lightning Bolt deals 3 damage to any target.', 'lightning_bolt.jpg'),
        (5, 'Goblin Piker', '{1}{R}', 'Creature — Goblin Warrior', '2', '1', '', 'goblin_piker.jpg'),
        # Add more cards as needed
    ]
    game = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game.show()
    sys.exit(app.exec_())
