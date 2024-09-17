# planeswalker_card.py

from card import Card

class PlaneswalkerCard(Card):
    """
    Represents a planeswalker card in the game.

    Attributes:
        abilities (list): A list of abilities with costs.
        loyalty (int): Current loyalty counters.
    """

    def __init__(self, name, mana_cost, description, abilities, starting_loyalty):
        super().__init__(name, mana_cost, 'Planeswalker', description)
        self.abilities = abilities  # A list of abilities with costs
        self.loyalty = starting_loyalty

    def play(self, game, player):
        self.owner = player
        player.battlefield.append(self)
        print(f"{player.name} plays planeswalker: {self.name}")

    def activate_ability(self, ability_index, game):
        ability = self.abilities[ability_index]
        cost = ability['cost']
        effect = ability['effect']
        self.loyalty += cost
        if self.loyalty <= 0:
            # Planeswalker is destroyed
            self.owner.battlefield.remove(self)
            self.owner.graveyard.append(self)
            print(f"{self.name} is destroyed due to insufficient loyalty")
        else:
            effect(game, self.owner)
            print(f"{self.owner.name} activates {self.name}'s ability: {ability['description']}")
