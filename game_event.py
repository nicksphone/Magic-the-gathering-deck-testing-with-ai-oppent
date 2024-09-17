# game_event.py

class GameEvent:
    """
    Represents an event that occurs in the game, used for triggering abilities.
    """
    def __init__(self, event_type, **kwargs):
        self.event_type = event_type
        for key, value in kwargs.items():
            setattr(self, key, value)
        # Examples of event types: 'enter_battlefield', 'spell_cast', 'creature_dies', etc.
