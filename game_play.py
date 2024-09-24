# game_play.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QHBoxLayout, QScrollArea
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QSize
import os
import re

class ManaSource:
    def __init__(self, name, mana_type='C', is_tapped=False):
        self.name = name
        self.mana_type = mana_type  # 'C', 'W', 'U', 'B', 'R', 'G'
        self.is_tapped = is_tapped

    def tap(self):
        if not self.is_tapped:
            self.is_tapped = True
            return True
        return False

    def reset_tap(self):
        self.is_tapped = False

    def __str__(self):
        return f"{self.name} (Tapped: {self.is_tapped}, Type: {self.mana_type})"

class Card:
    def __init__(self, card_data):
        self.id = card_data[0]
        self.name = card_data[1]
        self.mana_cost = card_data[2]
        self.type_line = card_data[3]
        self.power = card_data[4]
        self.toughness = card_data[5]
        self.abilities = card_data[6].split(', ') if card_data[6] else []
        self.image_path = card_data[7]  # Use image_path instead of image_url

    def __str__(self):
        return f"{self.name} (Cost: {self.mana_cost})"

    def get_pixmap(self):
        """
        Returns the QPixmap object of the card image.
        """
        if self.image_path and os.path.exists(self.image_path):
            return QPixmap(self.image_path)
        else:
            return QPixmap('default_card_image.jpg')  # Provide a default image if not available

class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None, ai_deck=None):
        super().__init__(parent)
        self.player_deck = [Card(card_data) for card_data in player_deck] or []
        self.ai_deck = [Card(card_data) for card_data in ai_deck] or []
        self.player_hand = []
        self.player_battlefield = []
        self.ai_hand = []
        self.ai_battlefield = []
        self.life_total = 20
        self.ai_life_total = 20

        # Initialize mana sources with different types
        self.mana_sources = [
            ManaSource("Plains", 'W'),
            ManaSource("Island", 'U'),
            ManaSource("Swamp", 'B'),
            ManaSource("Mountain", 'R'),
            ManaSource("Forest", 'G')
        ]

        # Initialize the player's mana pool as a dictionary of mana types
        self.player_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}

        self.selected_card = None  # Initialize selected card
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

        # Mana sources
        self.mana_sources_layout = QHBoxLayout()
        self.mana_sources_buttons = []

        for source in self.mana_sources:
            btn = QPushButton(source.name)
            btn.clicked.connect(lambda checked, s=source: self.tap_mana_source(s))
            self.mana_sources_buttons.append(btn)
            self.mana_sources_layout.addWidget(btn)

        self.main_layout.addLayout(self.mana_sources_layout)

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
        play_btn = QPushButton('Play Card', self)
        play_btn.clicked.connect(self.play_card)
        button_layout.addWidget(play_btn)

        attack_btn = QPushButton('Attack', self)
        attack_btn.clicked.connect(self.attack)
        button_layout.addWidget(attack_btn)

        end_turn_btn = QPushButton('End Turn', self)
        end_turn_btn.clicked.connect(self.end_turn)
        button_layout.addWidget(end_turn_btn)

        self.main_layout.addLayout(button_layout)

        self.setLayout(self.main_layout)

        self.draw_initial_hand()
        self.ai_draw_initial_hand()

    def resizeEvent(self, event):
        """
        Overrides the resize event to adjust the card image sizes when the window is resized.
        """
        super().resizeEvent(event)
        self.update_hand_display()
        self.update_battlefield_display()
        self.update_ai_battlefield_display()

    def calculate_card_size(self, area_widget, num_cards):
        """
        Calculates the appropriate card size based on the area widget size and number of cards.
        """
        if num_cards == 0:
            return QSize(0, 0)

        # Get the available width in the scroll area
        available_width = area_widget.width() - (area_widget.verticalScrollBar().sizeHint().width())
        available_height = area_widget.height()

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
        card_size = self.calculate_card_size(self.hand_area.viewport(), num_cards)

        # Display cards in hand
        for card in self.player_hand:
            card_label = QLabel()
            pixmap = card.get_pixmap().scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            card_label.setObjectName(card.name)
            card_label.mousePressEvent = self.create_hand_card_click_event(card)
            self.hand_layout.addWidget(card_label)

        # Update the layout
        self.hand_layout.addStretch()

    def update_battlefield_display(self):
        # Clear current battlefield display
        for i in reversed(range(self.battlefield_layout.count())):
            widget = self.battlefield_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        num_cards = len(self.player_battlefield)
        card_size = self.calculate_card_size(self.battlefield_area.viewport(), num_cards)

        # Display cards on battlefield
        for card in self.player_battlefield:
            card_label = QLabel()
            pixmap = card.get_pixmap().scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            self.battlefield_layout.addWidget(card_label)

        # Update the layout
        self.battlefield_layout.addStretch()

    def update_ai_battlefield_display(self):
        # Clear current AI battlefield display
        for i in reversed(range(self.ai_battlefield_layout.count())):
            widget = self.ai_battlefield_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        num_cards = len(self.ai_battlefield)
        card_size = self.calculate_card_size(self.ai_battlefield_area.viewport(), num_cards)

        # Display cards on AI's battlefield
        for card in self.ai_battlefield:
            card_label = QLabel()
            pixmap = card.get_pixmap().scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            card_label.setPixmap(pixmap)
            self.ai_battlefield_layout.addWidget(card_label)

        # Update the layout
        self.ai_battlefield_layout.addStretch()

    def create_hand_card_click_event(self, card):
        def hand_card_click_event(event):
            self.selected_card = card
            QMessageBox.information(self, "Card Selected", f"You selected {card.name}.")
        return hand_card_click_event

    def tap_mana_source(self, source):
        if not source.is_tapped:
            source.tap()
            self.player_mana_pool[source.mana_type] += 1
            self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")
            # Disable the button since it's tapped
            for btn in self.mana_sources_buttons:
                if btn.text() == source.name:
                    btn.setEnabled(False)
                    break
            QMessageBox.information(self, "Mana Tapped", f"{source.name} is now tapped and added {source.mana_type} mana.")
        else:
            QMessageBox.warning(self, "Already Tapped", f"{source.name} is already tapped.")

    def reset_all_mana_sources(self):
        for source in self.mana_sources:
            source.reset_tap()
        # Enable all mana source buttons
        for btn in self.mana_sources_buttons:
            btn.setEnabled(True)
        QMessageBox.information(self, "Mana Reset", "All available mana sources have been reset.")

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

    def has_enough_mana(self, mana_cost):
        """
        Checks if the player has enough mana in their pool to pay the mana cost.
        """
        temp_pool = self.player_mana_pool.copy()
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

    def play_card(self):
        if self.selected_card and self.selected_card in self.player_hand:
            card = self.selected_card
            mana_cost = self.parse_mana_cost(card.mana_cost)
            if self.has_enough_mana(mana_cost):
                # Subtract the mana cost from the player's mana pool
                for mana_type, amount in mana_cost.items():
                    self.player_mana_pool[mana_type] -= amount
                self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool}")
                # Handle card types and play accordingly
                if 'Creature' in card.type_line:
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
        if not self.player_battlefield:
            QMessageBox.warning(self, "No Creatures", "You have no creatures to attack with!")
            return

        total_damage = 0
        for creature in self.player_battlefield:
            if creature.power.isdigit():
                total_damage += int(creature.power)
        self.ai_life_total -= total_damage
        self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
        QMessageBox.information(self, "Attack Successful", f"You dealt {total_damage} damage to the AI!")

        self.check_win_loss_condition()

    def end_turn(self):
        self.apply_unused_mana_penalty()
        self.reset_all_mana_sources()
        self.ai_take_turn()
        if self.player_deck:
            card = self.player_deck.pop(0)
            self.player_hand.append(card)
            self.update_hand_display()
        self.hand_label.setText(f"Your Hand:")

    def ai_take_turn(self):
        # Implement AI actions here
        QMessageBox.information(self, "AI Turn", "The AI takes its turn.")
        # AI draws a card
        if self.ai_deck:
            card = self.ai_deck.pop(0)
            self.ai_hand.append(card)

        # For simplicity, AI plays the first creature in its hand if it can
        creature_played = False
        for card in self.ai_hand:
            if 'Creature' in card.type_line:
                self.ai_hand.remove(card)
                self.ai_battlefield.append(card)
                self.update_ai_battlefield_display()
                creature_played = True
                break

        # AI attacks if it has creatures
        if self.ai_battlefield:
            ai_damage = 0
            for creature in self.ai_battlefield:
                if creature.power.isdigit():
                    ai_damage += int(creature.power)
            self.life_total -= ai_damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Attacks", f"The AI attacks and deals {ai_damage} damage to you!")
            self.check_win_loss_condition()

    def check_win_loss_condition(self):
        if self.ai_life_total <= 0:
            QMessageBox.information(self, "Victory", "You defeated the AI!")
            self.close()
        elif self.life_total <= 0:
            QMessageBox.critical(self, "Defeat", "You have been defeated by the AI.")
            self.close()
