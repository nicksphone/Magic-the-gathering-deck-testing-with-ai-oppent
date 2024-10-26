# stack_manager.py (new)
from typing import List, Dict, Optional
from collections import deque
from enum import Enum

class Priority(Enum):
  ACTIVE_PLAYER = "active_player"
  NON_ACTIVE_PLAYER = "non_active_player"
  NONE = "none"

class StackObject:
  def __init__(self, source, effect, targets=None, controller=None):
      self.source = source
      self.effect = effect
      self.targets = targets or []
      self.controller = controller
      self.timestamp = 0

class StackManager:
  def __init__(self, game_state):
      self.game_state = game_state
      self.stack = deque()
      self.priority = Priority.NONE
      self.waiting_for_response = False
      self.passed_priority = set()
      
  def add_to_stack(self, stack_object: StackObject) -> bool:
      """Add an object to the stack"""
      if self._can_add_to_stack(stack_object):
          stack_object.timestamp = len(self.stack)
          self.stack.append(stack_object)
          self._grant_priority(stack_object.controller)
          return True
      return False
      
  def resolve_top(self) -> Optional[Dict]:
      """Resolve the top object of the stack"""
      if not self.stack:
          return None
          
      stack_object = self.stack.pop()
      
      # Check if targets are still legal
      if not self._verify_targets(stack_object):
          return {'result': 'fizzled', 'reason': 'illegal_targets'}
          
      # Resolve the effect
      try:
          result = stack_object.effect.effect_function(
              self.game_state,
              stack_object.source,
              stack_object.targets
          )
          return {'result': 'resolved', 'effect_result': result}
      except Exception as e:
          return {'result': 'failed', 'reason': str(e)}
          
  def pass_priority(self, player: str):
      """Handle a player passing priority"""
      self.passed_priority.add(player)
      
      if len(self.passed_priority) >= 2:
          # Both players passed priority
          if self.stack:
              # Resolve top of stack
              result = self.resolve_top()
              self.passed_priority.clear()
              self._grant_priority(self.game_state.active_player)
              return result
          else:
              # Move to next phase
              self.passed_priority.clear()
              self.priority = Priority.NONE
              return {'result': 'phase_end'}
      else:
          # Give priority to other player
          self._grant_priority_to_next_player()
          return {'result': 'priority_passed'}
          
  def _can_add_to_stack(self, stack_object: StackObject) -> bool:
      """Check if an object can be added to the stack"""
      if stack_object.effect.timing == EffectTiming.SORCERY:
          return (self.game_state.active_player == stack_object.controller and
                 not self.stack and
                 self.game_state.is_main_phase())
      return True
      
  def _verify_targets(self, stack_object: StackObject) -> bool:
      """Verify all targets are still legal"""
      if not stack_object.targets:
          return True
          
      for target in stack_object.targets:
          if not self._is_target_legal(target, stack_object):
              return False
      return True
      
  def _is_target_legal(self, target, stack_object: StackObject) -> bool:
      """Check if a target is still legal"""
      # Check if target still exists in appropriate zone
      if not self.game_state.object_exists(target):
          return False
          
      # Check if target still meets targeting restrictions
      if hasattr(stack_object.effect, 'targeting_restrictions'):
          if not self._meets_targeting_restrictions(target, 
                                                  stack_object.effect.targeting_restrictions):
              return False
              
      # Check for protection/shroud/hexproof
      if hasattr(target, 'has_protection_from'):
          if target.has_protection_from(stack_object.source):
              return False
              
      if hasattr(target, 'hexproof'):
          if target.controller != stack_object.controller:
              return False
              
      if hasattr(target, 'shroud'):
          return False
          
      return True
      
  def _grant_priority(self, player: str):
      """Grant priority to a player"""
      self.priority = Priority.ACTIVE_PLAYER if player == self.game_state.active_player \
                     else Priority.NON_ACTIVE_PLAYER
      self.passed_priority.clear()
      
  def _grant_priority_to_next_player(self):
      """Grant priority to the next player in turn order"""
      if self.priority == Priority.ACTIVE_PLAYER:
          self.priority = Priority.NON_ACTIVE_PLAYER
      else:
          self.priority = Priority.ACTIVE_PLAYER

# Created/Modified files during execution:
print("Created stack_manager.py")
