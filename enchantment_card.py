# enchantment_card.py

from card import Card

class EnchantmentCard(Card):
    """
    Represents an enchantment card in the game.

    Attributes:
        effect (callable): The effect of the enchantment.
        subtype (str): 'Enchantment' or 'Aura'.
        attached_to (Card): The card this Aura is attached to.
    """

    def __init__(self, name, mana_cost, description, effect=None, subtype='Enchantment', replacement_effects=None):
        super().__init__(name, mana_cost, 'Enchantment', description)
        self.effect = effect  # Function that defines the enchantment's effect
        self.subtype = subtype  # 'Enchantment' or 'Aura'
        self.attached_to = None  # For Auras, the card it's attached to
        self.replacement_effects = replacement_effects if replacement_effects else []

    def play(self, game, player):
        self.owner = player
        if self.subtype == 'Aura':
            # Attach to a target
            target = player.select_target_for_aura(game)
            if target:
                self.attached_to = target
                target.enchantments.append(self)
                # Update the replacement effect's source
                for effect in self.replacement_effects:
                    effect.source = self
                # Register replacement effects
                if self.replacement_effects:
                    game.replacement_effects.extend(self.replacement_effects)
                game.logger.record(f"{player.name} enchants {target.name} with {self.name}")
            else:
                game.logger.record(f"{self.name} has no valid targets")
                player.graveyard.append(self)
        else:
            # Apply global effect
            player.battlefield.append(self)
            self.enter_battlefield(game)
            game.logger.record(f"{player.name} plays enchantment: {self.name}")
