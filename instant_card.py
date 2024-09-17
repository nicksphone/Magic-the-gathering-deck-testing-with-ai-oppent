# instant_card.py

from card import Card

class InstantCard(Card):
    """
    Represents instant cards with immediate effects.
    """
    def __init__(self, name, mana_cost, effect, description, target_required=False, keywords=None):
        super().__init__(name, mana_cost, card_type='Instant', description=description, keywords=keywords, timing='Instant')
        self.effect = effect
        self.target_required = target_required

    def resolve(self, game):
        if self.target_required and not self.target:
            game.logger.record(f"{self.name} has no valid target and fizzles.")
        else:
            self.effect(game, self.owner, self.target)
        self.owner.graveyard.append(self)
        self.zone = 'graveyard'
        game.logger.record(f"{self.name} resolves and is put into {self.owner.name}'s graveyard")
