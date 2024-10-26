# ai_opponent.py (new)
from typing import List, Dict, Optional, Tuple
from enum import Enum
from card import Card
import random
import numpy as np

class AIStrategy(Enum):
  AGGRESSIVE = "aggressive"
  CONTROL = "control"
  MIDRANGE = "midrange"
  COMBO = "combo"

class AIDecisionMaker:
  def __init__(self, difficulty: str = "medium"):
      self.difficulty = difficulty
      self.memory = []  # Remember past plays and their outcomes
      self.learning_rate = 0.1
      self.strategy = None
      self.threat_threshold = 0.6

  def analyze_deck(self, deck: List[Card]) -> AIStrategy:
      """Analyze deck composition to determine optimal strategy"""
      creature_count = sum(1 for card in deck if card.is_creature())
      instant_count = sum(1 for card in deck if card.is_instant())
      sorcery_count = sum(1 for card in deck if card.is_sorcery())
      avg_cmc = sum(card.get_cmc() for card in deck) / len(deck)

      # Calculate strategy scores
      scores = {
          AIStrategy.AGGRESSIVE: self._calculate_aggro_score(deck),
          AIStrategy.CONTROL: self._calculate_control_score(deck),
          AIStrategy.MIDRANGE: self._calculate_midrange_score(deck),
          AIStrategy.COMBO: self._calculate_combo_score(deck)
      }

      self.strategy = max(scores.items(), key=lambda x: x[1])[0]
      return self.strategy

  def _calculate_aggro_score(self, deck: List[Card]) -> float:
      score = 0
      for card in deck:
          if card.is_creature():
              # Favor low-cost, high-power creatures
              if card.get_cmc() <= 3 and card.get_power() >= 2:
                  score += 1
              if 'Haste' in card.abilities:
                  score += 0.5
          elif card.is_instant() and 'damage' in card.oracle_text.lower():
              score += 0.5
      return score / len(deck)

  def _calculate_control_score(self, deck: List[Card]) -> float:
      score = 0
      for card in deck:
          if 'Counter' in card.oracle_text:
              score += 1
          elif 'Destroy' in card.oracle_text or 'Exile' in card.oracle_text:
              score += 0.8
          elif card.is_creature() and card.get_cmc() >= 5:
              score += 0.3
      return score / len(deck)

  def _calculate_midrange_score(self, deck: List[Card]) -> float:
      score = 0
      for card in deck:
          if card.is_creature():
              if 3 <= card.get_cmc() <= 5:
                  score += 1
              if card.get_power() >= 3 and card.get_toughness() >= 3:
                  score += 0.5
          elif 'Draw' in card.oracle_text:
              score += 0.3
      return score / len(deck)

  def _calculate_combo_score(self, deck: List[Card]) -> float:
      score = 0
      card_names = [card.name for card in deck]
      
      # Look for card synergies and duplicates
      for card in deck:
          if card_names.count(card.name) >= 3:
              score += 1
          if 'Search your library' in card.oracle_text:
              score += 0.5
          if 'When' in card.oracle_text or 'Whenever' in card.oracle_text:
              score += 0.3
      return score / len(deck)

  def evaluate_game_state(self, game_state) -> Dict[str, float]:
      """Evaluate the current game state"""
      evaluation = {
          'board_control': self._evaluate_board_control(game_state),
          'life_total_advantage': self._evaluate_life_totals(game_state),
          'card_advantage': self._evaluate_card_advantage(game_state),
          'mana_advantage': self._evaluate_mana_advantage(game_state),
          'threat_level': self._evaluate_threats(game_state)
      }
      return evaluation

  def choose_action(self, game_state, possible_actions: List[Dict]) -> Dict:
      """Choose the best action based on current strategy and game state"""
      if not possible_actions:
          return None

      evaluation = self.evaluate_game_state(game_state)
      action_scores = []

      for action in possible_actions:
          score = self._score_action(action, evaluation)
          action_scores.append((action, score))

      # Add some randomness based on difficulty
      if self.difficulty == "easy":
          randomness = 0.3
      elif self.difficulty == "medium":
          randomness = 0.15
      else:
          randomness = 0.05

      # Choose action with highest score plus some randomness
      action_scores = [(action, score + random.uniform(-randomness, randomness)) 
                      for action, score in action_scores]
      return max(action_scores, key=lambda x: x[1])[0]

  def _score_action(self, action: Dict, evaluation: Dict) -> float:
      """Score an action based on current evaluation and strategy"""
      score = 0
      action_type = action.get('type', '')

      if self.strategy == AIStrategy.AGGRESSIVE:
          score += self._score_aggressive_action(action, evaluation)
      elif self.strategy == AIStrategy.CONTROL:
          score += self._score_control_action(action, evaluation)
      elif self.strategy == AIStrategy.MIDRANGE:
          score += self._score_midrange_action(action, evaluation)
      elif self.strategy == AIStrategy.COMBO:
          score += self._score_combo_action(action, evaluation)

      # Adjust score based on game state
      if evaluation['threat_level'] > self.threat_threshold:
          score += self._score_defensive_action(action)

      return score

  def _score_aggressive_action(self, action: Dict, evaluation: Dict) -> float:
      score = 0
      if action['type'] == 'attack':
          score += 1.5
      elif action['type'] == 'play_creature':
          creature = action['card']
          if creature.get_cmc() <= 3 and creature.get_power() >= 2:
              score += 1
      elif action['type'] == 'cast_spell' and 'damage' in action['card'].oracle_text.lower():
          score += 1
      return score

  def _score_control_action(self, action: Dict, evaluation: Dict) -> float:
      score = 0
      if action['type'] == 'counter_spell':
          score += 1.5
      elif action['type'] == 'removal':
          score += 1
      elif action['type'] == 'draw_cards':
          score += 0.8
      return score

  def _score_midrange_action(self, action: Dict, evaluation: Dict) -> float:
      score = 0
      if action['type'] == 'play_creature':
          creature = action['card']
          if 3 <= creature.get_cmc() <= 5:
              score += 1
      elif evaluation['board_control'] < 0:
          score += self._score_defensive_action(action)
      return score

  def _score_combo_action(self, action: Dict, evaluation: Dict) -> float:
      score = 0
      if action['type'] == 'tutor':
          score += 1.5
      elif action['type'] == 'draw_cards':
          score += 1
      elif action['type'] == 'combo_piece':
          score += 2
      return score

  def _score_defensive_action(self, action: Dict) -> float:
      score = 0
      if action['type'] == 'block':
          score += 1
      elif action['type'] == 'removal':
          score += 1.5
      elif action['type'] == 'gain_life':
          score += 0.5
      return score

  def update_memory(self, action: Dict, result: Dict):
      """Update AI memory with action results"""
      self.memory.append({
          'action': action,
          'result': result,
          'success': result.get('success', False)
      })
      
      # Keep memory size manageable
      if len(self.memory) > 1000:
          self.memory = self.memory[-1000:]

  def learn_from_memory(self):
      """Adjust strategy based on past experiences"""
      if len(self.memory) < 10:
          return

      recent_memory = self.memory[-10:]
      success_rate = sum(1 for m in recent_memory if m['success']) / len(recent_memory)

      # Adjust threat threshold based on success rate
      if success_rate < 0.4:
          self.threat_threshold *= (1 - self.learning_rate)
      elif success_rate > 0.6:
          self.threat_threshold *= (1 + self.learning_rate)

      # Keep threshold in reasonable bounds
      self.threat_threshold = max(0.3, min(0.9, self.threat_threshold))

# Created/Modified files during execution:
print("Created ai_opponent.py")
