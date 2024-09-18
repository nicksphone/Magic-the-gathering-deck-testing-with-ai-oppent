# card_factory.py

import sqlite3
import requests
import logging
from creature_card import CreatureCard
from land_card import LandCard
from instant_card import InstantCard
from sorcery_card import SorceryCard
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CardFactory:
    """
    Factory class to create card instances by name using a local SQLite database.
    Falls back to the Scryfall API if the card is not found locally.
    """

    SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"

    def __init__(self, db_path='mtg_cards.db'):
        """
        Initializes the CardFactory with a connection to the SQLite database.
        
        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        logger.info(f"Connected to SQLite database at '{self.db_path}'.")

    def __del__(self):
        """
        Ensures that the database connection is closed when the factory is destroyed.
        """
        self.conn.close()
        logger.info("Closed the SQLite database connection.")

    @lru_cache(maxsize=1000)
    def create_card(self, card_name):
        """
        Creates and returns a card instance based on the card name.
        Prioritizes fetching from the local database; falls back to the Scryfall API if not found.
        
        Args:
            card_name (str): The name of the card to create.
        
        Returns:
            Card: An instance of the specified card or None if not found.
        """
        card = self.fetch_card_from_db(card_name)
        if card:
            logger.info(f"Card '{card_name}' fetched from local database.")
            return card
        else:
            logger.info(f"Card '{card_name}' not found locally. Fetching from Scryfall API...")
            card = self.fetch_card_from_api(card_name)
            if card:
                self.insert_card_into_db(card)
                logger.info(f"Card '{card_name}' fetched from API and inserted into local database.")
                return card
            else:
                logger.error(f"Card '{card_name}' could not be found in the local database or via the API.")
                return None

    def fetch_card_from_db(self, card_name):
        """
        Fetches a card from the local SQLite database by name.
        
        Args:
            card_name (str): The name of the card to fetch.
        
        Returns:
            Card: An instance of the card or None if not found.
        """
        try:
            self.cursor.execute("SELECT * FROM cards WHERE name = ?", (card_name,))
            row = self.cursor.fetchone()
            if row:
                return self.parse_card_from_db(row)
            else:
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error while fetching '{card_name}': {e}")
            return None

    def fetch_card_from_api(self, card_name):
        """
        Fetches a card from the Scryfall API by exact name.
        
        Args:
            card_name (str): The name of the card to fetch.
        
        Returns:
            Card: An instance of the card or None if not found.
        """
        try:
            params = {"exact": card_name}
            response = requests.get(self.SCRYFALL_API_URL, params=params)
            response.raise_for_status()
            card_data = response.json()
            return self.parse_card(card_data)
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching '{card_name}': {http_err}")
        except Exception as err:
            logger.error(f"An error occurred while fetching '{card_name}': {err}")
        return None

    def parse_card_from_db(self, row):
        """
        Parses a database row into a card instance.
        
        Args:
            row (tuple): The database row containing card data.
        
        Returns:
            Card: An instance of the appropriate card class.
        """
        (card_id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url) = row
        abilities = keywords.split(', ') if keywords else []
        
        # Determine the card class based on its type
        if "Creature" in type_line:
            card_class = CreatureCard
        elif "Instant" in type_line:
            card_class = InstantCard
        elif "Sorcery" in type_line:
            card_class = SorceryCard
        elif "Land" in type_line:
            mana_type = self.parse_mana_type(type_line)
            return LandCard(name=name, mana_type=mana_type, image_url=image_url)
        else:
            logger.warning(f"Card type '{type_line}' not supported for card '{name}'.")
            return None  # You can extend this to support more card types

        return card_class(
            name=name,
            mana_cost=self.parse_mana_cost(mana_cost),
            power=power,
            toughness=toughness,
            description=oracle_text,
            abilities=abilities,
            keywords=keywords.split(', ') if keywords else [],
            image_url=image_url
        )

    def parse_card(self, data):
        """
        Parses the JSON data from Scryfall and returns an instance of the appropriate card class.
        
        Args:
            data (dict): The JSON data of the card.
        
        Returns:
            Card: An instance of the appropriate card class.
        """
        card_type = data.get("type_line", "")
        name = data.get("name", "")
        mana_cost = self.parse_mana_cost(data.get("mana_cost", ""))
        power = self.parse_power(data.get("power"))
        toughness = self.parse_toughness(data.get("toughness"))
        oracle_text = data.get("oracle_text", "")
        keywords = data.get("keywords", [])
        image_url = self.get_image_url(data)
        
        # Determine the card class based on its type
        if "Creature" in card_type:
            card_class = CreatureCard
        elif "Instant" in card_type:
            card_class = InstantCard
        elif "Sorcery" in card_type:
            card_class = SorceryCard
        elif "Land" in card_type:
            mana_type = self.parse_mana_type(card_type)
            return LandCard(name=name, mana_type=mana_type, image_url=image_url)
        else:
            logger.warning(f"Card type '{card_type}' not supported for card '{name}'.")
            return None  # You can extend this to support more card types

        # Create the card instance
        return card_class(
            name=name,
            mana_cost=mana_cost,
            power=power,
            toughness=toughness,
            description=oracle_text,
            abilities=keywords,  # Assign keywords as abilities; adjust as needed
            keywords=keywords,
            image_url=image_url
        )

    def insert_card_into_db(self, card):
        """
        Inserts a card into the local SQLite database.
        
        Args:
            card (Card): The card instance to insert.
        """
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO cards (id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card.id,  # Assuming each card has a unique 'id' attribute
                card.name,
                card.type_line,
                self.serialize_mana_cost(card.mana_cost),
                self.serialize_colors(card.colors),
                card.power,
                card.toughness,
                card.description,
                ', '.join(card.abilities) if card.abilities else '',
                card.image_url
            ))
            self.conn.commit()
            logger.info(f"Inserted card '{card.name}' into the local database.")
        except sqlite3.Error as e:
            logger.error(f"Database error while inserting '{card.name}': {e}")

    def serialize_mana_cost(self, mana_cost_dict):
        """
        Serializes the mana cost dictionary into a string.
        
        Args:
            mana_cost_dict (dict): The mana cost dictionary.
        
        Returns:
            str: The serialized mana cost string.
        """
        mana_symbols = []
        for color, count in mana_cost_dict.items():
            if color == "Colorless":
                mana_symbols.extend([str(count)])
            else:
                mana_symbols.extend([color[0]] * count)
        return '{' + '}{'.join(mana_symbols) + '}' if mana_symbols else ''

    def serialize_colors(self, colors_list):
        """
        Serializes the colors list into a comma-separated string.
        
        Args:
            colors_list (list): The list of colors.
        
        Returns:
            str: The serialized colors string.
        """
        return ','.join(colors_list) if colors_list else ''

    def parse_mana_cost(self, mana_cost_str):
        """
        Parses the mana cost string into a dictionary.
        
        Args:
            mana_cost_str (str): The mana cost string (e.g., "{1}{G}{G}").
        
        Returns:
            dict: A dictionary mapping colors to their counts.
        """
        mana_pool = {'White': 0, 'Blue': 0, 'Black': 0, 'Red': 0, 'Green': 0, 'Colorless': 0}
        if not mana_cost_str:
            return mana_pool
        # Split by '}{', remove '{' and '}', then process
        symbols = mana_cost_str.replace('{', '').replace('}', '').split()
        for symbol in symbols:
            if symbol.isdigit():
                mana_pool['Colorless'] += int(symbol)
            else:
                color = self.mana_symbol_to_color(symbol)
                if color:
                    mana_pool[color] += 1
        return mana_pool

    def mana_symbol_to_color(self, symbol):
        """
        Converts a mana symbol to its corresponding color.
        
        Args:
            symbol (str): The mana symbol (e.g., 'G', 'U').
        
        Returns:
            str: The corresponding color or None.
        """
        symbol_color_map = {
            'W': 'White',
            'U': 'Blue',
            'B': 'Black',
            'R': 'Red',
            'G': 'Green',
        }
        return symbol_color_map.get(symbol.upper())

    def parse_power(self, power_str):
        """
        Parses the power string to an integer.
        
        Args:
            power_str (str): The power string.
        
        Returns:
            int: The power value or 0 if not applicable.
        """
        try:
            return int(power_str)
        except (TypeError, ValueError):
            return 0

    def parse_toughness(self, toughness_str):
        """
        Parses the toughness string to an integer.
        
        Args:
            toughness_str (str): The toughness string.
        
        Returns:
            int: The toughness value or 0 if not applicable.
        """
        try:
            return int(toughness_str)
        except (TypeError, ValueError):
            return 0

    def parse_mana_type(self, type_line):
        """
        Parses the mana type from the type line.
        
        Args:
            type_line (str): The type line of the card.
        
        Returns:
            str: The mana type or None.
        """
        if "Mountain" in type_line:
            return "Red"
        elif "Plains" in type_line:
            return "White"
        elif "Island" in type_line:
            return "Blue"
        elif "Swamp" in type_line:
            return "Black"
        elif "Forest" in type_line:
            return "Green"
        return None

    def get_image_url(self, data):
        """
        Retrieves the image URL from the card data.
        
        Args:
            data (dict): The JSON data of the card.
        
        Returns:
            str: The image URL or None if not available.
        """
        # Prefer high-quality images; adjust as needed
        image_uris = data.get("image_uris", {})
        if image_uris:
            return image_uris.get("normal")  # You can choose 'png', 'art_crop', etc.
        # Handle double-faced cards
        if "card_faces" in data:
            return data["card_faces"][0].get("image_uris", {}).get("normal")
        return None
