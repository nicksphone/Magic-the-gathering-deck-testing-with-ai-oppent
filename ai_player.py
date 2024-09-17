# ai_player.py

from player import Player
from creature_card import CreatureCard
from land_card import LandCard

class AIPlayer(Player):
    """
    Represents an AI-controlled player with decision-making capabilities.
    """
    def __init__(self, name, is_ai=True):
        super().__init__(name, is_ai)
        # Additional AI-specific attributes can be added here

    def decide_response(self, game):
        if game.stack:
            top_spell = game.stack[-1]
            if self.should_counter_spell(top_spell):
                counterspell = self.find_counterspell()
                if counterspell:
                    self.play_card_from_hand(counterspell, game)
                    return
        game.pass_priority()

    def should_counter_spell(self, spell):
        # Simple logic: counter spells that are harmful
        if spell.owner != self and isinstance(spell, (CreatureCard,)):
            return True
        return False

    def find_counterspell(self):
        for card in self.hand:
            if card.name == "Counterspell" and self.can_pay_mana_cost(card.mana_cost):
                return card
        return None

    def take_actions(self, game):
        # Play a land if possible
        if self.can_play_land():
            land = self.find_land_in_hand()
            if land:
                self.play_land(land)
                game.logger.record(f"{self.name} plays {land.name}")
                self.game.gui.update_gui()

        # Tap lands to generate mana
        self.tap_available_lands()

        # Play spells based on strategy
        self.attempt_to_cast_spell(game)

    def can_play_land(self):
        # For simplicity, allow one land per turn
        return not getattr(self, 'land_played_this_turn', False)

    def play_land(self, land_card):
        self.hand.remove(land_card)
        self.battlefield.append(land_card)
        setattr(self, 'land_played_this_turn', True)
        land_card.zone = 'battlefield'

    def find_land_in_hand(self):
        for card in self.hand:
            if isinstance(card, LandCard):
                return card
        return None

    def tap_available_lands(self):
        for card in self.battlefield:
            if isinstance(card, LandCard) and not card.tap_status:
                card.tap_status = True
                self.mana_pool[card.mana_type] += 1

    def attempt_to_cast_spell(self, game):
        # Prioritize casting creatures
        for card in self.hand:
            if isinstance(card, CreatureCard) and self.can_play_card(card, game) and self.can_pay_mana_cost(card.mana_cost):
                self.play_card_from_hand(card, game)
                self.game.gui.update_gui()
                return
        # Cast other spells
        for card in self.hand:
            if self.can_play_card(card, game) and self.can_pay_mana_cost(card.mana_cost):
                self.play_card_from_hand(card, game)
                self.game.gui.update_gui()
                return

    def declare_attackers(self, game):
        # For simplicity, attack with all untapped creatures
        self.attackers = []
        for creature in self.battlefield:
            if isinstance(creature, CreatureCard) and not creature.tap_status and creature.can_attack():
                self.attackers.append(creature)
                creature.tap_status = True  # Tapped when declared as attacker
        game.logger.record(f"{self.name} declares attackers: {[creature.name for creature in self.attackers]}")

    def declare_blockers(self, game, attackers):
        # Simple blocking logic: block the first attacker with the first available blocker
        self.blockers = {}
        blockers_available = [creature for creature in self.battlefield if isinstance(creature, CreatureCard) and not creature.tap_status]
        for attacker in attackers:
            if blockers_available:
                blocker = blockers_available.pop(0)
                self.blockers[attacker] = blocker
                blocker.tap_status = True  # Tapped when declared as blocker
        game.logger.record(f"{self.name} declares blockers: {self.blockers}")

    def assign_combat_damage(self, game):
        # Simplified combat damage assignment
        opponent = game.get_opponent(self)
        for attacker in self.attackers:
            if attacker in opponent.blockers:
                blocker = opponent.blockers[attacker]
                # Simultaneous damage
                blocker.toughness -= attacker.power
                attacker.toughness -= blocker.power
            else:
                opponent.life_total -= attacker.power
                game.logger.record(f"{attacker.name} deals {attacker.power} damage to {opponent.name}")
        # Clear attackers and blockers
        self.attackers = []
        opponent.blockers = {}
