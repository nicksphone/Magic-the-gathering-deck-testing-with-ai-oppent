# db_utilities.py

import sqlite3
from image_downloader import download_image

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
        INSERT INTO cards (name, mana_cost, type_line, power, toughness, abilities, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)''', 
        (name, mana_cost, type_line, power, toughness, abilities, image_path))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Card '{name}' already exists in the database.")
    
    conn.close()
