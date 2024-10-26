# combat_manager.py (updated)
from typing import List, Dict, Optional
from card import Card

class CombatManager:
  def __init__(self, game_state):
      self.game_state = game_state
      self.attackers = []
      self.blockers = {}
      self.damage_assignment_order = {}
      self.combat_triggers = []
      
  def declare_attacker(self, attacker: Card, target: str) -> bool:
      """Declare a creature as an attacker"""
      if self.can_attack(attacker):
          self.attackers.append({
              'creature': attacker,
              'target': target
          })
          attacker.tap()
          self._handle_attack_triggers(attacker)
          return True
      return False
      
  def declare_blocker(self, blocker: Card, attacker: Card) -> bool:
      """Declare a creature as a blocker"""
      if self.can_block(blocker, attacker):
          if attacker not in self.blockers:
              self.blockers[attacker] = []
          self.blockers[attacker].append(blocker)
          self._handle_block_triggers(blocker, attacker)
          return True
      return False
      
  def resolve_combat_phase(self) -> Dict:
      """Resolve the entire combat phase"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'life_total_changes': {},
          'triggers': []
      }
      
      # First strike damage
      first_strike_results = self._handle_first_strike_damage()
      results = self._merge_combat_results(results, first_strike_results)
      
      # Regular combat damage
      regular_damage_results = self._handle_regular_damage()
      results = self._merge_combat_results(results, regular_damage_results)
      
      # Handle end of combat triggers
      results['triggers'].extend(self._handle_end_of_combat_triggers())
      
      return results
      
  def _handle_first_strike_damage(self) -> Dict:
      """Handle first strike and double strike damage"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'life_total_changes': {},
          'triggers': []
      }
      
      first_strikers = [a for a in self.attackers 
                       if ('First Strike' in a['creature'].abilities or 
                           'Double Strike' in a['creature'].abilities)]
                           
      for attacker in first_strikers:
          damage_result = self._resolve_creature_combat(attacker['creature'], 
                                                      attacker['target'])
          results = self._merge_combat_results(results, damage_result)
          
      return results
      
  def _handle_regular_damage(self) -> Dict:
      """Handle regular combat damage"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'life_total_changes': {},
          'triggers': []
      }
      
      # Get all attackers that either don't have first strike or have double strike
      regular_attackers = [a for a in self.attackers 
                         if 'First Strike' not in a['creature'].abilities or 
                            'Double Strike' in a['creature'].abilities]
                            
      for attacker in regular_attackers:
          damage_result = self._resolve_creature_combat(attacker['creature'], 
                                                      attacker['target'])
          results = self._merge_combat_results(results, damage_result)
          
      return results
      
  def _resolve_creature_combat(self, attacker: Card, target: str) -> Dict:
      """Resolve combat for a single attacking creature"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'life_total_changes': {},
          'triggers': []
      }
      
      # Handle blocked creature
      if attacker in self.blockers:
          blocker_results = self._handle_blocked_creature(attacker, self.blockers[attacker])
          results = self._merge_combat_results(results, blocker_results)
      else:
          # Handle unblocked creature
          damage = attacker.get_power()
          if target == 'player':
              self.game_state.player_life -= damage
              results['life_total_changes']['player'] = -damage
          else:
              self.game_state.ai_life -= damage
              results['life_total_changes']['ai'] = -damage
              
      return results
      
  def _handle_blocked_creature(self, attacker: Card, blockers: List[Card]) -> Dict:
      """Handle combat damage for a blocked creature"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'triggers': []
      }
      
      # Get damage assignment order
      ordered_blockers = self.damage_assignment_order.get(attacker, blockers)
      
      # Assign attacker's damage to blockers
      remaining_damage = attacker.get_power()
      for blocker in ordered_blockers:
          if remaining_damage <= 0:
              break
              
          damage_to_assign = min(remaining_damage, 
                               self._calculate_lethal_damage(blocker))
          results['damage_dealt'][blocker] = damage_to_assign
          
          if damage_to_assign >= blocker.get_toughness():
              results['creatures_killed'].append(blocker)
              
          remaining_damage -= damage_to_assign
          
      # Assign blocker damage to attacker
      total_blocker_damage = sum(b.get_power() for b in blockers)
      results['damage_dealt'][attacker] = total_blocker_damage
      
      if total_blocker_damage >= attacker.get_toughness():
          results['creatures_killed'].append(attacker)
          
      return results
      
  def _merge_combat_results(self, results1: Dict, results2: Dict) -> Dict:
      """Merge two combat results dictionaries"""
      merged = {
          'damage_dealt': {**results1['damage_dealt'], **results2['damage_dealt']},
          'creatures_killed': results1['creatures_killed'] + results2['creatures_killed'],
          'life_total_changes': {**results1['life_total_changes'], 
                               **results2['life_total_changes']},
          'triggers': results1['triggers'] + results2['triggers']
      }
      return merged

# Created/Modified files during execution:
print("Updated combat_manager.py")
