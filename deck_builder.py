# deck_builder.py
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget,
    QLabel, QLineEdit, QMessageBox, QFileDialog
)
from api import fetch_card_data
from db_utilities import insert_card_data, get_card_by_name
from main import parse_deck_file  # Import the parse_deck_file function

class DeckBuilderApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.deck = []  # The player's deck (list of card names)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering Deck Builder')
        self.setGeometry(300, 300, 400, 400)
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

        # Load deck from file button
        load_deck_btn = QPushButton('Load Deck from File', self)
        load_deck_btn.clicked.connect(self.load_deck_from_file)
        vbox.addWidget(load_deck_btn)

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
            # Handle quantity if specified
            parts = card_name.split(' ', 1)
            if len(parts) == 2 and parts[0].isdigit():
                quantity = int(parts[0])
                card_name = parts[1].strip()
            else:
                quantity = 1
            
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
            
            for _ in range(quantity):
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

    def load_deck_from_file(self):
        """
        Loads a deck from a text file.
        """
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Deck File", "", "Text Files (*.txt)")
        
        if not file_path:
            return
        
        deck_names = parse_deck_file(file_path)
        
        for card_name in deck_names:
            self.search_entry.setText(card_name)
            self.add_card()

    def finish_deck(self):
        """
        Finalizes the deck and closes the deck builder.
        """
        if len(self.deck) < 7:
            QMessageBox.warning(self, "Deck Too Small", "You need at least 7 cards to start the game.")
        else:
            # Close the deck builder window
            self.close()

    def get_deck_card_names(self):
        """
        Returns the list of card names in the player's deck.
        """
        return self.deck

# New method to save the deck
def save_deck(self):
    file_dialog = QFileDialog()
    file_path, _ = file_dialog.getSaveFileName(self, "Save Deck File", "", "Text Files (*.txt)")
    
    if file_path:
        with open(file_path, 'w') as f:
            for card_name in self.deck:
                f.write(card_name + '\n')
                
        QMessageBox.information(self, "Deck Saved", "Your deck has been saved.")

# Connect the save_deck method to a button
save_deck_btn = QPushButton('Save Deck', self)
save_deck_btn.clicked.connect(self.save_deck)
vbox.addWidget(save_deck_btn)
self.setLayout(vbox)
