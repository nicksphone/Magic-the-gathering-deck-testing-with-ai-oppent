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
            
        if attacker.has_summoning
        def _check_legal_attack(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if an attack is legal"""
        attacker = action['creature']
        
        if game_state.current_phase != GamePhase.COMBAT_ATTACK:
            return False, "Can only declare attackers during combat attack phase"
            
        if attacker.is_tapped:
            return False, "Cannot attack with tapped creature"
            
        if attacker.has_summoning_sickness and not 'Haste' in attacker.abilities:
            return False, "Creature has summoning sickness"
            
        if 'Defender' in attacker.abilities:
            return False, "Creatures with defender can't attack"
            
        return True, ""

    def _check_legal_block(self, action: Dict, game_state) -> Tuple[bool, str]:
        """Check if a block is legal"""
        blocker = action['blocker']
        attacker = action['attacker']
        
        if game_state.current_phase != GamePhase.COMBAT_BLOCK:
            return False, "Can only declare blockers during combat block phase"
            
        if blocker.is_tapped:
            return False, "Cannot block with tapped creature"
            
        # Check evasion abilities
        if 'Flying' in attacker.abilities and not ('Flying' in blocker.abilities or 'Reach' in blocker.abilities):
            return False, "Can't block flying creature"
            
        if 'Shadow' in attacker.abilities and not 'Shadow' in blocker.abilities:
            return False, "Can't block shadow creature"
            
        if 'Horsemanship' in attacker.abilities and not 'Horsemanship' in blocker.abilities:
            return False, "Can't block creature with horsemanship"
            
        if 'Unblockable' in attacker.abilities:
            return False, "Cannot block unblockable creature"
            
        return True, ""

    def resolve_combat(self, game_state) -> List[Dict]:
        """Resolve entire combat phase"""
        results = []
        
        # Beginning of combat triggers
        results.extend(self._handle_combat_triggers(game_state, 'begin_combat'))
        
        # Declare attackers
        if game_state.current_phase == GamePhase.COMBAT_ATTACK:
            results.extend(self._handle_attack_declaration(game_state))
            
        # Declare blockers
        if game_state.current_phase == GamePhase.COMBAT_BLOCK:
            results.extend(self._handle_block_declaration(game_state))
            
        # Combat damage
        if game_state.current_phase == GamePhase.COMBAT_DAMAGE:
            results.extend(self._handle_combat_damage(game_state))
            
        # End of combat triggers
        results.extend(self._handle_combat_triggers(game_state, 'end_combat'))
        
        return results

    def _handle_combat_damage(self, game_state) -> List[Dict]:
        """Handle combat damage step"""
        results = []
        
        # First strike damage
        first_strike_creatures = self._get_first_strike_creatures(game_state)
        if first_strike_creatures:
            results.extend(self._assign_combat_damage(first_strike_creatures, game_state))
            
        # Regular combat damage
        regular_damage_creatures = self._get_regular_damage_creatures(game_state)
        results.extend(self._assign_combat_damage(regular_damage_creatures, game_state))
        
        return results

    def _assign_combat_damage(self, creatures: List[Card], game_state) -> List[Dict]:
        """Assign and resolve combat damage"""
        results = []
        
        for creature in creatures:
            if creature in game_state.attackers:
                # Handle attacking creature damage
                if creature in game_state.blocks:
                    # Creature is blocked
                    blockers = game_state.blocks[creature]
                    damage_assignment = self._assign_damage_to_blockers(creature, blockers)
                    results.extend(self._apply_combat_damage(damage_assignment))
                else:
                    # Creature is unblocked
                    results.append({
                        'type': 'combat_damage',
                        'source': creature,
                        'target': game_state.defending_player,
                        'amount': creature.power
                    })
                    
        return results

    def _assign_damage_to_blockers(self, attacker: Card, blockers: List[Card]) -> List[Dict]:
        """Assign attacker's damage to blocking creatures"""
        assignments = []
        remaining_damage = attacker.power
        
        # Implement damage assignment order rules
        ordered_blockers = self._get_damage_assignment_order(blockers)
        
        for blocker in ordered_blockers:
            if remaining_damage <= 0:
                break
                
            # Must assign lethal damage to each blocker in order
            lethal_damage = self._calculate_lethal_damage(blocker)
            damage_to_assign = min(lethal_damage, remaining_damage)
            
            assignments.append({
                'type': 'combat_damage',
                'source': attacker,
                'target': blocker,
                'amount': damage_to_assign
            })
            
            remaining_damage -= damage_to_assign
            
        return assignments

    def _calculate_lethal_damage(self, creature: Card) -> int:
        """Calculate lethal damage for a creature"""
        # Account for damage already marked on the creature
        return max(0, creature.toughness - creature.damage_marked)

    def _get_damage_assignment_order(self, creatures: List[Card]) -> List[Card]:
        """Get creatures in damage assignment order"""
        # In a real implementation, this would handle the attacking player's chosen order
        return sorted(creatures, key=lambda x: (x.toughness, x.power))

    def _apply_combat_damage(self, damage_assignments: List[Dict]) -> List[Dict]:
        """Apply combat damage and handle results"""
        results = []
        
        for assignment in damage_assignments:
            target = assignment['target']
            amount = assignment['amount']
            
            if isinstance(target, Card):
                # Damage to creature
                target.damage_marked += amount
                results.append({
                    'type': 'damage_marked',
                    'target': target,
                    'amount': amount
                })
                
                # Check for death
                if target.damage_marked >= target.toughness:
                    results.append({
                        'type': 'creature_death',
                        'creature': target
                    })
            else:
                # Damage to player
                target.life_total -= amount
                results.append({
                    'type': 'life_loss',
                    'player': target,
                    'amount': amount
                })
                
        return results

    def handle_triggers(self, event: Dict, game_state) -> List[Dict]:
        """Handle triggered abilities"""
        triggers = []
        
        # Check all permanents for relevant triggers
        for permanent in game_state.get_all_permanents():
            if hasattr(permanent, 'triggered_abilities'):
                for trigger in permanent.triggered_abilities:
                    if self._does_trigger_match_event(trigger, event):
                        triggers.append({
                            'ability': trigger,
                            'source': permanent,
                            'controller': permanent.controller
                        })
                        
        return triggers

    def _does_trigger_match_event(self, trigger: Dict, event: Dict) -> bool:
        """Check if a trigger condition matches an event"""
        trigger_condition = trigger.get('condition', {})
        
        for key, value in trigger_condition.items():
            if key not in event or event[key] != value:
                return False
                
        return True

    def apply_replacement_effects(self, event: Dict, game_state) -> Dict:
        """Apply any applicable replacement effects to an event"""
        modified_event = event.copy()
        
        for effect in game_state.replacement_effects:
            if self._does_effect_apply(effect, modified_event):
                modified_event = effect['modify'](modified_event)
                
        return modified_event

    def _does_effect_apply(self, effect: Dict, event: Dict) -> bool:
        """Check if a replacement effect applies to an event"""
        effect_condition = effect.get('condition', {})
        
        for key, value in effect_condition.items():
            if key not in event or event[key] != value:
                return False
                
        return True

# Created/Modified files during execution:
print("Updated game_rules_engine.py")
