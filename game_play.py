import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox
from random import choice, randint

class Card:
    """
    A basic structure for cards, including creatures and spells.
    """
    def __init__(self, name, card_type, ability=None, power=0, toughness=0):
        self.name = name
        self.card_type = card_type  # e.g., 'creature', 'spell'
        self.ability = ability  # e.g., 'deal_damage', 'heal', 'boost'
        self.power = power  # Used for creatures
        self.toughness = toughness  # Used for creatures
    
    def __str__(self):
        return self.name

class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None, ai_deck=None):
        super().__init__(parent)
        self.player_deck = player_deck or []  # The player's deck
        self.ai_deck = ai_deck or []  # AI's deck
        self.player_hand = []  # Cards currently in the player's hand
        self.player_battlefield = []  # Cards currently on the battlefield
        self.ai_hand = []  # AI's hand
        self.ai_battlefield = []  # AI's battlefield
        self.life_total = 20  # Player's starting life total
        self.ai_life_total = 20  # AI's starting life total
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering - Game Play (Enhanced)')
        self.setGeometry(300, 300, 600, 400)

        vbox = QVBoxLayout()

        # Life total display
        self.life_label = QLabel(f"Your Life Total: {self.life_total}", self)
        self.ai_life_label = QLabel(f"AI Life Total: {self.ai_life_total}", self)
        vbox.addWidget(self.life_label)
        vbox.addWidget(self.ai_life_label)

        # Hand display
        self.hand_label = QLabel(f"Your Hand: {len(self.player_hand)} cards", self)
        self.hand_list = QListWidget(self)
        vbox.addWidget(self.hand_label)
        vbox.addWidget(self.hand_list)

        # Battlefield display
        self.battlefield_label = QLabel("Your Battlefield:", self)
        self.battlefield_list = QListWidget(self)
        vbox.addWidget(self.battlefield_label)
        vbox.addWidget(self.battlefield_list)

        # Play card button
        play_btn = QPushButton('Play Card', self)
        play_btn.clicked.connect(self.play_card)
        vbox.addWidget(play_btn)

        # Attack button
        attack_btn = QPushButton('Attack', self)
        attack_btn.clicked.connect(self.attack)
        vbox.addWidget(attack_btn)

        # End turn button
        end_turn_btn = QPushButton('End Turn', self)
        end_turn_btn.clicked.connect(self.end_turn)
        vbox.addWidget(end_turn_btn)

        self.setLayout(vbox)

        # Draw initial hand for the player
        self.draw_initial_hand()

    def draw_initial_hand(self):
        """
        Draws an initial hand of 7 cards for the player.
        """
        for _ in range(7):
            if self.player_deck:
                card = self.player_deck.pop(0)  # Draw card from the deck
                self.player_hand.append(card)
                self.hand_list.addItem(card.name)

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def play_card(self):
        """
        Allows the player to play a card from their hand onto the battlefield.
        """
        selected_card = self.hand_list.currentItem()
        if selected_card:
            card_name = selected_card.text()
            card = next(card for card in self.player_hand if card.name == card_name)
            if card.card_type == 'creature':
                self.player_battlefield.append(card)
                self.battlefield_list.addItem(card.name)
            elif card.card_type == 'spell':
                self.cast_spell(card)

            self.player_hand.remove(card)
            self.hand_list.takeItem(self.hand_list.row(selected_card))

            self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def cast_spell(self, card):
        """
        Casts a spell from the player's hand.
        """
        if card.ability == 'deal_damage':
            damage = randint(2, 5)  # Random damage for this spell
            self.ai_life_total -= damage
            self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
            QMessageBox.information(self, "Spell Cast", f"You cast {card.name} and dealt {damage} damage to the AI!")
        elif card.ability == 'heal':
            heal = randint(2, 5)
            self.life_total += heal
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "Spell Cast", f"You cast {card.name} and healed {heal} life!")
        elif card.ability == 'boost':
            boost = randint(1, 3)
            if self.player_battlefield:
                boosted_card = choice(self.player_battlefield)
                boosted_card.power += boost
                QMessageBox.information(self, "Spell Cast", f"{boosted_card.name} is boosted by {boost} power!")

        self.check_win_loss_condition()

    def attack(self):
        """
        Simulates attacking the AI with all creatures on the player's battlefield.
        """
        if not self.player_battlefield:
            QMessageBox.warning(self, "No Creatures", "You have no creatures to attack with!")
            return

        damage = sum([creature.power for creature in self.player_battlefield])
        self.ai_life_total -= damage
        self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
        QMessageBox.information(self, "Attack Successful", f"You dealt {damage} damage to the AI!")

        self.check_win_loss_condition()

    def end_turn(self):
        """
        Ends the player's turn and allows the AI to take its turn.
        """
        self.ai_take_turn()

        # Draw a new card for the player for the next turn
        if self.player_deck:
            card = self.player_deck.pop(0)
            self.player_hand.append(card)
            self.hand_list.addItem(card.name)

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def ai_take_turn(self):
        """
        The AI's turn logic.
        """
        if not self.ai_hand and not self.ai_battlefield and self.ai_deck:
            self.draw_ai_hand()

        if self.ai_hand:
            # AI plays a card based on its archetype (simple logic for now)
            card = self.ai_hand.pop(0)
            if card.card_type == 'creature':
                self.ai_battlefield.append(card)
                QMessageBox.information(self, "AI Played a Creature", f"AI played {card.name} onto the battlefield!")
            elif card.card_type == 'spell':
                if card.ability == 'deal_damage':
                    self.life_total -= randint(2, 5)
                    self.life_label.setText(f"Your Life Total: {self.life_total}")
                    QMessageBox.information(self, "AI Cast a Spell", f"AI cast {card.name} and dealt damage to you!")

        # AI attacks if it has creatures
        if self.ai_battlefield:
            ai_damage = sum([creature.power for creature in self.ai_battlefield])
            self.life_total -= ai_damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Attacks", f"The AI attacks and deals {ai_damage} damage to you!")

        self.check_win_loss_condition()

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
    # Sample deck with creature and spell cards
    player_deck = [
        Card('Fire Elemental', 'creature', power=3, toughness=3),
        Card('Healing Light', 'spell', ability='heal'),
        Card('Lightning Bolt', 'spell', ability='deal_damage'),
        Card('Warrior', 'creature', power=2, toughness=2),
        Card('Boost Spell', 'spell', ability='boost')
    ]
    
    ai_deck = [
        Card('AI Warrior', 'creature', power=2, toughness=2),
        Card('AI Spell', 'spell', ability='deal_damage')
    ]

    app = QApplication(sys.argv)
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())

