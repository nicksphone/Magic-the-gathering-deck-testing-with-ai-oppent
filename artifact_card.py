# artifact_card.py

from card import Card

class ArtifactCard(Card)
    
    Represents an artifact card in the game.

    Attributes
        effect (callable) The effect of the artifact.
        is_creature (bool) Whether the artifact is also a creature.
        power (int) Power if it's an artifact creature.
        toughness (int) Toughness if it's an artifact creature.
        activated_abilities (list) List of ActivatedAbility instances.
    

    def __init__(self, name, mana_cost, description, effect=None, is_creature=False, power=0, toughness=0, activated_abilities=None)
        super().__init__(name, mana_cost, 'Artifact', description)
        self.effect = effect  # Optional effect function
        self.is_creature = is_creature
        self.power = power
        self.toughness = toughness
        self.tap_status = False
        self.summoning_sickness = True
        self.abilities = []
        self.activated_abilities = activated_abilities if activated_abilities else []

    def play(self, game, player)
        self.owner = player
        player.battlefield.append(self)
        if self.is_creature
            print(f{player.name} plays artifact creature {self.name})
        else
            if self.effect
                self.effect(game, player)
            print(f{player.name} plays artifact {self.name})
        self.enter_battlefield(game)
