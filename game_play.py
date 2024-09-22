import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox
from random import choice, randint

class ManaSource:
    """
    Represents a mana source (land) that can be tapped or untapped.
    """
    def __init__(self, name, tapped=False, untap_modifier=False):
        self.name = name
        self.tapped = tapped  # Whether the mana source is tapped
        self.untap_modifier = untap_modifier  # Prevents it from untapping if True

    def tap(self):
        if not self.tapped:
            self.tapped = True
            return True  # Successfully tapped
        return False  # Already tapped

    def untap(self):
        if not self.untap_modifier:
            self.tapped = False

class Card:
    """
    A structure for cards, including creatures and spells with specific abilities.
    """
    def __init__(self, name, card_type, mana_cost, ability=None, power=0, toughness=0, abilities=None):
        self.name = name
        self.card_type = card_type  # e.g., 'creature', 'spell'
        self.mana_cost = mana_cost  # How much mana it costs to play
        self.ability = ability  # e.g., 'deal_damage', 'heal', 'boost'
        self.power = power  # Used for creatures
        self.toughness = toughness  # Used for creatures
        self.abilities = abilities or []  # e.g., ['flying', 'trample']

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
        self.mana_sources = [ManaSource(f"Land {i + 1}") for i in range(5)]  # Player starts with 5 lands
        self.player_mana_pool = 0  # Amount of untapped mana available
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering - Mana and Untap Enhanced Game')
        self.setGeometry(300, 300, 600, 400)

        vbox = QVBoxLayout()

        # Life total display
        self.life_label = QLabel(f"Your Life Total: {self.life_total}", self)
        self.ai_life_label = QLabel(f"AI Life Total: {self.ai_life_total}", self)
        vbox.addWidget(self.life_label)
        vbox.addWidget(self.ai_life_label)

        # Mana display
        self.mana_label = QLabel(f"Your Mana Pool: {self.player_mana_pool} available", self)
        vbox.addWidget(self.mana_label)

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

        # Tap Mana Button
        tap_mana_btn = QPushButton('Tap Mana', self)
        tap_mana_btn.clicked.connect(self.tap_mana)
        vbox.addWidget(tap_mana_btn)

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

    def tap_mana(self):
        """
        Taps a mana source if it's untapped, adding mana to the player's pool.
        """
        untapped_sources = [source for source in self.mana_sources if not source.tapped]
        if untapped_sources:
            mana_source = untapped_sources[0]  # Tap the first available untapped mana source
            mana_source.tap()
            self.player_mana_pool += 1
            self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool} available")
            QMessageBox.information(self, "Mana Tapped", f"{mana_source.name} is tapped.")
        else:
            QMessageBox.warning(self, "No Untapped Mana", "All mana sources are already tapped.")

    def play_card(self):
        """
        Allows the player to play a card from their hand onto the battlefield, if they have enough mana.
        """
        selected_card = self.hand_list.currentItem()
        if selected_card:
            card_name = selected_card.text()
            card = next(card for card in self.player_hand if card.name == card_name)

            if self.player_mana_pool >= card.mana_cost:  # Check if the player has enough mana
                if card.card_type == 'creature':
                    self.player_battlefield.append(card)
                    self.battlefield_list.addItem(card.name)
                elif card.card_type == 'spell':
                    self.cast_spell(card)

                self.player_mana_pool -= card.mana_cost  # Subtract the mana cost
                self.mana_label.setText(f"Your Mana Pool: {self.player_mana_pool} available")

                self.player_hand.remove(card)
                self.hand_list.takeItem(self.hand_list.row(selected_card))
                self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")
            else:
                QMessageBox.warning(self, "Not Enough Mana", f"You need {card.mana_cost} mana to play {card.name}.")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def cast_spell(self, card):
        """
        Casts a spell from the player's hand, applying its effect.
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

        self.check_win_loss_condition()

    def attack(self):
        """
        Simulates attacking the AI with all creatures on the player's battlefield.
        """
        if not self.player_battlefield:
            QMessageBox.warning(self, "No Creatures", "You have no creatures to attack with!")
            return

        total_damage = sum([creature.power for creature in self.player_battlefield])
        self.ai_life_total -= total_damage
        self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")
        QMessageBox.information(self, "Attack Successful", f"You dealt {total_damage} damage to the AI!")

        self.check_win_loss_condition()

    def end_turn(self):
        """
        Ends the player's turn, applies unused mana penalty, and allows the AI to take its turn.
        """
        self.apply_unused_mana_penalty()

        # Untap all mana sources unless they are prevented from untapping
        self.untap_all_mana()

        self.ai_take_turn()

        # Draw a new card for the player for the next turn
        if self.player_deck:
            card = self.player_deck.pop(0)
            self.player_hand.append(card)
            self.hand_list.addItem(card.name)

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def apply_unused_mana_penalty(self):
        """
        Any tapped but unused mana at the end of the player's turn causes 1 point of damage per unused mana.
        """
        unused_mana = self.player_mana_pool
        if unused_mana > 0:
            self.life_total -= unused_mana
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.warning(self, "Unused Mana Penalty", f"You take {unused_mana} damage from unused mana!")
        self.player_mana_pool = 0  # Reset mana pool

    def untap_all_mana(self):
        """
        Untaps all mana sources unless a specific modifier prevents them from untapping.
        """
        for source in self.mana_sources:
            source.untap()

        QMessageBox.information(self, "Mana Untapped", "All untapped mana sources have been untapped.")

    def ai_take_turn(self):
        """
        The AI's turn logic, taking into account combat and card abilities.
        """
        if not self.ai_hand and not self.ai_battlefield and self.ai_deck:
            self.draw_ai_hand()

        if self.ai_hand:
            card = self.ai_hand.pop(0)  # AI plays the first card in its hand
            if card.card_type == 'creature':
                self.ai_battlefield.append(card)
                QMessageBox.information(self, "AI Played a Creature", f"AI played {card.name} onto the battlefield!")
            elif card.card_type == 'spell':
                self.cast_ai_spell(card)

        # AI attacks if it has creatures
        if self.ai_battlefield:
            ai_damage = sum([creature.power for creature in self.ai_battlefield])
            self.life_total -= ai_damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Attacks", f"The AI attacks and deals {ai_damage} damage to you!")

        self.check_win_loss_condition()

    def cast_ai_spell(self, card):
        """
        The AI casts a spell, applying its effect.
        """
        if card.ability == 'deal_damage':
            damage = randint(2, 5)  # Random damage for this spell
            self.life_total -= damage
            self.life_label.setText(f"Your Life Total: {self.life_total}")
            QMessageBox.information(self, "AI Cast a Spell", f"AI cast {card.name} and dealt {damage} damage to you!")

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
    # Sample deck with creature and spell cards, including specific abilities and mana costs
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
