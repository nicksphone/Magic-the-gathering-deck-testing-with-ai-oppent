# mana_system.py (new)
from typing import Dict, List, Optional
from enum import Enum
from collections import defaultdict

class ManaType(Enum):
  WHITE = "W"
  BLUE = "U"
  BLACK = "B"
  RED = "R"
  GREEN = "G"
  COLORLESS = "C"
  GENERIC = "X"

class ManaPool:
  def __init__(self):
      self.pool = defaultdict(int)
      
  def add_mana(self, mana_type: ManaType, amount: int = 1):
      """Add mana to the pool"""
      self.pool[mana_type] += amount
      
  def remove_mana(self, mana_type: ManaType, amount: int = 1) -> bool:
      """Remove mana from the pool"""
      if self.pool[mana_type] >= amount:
          self.pool[mana_type] -= amount
          return True
      return False
      
  def clear(self):
      """Clear the mana pool"""
      self.pool.clear()
      
  def get_total(self) -> int:
      """Get total amount of mana in pool"""
      return sum(self.pool.values())
      
  def can_pay(self, cost: Dict[ManaType, int]) -> bool:
      """Check if the pool can pay a mana cost"""
      temp_pool = self.pool.copy()
      
      # First, pay colored costs
      for mana_type, amount in cost.items():
          if mana_type != ManaType.GENERIC:
              if temp_pool[mana_type] < amount:
                  return False
              temp_pool[mana_type] -= amount
              
      # Then, check if enough mana remains for generic costs
      if ManaType.GENERIC in cost:
          generic_cost = cost[ManaType.GENERIC]
          available_mana = sum(temp_pool.values())
          if available_mana < generic_cost:
              return False
              
      return True

class ManaCost:
  def __init__(self, cost_string: str):
      self.cost = self._parse_cost(cost_string)
      
  def _parse_cost(self, cost_string: str) -> Dict[ManaType, int]:
      """Parse a mana cost string into a dictionary"""
      cost = defaultdict(int)
      
      # Handle generic mana
      import re
      generic = re.findall(r'^\{(\d+)\}', cost_string)
      if generic:
          cost[ManaType.GENERIC] = int(generic[0])
          
      # Handle colored mana
      for symbol in ManaType:
          if symbol != ManaType.GENERIC:
              cost[symbol] = cost_string.count(f'{{{symbol.value}}}')
              
      return dict(cost)
      
  def get_cmc(self) -> int:
      """Get converted mana cost"""
      return sum(self.cost.values())
      
  def can_be_paid_with(self, mana_pool: ManaPool) -> bool:
      """Check if this cost can be paid with given mana pool"""
      return mana_pool.can_pay(self.cost)

class ManaAbility:
  def __init__(self, produces: Dict[ManaType, int], cost: Optional[Dict] = None):
      self.produces = produces
      self.cost = cost or {}
      
  def can_activate(self, source: 'Card') -> bool:
      """Check if the ability can be activated"""
      if 'tap' in self.cost and source.is_tapped:
          return False
      return True
      
  def activate(self, source: 'Card') -> bool:
      """Activate the mana ability"""
      if not self.can_activate(source):
          return False
          
      # Pay costs
      if 'tap' in self.cost:
          source.tap()
          
      # Add mana to controller's mana pool
      for mana_type, amount in self.produces.items():
          source.controller.mana_pool.add_mana(mana_type, amount)
          
      return True

class ManaManager:
  def __init__(self, game_state):
      self.game_state = game_state
      self.mana_abilities = {}
      
  def register_mana_ability(self, card: 'Card', ability: ManaAbility):
      """Register a mana ability for a card"""
      self.mana_abilities[card] = ability
      
  def activate_mana_ability(self, source: 'Card') -> bool:
      """Attempt to activate a card's mana ability"""
      if source in self.mana_abilities:
          ability = self.mana_abilities[source]
          return ability.activate(source)
      return False
      
  def auto_pay_mana(self, player: str, cost: ManaCost) -> bool:
      """Attempt to automatically pay a mana cost"""
      # Get all available mana sources
      available_sources = self._get_available_mana_sources(player)
      
      # Try to find a valid payment combination
      
