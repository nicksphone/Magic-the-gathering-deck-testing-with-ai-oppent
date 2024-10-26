from typing import List, Dict, Optional, Set
from enum import Enum
from card import Card

class TargetType(Enum):
  PLAYER = "player"
  CREATURE = "creature"
  PERMANENT = "permanent"
  SPELL = "spell"
  ANY = "any"

class Target:
  def __init__(self, target_type: TargetType, restrictions: Dict = None):
      self.type = target_type
      self.restrictions = restrictions or {}
      self.selected_targets = []

class TargetingSystem:
  def __init__(self, game_state):
      self.game_state = game_state
      self.current_spell = None
      self.required_targets = []
      self.selected_targets = []
      
  def get_valid_targets(self, target_type: TargetType, restrictions: Dict) -> List:
      """Get all valid targets based on type and restrictions"""
      valid_targets = []
      
      if target_type == TargetType.PLAYER:
          valid_targets.extend(['player', 'ai'])
          
      elif target_type == TargetType.CREATURE:
          # Get all creatures from both battlefields
          creatures = (self.game_state.player_battlefield +
                     self.game_state.ai_battlefield)
          for creature in creatures:
              if creature.is_creature() and self.meets_restrictions(creature, restrictions):
                  valid_targets.append(creature)
                  
      elif target_type == TargetType.PERMANENT:
          # Get all permanents from both battlefields
          permanents = (self.game_state.player_battlefield +
                      self.game_state.ai_battlefield +
                      self.game_state.player_lands +
                      self.game_state.ai_lands)
          for permanent in permanents:
              if self.meets_restrictions(permanent, restrictions):
                  valid_targets.append(permanent)
                  
      elif target_type == TargetType.SPELL:
          # Get spells on the stack
          for spell in self.game_state.stack:
              if self.meets_restrictions(spell['card'], restrictions):
                  valid_targets.append(spell)
                  
      return valid_targets
      
  def meets_restrictions(self, obj: Card, restrictions: Dict) -> bool:
      """Check if an object meets targeting restrictions"""
      for key, value in restrictions.items():
          if key == 'color':
              if not hasattr(obj, 'colors') or value not in obj.colors:
                  return False
          elif key == 'type':
              if not hasattr(obj, 'type_line') or value not in obj.type_line:
                  return False
          elif key == 'power':
              if not hasattr(obj, 'power') or int(obj.power) != value:
                  return False
          elif key == 'toughness':
              if not hasattr(obj, 'toughness') or int(obj.toughness) != value:
                  return False
          elif key == 'controller':
              controller = self.get_controller(obj)
              if controller != value:
                  return False
                  
      return True
      
  def get_controller(self, obj: Card) -> str:
      """Determine who controls a given object"""
      if obj in self.game_state.player_battlefield or obj in self.game_state.player_lands:
          return 'player'
      elif obj in self.game_state.ai_battlefield or obj in self.game_state.ai_lands:
          return 'ai'
      return None
      
  def can_target(self, source: Card, target: Card) -> bool:
      """Check if a target is legal for a given source"""
      # Check for protection
      if hasattr(target, 'protection'):
          for protection in target.protection:
              if self.is_protected_from(target, source, protection):
                  return False
                  
      # Check for hexproof/shroud
      if hasattr(target, 'hexproof'):
          controller = self.get_controller(target)
          source_controller = self.get_controller(source)
          if controller != source_controller:
              return False
              
      if hasattr(target, 'shroud'):
          return False
          
      return True
      
  def is_protected_from(self, target: Card, source: Card, protection: str) -> bool:
      """Check if target is protected from source based on protection type"""
      if protection == 'color':
          return any(color in source.colors for color in target.protection['color'])
      elif protection == 'type':
          return any(type_line in source.type_line for type_line in target.protection['type'])
      return False
      
  def select_target(self, target) -> bool:
      """Add a target to the selected targets list"""
      if not self.current_spell:
          return False
          
      if len(self.selected_targets) >= len(self.required_targets):
          return False
          
      current_target_type = self.required_targets[len(self.selected_targets)].type
      current_restrictions = self.required_targets[len(self.selected_targets)].restrictions
      
      # Verify target is valid
      valid_targets = self.get_valid_targets(current_target_type, current_restrictions)
      if target not in valid_targets:
          return False
          
      # Check if target can be targeted
      if not self.can_target(self.current_spell, target):
          return False
          
      self.selected_targets.append(target)
      return True
      
  def start_targeting(self, spell: Card, required_targets: List[Target]):
      """Start the targeting process for a spell"""
      self.current_spell = spell
      self.required_targets = required_targets
      self.selected_targets = []
      
  def finish_targeting(self) -> bool:
      """Check if all required targets have been selected"""
      return len(self.selected_targets) == len(self.required_targets)
      
  def clear_targeting(self):
      """Reset targeting system"""
      self.current_spell = None
      self.required_targets = []
      self.selected_targets = []
      
  def get_targeting_requirements(self, card: Card) -> List[Target]:
      """Parse a card's oracle text to determine targeting requirements"""
      requirements = []
      if not hasattr(card, 'oracle_text'):
          return requirements
          
      text = card.oracle_text.lower()
      
      # Parse "target creature" patterns
      if 'target creature' in text:
          requirements.append(Target(TargetType.CREATURE))
          
      # Parse "target player" patterns
      if 'target player' in text:
          requirements.append(Target(TargetType.PLAYER))
          
      # Parse "target permanent" patterns
      if 'target permanent' in text:
          requirements.append(Target(TargetType.PERMANENT))
          
      # Parse "target spell" patterns
      if 'target spell' in text:
          requirements.append(Target(TargetType.SPELL))
          
      # Parse more complex targeting requirements
      if 'target creature with power' in text:
          power = int(text.split('power')[1].split()[0])
          requirements.append(Target(TargetType.CREATURE, {'power': power}))
          
      return requirements
