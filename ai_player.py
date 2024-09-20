class AIPlayer(Player):
    def __init__(self, name, deck):
        super().__init__(name)
        self.deck = deck
        self.personality = self.evaluate_deck()  # Assign AI personality based on the deck

    def evaluate_deck(self):
        """
        Analyze the deck and assign a personality (Aggro, Control, Midrange).
        """
        creature_count = 0
        removal_count = 0
        counterspell_count = 0
        card_draw_count = 0

        for card in self.deck:
            if isinstance(card, CreatureCard) and int(card.mana_cost) <= 3:
                creature_count += 1  # Aggro decks usually have many low-cost creatures
            if isinstance(card, InstantCard) or isinstance(card, SorceryCard):
                if "destroy" in card.oracle_text or "exile" in card.oracle_text:
                    removal_count += 1  # Control decks have a high number of removal spells
                if "counter" in card.oracle_text:
                    counterspell_count += 1  # Control decks have counterspells
                if "draw" in card.oracle_text:
                    card_draw_count += 1  # Control decks focus on card draw for card advantage

        # If the deck is filled with low-cost creatures, it's likely an aggro deck
        if creature_count >= len(self.deck) * 0.4:
            return "Aggro"

        # If the deck has lots of removal and counterspells, it's a control deck
        if removal_count + counterspell_count >= len(self.deck) * 0.3:
            return "Control"

        # Otherwise, the deck is balanced (Midrange)
        return "Midrange"

    def take_actions(self, game):
        """
        The AI takes its turn by analyzing the board state and making decisions.
        Behavior will depend on the AI's personality (Aggro, Control, Midrange).
        """
        if self.personality == "Aggro":
            self.play_aggressive(game)
        elif self.personality == "Control":
            self.play_control(game)
        else:
            self.play_midrange(game)
    
    def play_aggressive(self, game):
        """
        Aggro playstyle: Play creatures aggressively, attack early and often.
        """
        # Play low-cost creatures as soon as possible
        self.play_optimal_creature(game)
        
        # Attack with all creatures that can attack
        self.declare_attackers(game)
    
    def play_control(self, game):
        """
        Control playstyle: Focus on controlling the board, playing removal, counterspells, and card draw.
        """
        # Prioritize spells that control the board (removal, counterspells, card draw)
        self.cast_control_spells(game)

        # Hold back on creatures unless necessary
        if len(self.battlefield) < 2:
            self.play_optimal_creature(game)

    def play_midrange(self, game):
        """
        Midrange playstyle: Balanced between aggression and control.
        """
        # Play creatures strategically, attack when advantageous
        if len(self.battlefield) > len(game.player.battlefield):
            self.declare_attackers(game)
        else:
            self.play_optimal_creature(game)
        
        # Cast spells to maintain control
        self.cast_control_spells(game)

    def play_optimal_creature(self, game):
        """
        Play the best creature available based on current mana and board state.
        """
        best_creature = None
        highest_value = 0
        
        for card in self.hand:
            if isinstance(card, CreatureCard):
                value = self.evaluate_card(card, game)
                if value > highest_value and self.can_play_card(card):
                    best_creature = card
                    highest_value = value

        if best_creature:
            self.play_card_from_hand(best_creature, game)
            print(f"AI plays {best_creature.name}")

    def cast_control_spells(self, game):
        """
        Cast the best control spells available, focusing on removal and counterspells.
        """
        for card in self.hand:
            if isinstance(card, InstantCard) or isinstance(card, SorceryCard):
                if self.should_cast_removal(card, game) or self.should_cast_counterspell(card, game):
                    self.play_card_from_hand(card, game)
                    print(f"AI casts {card.name}")

    def should_cast_removal(self, card, game):
        """
        Decide if a removal spell should be cast, based on the opponent's board state.
        """
        if "destroy" in card.oracle_text or "exile" in card.oracle_text:
            best_target = self.find_best_removal_target(game)
            return best_target is not None

    def should_cast_counterspell(self, card, game):
        """
        Decide if a counterspell should be cast, based on the stack.
        """
        return "counter" in card.oracle_text and len(game.stack) > 0
    
    def declare_attackers(self, game):
        """
        Aggro and Midrange AIs attack aggressively, Control AI attacks only if it's safe.
        """
        attackers = []

        for creature in self.battlefield:
            if isinstance(creature, CreatureCard) and not creature.tapped:
                attackers.append(creature)

        if attackers:
            for creature in attackers:
                game.declare_attack(creature, self, game.player)
                print(f"AI attacks with {creature.name}")
