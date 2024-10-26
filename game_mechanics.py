from typing import List, Dict, Optional, Tuple
from enum import Enum
from card import Card

class Phase(Enum):
  UNTAP = "Untap"
  UPKEEP = "Upkeep"
  DRAW = "Draw"
  MAIN1 = "Main 1"
  COMBAT_BEGIN = "Beginning of Combat"
  COMBAT_DECLARE_ATTACKERS = "Declare Attackers"
  COMBAT_DECLARE_BLOCKERS = "Declare Blockers"
  COMBAT_DAMAGE = "Combat Damage"
  COMBAT_END = "End of Combat"
  MAIN2 = "Main 2"
  END = "End"
  CLEANUP = "Cleanup"

class GameState:
  def __init__(self):
      self.turn_number = 1
      self.current_phase = Phase.UNTAP
      self.active_player = 'player'
      self.priority_player = 'player'
      self.stack = []
      self.passed_priority = set()
      
      # Player states
      self.player_life = 20
      self.player_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      self.player_lands_played = 0
      
      # AI states
      self.ai_life = 20
      self.ai_mana_pool = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
      self.ai_lands_played = 0

class CombatResolver:
  @staticmethod
  def resolve_combat(attackers: List[Card], blockers: Dict[Card, List[Card]], 
                    game_state: GameState) -> Dict:
      """Resolve combat between attackers and blockers"""
      results = {
          'damage_to_player': 0,
          'damage_to_ai': 0,
          'creatures_killed': [],
          'creatures_damaged': {}
      }
      
      # Handle First Strike/Double Strike first
      CombatResolver._resolve_first_strike_damage(attackers, blockers, results)
      
      # Handle normal combat damage
      CombatResolver._resolve_normal_damage(attackers, blockers, results)
      
      return results

  @staticmethod
  def _resolve_first_strike_damage(attackers: List[Card], blockers: Dict[Card, List[Card]], 
                                 results: Dict):
      """Handle first strike and double strike damage"""
      for attacker in attackers:
          if 'First Strike' in attacker.abilities or 'Double Strike' in attacker.abilities:
              if attacker in blockers:
                  # Handle blocked creature with first/double strike
                  for blocker in blockers[attacker]:
                      CombatResolver._apply_combat_damage(attacker, blocker, results)
              else:
                  # Unblocked creature with first/double strike
                  results['damage_to_player'] += attacker.get_power()

  @staticmethod
  def _resolve_normal_damage(attackers: List[Card], blockers: Dict[Card, List[Card]], 
                           results: Dict):
      """Handle normal combat damage"""
      for attacker in attackers:
          # Skip if creature died to first strike
          if attacker in results['creatures_killed']:
              continue
              
          if attacker in blockers:
              # Handle blocked creatures
              for blocker in blockers[attacker]:
                  if blocker not in results['creatures_killed']:
                      CombatResolver._apply_combat_damage(attacker, blocker, results)
          else:
              # Handle unblocked creatures
              if 'First Strike' not in attacker.abilities:
                  results['damage_to_player'] += attacker.get_power()

  @staticmethod
  def _apply_combat_damage(attacker: Card, blocker: Card, results: Dict):
      """Apply combat damage between two creatures"""
      # Deal damage
      attacker_damage = attacker.get_power()
      blocker_damage = blocker.get_power()
      
      # Track damage dealt
      if attacker not in results['creatures_damaged']:
          results['creatures_damaged'][attacker] = 0
      if blocker not in results['creatures_damaged']:
          results['creatures_damaged'][blocker] = 0
          
      results['creatures_damaged'][attacker] += blocker_damage
      results['creatures_damaged'][blocker] += attacker_damage
      
      # Check for deaths
      if results['creatures_damaged'][attacker] >= attacker.get_toughness():
          results['creatures_killed'].append(attacker)
      if results['creatures_damaged'][blocker] >= blocker.get_toughness():
          results['creatures_killed'].append(blocker)

class ManaHandler:
  @staticmethod
  def can_pay_cost(mana_pool: Dict[str, int], mana_cost: str) -> bool:
      """Check if a mana cost can be paid from a mana pool"""
      required_mana = ManaHandler.parse_mana_cost(mana_cost)
      temp_pool = mana_pool.copy()
      
      # Check colored mana requirements
      for color in 'WUBRG':
          if required_mana[color] > temp_pool[color]:
              return False
          temp_pool[color] -= required_mana[color]
          
      # Check generic mana requirement
      total_available = sum(temp_pool.values())
      return total_available >= required_mana['C']

  @staticmethod
  def pay_mana_cost(mana_pool: Dict[str, int], mana_cost: str) -> bool:
      """Attempt to pay a mana cost from a mana pool"""
      if not ManaHandler.can_pay_cost(mana_pool, mana_cost):
          return False
          
      required_mana = ManaHandler.parse_mana_cost(mana_cost)
      
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

  @staticmethod
  def parse_mana_cost(mana_cost: str) -> Dict[str, int]:
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

class StackManager:
  def __init__(self):
      self.stack: List[Dict] = []
      
  def add_to_stack(self, spell_data: Dict):
      """Add a spell or ability to the stack"""
      self.stack.append(spell_data)
      
  def resolve_top(self) -> Optional[Dict]:
      """Resolve the top item of the stack"""
      if self.stack:
          return self.stack.pop()
      return None
      
  def is_empty(self) -> bool:
      """Check if the stack is empty"""
      return len(self.stack) == 0

class AbilityResolver:
  @staticmethod
  def resolve_ability(ability: str, source: Card, targets: List[Card], 
                     game_state: GameState) -> Dict:
      """Resolve a card ability"""
      results = {'success': True, 'effects': []}
      
      # Handle different ability types
      if 'Draw' in ability:
          count = int(ability.split()[1])
          results['effects'].append(('draw', count))
          
      elif 'Damage' in ability:
          damage = int(ability.split()[1])
          for target in targets:
              results['effects'].append(('damage', target, damage))
              
      elif 'Gain Life' in ability:
          life = int(ability.split()[2])
          results['effects'].append(('life_gain', life))
          
      elif 'Counter' in ability:
          if targets:
              results['effects'].append(('counter', targets[0]))
              
      return results

class TurnManager:
  def __init__(self, game_state: GameState):
      self.game_state = game_state
      self.phase_order = list(Phase)
      self.current_phase_index = 0
      
  def advance_phase(self) -> Phase:
      """Advance to the next phase"""
      self.current_phase_index = (self.current_phase_index + 1) % len(self.phase_order)
      new_phase = self.phase_order[self.current_phase_index]
      self.game_state.current_phase = new_phase
      
      if new_phase == Phase.UNTAP:
          self.game_state.turn_number += 1
          self.game_state.active_player = 'ai' if self.game_state.active_player == 'player' else 'player'
          
      return new_phase
      
  def handle_phase_actions(self) -> List[Dict]:
      """Handle automatic actions for the current phase"""
      phase = self.game_state.current_phase
      actions = []
      
      if phase == Phase.UNTAP:
          actions.append({'type': 'untap_all'})
          
      elif phase == Phase.UPKEEP:
          actions.append({'type': 'trigger_upkeep'})
          
      elif phase == Phase.DRAW:
          if self.game_state.turn_number > 1 or self.game_state.active_player == 'ai':
              actions.append({'type': 'draw_card'})
              
      elif phase == Phase.CLEANUP:
          actions.append({'type': 'cleanup'})
          
      return actions
