from api import fetch_card_data
from db_utilities import create_database, insert_card_data, get_card_by_name, load_deck_from_db
from game_play import GamePlayApp
from PyQt5.QtWidgets import QApplication
import sys

def fetch_and_store_missing_cards(deck):
    """
    Check the database for missing cards in the deck and fetch them from the Scryfall API if needed.
    """
    missing_cards = []
    
    # Check each card in the deck to see if it's in the database
    for card_name in deck:
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

def initialize_game():
    # Initialize the database
    create_database()
    
    # Example player and AI decks
    player_deck_names = ['Black Lotus', 'Serra Angel', 'Lightning Bolt']
    ai_deck_names = ['AI Flying Warrior', 'AI Trample Beast', 'AI First Strike Knight']
    
    # Fetch and store missing cards for both player and AI decks
    fetch_and_store_missing_cards(player_deck_names)
    fetch_and_store_missing_cards(ai_deck_names)

    # Load the decks from the database after fetching missing cards
    player_deck = load_deck_from_db(player_deck_names)
    ai_deck = load_deck_from_db(ai_deck_names)

    # Launch the game using PyQt5
    app = QApplication(sys.argv)
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    initialize_game()
