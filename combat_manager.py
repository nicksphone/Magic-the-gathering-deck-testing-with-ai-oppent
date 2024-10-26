from typing import List, Dict, Optional
from card import Card

class CombatManager:
  def __init__(self):
      self.attackers = []
      self.blockers = {}
      self.damage_assignment = {}
      self.first_strike_damage = {}
      self.regular_damage = {}

  def declare_attacker(self, creature: Card) -> bool:
      """Declare a creature as an attacker"""
      if self.can_attack(creature):
          self.attackers.append(creature)
          creature.tap()
          return True
      return False

  def can_attack(self, creature: Card) -> bool:
      """Check if a creature can attack"""
      return (not creature.is_tapped and 
              not creature.summoning_sickness and 
              not creature.has_defender())

  def declare_blocker(self, blocker: Card, attacker: Card) -> bool:
      """Declare a creature as a blocker"""
      if self.can_block(blocker, attacker):
          if attacker not in self.blockers:
              self.blockers[attacker] = []
          self.blockers[attacker].append(blocker)
          return True
      return False

  def can_block(self, blocker: Card, attacker: Card) -> bool:
      """Check if a creature can block another creature"""
      if blocker.is_tapped:
          return False

      # Handle flying
      if "Flying" in attacker.abilities:
          if "Flying" not in blocker.abilities and "Reach" not in blocker.abilities:
              return False

      # Handle other evasion abilities
      if "Fear" in attacker.abilities:
          if "Artifact" not in blocker.type_line and "Black" not in blocker.colors:
              return False

      if "Shadow" in attacker.abilities:
          if "Shadow" not in blocker.abilities:
              return False

      return True

  def resolve_combat(self) -> Dict:
      """Resolve combat damage"""
      results = {
          'damage_dealt': {},
          'creatures_killed': [],
          'player_damage': 0,
          'opponent_damage': 0
      }

      # Handle first strike/double strike damage
      self.resolve_first_strike_damage(results)
      
      # Handle regular damage
      self.resolve_regular_damage(results)

      return results

  def resolve_first_strike_damage(self, results: Dict):
      """Handle first strike and double strike damage"""
      for attacker in self.attackers:
          if ("First Strike" in attacker.abilities or 
              "Double Strike" in attacker.abilities):
              if attacker in self.blockers:
                  # Handle blocked creature with first strike
                  for blocker in self.blockers[attacker]:
                      self.apply_combat_damage(attacker, blocker, results)
              else:
                  # Unblocked creature with first strike
                  results['opponent_damage'] += attacker.get_power()

  def resolve_regular_damage(self, results: Dict):
      """Handle regular combat damage"""
      for attacker in self.attackers:
          # Skip if creature died to first strike
          if attacker in results['creatures_killed']:
              continue

          if attacker in self.blockers:
              # Handle blocked creatures
              for blocker in self.blockers[attacker]:
                  if blocker not in results['creatures_killed']:
                      self.apply_combat_damage(attacker, blocker, results)
          else:
              # Handle unblocked creatures
              if ("First Strike" not in attacker.abilities and 
                  "Double Strike" not in attacker.abilities):
                  results['opponent_damage'] += attacker.get_power()

  def apply_combat_damage(self, attacker: Card, blocker: Card, results: Dict):
      """Apply combat damage between creatures"""
      # Deal damage
      attacker_damage = attacker.get_power()
      blocker_damage = blocker.get_power()

      # Track damage dealt
      if attacker not in results['damage_dealt']:
          results['damage_dealt'][attacker] = 0
      if blocker not in results['damage_dealt']:
          results['damage_dealt'][blocker] = 0

      results['damage_dealt'][attacker] += blocker_damage
      results['damage_dealt'][blocker] += attacker_damage

      # Check for deaths
      if results['damage_dealt'][attacker] >= attacker.get_toughness():
          if attacker not in results['creatures_killed']:
              results['creatures_killed'].append(attacker)

      if results['damage_dealt'][blocker] >= blocker.get_toughness():
          if blocker not in results['creatures_killed']:
              results['creatures_killed'].append(blocker)

  def handle_combat_triggers(self, phase: str) -> List[Dict]:
      """Handle combat-related triggers"""
      triggers = []
      
      if phase == 'begin_combat':
          for attacker in self.attackers:
              if hasattr(attacker, 'combat_triggers'):
                  triggers.extend(attacker.combat_triggers('begin_combat'))
                  
      elif phase == 'declare_attackers':
          for attacker in self.attackers:
              if hasattr(attacker, 'combat_triggers'):
                  triggers.extend(attacker.combat_triggers('attack'))
                  
      elif phase == 'declare_blockers':
          for blockers_list in self.blockers.values():
              for blocker in blockers_list:
                  if hasattr(blocker, 'combat_triggers'):
                      triggers.extend(blocker.combat_triggers('block'))
                      
      return triggers

  def check_combat_requirements(self) -> List[str]:
      """Check if all combat requirements are met"""
      errors = []
      
      # Check if creatures that must attack are attacking
      for creature in self.potential_attackers:
          if "Must attack" in creature.abilities and creature not in self.attackers:
              errors.append(f"{creature.name} must attack if able")
              
      # Check if enough blockers are declared
      for creature in self.potential_blockers:
          if "Must block" in creature.abilities:
              if not any(creature in blockers for blockers in self.blockers.values()):
                  errors.append(f"{creature.name} must block if able")
                  
      return errors

  def validate_combat_step(self) -> bool:
      """Validate the current combat step"""
      errors = self.check_combat_requirements()
      return len(errors) == 0

  def reset_combat(self):
      """Reset combat state for next combat phase"""
      self.attackers = []
      self.blockers = {}
      self.damage_assignment = {}
      self.first_strike_damage = {}
      self.regular_damage = {}
