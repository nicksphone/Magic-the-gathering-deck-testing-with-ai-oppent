# replacement_effect.py

class ReplacementEffect:
    """
    Represents a replacement effect that can modify or replace events.

    Attributes:
        condition (callable): Function that checks if the effect applies to an event.
        modify_event_function (callable): Function that modifies the event.
        duration (str): 'permanent' or 'until_end_of_turn'.
        source (Card): The source of the replacement effect.
    """

    def __init__(self, condition, modify_event_function, duration='permanent', source=None):
        self.condition = condition
        self.modify_event_function = modify_event_function
        self.duration = duration
        self.source = source

    def modify_event(self, event, game):
        if self.condition(event, game, self.source):
            return self.modify_event_function(event, game, self.source)
        return event
