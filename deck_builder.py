# deck_builder.py

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QLineEdit, QMessageBox
from api import fetch_card_data
from db_utilities import insert_card_data, get_card_by_name

class DeckBuilderApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.deck = []  # The player's deck (list of card names)
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
        card_name = self.search_entry.text().strip()
        if card_name:
            # Check if the card exists in the database
            card = get_card_by_name(card_name)
            if not card:
                # Fetch from API and insert into the database
                card_data = fetch_card_data(card_name)
                if card_data:
                    insert_card_data(card_data)
                    print(f"Card '{card_name}' added to database.")
                else:
                    QMessageBox.warning(self, "Card Not Found", f"Card '{card_name}' not found.")
                    return

            self.deck.append(card_name)
            self.deck_list.addItem(card_name)
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
            self.deck.remove(card_name)
            self.deck_list.takeItem(self.deck_list.row(selected_card))
        else:
            QMessageBox.warning(self, "No Card Selected", "Please select a card to remove.")

    def finish_deck(self):
        """
        Finalizes the deck and closes the deck builder.
        """
        if len(self.deck) < 7:
            QMessageBox.warning(self, "Deck Too Small", "You need at least 7 cards to start the game.")
        else:
            self.close()  # Close the deck builder window

    def get_deck_card_names(self):
        """
        Returns the list of card names in the player's deck.
        """
        return self.deck

# The main block is no longer needed since we launch the deck builder from main.py
