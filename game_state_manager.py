from typing import List, Dict, Optional, Set
from enum import Enum
from card import Card

class GamePhase(Enum):
  BEGIN = "Beginning Phase"
  UNTAP = "Untap Step"
  UPKEEP = "Upkeep Step"
  DRAW = "Draw Step"
  MAIN1 = "First Main Phase"
  COMBAT_BEGIN = "Beginning of Combat"
  COMBAT_DECLARE_ATTACKERS = "Declare Attackers"
  COMBAT_DECLARE_BLOCKERS = "Declare Blockers"
  COMBAT_DAMAGE = "Combat Damage"
  COMBAT_END = "End of Combat"
  MAIN2 = "Second Main Phase"
  END = "End Phase"
  CLEANUP = "Cleanup Step"

class GameStateManager:
  def __init__(self):
      self.current_phase = GamePhase.BEGIN
      self.turn_number = 1
      self.active_player = 'player'
      self.priority_player = 'player'
      
      # Game zones
      self.zones = {
          'player_library': [],
          'player_hand': [],
          'player_battlefield': [],
          'player_graveyard': [],
          'player_exile': [],
          'ai_library': [],
          'ai_hand': [],
          'ai_battlefield': [],
          'ai_graveyard': [],
          'ai_exile': []
      }
      
      # Game state tracking
      self.life_totals = {'player': 20, 'ai': 20}
      self.mana_pools = {
          'player': {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0},
          'ai': {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      }
      
      # Turn tracking
      self.lands_played = {'player': 0, 'ai': 0}
      self.spells_cast = {'player': 0, 'ai': 0}
      
      # Combat tracking
      self.attackers = []
      self.blockers = {}
      self.damage_assignment = {}
      
      # Stack and priority
      self.stack = []
      self.passed_priority = set()

  def initialize_game(self, player_deck: List[Card], ai_deck: List[Card]):
      """Initialize the game state with decks"""
      self.zones['player_library'] = player_deck.copy()
      self.zones['ai_library'] = ai_deck.copy()
      self.draw_opening_hands()

  def draw_opening_hands(self):
      """Draw opening hands for both players"""
      for _ in range(7):
          self.draw_card('player')
          self.draw_card('ai')

  def draw_card(self, player: str) -> Optional[Card]:
      """Draw a card from library to hand"""
      library = self.zones[f'{player}_library']
      if not library:
          return None
          
      card = library.pop(0)
      self.zones[f'{player}_hand'].append(card)
      return card

  def advance_phase(self) -> GamePhase:
      """Advance to the next phase"""
      phase_order = list(GamePhase)
      current_index = phase_order.index(self.current_phase)
      self.current_phase = phase_order[(current_index + 1) % len(phase_order)]
      
      # Reset priority when changing phases
      self.priority_player = self.active_player
      self.passed_priority.clear()
      
      # Handle phase-specific actions
      self.handle_phase_begin()
      
      return self.current_phase

  def handle_phase_begin(self):
      """Handle automatic actions at the beginning of each phase"""
      if self.current_phase == GamePhase.UNTAP:
          self.handle_untap_step()
      elif self.current_phase == GamePhase.UPKEEP:
          self.handle_upkeep_step()
      elif self.current_phase == GamePhase.DRAW:
          self.handle_draw_step()
      elif self.current_phase == GamePhase.CLEANUP:
          self.handle_cleanup_step()

  def handle_untap_step(self):
      """Handle untap step actions"""
      battlefield = self.zones[f'{self.active_player}_battlefield']
      for permanent in battlefield:
          permanent.untap()
          if permanent.is_creature():
              permanent.summoning_sickness = False

  def handle_upkeep_step(self):
      """Handle upkeep triggers"""
      battlefield = self.zones[f'{self.active_player}_battlefield']
      for permanent in battlefield:
          if hasattr(permanent, 'upkeep_trigger'):
              self.add_trigger_to_stack(permanent.upkeep_trigger)

  def handle_draw_step(self):
      """Handle draw step"""
      if self.turn_number > 1 or self.active_player == 'ai':
          self.draw_card(self.active_player)

  def handle_cleanup_step(self):
      """Handle cleanup step"""
      # Discard down to maximum hand size
      hand = self.zones[f'{self.active_player}_hand']
      while len(hand) > 7:
          self.discard_card(self.active_player)
          
      # Remove all damage from creatures
      battlefield = self.zones[f'{self.active_player}_battlefield']
      for permanent in battlefield:
          if permanent.is_creature():
              permanent.damage_marked = 0
              
      # End "until end of turn" effects
      self.remove_end_of_turn_effects()

  def can_play_land(self, player: str) -> bool:
      """Check if a player can play a land"""
      return (self.current_phase in [GamePhase.MAIN1, GamePhase.MAIN2] and
              self.lands_played[player] < 1 and
              player == self.active_player)

  def play_land(self, player: str, land: Card) -> bool:
      """Attempt to play a land"""
      if not self.can_play_land(player):
          return False
          
      hand = self.zones[f'{player}_hand']
      battlefield = self.zones[f'{player}_battlefield']
      
      if land in hand and land.is_land():
          hand.remove(land)
          battlefield.append(land)
          self.lands_played[player] += 1
          return True
          
      return False

  def can_cast_spell(self, player: str, spell: Card) -> bool:
      """Check if a spell can be cast"""
      # Check timing restrictions
      if spell.is_sorcery():
          if (self.current_phase not in [GamePhase.MAIN1, GamePhase.MAIN2] or
              self.stack or
              player != self.active_player):
              return False
              
      # Check if player has priority
      if self.priority_player != player:
          return False
          
      # Check if player has enough mana
      return self.has_enough_mana(player, spell.mana_cost)

  def cast_spell(self, player: str, spell: Card) -> bool:
      """Attempt to cast a spell"""
      if not self.can_cast_spell(player, spell):
          return False
          
      # Pay mana cost
      if not self.pay_mana_cost(player, spell.mana_cost):
          return False
          
      # Move spell to stack
      hand = self.zones[f'{player}_hand']
      if spell in hand:
          hand.remove(spell)
          self.stack.append({
              'spell': spell,
              'controller': player,
              'targets': []  # Add targeting logic as needed
          })
          return True
          
      return False

  def resolve_stack(self):
      """Resolve the top item of the stack"""
      if not self.stack:
          return
          
      item = self.stack.pop()
      spell = item['spell']
      controller = item['controller']
      
      if spell.is_creature():
          # Put creature onto battlefield
          battlefield = self.zones[f'{controller}_battlefield']
          battlefield.append(spell)
          spell.summoning_sickness = True
      else:
          # Handle instant/sorcery effects
          self.resolve_spell_effects(spell, controller)
          # Move to graveyard
          graveyard = self.zones[f'{controller}_graveyard']
          graveyard.append(spell)

  def has_enough_mana(self, player: str, mana_cost: str) -> bool:
      """Check if a player has enough mana to pay a cost"""
      required_mana = self.parse_mana_cost(mana_cost)
      mana_pool = self.mana_pools[player]
      
      # Check colored mana requirements
      for color in 'WUBRG':
          if required_mana[color] > mana_pool[color]:
              return False
              
      # Check generic mana requirement
      total_available = sum(mana_pool.values())
      return total_available >= required_mana['C']

  def pay_mana_cost(self, player: str, mana_cost: str) -> bool:
      """Attempt to pay a mana cost"""
      if not self.has_enough_mana(player, mana_cost):
          return False
          
      required_mana = self.parse_mana_cost(mana_cost)
      mana_pool = self.mana_pools[player]
      
      # Pay colored costs
      for color in 'WUBRG':
          mana_pool[color] -= required_mana[color]
          
      # Pay generic costs
      remaining = required_mana['C']
      for color in 'CWUBRG':
          while remaining > 0 and mana_pool[color] > 0:
              mana_pool[color] -= 1
              remaining -= 1
              
      return True

  def parse_mana_cost(self, mana_cost: str) -> Dict[str, int]:
      """Parse a mana cost string into a dictionary"""
      result = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      
      if not mana_cost:
          return result
          
      # Handle generic mana
      import re
      generic = re.findall(r'\{(\d+)\}', mana_cost)
      if generic:
          result['C'] = sum(int(x) for x in generic)
          
      # Handle colored mana
      for color in 'WUBRG':
          result[color] = mana_cost.count('{' + color + '}')
          
      return result

  def check_state_based_actions(self) -> List[Dict]:
      """Check and apply state-based actions"""
      actions = []
      
      # Check all permanents on battlefield
      for player in ['player', 'ai']:
          battlefield = self.zones[f'{player}_battlefield']
          for permanent in battlefield[:]:  # Create a copy to modify during iteration
              if permanent.is_creature():
                  # Check for lethal damage
                  if permanent.damage_marked >= permanent.get_toughness():
                      battlefield.remove(permanent)
                      self.zones[f'{player}_graveyard'].append(permanent)
                      actions.append({
                          'action': 'destroy',
                          'permanent': permanent,
                          'reason': 'lethal_damage'
                      })
                  # Check for zero toughness
                  elif permanent.get_toughness() <= 0:
                      battlefield.remove(permanent)
                      self.zones[f'{player}_graveyard'].append(permanent)
                      actions.append({
                          'action': 'destroy',
                          'permanent': permanent,
                          'reason': 'zero_toughness'
                      })
                      
      # Check player life totals
      for player in ['player', 'ai']:
          if self.life_totals[player] <= 0:
              actions.append({
                  'action': 'game_loss',
                  'player': player,
                  'reason': 'zero_life'
              })
              
      return actions

  def handle_combat(self) -> Dict:
      """Handle the combat phase"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'life_total_changes': {'player': 0, 'ai': 0}
      }
      
      # Handle combat damage
      for attacker in self.attackers:
          if attacker in self.blockers:
              # Handle blocked creatures
              blockers = self.blockers[attacker]
              self.resolve_combat_damage(attacker, blockers, results)
          else:
              # Handle unblocked creatures
              defender = 'ai' if self.active_player == 'player' else 'player'
              damage = attacker.get_power()
              results['life_total_changes'][defender] -= damage
              
      # Apply results
      for player, life_change in results['life_total_changes'].items():
          self.life_totals[player] += life_change
          
      # Move dead creatures to graveyard
      for creature in results['creatures_killed']:
          owner = 'player' if creature in self.zones['player_battlefield'] else 'ai'
          self.zones[f'{owner}_battlefield'].remove(creature)
          self.zones[f'{owner}_graveyard'].append(creature)
          
      return results

  def resolve_combat_damage(self, attacker: Card, blockers: List[Card], results: Dict):
      """Resolve combat damage between an attacker and its blockers"""
      # Calculate total blocking damage
      blocking_damage = sum(blocker.get_power() for blocker in blockers)
      
      # Deal damage to blockers
      attacker_damage = attacker.get_power()
      for blocker in blockers:
          damage_to_blocker = min(attacker_damage, blocker.get_toughness())
          results['damage_dealt'][blocker] = damage_to_blocker
          if damage_to_blocker >= blocker.get_toughness():
              results['creatures_killed'].append(blocker)
          attacker_damage -= damage_to_blocker
          
      # Deal damage to attacker
      if blocking_damage >= attacker.get_toughness():
          results['creatures_killed'].append(attacker)

  def remove_end_of_turn_effects(self):
      """Remove all "until end of turn" effects"""
      for player in ['player', 'ai']:
          battlefield = self.zones[f'{player}_battlefield']
          for permanent in battlefield:
              if hasattr(permanent, 'end_of_turn_effects'):
                  permanent.end_of_turn_effects.clear()
