import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox

class GamePlayApp(QWidget):
    def __init__(self, parent=None, player_deck=None):
        super().__init__(parent)
        self.player_deck = player_deck or []  # The player's deck
        self.player_hand = []  # Cards currently in the player's hand
        self.battlefield = []  # Cards currently on the battlefield
        self.ai_hand = ['AI Card 1', 'AI Card 2', 'AI Card 3']  # The AI's hand
        self.ai_battlefield = []  # AI's battlefield
        self.life_total = 20  # Player's starting life total
        self.ai_life_total = 20  # AI's starting life total
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering - Game Play')
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
                self.hand_list.addItem(card)

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

    def play_card(self):
        """
        Allows the player to play a card from their hand onto the battlefield.
        """
        selected_card = self.hand_list.currentItem()
        if selected_card:
            card_name = selected_card.text()
            self.player_hand.remove(card_name)
            self.battlefield.append(card_name)
            self.battlefield_list.addItem(card_name)
            self.hand_list.takeItem(self.hand_list.row(selected_card))

            self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to play.")

    def end_turn(self):
        """
        Ends the player's turn and allows the AI to take its turn.
        """
        # AI's turn to play a random card (basic AI logic for now)
        if self.ai_hand:
            card = self.ai_hand.pop(0)  # AI plays the first card from its hand
            self.ai_battlefield.append(card)
            self.ai_life_total -= 1  # For example, just deal 1 damage to the player
            self.ai_life_label.setText(f"AI Life Total: {self.ai_life_total}")

        # Check for win/loss condition
        if self.ai_life_total <= 0:
            QMessageBox.information(self, "Victory", "You defeated the AI!")
            self.close()
        elif self.life_total <= 0:
            QMessageBox.critical(self, "Defeat", "You have been defeated by the AI.")
            self.close()

        # Draw a new card for the player for the next turn
        if self.player_deck:
            card = self.player_deck.pop(0)
            self.player_hand.append(card)
            self.hand_list.addItem(card)

        self.hand_label.setText(f"Your Hand: {len(self.player_hand)} cards")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    game_play = GamePlayApp(player_deck=['Card 1', 'Card 2', 'Card 3', 'Card 4', 'Card 5', 'Card 6', 'Card 7'])
    game_play.show()
    sys.exit(app.exec_())
