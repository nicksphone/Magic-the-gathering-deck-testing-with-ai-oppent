# activated_ability.py

class ActivatedAbility:
    """
    Represents an activated ability on a card.
    """
    def __init__(self, cost_function, effect, description, timing='Any'):
        self.cost_function = cost_function  # Function to pay costs
        self.effect = effect  # Effect function
        self.description = description
        self.timing = timing  # 'Any' or 'Sorcery'
        self.owner = None  # Set when ability is activated
        self.source_card = None

    def can_activate(self, source_card, player, game):
        if self.timing == 'Any':
            return True
        elif self.timing == 'Sorcery' and game.phase in ['Main1', 'Main2'] and player == game.get_current_player() and not game.stack:
            return True
        else:
            return False

    def activate(self, source_card, player, game):
        if self.can_activate(source_card, player, game):
            if self.cost_function(source_card):
                self.owner = player
                self.source_card = source_card
                game.add_to_stack(self)
            else:
                game.logger.record(f"{player.name} cannot pay the activation cost for {self.description}")
        else:
            game.logger.record(f"{player.name} cannot activate {self.description} at this time.")

    def resolve(self, game):
        self.effect(game, self.owner, self.source_card)
