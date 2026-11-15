"""Complete fixed-condition self-copy instructions and retained native objects."""
import re

from game_state.state import Zone,object_incarnation
from rules_engine.card_types import graveyard_card_types,is_token_card

KEY='copy_self_from_graveyard'
PERMANENT_TYPES={'Artifact','Battle','Creature','Enchantment','Land','Planeswalker'}
TAIL=(r' becomes a copy of target permanent card in your graveyard until end of turn\.\s+'
      r'Activate only if there are four or more card types among cards in your graveyard\.')
SELF=r'this (?:permanent|land|creature|artifact|enchantment|planeswalker|battle)'


def compile_instruction(text,name):
    names='|'.join(re.escape(value) for value in dict.fromkeys((name,name.split(',',1)[0])) if value)
    subject=SELF+('|' + names if names else '')
    if re.fullmatch(r'(?:'+subject+r')'+TAIL,(text or '').strip(),re.I):
        return {'minimum_types':4}
    return None


def looks_like(text):
    return re.search(r'\bbecomes a copy of target\b[^\n]*\bgraveyard\b',text or '',re.I) is not None


def target_hints(state,text,controller):
    # The target domain of a retained complete instruction does not change when
    # an earlier copy changes the source's current name. Creation still requires
    # compile_instruction's actual self reference.
    if not re.fullmatch(r'[^:\n]+?'+TAIL,(text or '').strip(),re.I):
        return None
    return {'graveyard_card_targets':[
        {'id':cid,'name':state.cards[cid].name,'owner':controller,'controller':state.cards[cid].controller}
        for cid in state.players[controller].graveyard if eligible_target(state,controller,cid)]}


def eligible_target(state,controller,cid):
    card=state.cards.get(cid)
    return (type(controller) is int and controller in state.players and card is not None
            and card.owner==controller and card.zone==Zone.GRAVEYARD
            and cid in state.players[controller].graveyard and not is_token_card(card)
            and bool(PERMANENT_TYPES.intersection(card.types)))


def activation_available(state,controller,ability,name):
    instruction=compile_instruction(ability.get('raw_effect_text',ability.get('text','')),name)
    return (instruction is None or type(controller) is int and controller in state.players
            and len(graveyard_card_types(state,[controller]))>=instruction['minimum_types'])


def resolve(state,controller,payload):
    from rules_engine.action_validation import ActionRejected
    from rules_engine.targeting import validate_announced_target_references,announced_target_reference_matches
    from rules_engine.copiable_values import apply,values
    source=state.cards.get(payload.get('source_card_id') or payload.get('__source_card_id'))
    reference=payload.get('__activation_source_reference')
    if (type(reference) is not dict or set(reference)!={'incarnation','zone_change_sequence'}
            or any(type(value) is not int or value<0 for value in reference.values())):
        raise ActionRejected('Self-copy requires its retained activation source')
    if (source is None or source.zone!=Zone.BATTLEFIELD
            or object_incarnation(source)!=reference['incarnation']
            or source.zone_change_sequence!=reference['zone_change_sequence']):
        return
    target=payload.get('target_card_id')
    announced=payload.get('__announced_targets')
    references=payload.get('__announced_target_references')
    validate_announced_target_references(announced,references)
    if (not eligible_target(state,controller,target)
            or not announced_target_reference_matches(state,references,('target_card_id',),target)):
        return
    apply(source,values(state.cards[target]),until_end_of_turn=True)
