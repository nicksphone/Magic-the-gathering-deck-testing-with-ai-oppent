# events.py

class GameEvent:
    """
    Represents an event that occurs in the game.

    Attributes:
        event_type (str): The type of the event (e.g., 'enter_battlefield', 'spell_cast').
        kwargs (dict): Additional data about the event.
    """

    def __init__(self, event_type, **kwargs):
        self.event_type = event_type  # e.g., 'enter_battlefield', 'spell_cast'
        self.kwargs = kwargs  # Additional data about the event
