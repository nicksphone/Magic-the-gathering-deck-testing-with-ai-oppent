"""Supported static declaration limits; independent effects intersect, not add."""
import re

from game_state.state import Zone
from rules_engine.static_conditions import number


def parse_declaration_limit(clause):
    match = re.fullmatch(r'no more than (\w+) creatures? can (attack|block)( you)? each combat', clause)
    if not match or number(match[1]) is None or match[2] == 'block' and match[3]:
        return None
    return {'kind': match[2], 'maximum': number(match[1]), 'scope': 'you' if match[3] else 'all'}


def declaration_limit_view(state, kind):
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    sources = [(state.cards[cid], clause, spec)
               for player in state.players.values() for cid in player.battlefield
               if state.cards[cid].zone == Zone.BATTLEFIELD
               for clause in static_clauses(state.cards[cid].oracle_text)
               if (spec := parse_declaration_limit(clause)) and spec['kind'] == kind]
    if not sources:
        return {'maximum': None, 'target_limits': {}, 'sources': []}
    losses = _printed_ability_loss_sources(state)
    maximum, targets, records = None, {}, []
    for source, clause, spec in sources:
        if printed_abilities_suppressed(state, source.id, losses=losses):
            continue
        cap = spec['maximum']
        if spec['scope'] == 'all':
            maximum = cap if maximum is None else min(maximum, cap)
        elif source.controller != state.active_player:
            target = f'player:{source.controller}'
            targets[target] = min(targets.get(target, cap), cap)
        else:
            continue
        records.append({**spec, 'source_id': source.id, 'source_name': source.name, 'clause': clause,
                        'target': f'player:{source.controller}' if spec['scope'] == 'you' else None})
    return {'maximum': maximum, 'target_limits': targets, 'sources': records}


def attackers_within_limits(state, ids, targets=None):
    view = declaration_limit_view(state, 'attack')
    if view['maximum'] is not None and len(ids) > view['maximum']:
        return False
    targets = targets or {}
    default = f'player:{3-state.active_player}'
    return all(sum(targets.get(cid, default) == target for cid in ids) <= cap
               for target, cap in view['target_limits'].items())


def blockers_within_limits(state, blocks):
    cap = declaration_limit_view(state, 'block')['maximum']
    return cap is None or len({bid for ids in blocks.values() for bid in ids}) <= cap
