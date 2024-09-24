# main.py

from api import fetch_card_data
from db_utilities import create_database, insert_card_data, get_card_by_name, load_deck_from_db
from game_play import GamePlayApp
from deck_builder import DeckBuilderApp
from PyQt5.QtWidgets import QApplication
import sys
import os
import random

def fetch_and_store_missing_cards(deck_names):
    """
    Check the database for missing cards in the deck and fetch them from the Scryfall API if needed.
    """
    missing_cards = []
    
    # Check each card in the deck to see if it's in the database
    for card_name in deck_names:
        card = get_card_by_name(card_name)
        if card is None:
            # Card not found, mark it as missing
            missing_cards.append(card_name)
    
    # Fetch missing cards from the API and insert into the database
    for card_name in missing_cards:
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

    with open(os.path.join(ai_decks_folder, selected_deck_file), 'r') as file:
        ai_deck_names = file.read().splitlines()

    return ai_deck_names

def initialize_game():
    # Initialize the database
    create_database()

    app = QApplication(sys.argv)

    # Launch the deck builder for the player
    deck_builder = DeckBuilderApp()
    deck_builder.show()
    app.exec_()

    # After the player has built their deck
    player_deck_names = deck_builder.get_deck_card_names()

    # Fetch and store missing cards for the player's deck
    fetch_and_store_missing_cards(player_deck_names)

    # Load the player's deck from the database
    player_deck = load_deck_from_db(player_deck_names)

    # Load the AI's deck
    ai_deck_names = load_ai_deck()
    if not ai_deck_names:
        print("AI deck could not be loaded. Exiting the game.")
        sys.exit()

    # Fetch and store missing cards for the AI deck
    fetch_and_store_missing_cards(ai_deck_names)

    # Load the AI's deck from the database
    ai_deck = load_deck_from_db(ai_deck_names)

    # Start the game
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    initialize_game()
