# land_card.py

from card import Card

class LandCard(Card):
    """
    Represents land cards that can be tapped for mana.
    """
    def __init__(self, name, mana_type):
        super().__init__(name, mana_cost={}, card_type='Land', description=f"Tap: Add {mana_type} mana.")
        self.mana_type = mana_type
        self.tap_status = False
        self.timing = 'Land'

    def resolve(self, game):
        self.owner.battlefield.append(self)
        self.zone = 'battlefield'
        game.logger.record(f"{self.name} enters the battlefield under {self.owner.name}'s control")
