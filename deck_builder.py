import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QLineEdit, QMessageBox, QFileDialog

class DeckBuilderApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.deck = []
        self.parent = parent  # We'll use this later for transitions
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Magic: The Gathering Deck Tester')
        self.setGeometry(300, 300, 400, 300)

        vbox = QVBoxLayout()

        # Deck upload button
        upload_btn = QPushButton('Upload Deck', self)
        upload_btn.clicked.connect(self.upload_deck)
        vbox.addWidget(upload_btn)

        # Card search input
        self.search_label = QLabel('Search and Add Cards:', self)
        vbox.addWidget(self.search_label)
        
        self.search_entry = QLineEdit(self)
        vbox.addWidget(self.search_entry)

        # Search button
        search_btn = QPushButton('Add Card', self)
        search_btn.clicked.connect(self.search_card)
        vbox.addWidget(search_btn)

        # Deck listbox
        self.deck_listbox = QListWidget(self)
        vbox.addWidget(self.deck_listbox)

        # Save deck button
        save_btn = QPushButton('Save Deck', self)
        save_btn.clicked.connect(self.save_deck)
        vbox.addWidget(save_btn)

        # Load deck button
        load_btn = QPushButton('Load Deck', self)
        load_btn.clicked.connect(self.load_deck)
        vbox.addWidget(load_btn)

        # Start game button
        start_btn = QPushButton('Start Game', self)
        start_btn.clicked.connect(self.start_game)
        vbox.addWidget(start_btn)

        self.setLayout(vbox)

    def upload_deck(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Deck File", "", "Text Files (*.txt);;CSV Files (*.csv)", options=options)
        if file_name:
            with open(file_name, 'r') as file:
                cards = file.readlines()
                for card_name in cards:
                    card_name = card_name.strip()
                    # Dummy function to simulate fetching card data
                    card = self.fetch_and_store_card(card_name)
                    if card:
                        self.deck.append(card)
                        self.deck_listbox.addItem(card_name)

    def search_card(self):
        card_name = self.search_entry.text()
        if card_name:
            card = self.fetch_and_store_card(card_name)
            if card:
                self.deck.append(card)
                self.deck_listbox.addItem(card_name)
                QMessageBox.information(self, "Card Added", f"'{card_name}' added to your deck.")
            else:
                QMessageBox.critical(self, "Card Not Found", f"Could not find '{card_name}'.")
        else:
            QMessageBox.warning(self, "Input Required", "Please enter a card name.")

    def save_deck(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Deck", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'w') as file:
                deck_data = [card for card in self.deck]
                file.write(str(deck_data))  # Save deck names in a simple format
            QMessageBox.information(self, "Deck Saved", "Your deck has been saved successfully.")

    def load_deck(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Deck", "", "JSON Files (*.json)", options=options)
        if file_name:
            with open(file_name, 'r') as file:
                deck_data = eval(file.read())  # Read and evaluate the saved deck data
                self.deck_listbox.clear()  # Clear current deck
                self.deck = deck_data
                for card in deck_data:
                    self.deck_listbox.addItem(card)

    def start_game(self):
        if not self.deck:
            QMessageBox.warning(self, "Empty Deck", "Please add cards to your deck before starting the game.")
        else:
            # Here we would transition to the game screen (this is where we call the parent to transition)
            QMessageBox.information(self, "Start Game", "Game play screen is under development.")
            # If you have a main application class, you could call `self.parent.transition_to_game(self.deck)`

    def fetch_and_store_card(self, card_name):
        # Dummy function to simulate card fetching logic
        return card_name if card_name else None


if __name__ == '__main__':
    app = QApplication(sys.argv)
    deck_builder = DeckBuilderApp()
    deck_builder.show()
    sys.exit(app.exec_())
