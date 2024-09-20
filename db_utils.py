import sqlite3
import os

# Database file path
DB_FILE_PATH = 'magic_cards.db'

def initialize_database():
    """
    Check if the database exists, and create it if not.
    """
    if not os.path.exists(DB_FILE_PATH):
        create_database()
    else:
        print("Database already exists.")

def create_database():
    """
    Create the database and the necessary tables.
    """
    conn = sqlite3.connect(DB_FILE_PATH)
    cursor = conn.cursor()

    # Create a table to store card data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_name TEXT NOT NULL,
        mana_cost TEXT,
        card_type TEXT,
        attack INTEGER,
        defense INTEGER,
        abilities TEXT,
        image_path TEXT
    );
    ''')

    # Commit and close
    conn.commit()
    conn.close()
    print("Database created successfully.")
