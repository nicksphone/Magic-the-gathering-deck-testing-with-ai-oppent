# game_play.py

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox
from random import randint

class ManaSource:
    def __init__(self, name, is_tapped=False):
        self.name = name
        self.is_tapped = is_tapped

    def tap(self):
        if not self.is_tapped:
            self.is_tapped = True
            return True
        return False

    def reset_tap(self):
        self.is_tapped = False

    def __str__(self):
        return f"{self.name} (Tapped: {self.is_tapped})"

class Card:
    def __init__(self, card_data):
        self.name = card_data[1]
        self.mana_cost = card_data[2]
        self.type_line = card_data[3]
        self.power = card_data[4]
        self.toughness = card_data[5]
        self.abilities = card_data[6].split(', ') if card_data[6] else []
        self.image_url = card_data[7]

    def __str__(self):
        return f"{self.name} (Cost: {self.mana_cost})"

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
        self.mana_sources = [ManaSource(f"Land {i + 1}") for i in range(5)]
        self.player_mana_pool = 0
        self.initUI()

    def initUI(self):
        # ... (UI setup code remains the same)

        self.draw_initial_hand()

    def draw_initial_hand(self):
        for _ in range(7):
            if self.player_deck:
                card = self.player_deck.pop(0)
                self.player_hand.append(card)
                self.hand_list.addItem(str(card))

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    # ... (other methods remain mostly the same)

    def play_card(self):
        selected_card_item = self.hand_list.currentItem()
        if selected_card_item:
            card_name = selected_card_item.text().split(' (Cost:')[0]
            card = next((c for c in self.player_hand if c.name == card_name), None)
            if card:
                mana_cost = self.parse_mana_cost(card.mana_cost)
                if self.player_mana_pool >= mana_cost:
                    # Handle card types and play accordingly
                    if 'Creature' in card.type_line:
                        self.player_battlefield.append(card)
                        self.battlefield_list.addItem(str(card))
                    elif 'Instant' in card.type_line or 'Sorcery' in card.type_line:
                        self.cast_spell(card)
                    # Deduct mana and update UI
                    self.player_mana_pool -= mana_cost
                    self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool} available")
                    self.player_hand.remove(card)
                    self.hand_list.takeItem(self.hand_list.row(selected_card_item))
                    self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")
                else:
                    QMessageBox.warning(self, "Not Enough Mana", f"You need {mana_cost} mana to play {card.name}.")
            else:
                QMessageBox.warning(self, "Card Not Found", "Selected card not found in hand.")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def parse_mana_cost(self, mana_cost_str):
        # Simplified parsing; you can expand this to handle colored mana
        import re
        numbers = re.findall(r'\d+', mana_cost_str)
        total_cost = sum(int(num) for num in numbers)
        # Count colored mana symbols as 1 each
        colored_mana = re.findall(r'{[A-Z]}', mana_cost_str)
        total_cost += len(colored_mana)
        return total_cost

    # Update other methods to use the Card class attributes
    # ...

# The main block is no longer needed since we launch the game from main.py
