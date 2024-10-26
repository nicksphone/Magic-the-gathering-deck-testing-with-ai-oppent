# effects_system.py (new)
from typing import List, Dict, Optional, Callable
from enum import Enum
from dataclasses import dataclass

class EffectType(Enum):
  STATIC = "static"
  TRIGGERED = "triggered"
  ACTIVATED = "activated"
  REPLACEMENT = "replacement"
  ONE_SHOT = "one_shot"

class EffectTiming(Enum):
  INSTANT = "instant"
  SORCERY = "sorcery"
  SPECIAL = "special"

@dataclass
class Effect:
  type: EffectType
  timing: EffectTiming
  effect_function: Callable
  cost: Optional[Dict] = None
  conditions: Optional[List[Dict]] = None
  targets: Optional[List[Dict]] = None
  duration: Optional[str] = None

class AbilityManager:
  def __init__(self):
      self.registered_abilities = {}
      self.active_effects = []
      self.effect_timestamps = {}
      
  def register_ability(self, card_name: str, ability: Effect):
      """Register a card's ability"""
      if card_name not in self.registered_abilities:
          self.registered_abilities[card_name] = []
      self.registered_abilities[card_name].append(ability)
      
  def activate_ability(self, source: 'Card', ability: Effect, targets: List = None) -> bool:
      """Attempt to activate an ability"""
      if ability.type == EffectType.ACTIVATED:
          if self._can_activate_ability(source, ability):
              if self._pay_ability_costs(source, ability.cost):
                  self._add_to_stack(source, ability, targets)
                  return True
      return False
      
  def apply_static_effects(self, game_state):
      """Apply all static effects in correct layer order"""
      layers = self._get_effect_layers()
      for layer in layers:
          effects = self._get_effects_for_layer(layer)
          for effect in effects:
              if effect.type == EffectType.STATIC:
                  effect.effect_function(game_state)
                  
  def trigger_ability(self, trigger_event: Dict) -> List[Effect]:
      """Check and trigger relevant abilities"""
      triggered = []
      for effects in self.registered_abilities.values():
          for effect in effects:
              if effect.type == EffectType.TRIGGERED:
                  if self._check_trigger_conditions(effect, trigger_event):
                      triggered.append(effect)
      return triggered
      
  def _can_activate_ability(self, source: 'Card', ability: Effect) -> bool:
      """Check if an ability can be activated"""
      if ability.timing == EffectTiming.SORCERY:
          if not source.controller.can_cast_sorcery():
              return False
      return all(self._check_condition(cond) for cond in (ability.conditions or []))
      
  def _pay_ability_costs(self, source: 'Card', costs: Dict) -> bool:
      """Attempt to pay ability costs"""
      if not costs:
          return True
          
      # Create a cost payment transaction
      transaction = CostTransaction(source)
      
      for cost_type, cost_value in costs.items():
          if not transaction.can_pay_cost(cost_type, cost_value):
              transaction.rollback()
              return False
          transaction.pay_cost(cost_type, cost_value)
          
      transaction.commit()
      return True
      
  def _add_to_stack(self, source: 'Card', ability: Effect, targets: List):
      """Add ability to the stack"""
      stack_object = {
          'source': source,
          'ability': ability,
          'targets': targets,
          'timestamp': self._get_timestamp()
      }
      source.game_state.stack.append(stack_object)
      
  def _get_timestamp(self) -> int:
      """Get current timestamp for ordering effects"""
      return len(self.effect_timestamps)

class CostTransaction:
  def __init__(self, source: 'Card'):
      self.source = source
      self.paid_costs = []
      
  def can_pay_cost(self, cost_type: str, cost_value: any) -> bool:
      """Check if a cost can be paid"""
      if cost_type == 'mana':
          return self.source.controller.can_pay_mana(cost_value)
      elif cost_type == 'tap':
          return not self.source.is_tapped
      elif cost_type == 'sacrifice':
          return True  # Can always sacrifice if you control the permanent
      return False
      
  def pay_cost(self, cost_type: str, cost_value: any):
      """Pay a cost and record it"""
      if cost_type == 'mana':
          self.source.controller.pay_mana(cost_value)
      elif cost_type == 'tap':
          self.source.tap()
      elif cost_type == 'sacrifice':
          self.source.sacrifice()
      self.paid_costs.append((cost_type, cost_value))
      
  def rollback(self):
      """Rollback all paid costs"""
      for cost_type, cost_value in reversed(self.paid_costs):
          if cost_type == 'mana':
              self.source.controller.refund_mana(cost_value)
          elif cost_type == 'tap':
              self.source.untap()
          # Sacrifice cannot be rolled back
          
  def commit(self):
      """Commit the transaction"""
      self.paid_costs.clear()

# Created/Modified files during execution:
print("Created effects_system.py")
