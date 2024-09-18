# populate_cards_db.py

import requests
import sqlite3
import json
import os
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
ALL_CARDS_ENDPOINT = "https://api.scryfall.com/cards/search?order=set&q=e%3Akhm&unique=prints"  # Example set; modify as needed
DATABASE_NAME = "mtg_cards.db"

def get_bulk_data_url():
    """
    Fetches the bulk data endpoint URL from Scryfall.
    
    Returns:
        str: The URL to the bulk data.
    """
    response = requests.get(BULK_DATA_URL)
    response.raise_for_status()
    data = response.json()
    for bulk in data['data']:
        if bulk['type'] == 'all_cards':
            return bulk['download_uri']
    raise ValueError("Bulk data for 'all_cards' not found.")

def download_all_cards():
    """
    Downloads all card data from Scryfall's bulk data endpoint.
    
    Returns:
        list: A list of card data dictionaries.
    """
    bulk_url = get_bulk_data_url()
    logger.info(f"Downloading bulk card data from {bulk_url}...")
    response = requests.get(bulk_url, stream=True)
    response.raise_for_status()
    
    # Save to a temporary file
    temp_file = "AllCards.json"
    with open(temp_file, 'wb') as f:
        for chunk in tqdm(response.iter_content(chunk_size=1024), desc="Downloading AllCards.json"):
            if chunk:
                f.write(chunk)
    
    # Load JSON data
    logger.info("Loading card data into memory...")
    with open(temp_file, 'r', encoding='utf-8') as f:
        all_cards = json.load(f)
    
    # Remove the temporary file
    os.remove(temp_file)
    
    logger.info(f"Downloaded and loaded {len(all_cards)} cards.")
    return all_cards

def create_database(db_name=DATABASE_NAME):
    """
    Creates the SQLite database and the 'cards' table.
    
    Args:
        db_name (str): The name of the SQLite database file.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Create 'cards' table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            name TEXT,
            type_line TEXT,
            mana_cost TEXT,
            colors TEXT,
            power INTEGER,
            toughness INTEGER,
            oracle_text TEXT,
            keywords TEXT,
            image_url TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database '{db_name}' created with 'cards' table.")

def insert_card(cursor, card):
    """
    Inserts a single card into the 'cards' table.
    
    Args:
        cursor (sqlite3.Cursor): The database cursor.
        card (dict): The card data dictionary.
    """
    try:
        card_id = card.get('id')
        name = card.get('name')
        type_line = card.get('type_line', '')
        mana_cost = card.get('mana_cost', '')
        colors = ','.join(card.get('colors', [])) if card.get('colors') else ''
        power = card.get('power')
        toughness = card.get('toughness')
        oracle_text = card.get('oracle_text', '')
        keywords = ','.join(card.get('keywords', [])) if card.get('keywords') else ''
        image_url = get_image_url(card)
        
        cursor.execute('''
            INSERT OR IGNORE INTO cards (id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (card_id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url))
    except sqlite3.Error as e:
        logger.error(f"Error inserting card '{name}': {e}")

def get_image_url(card):
    """
    Retrieves the image URL from the card data.
    
    Args:
        card (dict): The card data dictionary.
    
    Returns:
        str: The image URL or None if not available.
    """
    # Prefer high-quality images; adjust as needed
    image_uris = card.get("image_uris", {})
    if image_uris:
        return image_uris.get("normal")  # You can choose 'png', 'art_crop', etc.
    # Handle double-faced cards
    if "card_faces" in card:
        return card["card_faces"][0].get("image_uris", {}).get("normal")
    return None

def populate_database(db_name=DATABASE_NAME):
    """
    Populates the SQLite database with all card data.
    
    Args:
        db_name (str): The name of the SQLite database file.
    """
    all_cards = download_all_cards()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    logger.info("Inserting cards into the database...")
    for card in tqdm(all_cards, desc="Inserting cards"):
        insert_card(cursor, card)
    
    conn.commit()
    conn.close()
    logger.info("All cards have been inserted into the database.")

def main():
    """
    Main function to create and populate the database.
    """
    create_database()
    populate_database()

if __name__ == "__main__":
    main()
