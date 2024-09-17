# effects.py

class ReplacementEffect:
    """
    Represents a replacement effect that modifies events.
    """
    def apply(self, event, game):
        # Modify the event as needed
        return event

class ContinuousEffect:
    """
    Represents a continuous effect that applies over a duration.
    """
    def __init__(self, duration, effect_function):
        self.duration = duration
        self.effect_function = effect_function

    def apply(self, game):
        self.effect_function(game)
