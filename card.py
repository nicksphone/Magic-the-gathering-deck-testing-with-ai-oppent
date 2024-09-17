# card.py

class Card:
    """
    Base class for all cards.
    """
    def __init__(self, name, mana_cost, card_type, description, keywords=None, timing='Sorcery', owner=None):
        self.name = name
        self.mana_cost = mana_cost  # Dictionary like {'Red':1, 'Colorless':2}
        self.card_type = card_type
        self.description = description
        self.keywords = keywords if keywords else []
        self.timing = timing  # 'Instant' or 'Sorcery'
        self.owner = owner
        self.zone = 'library'
        self.target_required = False
        self.target = None

    def has_keyword(self, keyword):
        return keyword in self.keywords

    def resolve(self, game):
        # Default resolve method, to be overridden by subclasses
        pass

    def play(self, game, player):
        # Default play method, to be overridden by subclasses
        pass
