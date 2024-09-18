# test_card_factory.py

import unittest
from unittest.mock import patch, MagicMock
from card_factory import CardFactory
from creature_card import CreatureCard
from instant_card import InstantCard
from sorcery_card import SorceryCard
from land_card import LandCard

class TestCardFactory(unittest.TestCase):
    """
    Unit tests for the CardFactory class.
    """

    def setUp(self):
        """
        Sets up a CardFactory instance connected to a test database.
        """
        self.card_factory = CardFactory(db_path='test_mtg_cards.db')
        # Create test database schema
        self.card_factory.cursor.execute('''
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
        self.card_factory.conn.commit()

    def tearDown(self):
        """
        Closes the database connection and removes the test database file.
        """
        self.card_factory.conn.close()
        import os
        os.remove('test_mtg_cards.db')

    def test_create_card_from_db(self):
        """
        Tests creating a card that exists in the local database.
        """
        # Insert a test card into the database
        test_card_data = (
            "test-id-123",
            "Test Creature",
            "Creature — Test",
            "{1}{G}",
            "Green",
            2,
            3,
            "Test Creature does something.",
            "Flying",
            "https://example.com/test_creature.jpg"
        )
        self.card_factory.cursor.execute('''
            INSERT INTO cards (id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_card_data)
        self.card_factory.conn.commit()

        # Create the card
        card = self.card_factory.create_card("Test Creature")
        self.assertIsInstance(card, CreatureCard)
        self.assertEqual(card.name, "Test Creature")
        self.assertEqual(card.mana_cost['Green'], 1)
        self.assertEqual(card.mana_cost['Colorless'], 1)
        self.assertEqual(card.power, 2)
        self.assertEqual(card.toughness, 3)
        self.assertEqual(card.description, "Test Creature does something.")
        self.assertIn("Flying", card.abilities)
        self.assertEqual(card.image_url, "https://example.com/test_creature.jpg")

    @patch('card_factory.requests.get')
    def test_create_card_from_api(self, mock_get):
        """
        Tests creating a card that does not exist in the local database but exists via the API.
        """
        # Mock API response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "id": "api-id-456",
            "name": "API Instant",
            "type_line": "Instant",
            "mana_cost": "{U}",
            "oracle_text": "Draw two cards.",
            "image_uris": {
                "normal": "https://example.com/api_instant.jpg"
            },
            "keywords": []
        }
        mock_get.return_value = mock_response

        # Ensure the card is not in the local database
        card = self.card_factory.create_card("API Instant")
        self.assertIsInstance(card, InstantCard)
        self.assertEqual(card.name, "API Instant")
        self.assertEqual(card.mana_cost['Blue'], 1)
        self.assertEqual(card.mana_cost['Colorless'], 0)
        self.assertEqual(card.description, "Draw two cards.")
        self.assertEqual(card.abilities, [])
        self.assertEqual(card.image_url, "https://example.com/api_instant.jpg")

        # Verify that the card is now in the local database
        self.card_factory.cursor.execute("SELECT * FROM cards WHERE name = ?", ("API Instant",))
        row = self.card_factory.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "API Instant")

    @patch('card_factory.requests.get')
    def test_create_card_not_found(self, mock_get):
        """
        Tests creating a card that does not exist locally or via the API.
        """
        # Mock API 404 response
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error: Not Found for url")
        mock_get.return_value = mock_response

        # Attempt to create a nonexistent card
        card = self.card_factory.create_card("Nonexistent Card")
        self.assertIsNone(card)

    def test_create_land_card_from_db(self):
        """
        Tests creating a land card from the local database.
        """
        # Insert a test land into the database
        test_land_data = (
            "land-id-789",
            "Test Land",
            "Basic Land — Forest",
            "",
            "Green",
            None,
            None,
            "",
            "",
            "https://example.com/test_land.jpg"
        )
        self.card_factory.cursor.execute('''
            INSERT INTO cards (id, name, type_line, mana_cost, colors, power, toughness, oracle_text, keywords, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_land_data)
        self.card_factory.conn.commit()

        # Create the land
        card = self.card_factory.create_card("Test Land")
        self.assertIsInstance(card, LandCard)
        self.assertEqual(card.name, "Test Land")
        self.assertEqual(card.mana_type, "Green")
        self.assertEqual(card.image_url, "https://example.com/test_land.jpg")

if __name__ == "__main__":
    unittest.main()
