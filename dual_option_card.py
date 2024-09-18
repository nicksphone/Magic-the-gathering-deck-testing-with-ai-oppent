# dual_option_card.py

class DualOptionCard:
    def __init__(self, name, mana_cost, card_options, description, image_url=None):
        """
        Initializes a DualOptionCard that can be played in multiple ways.
        
        Args:
            name (str): The name of the card.
            mana_cost (str): The mana cost for the card.
            card_options (list): A list of tuples, each representing a different type the card can be played as.
                                For example: [("Creature", creature_stats), ("Land", land_type)].
            description (str): Description of the card's effects.
            image_url (str): URL of the card image.
        """
        self.name = name
        self.mana_cost = mana_cost
        self.card_options = card_options  # List of options (e.g., Creature, Land, etc.)
        self.description = description
        self.image_url = image_url
        self.owner = None

    def play_card(self, option, player):
        """
        Plays the card in the form chosen by the player.
        
        Args:
            option (str): The type of card being played (e.g., "Creature", "Land", etc.).
            player (Player): The player who is playing the card.
        """
        if option == "Creature":
            stats = self.get_option_stats("Creature")
            if stats:
                creature = CreatureCard(self.name, self.mana_cost, stats['power'], stats['toughness'], self.description, image_url=self.image_url)
                player.battlefield.append(creature)
                print(f"{player.name} played {self.name} as a Creature.")
        elif option == "Land":
            land_type = self.get_option_stats("Land")
            if land_type:
                land = LandCard(self.name, land_type, image_url=self.image_url)
                player.lands.append(land)
                print(f"{player.name} played {self.name} as a Land.")
        elif option == "Instant":
            print(f"{player.name} played {self.name} as an Instant.")
            # Apply instant effects
        elif option == "Sorcery":
            print(f"{player.name} played {self.name} as a Sorcery.")
            # Apply sorcery effects
        elif option == "Artifact":
            print(f"{player.name} played {self.name} as an Artifact.")
            player.battlefield.append(self)  # Place on the battlefield
        # Add other card types as needed (Enchantment, Planeswalker, etc.)

    def get_option_stats(self, option_type):
        """
        Retrieves the stats for the chosen option type (e.g., power/toughness for creatures, land type for lands).
        
        Args:
            option_type (str): The type of the card option (e.g., "Creature", "Land", etc.).
        
        Returns:
            dict or str: Returns the stats for the card option, if available.
        """
        for option, stats in self.card_options:
            if option == option_type:
                return stats
        return None
