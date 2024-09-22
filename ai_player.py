class AIPlayer:
    def __init__(self, deck):
        self.deck = deck
        self.hand = []
        self.battlefield = []
        self.strategy = self.determine_strategy()

    def determine_strategy(self):
        """
        Analyze the AI's deck to determine its playstyle (aggressive, defensive, or control).
        """
        aggressive_cards = sum(1 for card in self.deck if card['power'] and int(card['power']) >= 3)
        defensive_cards = sum(1 for card in self.deck if card['toughness'] and int(card['toughness']) >= 3)
        spell_count = sum(1 for card in self.deck if 'sorcery' in card['type_line'] or 'instant' in card['type_line'])

        if spell_count > aggressive_cards and spell_count > defensive_cards:
            return 'control'
        elif aggressive_cards > defensive_cards:
            return 'aggressive'
        else:
            return 'defensive'

    def draw_card(self):
        """
        AI draws a card from the deck to its hand.
        """
        if self.deck:
            card = self.deck.pop(0)
            self.hand.append(card)
            return card
        return None

    def play_turn(self, game_state):
        """
        AI makes decisions during its turn based on its strategy and current game state.
        """
        if not self.hand:
            self.draw_card()

        if self.strategy == 'aggressive':
            self.execute_aggressive_strategy(game_state)
        elif self.strategy == 'defensive':
            self.execute_defensive_strategy(game_state)
        elif self.strategy == 'control':
            self.execute_control_strategy(game_state)

    def execute_aggressive_strategy(self, game_state):
        """
        Aggressive strategy focuses on attacking and overwhelming the opponent.
        """
        print("AI is playing aggressively!")
        # AI chooses creatures to attack with
        self.attack_with_creatures()
        self.cast_offensive_spells()

    def execute_defensive_strategy(self, game_state):
        """
        Defensive strategy focuses on holding the line and preventing attacks.
        """
        print("AI is playing defensively!")
        # AI prioritizes playing creatures with high toughness
        self.play_defensive_creatures()
        self.hold_blockers()

    def execute_control_strategy(self, game_state):
        """
        Control strategy focuses on managing the opponent's board and playing removal.
        """
        print("AI is playing control!")
        # AI uses control spells and keeps mana for counterspells
        self.cast_control_spells()
        self.counter_opponent_spells(game_state)

    def attack_with_creatures(self):
        """
        AI chooses which creatures to attack with based on its strategy.
        """
        # Logic to choose the best creatures for attacking based on battlefield state

    def cast_offensive_spells(self):
        """
        AI casts spells that deal direct damage or remove blockers.
        """
        # Logic for casting offensive spells like Lightning Bolt, etc.

    def play_defensive_creatures(self):
        """
        AI plays creatures with higher toughness for defense.
        """
        # Logic to play creatures with high toughness

    def hold_blockers(self):
        """
        AI holds creatures back to block opponent's attacks.
        """
        # Logic to decide which creatures to hold for blocking

    def cast_control_spells(self):
        """
        AI casts spells to remove opponent's threats.
        """
        # Logic to cast control spells like removal and debuffs

    def counter_opponent_spells(self, game_state):
        """
        AI holds mana to counter opponent's spells.
        """
        # Logic to cast counterspells when the opponent plays key cards
