from typing import List, Dict, Optional, Set
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

class GameRules:
  @staticmethod
  def can_play_land(game_state) -> bool:
      """Check if a land can be played"""
      return (game_state.current_phase in [Phase.MAIN1, Phase.MAIN2] and
              game_state.lands_played_this_turn < game_state.lands_per_turn and
              game_state.active_player == game_state.priority_player)

  @staticmethod
  def can_cast_spell(card: Card, game_state) -> bool:
      """Check if a spell can be cast"""
      # Sorcery speed restrictions
      if card.is_sorcery():
          if (game_state.current_phase not in [Phase.MAIN1, Phase.MAIN2] or
              game_state.stack or
              game_state.active_player != game_state.priority_player):
              return False

      # Check if player has priority
      if game_state.priority_player != game_state.active_player:
          return False

      return True

  @staticmethod
  def can_attack(creature: Card, game_state) -> bool:
      """Check if a creature can attack"""
      return (not creature.is_tapped and
              not creature.summoning_sickness and
              game_state.current_phase == Phase.COMBAT_DECLARE_ATTACKERS and
              game_state.active_player == game_state.priority_player)

  @staticmethod
  def can_block(creature: Card, attacker: Card, game_state) -> bool:
      """Check if a creature can block an attacker"""
      if creature.is_tapped:
          return False

      # Check for evasion abilities
      if "Flying" in attacker.abilities and "Flying" not in creature.abilities and "Reach" not in creature.abilities:
          return False

      if "Fear" in attacker.abilities and "Artifact" not in creature.type_line and "Black" not in creature.type_line:
          return False

      return True

  @staticmethod
  def check_state_based_actions(game_state) -> List[Dict]:
      """Check and apply state-based actions"""
      actions = []

      # Check creature death
      for creature in game_state.battlefield:
          if creature.is_creature():
              # Check for lethal damage
              if creature.damage_marked >= creature.get_toughness():
                  actions.append({
                      'action': 'destroy',
                      'permanent': creature,
                      'reason': 'lethal_damage'
                  })
              # Check for zero or less toughness
              elif creature.get_toughness() <= 0:
                  actions.append({
                      'action': 'destroy',
                      'permanent': creature,
                      'reason': 'zero_toughness'
                  })

      # Check player loss conditions
      if game_state.player_life <= 0:
          actions.append({
              'action': 'game_loss',
              'player': 'player',
              'reason': 'zero_life'
          })
      if game_state.ai_life <= 0:
          actions.append({
              'action': 'game_loss',
              'player': 'ai',
              'reason': 'zero_life'
          })

      # Check for drawing from empty library
      if game_state.draw_attempted and not game_state.player_deck:
          actions.append({
              'action': 'game_loss',
              'player': 'player',
              'reason': 'empty_library'
          })
      if game_state.draw_attempted and not game_state.ai_deck:
          actions.append({
              'action': 'game_loss',
              'player': 'ai',
              'reason': 'empty_library'
          })

      return actions

  @staticmethod
  def apply_continuous_effects(game_state):
      """Apply continuous effects from permanents"""
      effects = []
      
      for permanent in game_state.battlefield:
          if hasattr(permanent, 'continuous_effects'):
              for effect in permanent.continuous_effects:
                  effects.append(effect)
                  
      # Sort effects by timestamp and dependency
      effects.sort(key=lambda x: (x.timestamp, x.layer))
      
      # Apply effects in proper order
      for effect in effects:
          effect.apply(game_state)

  @staticmethod
  def check_triggered_abilities(game_state, event: Dict) -> List[Dict]:
      """Check for and return triggered abilities based on an event"""
      triggers = []
      
      for permanent in game_state.battlefield:
          if hasattr(permanent, 'trigger_condition'):
              if permanent.trigger_condition(event):
                  triggers.append({
                      'source': permanent,
                      'ability': permanent.triggered_ability,
                      'controller': permanent.controller
                  })
                  
      return triggers

  @staticmethod
  def validate_target(target: Card, targeting_restrictions: Dict) -> bool:
      """Validate if a target is legal based on targeting restrictions"""
      if not target:
          return False
          
      for restriction, value in targeting_restrictions.items():
          if restriction == 'type':
              if value not in target.type_line:
                  return False
          elif restriction == 'color':
              if value not in target.colors:
                  return False
          elif restriction == 'power':
              if target.get_power() > value:
                  return False
          elif restriction == 'toughness':
              if target.get_toughness() > value:
                  return False
                  
      return True

  @staticmethod
  def check_protection(creature: Card, source: Card) -> bool:
      """Check if a creature has protection from a source"""
      if not hasattr(creature, 'protection'):
          return False
          
      for protection in creature.protection:
          if protection == 'color':
              if any(color in source.colors for color in creature.protection['color']):
                  return True
          elif protection == 'type':
              if any(type_line in source.type_line for type_line in creature.protection['type']):
                  return True
                  
      return False

  @staticmethod
  def can_be_regenerated(permanent: Card) -> bool:
      """Check if a permanent can be regenerated"""
      if not permanent.is_creature():
          return False
          
      # Check if the creature has already been regenerated this turn
      if permanent.regenerated_this_turn:
          return False
          
      # Check if the creature is being destroyed by effects that can't be regenerated from
      if permanent.cant_be_regenerated:
          return False
          
      return True

  @staticmethod
  def check_replacement_effects(event: Dict, game_state) -> Optional[Dict]:
      """Check for and apply replacement effects"""
      replacements = []
      
      for permanent in game_state.battlefield:
          if hasattr(permanent, 'replacement_effect'):
              if permanent.replacement_effect.applies_to(event):
                  replacements.append(permanent.replacement_effect)
                  
      # Let active player choose order if multiple replacement effects
      if len(replacements) > 1:
          # TODO: Implement player choice for replacement effect order
          pass
          
      # Apply the first replacement effect
      if replacements:
          return replacements[0].apply(event)
          
      return None

  @staticmethod
  def check_prevention_effects(damage_event: Dict, game_state) -> Dict:
      """Check for and apply damage prevention effects"""
      original_damage = damage_event['amount']
      remaining_damage = original_damage
      
      for permanent in game_state.battlefield:
          if hasattr(permanent, 'prevention_effect'):
              if permanent.prevention_effect.applies_to(damage_event):
                  remaining_damage = permanent.prevention_effect.apply(remaining_damage)
                  
      damage_event['amount'] = remaining_damage
      return damage_event
