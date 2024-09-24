# db_utilities.py

import sqlite3
from image_downloader import download_image

def create_database():
    """
    Create the SQLite database for storing card details.
    """
    conn = sqlite3.connect('mtg_cards.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        mana_cost TEXT,
        type_line TEXT,
        power TEXT,
        toughness TEXT,
        abilities TEXT,
        image_url TEXT
    )''')
    
    conn.commit()
    conn.close()

def insert_card_data(card_data):
    """
    Insert card data into the database, handling potential missing values.
    """
    conn = sqlite3.connect('mtg_cards.db')
    cursor = conn.cursor()

    name = card_data.get('name', 'N/A')
    mana_cost = card_data.get('mana_cost', 'N/A')
    type_line = card_data.get('type_line', 'N/A')
    power = card_data.get('power', 'N/A')
    toughness = card_data.get('toughness', 'N/A')
    abilities = ', '.join(card_data.get('keywords', []))
    image_url = card_data['image_uris']['normal'] if 'image_uris' in card_data else None

    # Download the image and get the local path
    image_path = None
    if image_url:
        image_path = download_image(image_url, name)

    try:
        cursor.execute('''
        INSERT OR IGNORE INTO cards (name, mana_cost, type_line, power, toughness, abilities, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)''', 
        (name, mana_cost, type_line, power, toughness, abilities, image_path))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Card '{name}' already exists in the database.")
    
    conn.close()

def get_card_by_name(card_name):
    """
    Retrieve a card from the database by its name.
    """
    conn = sqlite3.connect('mtg_cards.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cards WHERE name = ?', (card_name,))
    card = cursor.fetchone()
    conn.close()
    return card

def load_deck_from_db(deck_names):
    """
    Load a deck from the database using a list of card names.
    """
    deck = []
    for card_name in deck_names:
        card = get_card_by_name(card_name)
        if card:
            deck.append(card)
        else:
            print(f"Card '{card_name}' not found in the database.")
    return deck
