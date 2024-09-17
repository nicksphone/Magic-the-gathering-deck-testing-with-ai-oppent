# triggered_ability.py

class TriggeredAbility:
    """
    Represents a triggered ability on a card.
    """
    def __init__(self, trigger_condition, effect, description):
        self.trigger_condition = trigger_condition  # Function to check if the ability triggers
        self.effect = effect  # Effect function
        self.description = description
        self.owner = None  # Set when ability is triggered
        self.source_card = None

    def resolve(self, game):
        self.effect(game, self.owner, self.source_card)
