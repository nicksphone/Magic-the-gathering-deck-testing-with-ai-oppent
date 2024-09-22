# db.py
import sqlite3

def create_database():
    """
    Create the database and the 'cards' table if it doesn't already exist.
    """
    conn = sqlite3.connect('mtg_cards.db')
    cursor = conn.cursor()
    
    # Create table for storing card details
    cursor.execute('''CREATE TABLE IF NOT EXISTS cards
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       name TEXT,
                       mana_cost TEXT,
                       type_line TEXT,
                       power TEXT,
                       toughness TEXT,
                       abilities TEXT,
                       image_url TEXT)''')
    
    conn.commit()
    conn.close()

def insert_card_data(card_data):
    """
    Insert card data into the database.
    """
    conn = sqlite3.connect('mtg_cards.db')
    cursor = conn.cursor()
    
    # Extract relevant data from the card_data object
    name = card_data['name']
    mana_cost = card_data.get('mana_cost', 'N/A')
    type_line = card_data.get('type_line', 'N/A')
    power = card_data.get('power', 'N/A')
    toughness = card_data.get('toughness', 'N/A')
    abilities = ', '.join(card_data.get('keywords', []))  # Using keywords for abilities
    image_url = card_data['image_uris']['normal'] if 'image_uris' in card_data else None
    
    cursor.execute('''INSERT INTO cards (name, mana_cost, type_line, power, toughness, abilities, image_url)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                      (name, mana_cost, type_line, power, toughness, abilities, image_url))
    
    conn.commit()
    conn.close()
