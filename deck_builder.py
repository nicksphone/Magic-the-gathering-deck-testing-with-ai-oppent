import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QLineEdit, QMessageBox

class DeckBuilderApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.deck = []  # The player's deck
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering Deck Builder')
        self.setGeometry(300, 300, 400, 300)

        vbox = QVBoxLayout()

        # Deck list
        self.deck_list = QListWidget(self)
        vbox.addWidget(self.deck_list)

        # Card search input
        self.search_entry = QLineEdit(self)
        vbox.addWidget(self.search_entry)

        # Add card button
        add_card_btn = QPushButton('Add Card', self)
        add_card_btn.clicked.connect(self.add_card)
        vbox.addWidget(add_card_btn)

        # Remove card button
        remove_card_btn = QPushButton('Remove Selected Card', self)
        remove_card_btn.clicked.connect(self.remove_card)
        vbox.addWidget(remove_card_btn)

        # Finish button
        finish_btn = QPushButton('Finish Deck', self)
        finish_btn.clicked.connect(self.finish_deck)
        vbox.addWidget(finish_btn)

        self.setLayout(vbox)

    def add_card(self):
        """
        Adds a card to the deck based on the input in the search box.
        """
        card_name = self.search_entry.text()
        if card_name:
            # Create a basic card based on the input (this can be expanded with a proper card database)
            new_card = Card(card_name, 'creature', mana_cost=randint(1, 5), power=randint(1, 4), toughness=randint(1, 4))
            self.deck.append(new_card)
            self.deck_list.addItem(new_card.name)
            self.search_entry.clear()
        else:
            QMessageBox.warning(self, "Input Required", "Please enter a card name.")

    def remove_card(self):
        """
        Removes the selected card from the deck.
        """
        selected_card = self.deck_list.currentItem()
        if selected_card:
            card_name = selected_card.text()
            card = next(card for card in self.deck if card.name == card_name)
            self.deck.remove(card)
            self.deck_list.takeItem(self.deck_list.row(selected_card))
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to remove.")

    def finish_deck(self):
        """
        Finalizes the deck and starts the game.
        """
        if len(self.deck) < 7:
            QMessageBox.warning(self, "Deck Too Small", "You need at least 7 cards to start the game.")
        else:
            self.parent().transition_to_game(self.deck)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    deck_builder = DeckBuilderApp()
    deck_builder.show()
    sys.exit(app.exec_())
