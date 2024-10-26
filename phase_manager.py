from enum import Enum
from typing import List, Dict, Optional
from card import Card

class Phase(Enum):
  BEGIN = "Beginning Phase"
  UNTAP = "Untap Step"
  UPKEEP = "Upkeep Step"
  DRAW = "Draw Step"
  MAIN1 = "First Main Phase"
  COMBAT_BEGIN = "Beginning of Combat"
  COMBAT_DECLARE_ATTACKERS = "Declare Attackers"
  COMBAT_DECLARE_BLOCKERS = "Declare Blockers"
  COMBAT_DAMAGE = "Combat Damage"
  COMBAT_END = "End of Combat"
  MAIN2 = "Second Main Phase"
  END = "End Phase"
  CLEANUP = "Cleanup Step"

class PhaseManager:
  def __init__(self, game_state):
      self.game_state = game_state
      self.current_phase = Phase.BEGIN
      self.current_player = 'player'
      self.priority_player = 'player'
      self.passed_priority = set()
      self.stack = []
      
  def advance_phase(self) -> Phase:
      """Advance to the next phase"""
      phase_order = list(Phase)
      current_index = phase_order.index(self.current_phase)
      next_index = (current_index + 1) % len(phase_order)
      self.current_phase = phase_order[next_index]
      
      # Reset priority when changing phases
      self.priority_player = self.current_player
      self.passed_priority.clear()
      
      # Handle phase-specific actions
      self.handle_phase_begin()
      
      return self.current_phase
      
  def handle_phase_begin(self):
      """Handle automatic actions at the beginning of each phase"""
      if self.current_phase == Phase.UNTAP:
          self.handle_untap_step()
      elif self.current_phase == Phase.UPKEEP:
          self.handle_upkeep_step()
      elif self.current_phase == Phase.DRAW:
          self.handle_draw_step()
      elif self.current_phase == Phase.COMBAT_BEGIN:
          self.handle_combat_begin()
      elif self.current_phase == Phase.CLEANUP:
          self.handle_cleanup_step()
          
  def handle_untap_step(self):
      """Handle untap step actions"""
      # Untap all permanents controlled by active player
      if self.current_player == 'player':
          permanents = self.game_state.player_battlefield + self.game_state.player_lands
      else:
          permanents = self.game_state.ai_battlefield + self.game_state.ai_lands
          
      for permanent in permanents:
          permanent.untap()
          if permanent.is_creature():
              permanent.summoning_sickness = False
              
  def handle_upkeep_step(self):
      """Handle upkeep triggers"""
      triggers = []
      
      # Check for upkeep triggers
      if self.current_player == 'player':
          permanents = self.game_state.player_battlefield
      else:
          permanents = self.game_state.ai_battlefield
          
      for permanent in permanents:
          if hasattr(permanent, 'upkeep_trigger'):
              triggers.append({
                  'source': permanent,
                  'effect': permanent.upkeep_trigger,
                  'controller': self.current_player
              })
              
      # Add triggers to the stack
      for trigger in triggers:
          self.stack.append(trigger)
          
  def handle_draw_step(self):
      """Handle draw step"""
      if self.current_player == 'player':
          if self.game_state.turn_number > 1 or self.current_player != 'player':
              self.game_state.player_draw_card()
      else:
          self.game_state.ai_draw_card()
          
  def handle_combat_begin(self):
      """Handle beginning of combat"""
      # Reset combat-related flags
      if self.current_player == 'player':
          creatures = self.game_state.player_battlefield
      else:
          creatures = self.game_state.ai_battlefield
          
      for creature in creatures:
          if creature.is_creature():
              creature.attacking = False
              creature.blocking = None
              creature.damage_assigned = 0
              
  def handle_cleanup_step(self):
      """Handle cleanup step"""
      # Discard down to maximum hand size
      if self.current_player == 'player':
          while len(self.game_state.player_hand) > 7:
              self.game_state.player_discard()
      else:
          while len(self.game_state.ai_hand) > 7:
              self.game_state.ai_discard()
              
      # Remove all damage from creatures
      all_creatures = (self.game_state.player_battlefield + 
                      self.game_state.ai_battlefield)
      for creature in all_creatures:
          if creature.is_creature():
              creature.damage_marked = 0
              
      # End all "until end of turn" effects
      self.game_state.remove_end_of_turn_effects()
      
  def pass_priority(self, player: str):
      """Handle priority passing"""
      self.passed_priority.add(player)
      
      # If both players have passed priority
      if len(self.passed_priority) == 2:
          if self.stack:
              # Resolve top of stack
              self.resolve_stack()
          else:
              # Move to next phase
              self.advance_phase()
      else:
          # Give priority to other player
          self.priority_player = 'ai' if player == 'player' else 'player'
          
  def resolve_stack(self):
      """Resolve the top item of the stack"""
      if not self.stack:
          return
          
      # Get the top item
      item = self.stack.pop()
      
      # Handle different types of stack items
      if item.get('type') == 'spell':
          self.resolve_spell(item)
      elif item.get('type') == 'ability':
          self.resolve_ability(item)
      elif item.get('type') == 'trigger':
          self.resolve_trigger(item)
          
      # Reset priority after resolution
      self.priority_player = self.current_player
      self.passed_priority.clear()
      
  def resolve_spell(self, spell_item: Dict):
      """Resolve a spell from the stack"""
      spell = spell_item['spell']
      controller = spell_item['controller']
      
      if spell.is_creature():
          # Put creature onto battlefield
          if controller == 'player':
              self.game_state.player_battlefield.append(spell)
          else:
              self.game_state.ai_battlefield.append(spell)
      else:
          # Handle instant/sorcery effects
          self.handle_spell_effects(spell, controller)
          
      # Move spell to graveyard if it's not a permanent
      if not spell.is_permanent():
          if controller == 'player':
              self.game_state.player_graveyard.append(spell)
          else:
              self.game_state.ai_graveyard.append(spell)
              
  def resolve_ability(self, ability_item: Dict):
      """Resolve an activated or triggered ability"""
      ability = ability_item['ability']
      source = ability_item['source']
      controller = ability_item['controller']
      
      # Handle ability effects
      self.handle_ability_effects(ability, source, controller)
      
  def resolve_trigger(self, trigger_item: Dict):
      """Resolve a triggered ability"""
      trigger = trigger_item['effect']
      source = trigger_item['source']
      controller = trigger_item['controller']
      
      # Execute the trigger effect
      trigger(self.game_state, source, controller)
      
  def handle_spell_effects(self, spell: Card, controller: str):
      """Handle the effects of an instant or sorcery spell"""
      if hasattr(spell, 'effect'):
          spell.effect(self.game_state, controller)
          
  def handle_ability_effects(self, ability: Dict, source: Card, controller: str):
      """Handle the effects of an activated or triggered ability"""
      if 'effect' in ability:
          ability['effect'](self.game_state, source, controller)
          
  def can_cast_spell(self, spell: Card, player: str) -> bool:
      """Check if a spell can be cast in the current phase"""
      # Sorcery-speed restrictions
      if spell.is_sorcery() or spell.is_creature():
          if (self.current_phase not in [Phase.MAIN1, Phase.MAIN2] or
              self.stack or
              self.current_player != player):
              return False
              
      # Check if player has priority
      if self.priority_player != player:
          return False
          
      return True
      
  def can_activate_ability(self, ability: Dict, controller: str) -> bool:
      """Check if an ability can be activated"""
      # Check timing restrictions
      if ability.get('sorcery_speed', False):
          if (self.current_phase not in [Phase.MAIN1, Phase.MAIN2] or
              self.stack or
              self.current_player != controller):
              return False
              
      # Check if player has priority
      if self.priority_player != controller:
          return False
          
      return True
