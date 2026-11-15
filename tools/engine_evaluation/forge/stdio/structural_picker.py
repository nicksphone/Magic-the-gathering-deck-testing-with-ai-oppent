# SPDX-License-Identifier: GPL-3.0-or-later
# Original structural test client for the Forge Team/Card-Forge native engine.
# Uses only offered actor-visible choices; not an expert AI or training label.
from collections import defaultdict

tried = defaultdict(set)

def pick_stack_selection(frame):
    q=frame['question']; meta=frame['info'].get('stack_selection')
    if not isinstance(meta,dict): raise ValueError('CURRENT_STACK_SELECTION_REQUIRED')
    if meta.get('input')!=q['kind'][6:] or meta.get('actor')!=q['actor_id'] or frame['state']['actor_id']!=q['actor_id']:
        raise ValueError('CURRENT_STACK_CONTEXT_REQUIRED')
    if q['min']!=1 or q['max']!=1: raise ValueError('STACK_ONE_CLICK_REQUIRED')
    if any(type(meta.get(k)) is not int or meta[k]<0 for k in ('generation','priority_epoch','revision')):
        raise ValueError('INVALID_STACK_CONTEXT')
    offered={}; ok=None
    for option in q['choices']:
        value=option['display']
        if value=='button_ok': ok=option; continue
        if value=='button_cancel': continue
        if not isinstance(value,dict) or set(value)!={'stack_id','source'} or type(value['stack_id']) is not int or not isinstance(value['source'],dict):
            raise ValueError('INVALID_STACK_DESCRIPTOR')
        if value['source'].get('hidden') and value['source']!={'hidden':True}: raise ValueError('INVALID_HIDDEN_STACK_SOURCE')
        if value['stack_id'] in offered: raise ValueError('ALIASED_STACK_IDENTITY')
        offered[value['stack_id']]=option
    chosen=meta.get('chosen'); seen=set()
    if not isinstance(chosen,list): raise ValueError('INVALID_STACK_CHOSEN')
    for value in chosen:
        if not isinstance(value,dict) or type(value.get('stack_id')) is not int: raise ValueError('INVALID_STACK_CHOSEN')
        key=value['stack_id']
        if key in seen or key not in offered or offered[key]['display']!=value: raise ValueError('FOREIGN_OR_STALE_CHOSEN_STACK')
        seen.add(key)
    if ok is not None:return [ok['token']]
    for key,option in offered.items():
        if key not in seen:return [option['token']]
    raise ValueError('NO_UNCHOSEN_STACK_OR_NATIVE_OK')


def pick_selection(frame):
    q=frame['question']; selection=frame['info'].get('selection')
    if not isinstance(selection,dict): raise ValueError('NATIVE_SELECTION_REQUIRED')
    if q['min']!=1 or q['max']!=1: raise ValueError('NATIVE_SELECTION_ONE_CLICK_REQUIRED')
    if selection.get('input')!=q['kind'][6:] or selection.get('actor')!=q['actor_id'] or frame['state']['actor_id']!=q['actor_id']:
        raise ValueError('NATIVE_SELECTION_CURRENT_CONTEXT_REQUIRED')
    for key in ('min','max','generation','priority_epoch','revision'):
        if type(selection.get(key)) is not int or selection[key]<0: raise ValueError('NATIVE_SELECTION_INVALID_BOUNDS_OR_CONTEXT')
    minimum,maximum=selection['min'],selection['max']; chosen=selection.get('chosen')
    if not isinstance(chosen,list) or minimum>maximum or len(chosen)>maximum: raise ValueError('NATIVE_SELECTION_INVALID_BOUNDS')
    def identity(value):
        if not isinstance(value,dict) or value.get('hidden'): raise ValueError('NATIVE_SELECTION_HIDDEN_OR_UNKNOWN_ENTITY')
        keys=[key for key in ('card_id','player_id') if key in value]
        if len(keys)!=1 or type(value[keys[0]]) is not int or value[keys[0]]<0: raise ValueError('NATIVE_SELECTION_INVALID_IDENTITY')
        return keys[0],value[keys[0]]
    entities={}; ok=None
    for option in q['choices']:
        value=option['display']
        if value=='button_ok':
            if ok is not None: raise ValueError('NATIVE_SELECTION_DUPLICATE_OK')
            ok=option; continue
        if value=='button_cancel': continue
        key=identity(value)
        if key in entities: raise ValueError('NATIVE_SELECTION_AMBIGUOUS_IDENTITY')
        entities[key]=option
    if maximum>len(entities): raise ValueError('NATIVE_SELECTION_INVALID_BOUNDS')
    selected=set()
    for value in chosen:
        key=identity(value)
        if key in selected or key not in entities or entities[key]['display']!=value: raise ValueError('NATIVE_SELECTION_CHOSEN_NOT_CURRENT_OR_UNIQUE')
        selected.add(key)
    # Native hasEnoughTargets may authorize a special completion below min.
    if ok is not None: return [ok['token']]
    if len(selected)>=minimum:
        raise ValueError('NATIVE_SELECTION_NO_ENABLED_COMMIT')
    for key,option in entities.items():
        if key not in selected: return [option['token']]
    raise ValueError('NATIVE_SELECTION_NO_UNCHOSEN_ENTITY')


def pick(frame):
    q=frame['question']; options=q['choices']; kind=q['kind']; actor=q['actor_id']; info=frame['info']
    hand={c['card_id'] for p in frame['state']['players'] if p['player_id']==actor for c in p['zones']['Hand']['visible_cards']}
    def find(test): return next((x for x in options if test(x['display'])),None)
    ok=find(lambda d:d=='button_ok'); cancel=find(lambda d:d=='button_cancel')
    if kind.startswith('input:'):
        subtype=kind[6:]
        if 'stack_selection' in info or subtype=='InputSelectStackItems' or any(isinstance(x['display'],dict)and 'stack_id'in x['display']for x in options):
            return pick_stack_selection(frame)
        if 'selection' in info or subtype in ('InputSelectEntitiesFromList','InputSelectCardsFromList'):
            return pick_selection(frame)
        if subtype=='InputAttack':
            attacker=find(lambda x:isinstance(x,dict) and 'card_id' in x)
            if attacker and cancel and 'alpha' in info.get('cancel_label','').lower(): return [cancel['token']]
            return [ok['token']] if ok else [options[0]['token']]
        if subtype=='InputPassPriority':
            window=(frame['state']['turn'],frame['state']['phase'])
            def available(x): return isinstance(x,dict) and x.get('card_id') in hand and x['card_id'] not in tried[window]
            card=find(lambda x:available(x) and 'Land' in x.get('face',{}).get('type',''))
            if card is None: card=find(lambda x:available(x) and 'Creature' in x.get('face',{}).get('type',''))
            if card is None: card=find(available)
            if card:
                tried[window].add(card['display']['card_id'])
                return [card['token']]
        if subtype.startswith('InputPayMana'):
            if ok: return [ok['token']]
            if cancel: return [cancel['token']]
        if subtype=='InputSelectTargets':
            target=find(lambda x:isinstance(x,dict) and 'player_id' in x and x['player_id']!=actor)
            if target is None: target=find(lambda x:isinstance(x,dict) and 'card_id' in x and x.get('controller_id')!=actor)
            if target: return [target['token']]
        if ok: return [ok['token']]
        card=find(lambda x:isinstance(x,dict) and 'card_id' in x)
        return [(card or cancel or options[0])['token']]
    n=q['min']
    if kind=='getChoices': n=max(n,min(q['max'],1))
    if kind=='chooseSingleEntityForEffect': n=1 if options else 0
    return [x['token'] for x in options[:n]]


def tokens_for(frame, ticket):
    if frame['replay_offer'] != ticket['offer']:
        raise ValueError('OFFER_MISMATCH')
    tokens, used = [], set()
    for selected in ticket['selected']:
        matches = [(i, x) for i, x in enumerate(frame['question']['choices'])
                   if i not in used and x['display'] == selected]
        if len(matches) != 1:
            raise ValueError('AMBIGUOUS_OR_ABSENT_CURRENT_NATIVE_CHOICE')
        i, value = matches[0]
        used.add(i)
        tokens.append(value['token'])
    return tokens
