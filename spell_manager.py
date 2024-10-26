from typing import List, Dict, Optional
from card import Card
from enum import Enum

class SpellType(Enum):
  INSTANT = "Instant"
  SORCERY = "Sorcery"
  CREATURE = "Creature"
  ARTIFACT = "Artifact"
  ENCHANTMENT = "Enchantment"
  PLANESWALKER = "Planeswalker"

class TargetType(Enum):
  PLAYER = "player"
  CREATURE = "creature"
  PERMANENT = "permanent"
  SPELL = "spell"
  ANY = "any"

class SpellManager:
  def __init__(self, game_state):
      self.game_state = game_state
      self.stack = []
      self.effects_queue = []
      self.active_continuous_effects = []
      
  def cast_spell(self, spell: Card, controller: str, targets: List[Dict] = None) -> bool:
      """
      Attempt to cast a spell and put it on the stack
      """
      if not self.can_cast_spell(spell, controller):
          return False
          
      # Create spell object for the stack
      spell_object = {
          'card': spell,
          'controller': controller,
          'targets': targets or [],
          'effects': self.parse_spell_effects(spell)
      }
      
      # Add to stack
      self.stack.append(spell_object)
      return True
      
  def can_cast_spell(self, spell: Card, controller: str) -> bool:
      """
      Check if a spell can be cast
      """
      # Check timing restrictions
      if spell.is_sorcery():
          if (self.game_state.current_phase not in ['MAIN1', 'MAIN2'] or
              self.stack or
              controller != self.game_state.active_player):
              return False
              
      # Check if player has priority
      if controller != self.game_state.priority_player:
          return False
          
      return True
      
  def resolve_top_of_stack(self) -> Dict:
      """
      Resolve the top spell or ability on the stack
      """
      if not self.stack:
          return None
          
      spell_object = self.stack.pop()
      results = self.resolve_spell(spell_object)
      
      # Check state-based actions after resolution
      self.game_state.check_state_based_actions()
      
      return results
      
  def resolve_spell(self, spell_object: Dict) -> Dict:
      """
      Resolve a spell and its effects
      """
      results = {
          'success': True,
          'effects_applied': [],
          'targets_affected': []
      }
      
      spell = spell_object['card']
      controller = spell_object['controller']
      targets = spell_object['targets']
      effects = spell_object['effects']
      
      # Check if targets are still legal
      if not self.verify_targets(targets):
          results['success'] = False
          results['reason'] = 'illegal_targets'
          return results
          
      # Apply each effect
      for effect in effects:
          effect_result = self.apply_effect(effect, targets, controller)
          results['effects_applied'].append(effect_result)
          
      # Move spell to appropriate zone after resolution
      self.move_after_resolution(spell, controller)
      
      return results
      
  def verify_targets(self, targets: List[Dict]) -> bool:
      """
      Verify that all targets are still legal
      """
      for target in targets:
          if target['type'] == TargetType.CREATURE:
              if not self.is_creature_target_legal(target['object']):
                  return False
          elif target['type'] == TargetType.PLAYER:
              if not self.is_player_target_legal(target['object']):
                  return False
          elif target['type'] == TargetType.SPELL:
              if not self.is_spell_target_legal(target['object']):
                  return False
                  
      return True
      
  def parse_spell_effects(self, spell: Card) -> List[Dict]:
      """
      Parse the effects of a spell from its oracle text
      """
      effects = []
      if not hasattr(spell, 'oracle_text'):
          return effects
          
      text = spell.oracle_text.lower()
      
      # Parse damage effects
      if 'deals' in text and 'damage' in text:
          damage_amount = self.parse_damage_amount(text)
          effects.append({
              'type': 'damage',
              'amount': damage_amount,
              'target_type': self.parse_target_type(text)
          })
          
      # Parse draw effects
      if 'draw' in text:
          draw_amount = self.parse_draw_amount(text)
          effects.append({
              'type': 'draw',
              'amount': draw_amount
          })
          
      # Parse life gain/loss effects
      if 'gain' in text and 'life' in text:
          life_amount = self.parse_life_amount(text)
          effects.append({
              'type': 'life_gain',
              'amount': life_amount
          })
          
      return effects
      
  def apply_effect(self, effect: Dict, targets: List[Dict], controller: str) -> Dict:
      """
      Apply a single effect
      """
      result = {
          'effect_type': effect['type'],
          'success': True,
          'details': {}
      }
      
      if effect['type'] == 'damage':
          result['details'] = self.apply_damage_effect(effect, targets)
      elif effect['type'] == 'draw':
          result['details'] = self.apply_draw_effect(effect, controller)
      elif effect['type'] == 'life_gain':
          result['details'] = self.apply_life_effect(effect, controller)
          
      return result
      
  def apply_damage_effect(self, effect: Dict, targets: List[Dict]) -> Dict:
      """
      Apply damage effect to targets
      """
      results = {'damage_dealt': {}}
      
      for target in targets:
          if target['type'] == TargetType.CREATURE:
              creature = target['object']
              creature.damage_marked += effect['amount']
              results['damage_dealt'][creature.name] = effect['amount']
          elif target['type'] == TargetType.PLAYER:
              player = target['object']
              if player == 'player':
                  self.game_state.player_life -= effect['amount']
              else:
                  self.game_state.ai_life -= effect['amount']
              results['damage_dealt'][player] = effect['amount']
              
      return results
      
  def apply_draw_effect(self, effect: Dict, controller: str) -> Dict:
      """
      Apply draw effect
      """
      results = {'cards_drawn': []}
      
      for _ in range(effect['amount']):
          if controller == 'player':
              card = self.game_state.player_draw_card()
          else:
              card = self.game_state.ai_draw_card()
              
          if card:
              results['cards_drawn'].append(card.name)
              
      return results
      
  def apply_life_effect(self, effect: Dict, controller: str) -> Dict:
      """
      Apply life gain/loss effect
      """
      results = {'life_changed': 0}
      
      if controller == 'player':
          self.game_state.player_life += effect['amount']
          results['life_changed'] = effect['amount']
      else:
          self.game_state.ai_life += effect['amount']
          results['life_changed'] = effect['amount']
          
      return results
      
  def move_after_resolution(self, spell: Card, controller: str):
      """
      Move spell to appropriate zone after resolution
      """
      if spell.is_permanent():
          if controller == 'player':
              self.game_state.player_battlefield.append(spell)
          else:
              self.game_state.ai_battlefield.append(spell)
      else:
          if controller == 'player':
              self.game_state.player_graveyard.append(spell)
          else:
              self.game_state.ai_graveyard.append(spell)
              
  def add_continuous_effect(self, effect: Dict):
      """
      Add a continuous effect to the game
      """
      self.active_continuous_effects.append(effect)
      
  def remove_continuous_effect(self, effect: Dict):
      """
      Remove a continuous effect from the game
      """
      if effect in self.active_continuous_effects:
          self.active_continuous_effects.remove(effect)
          
  def apply_continuous_effects(self):
      """
      Apply all active continuous effects
      """
      for effect in self.active_continuous_effects:
          self.apply_continuous_effect(effect)
          
  def apply_continuous_effect(self, effect: Dict):
      """
      Apply a single continuous effect
      """
      if effect['type'] == 'static':
          self.apply_static_effect(effect)
      elif effect['type'] == 'replacement':
          self.apply_replacement_effect(effect)
          
  def apply_static_effect(self, effect: Dict):
      """
      Apply a static effect (like +1/+1 to all creatures)
      """
      affected_objects = self.get_affected_objects(effect)
      
      for obj in affected_objects:
          if 'power_mod' in effect:
              obj.power_modifier += effect['power_mod']
          if 'toughness_mod' in effect:
              obj.toughness_modifier += effect['toughness_mod']
          if 'abilities' in effect:
              obj.granted_abilities.extend(effect['abilities'])
              
  def apply_replacement_effect(self, effect: Dict):
      """
      Apply a replacement effect
      """
      # Implementation depends on specific replacement effects
      pass
      
  def get_affected_objects(self, effect: Dict) -> List:
      """
      Get all objects affected by a continuous effect
      """
      affected = []
      
      if effect.get('affects') == 'all_creatures':
          affected.extend(self.game_state.player_battlefield)
          affected.extend(self.game_state.ai_battlefield)
      elif effect.get('affects') == 'controlled_creatures':
          if effect['controller'] == 'player':
              affected.extend(self.game_state.player_battlefield)
          else:
              affected.extend(self.game_state.ai_battlefield)
              
      return [obj for obj in affected if obj.is_creature()]
