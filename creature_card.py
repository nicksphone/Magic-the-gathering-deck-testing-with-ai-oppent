# creature_card.py

from card import Card
from game_event import GameEvent

class CreatureCard(Card):
    """
    Represents creature cards with power, toughness, and abilities.
    """
    def __init__(self, name, mana_cost, power, toughness, description, abilities=None, keywords=None,
                 activated_abilities=None, triggered_abilities=None):
        super().__init__(name, mana_cost, card_type='Creature', description=description, keywords=keywords)
        self.power = power
        self.toughness = toughness
        self.base_power = power
        self.base_toughness = toughness
        self.abilities = abilities if abilities else []
        self.activated_abilities = activated_abilities if activated_abilities else []
        self.triggered_abilities = triggered_abilities if triggered_abilities else []
        self.tap_status = False
        self.summoning_sick = True  # Creatures have summoning sickness when they enter the battlefield

    def can_attack(self):
        return not self.tap_status and not self.summoning_sick and ('Defender' not in self.abilities)

    def resolve(self, game):
        self.owner.battlefield.append(self)
        self.zone = 'battlefield'
        game.logger.record(f"{self.name} enters the battlefield under {self.owner.name}'s control")
        # Trigger enter the battlefield abilities
        game.trigger_event(GameEvent(event_type='enter_battlefield', card=self))
        # Summoning sickness applies if the creature doesn't have Haste
        if 'Haste' not in self.abilities:
            self.summoning_sick = True
        else:
            self.summoning_sick = False

    def on_turn_start(self):
        # Remove summoning sickness at the beginning of your turn
        if self.owner.game.get_current_player() == self.owner:
            self.summoning_sick = False
