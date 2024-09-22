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
    def __init__(self, name, card_type, mana_cost, ability=None, power=0, toughness=0, abilities=None):
        self.name = name
        self.card_type = card_type
        self.mana_cost = mana_cost
        self.ability = ability
        self.power = power
        self.toughness = toughness
        self.abilities = abilities or []

    def __str__(self):
        return f"{self.name} (Cost: {self.mana_cost})"

class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None, ai_deck=None):
        super().__init__(parent)
        self.player_deck = player_deck or []
        self.ai_deck = ai_deck or []
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
        self.setWindowTitle('Magic: The Gathering')
        self.setGeometry(300, 300, 600, 400)

        vbox = QVBoxLayout()

        self.life_label = QLabel(f"Your Life Total: {self.life_total}", self)
        self.ai_life_label = QLabel(f"AI Life Total: {self.ai_life_total}", self)
        vbox.addWidget(self.life_label)
        vbox.addWidget(self.ai_life_label)

        self.mana_label = QLabel(f"Your Mana Pool: {self.player_mana_pool} available", self)
        vbox.addWidget(self.mana_label)

        self.hand_label = QLabel(f"Your Hand: {len(self.player_hand)} cards", self)
        self.hand_list = QListWidget(self)
        vbox.addWidget(self.hand_label)
        vbox.addWidget(self.hand_list)

        self.battlefield_label = QLabel("Your Battlefield:", self)
        self.battlefield_list = QListWidget(self)
        vbox.addWidget(self.battlefield_label)
        vbox.addWidget(self.battlefield_list)

        play_btn = QPushButton('Play Card', self)
        play_btn.clicked.connect(self.play_card)
        vbox.addWidget(play_btn)

        tap_mana_btn = QPushButton('Tap Mana', self)
        tap_mana_btn.clicked.connect(self.tap_mana)
        vbox.addWidget(tap_mana_btn)

        attack_btn = QPushButton('Attack', self)
        attack_btn.clicked.connect(self.attack)
        vbox.addWidget(attack_btn)

        end_turn_btn = QPushButton('End Turn', self)
        end_turn_btn.clicked.connect(self.end_turn)
        vbox.addWidget(end_turn_btn)

        self.setLayout(vbox)

        self.draw_initial_hand()

    def draw_initial_hand(self):
        for _ in range(7):
            if self.player_deck:
                card = self.player_deck.pop(0)
                self.player_hand.append(card)
                self.hand_list.addItem(str(card))

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def tap_mana(self):
        untapped_sources = [source for source in self.mana_sources if not source.is_tapped]
        if untapped_sources:
            mana_source = untapped_sources[0]
            mana_source.tap()
            self.player_mana_pool += 1
            self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool} available")
            QMessageBox.information(self, "Mana Tapped", f"{mana_source.name} is now tapped.")
        else:
            QMessageBox.warning(self, "No Untapped Mana", "All mana sources are already tapped.")

    def play_card(self):
        selected_card = self.hand_list.currentItem()
        if selected_card:
            card_name = selected_card.text()
            card = next(card for card in self.player_hand if str(card) == card_name)

            if self.player_mana_pool >= card.mana_cost:
                if card.card_type == 'creature':
                    self.player_battlefield.append(card)
                    self.battlefield_list.addItem(str(card))
                elif card.card_type == 'spell':
                    self.cast_spell(card)

                self.player_mana_pool -= card.mana_cost
                self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool} available")
                self.player_hand.remove(card)
                self.hand_list.takeItem(self.hand_list.row(selected_card))
                self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")
            else:
                QMessageBox.warning(self, "Not Enough Mana", f"You need {card.mana_cost} mana to play {card.name}.")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def cast_spell(self, card):
        if card.ability == 'deal_damage':
            damage = randint(2, 5)
            self.ai_life_total -= damage
            self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
            QMessageBox.information(self, "Spell Cast", f"You cast {card.name} and dealt {damage} damage to the AI!")
        elif card.ability == 'heal':
            heal = randint(2, 5)
            self.life_total += heal
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "Spell Cast", f"You cast {card.name} and healed {heal} life!")

        self.check_win_loss_condition()

    def attack(self):
        if not self.player_battlefield:
            QMessageBox.warning(self, "No Creatures", "You have no creatures to attack with!")
            return

        total_damage = sum([creature.power for creature in self.player_battlefield])
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
            self.hand_list.addItem(str(card))
        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def apply_unused_mana_penalty(self):
        unused_mana = self.player_mana_pool
        if unused_mana > 0:
            self.life_total -= unused_mana
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.warning(self, "Unused Mana Penalty", f"You take {unused_mana} damage from unused mana!")
        self.player_mana_pool = 0

    def reset_all_mana_sources(self):
        for source in self.mana_sources:
            source.reset_tap()
        QMessageBox.information(self, "Mana Reset", "All available mana sources have been reset.")

    def ai_take_turn(self):
        if not self.ai_hand and not self.ai_battlefield and self.ai_deck:
            self.draw_ai_hand()

        if self.ai_hand:
            card = self.ai_hand.pop(0)
            if card.card_type == 'creature':
                self.ai_battlefield.append(card)
                QMessageBox.information(self, "AI Played a Creature", f"AI played {card.name} onto the battlefield!")
            elif card.card_type == 'spell':
                self.cast_ai_spell(card)

        if self.ai_battlefield:
            ai_damage = sum([creature.power for creature in self.ai_battlefield])
            self.life_total -= ai_damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Attacks", f"The AI attacks and deals {ai_damage} damage to you!")

        self.check_win_loss_condition()

    def cast_ai_spell(self, card):
        if card.ability == 'deal_damage':
            damage = randint(2, 5)
            self.life_total -= damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Cast a Spell", f"AI cast {card.name} and dealt {damage} damage to you!")

    def check_win_loss_condition(self):
        if self.ai_life_total <= 0:
            QMessageBox.information(self, "Victory", "You defeated the AI!")
Here’s the corrected **`game_play.py`** with the continuation you need:

```python
    def check_win_loss_condition(self):
        """
        Check if either player or AI has won or lost the game.
        """
        if self.ai_life_total <= 0:
            QMessageBox.information(self, "Victory", "You defeated the AI!")
            self.close()
        elif self.life_total <= 0:
            QMessageBox.critical(self, "Defeat", "You have been defeated by the AI.")
            self.close()

    def draw_ai_hand(self):
        """
        Draws the AI's hand at the start of its turn.
        """
        for _ in range(7):
            if self.ai_deck:
                card = self.ai_deck.pop(0)
                self.ai_hand.append(card)

if __name__ == '__main__':
    # Sample decks for player and AI
    player_deck = [
        Card('Fire Elemental', 'creature', mana_cost=3, power=3, toughness=3, abilities=['flying']),
        Card('Healing Light', 'spell', mana_cost=2, ability='heal'),
        Card('Lightning Bolt', 'spell', mana_cost=1, ability='deal_damage'),
        Card('Trample Warrior', 'creature', mana_cost=4, power=4, toughness=4, abilities=['trample']),
        Card('Boost Spell', 'spell', mana_cost=2, ability='boost')
    ]
    
    ai_deck = [
        Card('AI Warrior', 'creature', mana_cost=2, power=2, toughness=2, abilities=['first strike']),
        Card('AI Spell', 'spell', mana_cost=3, ability='deal_damage')
    ]

    app = QApplication(sys.argv)
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())
