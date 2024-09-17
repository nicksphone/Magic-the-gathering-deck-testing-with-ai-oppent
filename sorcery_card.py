# sorcery_card.py

from card import Card

class SorceryCard(Card):
    """
    Represents sorcery cards with effects.
    """
    def __init__(self, name, mana_cost, effect, description, target_required=False, keywords=None):
        super().__init__(name, mana_cost, card_type='Sorcery', description=description, keywords=keywords)
        self.effect = effect
        self.target_required = target_required

    def resolve(self, game):
        if self.has_keyword("Storm"):
            self.resolve_storm(game)
        else:
            if self.target_required and not self.target:
                game.logger.record(f"{self.name} has no valid target and fizzles.")
            else:
                self.effect(game, self.owner, self.target)
        self.owner.graveyard.append(self)
        self.zone = 'graveyard'
        game.logger.record(f"{self.name} resolves and is put into {self.owner.name}'s graveyard")

    def resolve_storm(self, game):
        storm_count = len(game.spells_cast_this_turn) - 1
        for _ in range(storm_count + 1):
            if self.target_required and not self.target:
                game.logger.record(f"{self.name} has no valid target and fizzles.")
            else:
                self.effect(game, self.owner, self.target)
        game.logger.record(f"{self.name} resolves with Storm count: {storm_count}")
