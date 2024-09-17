# card_pool.py

import random

class CardPool:
    """
    Defines the card pool and manages booster pack generation.
    """
    def __init__(self):
        self.common_cards = [
            "Savannah Lions", "Silvercoat Lion", "Deadly Recluse", "Goblin Electromancer", "Lightning Bolt", "Llanowar Elves"
        ]
        self.uncommon_cards = [
            "Vampire Nighthawk", "Ascended Lawmage", "Darksteel Golem", "Counterspell", "Terror"
        ]
        self.rare_cards = [
            "Serra Angel", "Shivan Dragon", "Bloodbraid Elf", "Wrath of God"
        ]
        self.mythic_rare_cards = [
            "Grapeshot", "Jace, the Mind Sculptor", "Black Lotus"
        ]

    def generate_booster_pack(self):
        pack_contents = []

        # Add common cards (10 cards)
        for _ in range(10):
            card = random.choice(self.common_cards)
            pack_contents.append(card)

        # Add uncommon cards (3 cards)
        for _ in range(3):
            card = random.choice(self.uncommon_cards)
            pack_contents.append(card)

        # Add rare or mythic rare card (1 card)
        if random.random() < 0.125:  # 1 in 8 chance for mythic rare
            card = random.choice(self.mythic_rare_cards)
        else:
            card = random.choice(self.rare_cards)
        pack_contents.append(card)

        return pack_contents
