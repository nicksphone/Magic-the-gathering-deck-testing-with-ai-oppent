"""Deterministic printed-role advice from completed owned/public game facts."""
from collections import Counter
from dataclasses import replace
import re
from types import SimpleNamespace

from ai.deck_analysis import _cmc
from decks.sideboard import _to_counter
from knowledge.profiles import _face, complete_self_counter_prohibition
from knowledge.service import tags_for, estimate_for
from rules_engine.card_types import is_land_card, printed_card_types
from rules_engine.mana import _land_colors, parse_mana_cost
from rules_engine.printed_body import printed_body_gaps


def _view(row):
    data = dict(row)
    data['name'] = data.pop('card_name', '')
    data.setdefault('types', list(printed_card_types(data.get('type_line', ''))))
    return SimpleNamespace(**data)


def _land(row):
    return is_land_card({**row, 'name': row.get('card_name', '')})


def route_for(my_deck, game_events):
    if game_events.get('qualified') is not True:
        return 'decline'
    main, side = my_deck['mainboard'], my_deck['sideboard']
    if sum(_to_counter(main).values()) < 60:
        return 'decline'
    _to_counter(side)
    relevant = [row for row in main if row['card_name'] in game_events['held_counts'] and not _land(row)]
    relevant += [row for row in side if not _land(row)]
    if all(tags_for(_view(row)).source == 'persisted' and estimate_for(_view(row)) is not None
           for row in relevant):
        return 'knowledge'
    if relevant and all(row.get('match_ready') is True
            and row.get('card_data_sources') == ['offline_seed'] for row in relevant):
        return 'legacy'  # Known canonical offline data only, never an unknown-row escape.
    return 'decline'


def _profile(row):
    card = _view(row)
    if tags_for(card).source != 'persisted' or estimate_for(card) is None:
        return None
    snapshot = card.knowledge_snapshot
    index = card.selected_face_index if hasattr(card, 'selected_face_index') else None
    if snapshot['faces']:
        if index is None:
            # Never invent an unselected sideboard face for the caller.
            return None
        inputs = snapshot['estimates']['faces'][index]['printed_inputs']
    else:
        inputs = snapshot['estimates']['root']['printed_inputs']
    profile = _face(inputs, index, None)
    selected = SimpleNamespace(**{**inputs, 'types': printed_card_types(inputs['type_line'])})
    if printed_body_gaps(selected) or profile.known_gaps or set(profile.limitations) & {
            'unaccounted_raw_paragraph',
            'dynamic_or_unknown_numeric_payload'}:
        return None
    covered = []
    for spec in profile.ability_specs:
        if spec['kind'] != 'spell_effect' or spec['condition'] or spec['cost']:
            return None
        if spec['effects']:
            covered.append(spec)
            continue
        # Missing estimator effects need positive whole raw-clause coverage;
        # no prefix, erased reminder or physical target supplies that proof.
        start, end = spec['source_span']
        body = inputs['oracle_text'][start:end].strip()
        if not set(profile.types) & {'instant', 'sorcery'}:
            return None
        if complete_self_counter_prohibition(body, inputs['name']):
            covered.append(spec)
            continue
        if body != inputs['oracle_text'].strip():
            return None
        from rules_engine.oracle_effects import COUNTER_TARGET_SPELL_RE, infer_target_restrictions
        # Complete native counter grammar; never accept its prefix-search path.
        if body.endswith('.') and COUNTER_TARGET_SPELL_RE.fullmatch(body[:-1]):
            key = 'counter_spell'
            payload = {'target_kind': 'noncreature' if 'noncreature' in body.lower() else 'any'}
        elif re.fullmatch(r'destroy target nonartifact creature\.', body, re.I):
            key = 'destroy_permanent'
            # Symbolic domain projection, not rewritten Oracle or runtime state.
            payload = {**infer_target_restrictions(None, 'target creature', 1),
                       **infer_target_restrictions(None, body, 1)}
        else:
            return None
        covered.append({**spec, 'effects': [{'effect_key': key, 'payload': payload}]})
    return replace(profile, ability_specs=tuple(covered))


def _fit(profile, events, printed_body=None):
    # Only typed compiled spell effects authorize role matching. Conditional,
    # activated or triggered payoffs cannot masquerade as unconditional answers.
    effects = [effect['effect_key'] for spec in profile.ability_specs
               if spec['kind'] == 'spell_effect' and not spec['condition']
               for effect in spec['effects']]
    observed = {kind.lower() for kind in events['observed_types']}
    if ('sweeper' in profile.tags and 'destroy_all_creatures' in effects
            and events['observed_creature_count'] >= 6
            and events['own_creature_count'] < events['observed_creature_count']):
        return 3
    removal = ('removal' in profile.tags and set(effects) & {
            'destroy_permanent', 'exile', 'return_permanent_to_hand'}
            and observed & {'creature', 'artifact', 'enchantment', 'planeswalker'})
    counter = 'counter' in profile.tags and 'counter_spell' in effects and observed
    if (removal or counter) and printed_body is not None:
        from rules_engine.oracle_effects import infer_target_restrictions
        # The existing shared domain reader is stateless for these closed simple
        # removal/counter instructions. No artificial MatchState/StackItem/ID.
        try:
            restrictions = infer_target_restrictions(None, printed_body, 1)
        except (AttributeError, TypeError):
            return 0  # A context-dependent transport is unavailable, not guessed.
        if not set(restrictions) <= {'allowed_types', 'exclude_types'}:
            return 0
        for spec in profile.ability_specs:
            for effect in spec['effects']:
                domain = effect['payload']
                if set(domain) == {'allowed_types', 'exclude_types'}:
                    allowed = set(domain['allowed_types'])
                    if 'allowed_types' in restrictions:
                        allowed &= set(restrictions['allowed_types'])
                    restrictions = {**restrictions, 'allowed_types': sorted(allowed),
                        'exclude_types': sorted(set(restrictions.get('exclude_types', []))
                                                | set(domain['exclude_types']))}
        default = {'artifact', 'battle', 'creature', 'enchantment', 'planeswalker'}
        if counter:
            default |= {'instant', 'sorcery'}
        allowed = {kind.lower() for kind in restrictions.get('allowed_types', default)}
        excluded = {kind.lower() for kind in restrictions.get('exclude_types', [])}
        for types in events.get('public_type_groups', []):
            kinds = {kind.lower() for kind in types}
            if kinds & allowed and not kinds & excluded:
                return 2 if removal else 1
    return 0


def plan_swaps(my_deck, opp_deck, game_events):
    """Return <=3 existing stock-unit swaps; opp_deck is public facts, not a decklist."""
    if route_for(my_deck, game_events) != 'knowledge' or not my_deck['sideboard']:
        return []
    main, side = my_deck['mainboard'], my_deck['sideboard']
    sources = Counter()
    for row in main:
        if _land(row):
            for color in _land_colors(row['card_name'], row.get('type_line'), row.get('oracle_text')):
                sources[color] += row['quantity']
    incoming = []
    for row in side:
        if _land(row):
            continue
        profile = _profile(row)
        if profile is None:
            continue
        req = parse_mana_cost(row.get('mana_cost') or '')
        if any(sources[color] < max(4, amount*4) for color, amount in req.items()
               if color != 'generic' and amount):
            continue
        fit = _fit(profile, opp_deck, row.get('oracle_text'))
        if fit:
            incoming.append((fit, row))
    cuts = []
    for row in main:
        key = row['card_name']
        if (_land(row) or key in game_events['protected_stock']
                or game_events['held_counts'].get(key, 0) < 1):
            continue
        # A cut is supported by actual physical inactivity, not a predicted
        # payoff for effects that were never played. Canonical surface binding
        # remains mandatory; this does not admit the card to a new engine path.
        card = _view(row)
        if tags_for(card).source == 'persisted' and estimate_for(card) is not None:
            cuts.append(row)
    cuts.sort(key=lambda row: (-_cmc(row.get('mana_cost') or ''), row['card_name']))
    incoming.sort(key=lambda item: (-item[0], item[1]['card_name']))
    current = _to_counter(main)
    used, added = Counter(), Counter()
    result = []
    for _, row in incoming:
        key = row['card_name']
        for _ in range(row['quantity']):
            if len(result) == 3:
                return result
            if current[key] + added[key] >= 4:
                break
            cut = next((cut for cut in cuts if cut['card_name'] != key
                and used[cut['card_name']] < min(cut['quantity'], game_events['held_counts'][cut['card_name']])), None)
            if cut is None:
                break
            used[cut['card_name']] += 1
            added[key] += 1
            result.append({'out': cut['card_name'], 'in': key})
    return result
