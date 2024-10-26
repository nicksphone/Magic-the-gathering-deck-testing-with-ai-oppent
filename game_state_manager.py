# game_state_manager.py
import json
from typing import Dict, List
from card import Card
from mana_system import ManaPool
from game_rules_engine import GamePhase

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
          'player': ManaPool(),
          'ai': ManaPool()
      }
      
      # Turn tracking
      self.lands_played = {'player': 0, 'ai': 0}
      self.spells_cast = {'player': 0, 'ai': 0}
      
  def serialize(self) -> str:
      """Serialize the game state to a JSON string"""
      state = {
          'current_phase': self.current_phase.value,
          'turn_number': self.turn_number,
          'active_player': self.active_player,
          'priority_player': self.priority_player,
          'zones': {zone: [card.to_dict() for card in cards] for zone, cards in self.zones.items()},
          'life_totals': self.life_totals,
          'mana_pools': {player: mana_pool.pool for player, mana_pool in self.mana_pools.items()},
          'lands_played': self.lands_played,
          'spells_cast': self.spells_cast
      }
      return json.dumps(state, indent=4)

  def deserialize(self, state_json: str):
      """Deserialize the game state from a JSON string"""
      state = json.loads(state_json)
      
      self.current_phase = GamePhase[state['current_phase']]
      self.turn_number = state['turn_number']
      self.active_player = state['active_player']
      self.priority_player = state['priority_player']
      
      # Rebuild zones
      for zone, cards in state['zones'].items():
          self.zones[zone] = [Card.from_dict(card) for card in cards]
      
      self.life_totals = state['life_totals']
      for player, mana in state['mana_pools'].items():
          self.mana_pools[player].pool = mana
          
      self.lands_played = state['lands_played']
      self.spells_cast = state['spells_cast']

# Created/Modified files during execution:
print("Updated game_state_manager.py")
