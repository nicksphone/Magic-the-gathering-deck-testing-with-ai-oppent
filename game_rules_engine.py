# game_rules_engine.py (new)
from typing import List, Dict, Optional, Set
from enum import Enum
from card import Card

class GamePhase(Enum):
    UNTAP = "Untap"
    UPKEEP = "Upkeep"
    DRAW = "Draw"
    MAIN1 = "Main 1"
    COMBAT_BEGIN = "Beginning of Combat"
    COMBAT_ATTACK = "Declare Attackers"
    COMBAT_BLOCK = "Declare Blockers"
    COMBAT_DAMAGE = "Combat Damage"
    COMBAT_END = "End of Combat"
    MAIN2 = "Main 2"
    END = "End"
    CLEANUP = "Cleanup"

class GameAction(Enum):
    PLAY_LAND = "play_land"
    CAST_SPELL = "cast_spell"
    ACTIVATE_ABILITY = "activate_ability"
    ATTACK = "attack"
    BLOCK = "block"
    PASS_PRIORITY = "pass_priority"

class GameRulesEngine:
    def __init__(self):
        self.state_based_actions = [
            self._check_creature_death,
            self._check_player_life,
            self._check_empty_library,
            self._check_zero_loyalty,
            self._check_legendary_rule,
            self._check_token_existence,
            self._check_aura_attachment
        ]
        
        self.replacement_effects = []
        self.triggered_abilities = []
        self.continuous_effects = []
        
    def check_legal_action(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if an action is legal in the current game state"""
        action_type = GameAction(action['type'])
        
        if action_type == GameAction.PLAY_LAND:
            return self._check_legal_land_play(action, game_state)
        elif action_type == GameAction.CAST_SPELL:
            return self._check_legal_spell_cast(action, game_state)
        elif action_type == GameAction.ACTIVATE_ABILITY:
            return self._check_legal_ability_activation(action, game_state)
        elif action_type == GameAction.ATTACK:
            return self._check_legal_attack(action, game_state)
        elif action_type == GameAction.BLOCK:
            return self._check_legal_block(action, game_state)
            
        return False, "Unknown action type"

    def apply_state_based_actions(self, game_state) -> List[Dict]:
        """Apply all state-based actions"""
        actions_applied = []
        changes_made = True
        
        while changes_made:
            changes_made = False
            for action in self.state_based_actions:
                result = action(game_state)
                if result:
                    actions_applied.extend(result)
                    changes_made = True
                    
        return actions_applied

    def check_triggered_abilities(self, event: Dict, game_state) -> List[Dict]:
        """Check for and return all triggered abilities"""
        triggers = []
        
        for ability in self.triggered_abilities:
            if self._ability_triggers_from_event(ability, event):
                triggers.append({
                    'ability': ability,
                    'source': ability.source,
                    'controller': ability.controller
                })
                
        return triggers

    def apply_continuous_effects(self, game_state):
        """Apply all continuous effects in timestamp order"""
        # Sort effects by timestamp and dependency
        sorted_effects = self._sort_continuous_effects()
        
        # Apply effects in layers
        for layer in range(7):  # MTG has 7 layers of continuous effects
            effects_in_layer = [e for e in sorted_effects if e.layer == layer]
            for effect in effects_in_layer:
                effect.apply(game_state)

    def _check_legal_land_play(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if a land play is legal"""
        if game_state.current_phase not in [GamePhase.MAIN1, GamePhase.MAIN2]:
            return False, "Lands can only be played during main phases"
            
        if game_state.lands_played_this_turn >= game_state.lands_per_turn:
            return False, "Already played maximum number of lands this turn"
            
        if game_state.stack:
            return False, "Cannot play lands while spells are on the stack"
            
        return True, ""

    def _check_legal_spell_cast(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if a spell cast is legal"""
        spell = action['card']
        
        # Check timing restrictions
        if spell.is_sorcery() and not self._check_sorcery_timing(game_state):
            return False, "Can only cast sorceries during your main phase with an empty stack"
            
        # Check mana requirements
        if not self._check_mana_available(action, game_state):
            return False, "Insufficient mana to cast this spell"
            
        # Check if targets are legal
        if 'targets' in action and not self._check_legal_targets(action['targets'], spell, game_state):
            return False, "Invalid targets"
            
        return True, ""

    def _check_legal_ability_activation(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if an ability activation is legal"""
        ability = action['ability']
        source = action['source']
        
        # Check if source is legal
        if not source.is_on_battlefield():
            return False, "Ability source is not on battlefield"
            
        # Check timing restrictions
        if ability.sorcery_speed and not self._check_sorcery_timing(game_state):
            return False, "This ability can only be activated at sorcery speed"
            
        # Check costs
        if not self._check_ability_costs(ability, action, game_state):
            return False, "Cannot pay ability costs"
            
        return True, ""

    def _check_legal_attack(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if an attack is legal"""
        attacker = action['creature']
        
        if game_state.current_phase != GamePhase.COMBAT_ATTACK:
            return False, "Can only declare attackers during combat attack phase"
            
        if attacker.is_tapped:
            return False, "Cannot attack with tapped creature"
            
        if attacker.has_summoning_
