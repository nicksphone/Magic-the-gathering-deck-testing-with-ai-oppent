from typing import List, Dict, Optional
from enum import Enum
from card import Card

class EffectType(Enum):
DAMAGE = "damage"
DESTROY = "destroy"
EXILE = "exile"
COUNTER = "counter"
DRAW = "draw"
LIFE_GAIN = "life_gain"
LIFE_LOSS = "life_loss"
ADD_MANA = "add_mana"
MODIFY_POWER = "modify_power"
MODIFY_TOUGHNESS = "modify_toughness"
ADD_ABILITY = "add_ability"
REMOVE_ABILITY = "remove_ability"

class Effect:
def init(self, effect_type: EffectType, value: any = None, duration: str = None):
self.type = effect_type
self.value = value
self.duration = duration
self.source = None
self.targets = []

class EffectsManager:
def init(self, game_state):
self.game_state = game_state
self.active_effects = []
self.delayed_triggers = []

def add_effect(self, effect: Effect):
    """Add an effect to be tracked"""
    if effect.duration:
        self.active_effects.append(effect)
        
def resolve_effect(self, effect: Effect) -> Dict:
    """Resolve an individual effect"""
    results = {
        'success': True,
        'details': {}
    }
    
    if effect.type == EffectType.DAMAGE:
        results['details'] = self.apply_damage(effect)
    elif effect.type == EffectType.DESTROY:
        results['details'] = self.apply_destroy(effect)
    elif effect.type == EffectType.EXILE:
        results['details'] = self.apply_exile(effect)
    elif effect.type == EffectType.COUNTER:
        results['details'] = self.apply_counter(effect)
    elif effect.type == EffectType.DRAW:
        results['details'] = self.apply_draw(effect)
    elif effect.type == EffectType.LIFE_GAIN:
        results['details'] = self.apply_life_gain(effect)
    elif effect.type == EffectType.LIFE_LOSS:
        results['details'] = self.apply_life_loss(effect)
    elif effect.type == EffectType.ADD_MANA:
        results['details'] = self.apply_add_mana(effect)
    elif effect.type == EffectType.MODIFY_POWER:
        results['details'] = self.apply_modify_power(effect)
    elif effect.type == EffectType.MODIFY_TOUGHNESS:
        results['details'] = self.apply_modify_toughness(effect)
    elif effect.type == EffectType.ADD_ABILITY:
        results['details'] = self.apply_add_ability(effect)
    elif effect.type == EffectType.REMOVE_ABILITY:
        results['details'] = self.apply_remove_ability(effect)
        
    return results
    
def apply_damage(self, effect: Effect) -> Dict:
    """Apply damage effect"""
    results = {'damage_dealt': {}}
    
    for target in effect.targets:
        if isinstance(target, str):  # Player target
            if target == 'player':
                self.game_state.player_life -= effect.value
            else:
                self.game_state.ai_life -= effect.value
            results['damage_dealt'][target] = effect.value
        else:  # Creature target
            target.damage_marked += effect.value
            results['damage_dealt'][target.name] = effect.value
            
    return results
    
def apply_destroy(self, effect: Effect) -> Dict:
    """Apply destroy effect"""
    results = {'destroyed': []}
    
    for target in effect.targets:
        if target in self.game_state.player_battlefield:
            self.game_state.player_battlefield.remove(target)
            self.game_state.player_graveyard.append(target)
            results['destroyed'].append(target.name)
        elif target in self.game_state.ai_battlefield:
            self.game_state.ai_battlefield.remove(target)
            self.game_state.ai_graveyard.append(target)
            results['destroyed'].append(target.name)
            
    return results
    
def apply_exile(self, effect: Effect) -> Dict:
    """Apply exile effect"""
    results = {'exiled': []}
    
    for target in effect.targets:
        # Remove from current zone
        for zone in [self.game_state.player_battlefield, self.game_state.ai_battlefield,
                    self.game_state.player_graveyard, self.game_state.ai_graveyard]:
            if target in zone:
                zone.remove(target)
                
        # Add to exile zone
        if target in self.game_state.player_battlefield or target in self.game_state.player_graveyard:
            self.game_state.player_exile.append(target)
        else:
            self.game_state.ai_exile.append(target)
            
        results['exiled'].append(target.name)
        
    return results
    
def apply_counter(self, effect: Effect) -> Dict:
    """Apply counter effect"""
    results = {'countered': []}
    
    for target in effect.targets:
        if target in self.game_state.stack:
            self.game_state.stack.remove(target)
            # Move countered spell to graveyard
            if target['controller'] == 'player':
                self.game_state.player_graveyard.append(target['card'])
            else:
                self.game_state.ai_graveyard.append(target['card'])
            results['countered'].append(target['card'].name)
            
    return results
    
def apply_draw(self, effect: Effect) -> Dict:
    """Apply draw effect"""
    results = {'cards_drawn': []}
    
    controller = effect.source.controller
    for _ in range(effect.value):
        if controller == 'player':
            if self.game_state.player_deck:
                card = self.game_state.player_deck.pop(0)
                self.game_state.player_hand.append(card)
                results['cards_drawn'].append(card.name)
        else:
            if self.game_state.ai_deck:
                card = self.game_state.ai_deck.pop(0)
                self.game_state.ai_hand.append(card)
                results['cards_drawn'].append(card.name)
                
    return results
    
def apply_life_gain(self, effect: Effect) -> Dict:
    """Apply life gain effect"""
    results = {'life_gained': 0}
    
    controller = effect.source.controller
    if controller == 'player':
        self.game_state.player_life += effect.value
    else:
        self.game_state.ai_life += effect.value
        
    results['life_gained'] = effect.value
    return results
    
def apply_life_loss(self, effect: Effect) -> Dict:
    """Apply life loss effect"""
    results = {'life_lost': 0}
    
    for target in effect.targets:
        if target == 'player':
            self.game_state.player_life -= effect.value
        else:
            self.game_state.ai_life -= effect.value
            
        results['life_lost'] = effect.value
        
    return results
    
def apply_add_mana(self, effect: Effect) -> Dict:
    """Apply add mana effect"""
    results = {'mana_added': {}}
    
    controller = effect.source.controller
    mana_pool = (self.game_state.player_mana_pool if controller == 'player' 
                else self.game_state.ai_mana_pool)
                
    for mana_type, amount in effect.value.items():
        mana_pool[mana_type] += amount
        results['mana_added'][mana_type] = amount
        
    return results
    
def apply_modify_power(self, effect: Effect) -> Dict:
    """Apply power modification effect"""
    results = {'power_modified': []}
    
    for target in effect.targets:
        if target.is_creature():
            target.power_modifier = effect.value
            results['power_modified'].append({
                'card':

