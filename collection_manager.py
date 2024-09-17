# collection_manager.py

import json
import os

class CollectionManager:
    """
    Manages the player's card collection.
    """
    def __init__(self, player_name):
        self.player_name = player_name
        self.collection_file = f"{player_name}_collection.json"
        self.collection = self.load_collection()

    def load_collection(self):
        if os.path.exists(self.collection_file):
            with open(self.collection_file, 'r') as f:
                collection = json.load(f)
        else:
            collection = {}  # Start with an empty collection
        return collection

    def save_collection(self):
        with open(self.collection_file, 'w') as f:
            json.dump(self.collection, f, indent=4)

    def add_card(self, card_name, quantity=1):
        if card_name in self.collection:
            self.collection[card_name] += quantity
        else:
            self.collection[card_name] = quantity
        self.save_collection()

    def remove_card(self, card_name, quantity=1):
        if card_name in self.collection:
            self.collection[card_name] -= quantity
            if self.collection[card_name] <= 0:
                del self.collection[card_name]
            self.save_collection()

    def get_collection(self):
        return self.collection

    def get_card_quantity(self, card_name):
        return self.collection.get(card_name, 0)
