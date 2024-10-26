from typing import List, Dict, Optional
from card import Card

class AIPlayer:
  def __init__(self, deck: List[Card]):
      self.deck = deck
      self.hand = []
      self.battlefield = []
      self.graveyard = []
      self.life_total = 20
      self.lands_played_this_turn = 0
      self.mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      self.strategy = self.determine_strategy()

  def determine_strategy(self) -> str:
      """Analyze deck composition to determine optimal strategy"""
      creature_count = sum(1 for card in self.deck if card.is_creature())
      instant_count = sum(1 for card in self.deck if card.is_instant())
      sorcery_count = sum(1 for card in self.deck if card.is_sorcery())
      
      # Calculate average converted mana cost
      avg_cmc = sum(card.get_cmc() for card in self.deck) / len(self.deck)
      
      if avg_cmc < 3 and creature_count > 20:
          return 'aggressive'
      elif instant_count + sorcery_count > 15:
          return 'control'
      else:
          return 'midrange'

  def take_turn(self, game_state):
      """Execute AI turn"""
      # Untap Phase
      self.untap_step()
      
      # Upkeep Phase
      self.upkeep_step()
      
      # Draw Phase
      self.draw_step()
      
      # First Main Phase
      self.main_phase_one(game_state)
      
      # Combat Phase
      self.combat_phase(game_state)
      
      # Second Main Phase
      self.main_phase_two(game_state)
      
      # End Phase
      self.end_step()

  def untap_step(self):
      """Untap all permanents"""
      for permanent in self.battlefield:
          permanent.untap()
          if permanent.is_creature():
              permanent.summoning_sickness = False

  def upkeep_step(self):
      """Handle upkeep triggers"""
      for permanent in self.battlefield:
          if hasattr(permanent, 'upkeep_trigger'):
              permanent.upkeep_trigger(self)

  def draw_step(self):
      """Draw a card"""
      if self.deck:
          self.hand.append(self.deck.pop(0))

  def main_phase_one(self, game_state):
      """Execute first main phase"""
      # Play land if available
      self.play_land()
      
      # Generate mana
      self.tap_lands_for_mana()
      
      # Play spells based on strategy
      playable_cards = self.get_playable_cards()
      
      if self.strategy == 'aggressive':
          self.play_aggressive_spells(playable_cards, game_state)
      elif self.strategy == 'control':
          self.play_control_spells(playable_cards, game_state)
      else:
          self.play_midrange_spells(playable_cards, game_state)

  def play_land(self):
      """Play a land if possible"""
      if self.lands_played_this_turn == 0:
          for card in self.hand:
              if card.is_land():
                  self.hand.remove(card)
                  self.battlefield.append(card)
                  self.lands_played_this_turn = 1
                  break

  def tap_lands_for_mana(self):
      """Generate mana from lands"""
      self.mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      for permanent in self.battlefield:
          if permanent.is_land() and not permanent.is_tapped:
              permanent.tap()
              mana_types = permanent.get_mana_types()
              for mana_type in mana_types:
                  self.mana_pool[mana_type] += 1

  def get_playable_cards(self) -> List[Card]:
      """Return list of cards that can be played with current mana"""
      return [card for card in self.hand 
              if not card.is_land() and self.can_pay_mana_cost(card.mana_cost)]

  def play_aggressive_spells(self, playable_cards: List[Card], game_state):
      """Play creatures and combat tricks"""
      # Sort creatures by power/cost ratio
      creatures = [c for c in playable_cards if c.is_creature()]
      creatures.sort(key=lambda x: x.get_power() / x.get_cmc() if x.get_cmc() > 0 else float('inf'),
                    reverse=True)
      
      for creature in creatures:
          if self.can_pay_mana_cost(creature.mana_cost):
              self.cast_spell(creature)

  def play_control_spells(self, playable_cards: List[Card], game_state):
      """Play removal and counterspells"""
      threats = self.evaluate_threats(game_state)
      
      for card in playable_cards:
          if self.is_removal_spell(card) and threats:
              self.cast_spell(card, target=threats[0])
          elif self.is_counter_spell(card):
              # Save counter for opponent's turn
              continue

  def play_midrange_spells(self, playable_cards: List[Card], game_state):
      """Balance between creatures and spells"""
      # Play efficient creatures first
      creatures = [c for c in playable_cards if c.is_creature()]
      for creature in creatures:
          if self.can_pay_mana_cost(creature.mana_cost):
              self.cast_spell(creature)
      
      # Then play removal if needed
      removal = [c for c in playable_cards if self.is_removal_spell(c)]
      if removal and self.evaluate_threats(game_state):
          self.cast_spell(removal[0])

  def combat_phase(self, game_state):
      """Handle combat"""
      attackers = self.choose_attackers(game_state)
      if attackers:
          blocks = game_state.get('blocks', {})
          self.resolve_combat(attackers, blocks)

  def choose_attackers(self, game_state) -> List[Card]:
      """Decide which creatures should attack"""
      potential_attackers = [c for c in self.battlefield 
                           if c.is_creature() and not c.is_tapped 
                           and not c.summoning_sickness]
      
      attackers = []
      opponent_blockers = game_state.get('opponent_creatures', [])
      
      for attacker in potential_attackers:
          if self.should_attack(attacker, opponent_blockers, game_state):
              attackers.append(attacker)
              
      return attackers

  def should_attack(self, attacker: Card, opponent_blockers: List[Card], game_state) -> bool:
      """Determine if a creature should attack"""
      if self.strategy == 'aggressive':
          return True
          
      # Check for unfavorable blocks
      for blocker in opponent_blockers:
          if blocker.get_power() >= attacker.get_toughness() and \
             blocker.get_toughness() > attacker.get_power():
              return False
              
      return True

  def main_phase_two(self, game_state):
      """Execute second main phase"""
      playable_cards = self.get_playable_cards()
      
      if self.strategy == 'control':
          self.play_control_spells(playable_cards, game_state)
      else:
          self.play_remaining_spells(playable_cards)

  def end_step(self):
      """Handle end step and cleanup"""
      self.lands_played_this_turn = 0
      self.mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      
      # Discard down to maximum hand size
      while len(self.hand) > 7:
          self.discard_worst_card()

  def cast_spell(self, card: Card, target=None):
      """Cast a spell and handle its effects"""
      if self.can_pay_mana_cost(card.mana_cost):
          self.pay_mana_cost(card.mana_cost)
          self.hand.remove(card)
          
          if card.is_creature():
              card.summoning_sickness = True
              self.battlefield.append(card)
          elif card.is_instant() or card.is_sorcery():
              self.resolve_spell_effects(card, target)
              self.graveyard.append(card)

  def resolve_spell_effects(self, card: Card, target=None):
      """Handle spell effects"""
      if self.is_removal_spell(card):
          if target and target in self.battlefield:
              self.battlefield.remove(target)
              self.graveyard.append(target)

  def evaluate_threats(self, game_state) -> List[Card]:
      """Evaluate opponent's threats"""
      threats = []
      opponent_creatures = game_state.get('opponent_creatures', [])
      
      for creature in opponent_creatures:
          threat_level = self.calculate_threat_level(creature)
          if threat_level > 0:
              threats.append((creature, threat_level))
              
      threats.sort(key=lambda x: x[1], reverse=True)
      return [threat[0] for threat in threats]

  def calculate_threat_level(self, card: Card) -> float:
      """Calculate threat level of a card"""
      threat_level = 0
      
      if card.is_creature():
          threat_level += card.get_power()
          if hasattr(card, 'abilities'):
              threat_level += len(card.abilities) * 0.5
              
      return threat_level

  def is_removal_spell(self, card: Card) -> bool:
      """Check if a card is a removal spell"""
      if not hasattr(card, 'oracle_text'):
          return False
          
      removal_keywords = ['destroy', 'exile', 'damage', '-', 'sacrifice']
      return any(keyword in card.oracle_text.lower() for keyword in removal_keywords)

  def is_counter_spell(self, card: Card) -> bool:
      """Check if a card is a counterspell"""
      if not hasattr(card, 'oracle_text'):
          return False
          
      counter_keywords = ['counter target spell']
      return any(keyword in card.oracle_text.lower() for keyword in counter_keywords)

  def can_pay_mana_cost(self, mana_cost: str) -> bool:
      """Check if AI can pay the mana cost"""
      required_mana = self.parse_mana_cost(mana_cost)
      temp_pool = self.mana_pool.copy()
      
      # Check colored mana requirements
      for color in 'WUBRG':
          if required_mana[color] > temp_pool[color]:
              return False
          temp_pool[color] -= required_mana[color]
          
      # Check if enough mana remains for generic costs
      total_remaining = sum(temp_pool.values())
      return total_remaining >= required_mana['C']

  def parse_mana_cost(self, mana_cost: str) -> Dict[str, int]:
      """Parse mana cost string into dictionary"""
      cost = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      if not mana_cost:
          return cost
          
      # Handle generic mana
      generic = ''.join(filter(str.isdigit, mana_cost))
      if generic:
          cost['C'] = int(generic)
          
      # Handle colored mana
      for color in 'WUBRG':
          cost[color] = mana_cost.count('{' + color + '}')
          
      return cost

  def pay_mana_cost(self, mana_cost: str):
      """Pay the mana cost from the mana pool"""
      required_mana = self.parse_mana_cost(mana_cost)
      
      # Pay colored costs first
      for color in 'WUBRG':
          self.mana_pool[color] -= required_mana[color]
          
      # Pay generic costs from remaining mana
      remaining_generic = required_mana['C']
      for color in 'CWUBRG':  # Start with colorless
          while remaining_generic > 0 and self.mana_pool[color] > 0:
              self.mana_pool[color] -= 1
              remaining_generic -= 1
