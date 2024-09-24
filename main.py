# main.py

from api import fetch_card_data
from db_utilities import create_database, insert_card_data, get_card_by_name, load_deck_from_db
from game_play import GamePlayApp
from deck_builder import DeckBuilderApp
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog
import sys
import os
import random

def parse_deck_file(file_path):
    """
    Parses a deck file and returns a list of card names, expanding quantities.
    """
    deck_names = []
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue  # Skip empty lines
            # Split the line into quantity and card name
            parts = line.split(' ', 1)
            if len(parts) == 2 and parts[0].isdigit():
                quantity = int(parts[0])
                card_name = parts[1].strip()
            else:
                quantity = 1
                card_name = line
            deck_names.extend([card_name] * quantity)
    return deck_names

def fetch_and_store_missing_cards(deck_names):
    """
    Check the database for missing cards in the deck and fetch them from the Scryfall API if needed.
    """
    missing_cards = []

    # Create a set to avoid fetching the same card multiple times
    unique_card_names = set(deck_names)

    # Check each unique card in the deck to see if it's in the database
    for card_name in unique_card_names:
        card_name = card_name.strip()
        if not card_name:
            continue  # Skip empty lines
        card = get_card_by_name(card_name)
        if card is None:
            # Card not found, mark it as missing
            missing_cards.append(card_name)

    # Fetch missing cards from the API and insert into the database
    for card_name in missing_cards:
        print(f"Fetching card: {card_name}")
        card_data = fetch_card_data(card_name)
        if card_data:
            insert_card_data(card_data)
            print(f"Fetched and inserted missing card: {card_name}")
        else:
            print(f"Failed to fetch card: {card_name}")

def load_ai_deck():
    """
    Randomly select an AI deck from the 'ai_decks' folder and load it.
    """
    ai_decks_folder = 'ai_decks'
    if not os.path.exists(ai_decks_folder):
        print(f"No AI decks folder found at '{ai_decks_folder}'.")
        return []

    deck_files = [f for f in os.listdir(ai_decks_folder) if f.endswith('.txt')]
    if not deck_files:
        print(f"No AI decks found in '{ai_decks_folder}'.")
        return []

    selected_deck_file = random.choice(deck_files)
    print(f"AI selected deck: {selected_deck_file}")

    ai_deck_names = parse_deck_file(os.path.join(ai_decks_folder, selected_deck_file))
    return ai_deck_names

def initialize_game():
    # Initialize the database
    create_database()  # Ensure the database and table are created

    app = QApplication(sys.argv)

    # Prompt the user to choose how to provide their deck
    choice, ok = QInputDialog.getItem(None, "Deck Selection", "Choose how to select your deck:", ["Upload from file", "Build using Deck Builder"], 0, False)
    if not ok:
        print("No choice made. Exiting.")
        sys.exit()

    if choice == "Upload from file":
        # Let the user select a deck file
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(None, "Select Deck File", "", "Text Files (*.txt)")
        if not file_path:
            QMessageBox.warning(None, "No File Selected", "No deck file selected. Exiting.")
            sys.exit()
        player_deck_names = parse_deck_file(file_path)
    else:
        # Launch the deck builder for the player
        deck_builder = DeckBuilderApp()
        deck_builder.show()
        app.exec_()

        # After the player has built their deck and closed the deck builder
        player_deck_names = deck_builder.get_deck_card_names()

    if not player_deck_names:
        QMessageBox.warning(None, "Empty Deck", "Your deck is empty. Exiting.")
        sys.exit()

    # Fetch and store missing cards for the player's deck
    fetch_and_store_missing_cards(player_deck_names)

    # Load the player's deck from the database
    player_deck = load_deck_from_db(player_deck_names)

    # Shuffle the player's deck
    random.shuffle(player_deck)

    # Load the AI's deck
    ai_deck_names = load_ai_deck()
    if not ai_deck_names:
        print("AI deck could not be loaded. Exiting the game.")
        sys.exit()

    # Fetch and store missing cards for the AI deck
    fetch_and_store_missing_cards(ai_deck_names)

    # Load the AI's deck from the database
    ai_deck = load_deck_from_db(ai_deck_names)

    # Shuffle the AI's deck
    random.shuffle(ai_deck)

    # Start the game
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    initialize_game()
