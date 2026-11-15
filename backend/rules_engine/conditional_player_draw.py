"""Complete color-quality player draws evaluated when the instruction resolves."""
import re

from game_state.state import Zone
from rules_engine.colors import card_color_symbols
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types


COLORS={'white':'W','blue':'U','black':'B','red':'R','green':'G'}
QUALITIES=tuple(COLORS)+('monocolored','multicolored','colorless')
INSTRUCTION=re.compile(
    r'Each player who controls a (?P<quality>'+ '|'.join(QUALITIES)
    +r') creature draws a card\.?',re.I)


def compile_instruction(text):
    match=INSTRUCTION.fullmatch(without_reminder_text(text or '').strip())
    if match is None:return None
    return 'conditional_player_draw',{'quality':match['quality'].lower()}


def matches_quality(state,card,quality):
    colors=card_color_symbols(card,state)
    if quality in COLORS:return COLORS[quality] in colors
    if quality=='monocolored':return len(colors)==1
    if quality=='multicolored':return len(colors)>=2
    return not colors


def resolve_instruction(state,controller,payload):
    quality=payload['quality']
    if type(quality) is not str or quality not in QUALITIES:
        raise ValueError('Invalid conditional player draw quality')
    order=[state.active_player]+[p for p in state.players if p!=state.active_player]
    # Determine all recipients once, before any draw or replacement can pause.
    eligible=[p for p in order if any(
        (card:=state.cards.get(cid)) is not None and card.zone==Zone.BATTLEFIELD
        and card.controller==p and 'Creature' in effective_types(state,card)
        and matches_quality(state,card,quality)
        for cid in state.players[p].battlefield)]
    from effects.registry import resolve_effect
    resolve_effect(state,controller,'effect_sequence',{**payload,'effects':[
        {'effect_key':'draw_cards','payload':{'target_player':p,'amount':1}}
        for p in eligible]})
