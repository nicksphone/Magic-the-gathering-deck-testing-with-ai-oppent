# main.py

from api import fetch_card_data
from db import create_database, insert_card_data
from image_downloader import download_image
from game_play import GamePlayApp, Card  # Importing the gameplay logic
from PyQt5.QtWidgets import QApplication
import sys

# Fetch card data and insert into the database, with image download
def process_card(card_name):
    """
    Process a card: Fetch data from the API, store in the database, and download image.
    """
    card_data = fetch_card_data(card_name)
    
    if card_data:
        # Insert the card data into the database
        insert_card_data(card_data)
        
        # Download the card image
        if 'image_uris' in card_data:
            download_image(card_data['image_uris']['normal'], card_data['name'])

def process_bulk_cards(card_names):
    """
    Process multiple cards by name.
    """
    for card_name in card_names:
        process_card(card_name)

# Create a deck from the API data
def create_deck_from_api(card_names):
    """
    Creates a deck by fetching data from the API and building a list of Card objects.
    """
    deck = []
    for card_name in card_names:
        card_data = fetch_card_data(card_name)
        if card_data:
            card = Card(
                name=card_data['name'],
                card_type=card_data['type_line'],
                mana_cost=card_data.get('mana_cost', 'N/A'),
                power=card_data.get('power', 'N/A'),
                toughness=card_data.get('toughness', 'N/A'),
                abilities=card_data.get('keywords', [])
            )
            deck.append(card)
    
    return deck

# Game initialization
if __name__ == '__main__':
    # Create the database for storing cards
    create_database()
    
    # Example card names for player and AI decks
    player_card_names = ['Black Lotus', 'Lightning Bolt', 'Serra Angel']
    ai_card_names = ['AI Flying Warrior', 'AI Trample Beast', 'AI First Strike Knight']

    # Process and store card data
    process_bulk_cards(player_card_names)
    process_bulk_cards(ai_card_names)

    # Create decks from the API data
    player_deck = create_deck_from_api(player_card_names)
    ai_deck = create_deck_from_api(ai_card_names)

    # Launch the game using PyQt5
    app = QApplication(sys.argv)
    game_play = GamePlayApp(player_deck=player_deck, ai_deck=ai_deck)
    game_play.show()
    sys.exit(app.exec_())
