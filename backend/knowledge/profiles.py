"""Versioned printed-data estimates, never legal-action or measured-quality facts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math

from ai.deck_analysis import _cmc, analyze_deck
from card_data.tactical import _rules_surface, canonical_tactical_tags, printed_card_types, tactical_clauses
from effects.registry import EFFECT_HANDLERS
from knowledge.mechanic_metadata import mechanic_metadata
from rules_engine.closed_loyalty import compile_instruction
from rules_engine.continuous import _attached_keywords
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.oracle_effects import (
    DAMAGE_RE, TOKEN_COUNT_RE, TOKEN_PT_RE, _token_base_quantity,
    compile_draw_life_instruction, complete_stack_instruction_coverage,
)
from rules_engine.protection import extract_protection_keywords, hexproof_variants

SCHEMA_VERSION = 1
ESTIMATOR_VERSION = 'deterministic-tactical-v1'
MAX_TEXT = 16384
MAX_FACES = 16
MAX_CORPUS = 1024


@dataclass(frozen=True)
class AnswerRoute:
    effect_key: str
    target_zone: str
    targeted: bool
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class FaceProfile:
    face_index: int | None
    types: tuple[str, ...]
    tags: tuple[str, ...]
    play_value: float
    threat_level: int
    answerable_by: tuple[str, ...]
    cast_windows: tuple[str, ...]
    etb_impact: float | None
    attack_on_entry_hint: bool
    answer_routes: tuple[AnswerRoute, ...]
    ability_specs: tuple[dict, ...]
    known_gaps: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class TacticalProfile(FaceProfile):
    faces: tuple[FaceProfile, ...]
    context: dict
    input_sha256: str
    schema_version: int = SCHEMA_VERSION
    estimator_version: str = ESTIMATOR_VERSION


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _raw(card):
    if isinstance(card, dict):
        raw = deepcopy(card)
    else:
        raw = {key: deepcopy(getattr(card, key)) for key in (
            'name','oracle_text','type_line','types','mana_cost','power','toughness',
            'keywords','card_faces','scryfall_id','oracle_id') if hasattr(card, key)}
    text, faces = raw.get('oracle_text'), raw.get('card_faces')
    if text is not None and (not isinstance(text, str) or len(text) > MAX_TEXT):
        raise ValueError('Invalid or oversized Oracle text')
    if faces is not None and (not isinstance(faces, list) or len(faces) > MAX_FACES
            or any(not isinstance(face, dict) for face in faces)):
        raise ValueError('Invalid or oversized card faces')
    return raw


def _number(value):
    if type(value) not in (int, float, str):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    if not math.isfinite(result):
        raise ValueError('Nonfinite numeric characteristic')
    return result


def _effects(body, name, limits):
    # Entire effect body must be accounted for before extracting any payoff.
    steps = compile_instruction(body, name)
    if steps is None:
        direct = complete_stack_instruction_coverage(type('PrintedSurface', (),
            {'oracle_text': body, 'name': name})()) if not any(c in body for c in '()"\u201c\u201d') else None
        if direct is not None:
            return [{'effect_key': direct['effect_key'], 'payload': deepcopy(direct['payload'])}]
        count = TOKEN_COUNT_RE.search(body)
        if count is not None and count[1].lower() == 'x':
            limits.add('dynamic_or_unknown_numeric_payload')
        limits.add('uncompiled_effect_surface')
        return []
    effects = []
    for step in steps:
        key, data = step['effect_key'], deepcopy(step.get('data', {}))
        instruction = step.get('instruction', '').lower()
        draw = compile_draw_life_instruction(instruction+'.') if instruction else None
        if draw:
            effects.append({'effect_key': draw[0], 'payload': deepcopy(draw[1])})
            continue
        if key == 'create_token':
            count = _token_base_quantity(instruction, {}, 0)
            pt = TOKEN_PT_RE.search(instruction)
            if count is None or pt is None:
                limits.add('dynamic_or_unknown_numeric_payload')
                continue
            data = {'amount': count, 'power': int(pt[1]), 'toughness': int(pt[2])}
        elif key == 'deal_damage' and instruction:
            amount = DAMAGE_RE.search(instruction)
            if amount is None:
                limits.add('dynamic_or_unknown_numeric_payload')
                continue
            data['amount'] = int(amount[1])
        effects.append({'effect_key': key, 'payload': data})
    if not effects and (' x ' in ' '+body.lower()+' '):
        limits.add('dynamic_or_unknown_numeric_payload')
    return effects


def _impact(effects):
    total = 0.0
    for effect in effects:
        key, data = effect['effect_key'], effect['payload']
        amount = data.get('amount')
        if key == 'effect_sequence':
            total += _impact(data.get('effects', []))
        elif key in ('destroy_permanent','exile','destroy_all_creatures','counter_spell'):
            total += 1.0
        elif type(amount) in (int, float) and amount >= 0:
            if key == 'draw_cards': total += .8*amount
            elif key == 'deal_damage': total += .4*amount
            elif key in ('gain_life','lose_life','mill_cards'): total += .1*amount
            elif key == 'create_token': total += .2*amount*(data.get('power', 0)+data.get('toughness', 0))
    return total


def _routes(types, keywords, uncounterable):
    routes = []
    def add(key, zone, targeted, *conditions):
        if key in EFFECT_HANDLERS:
            routes.append(AnswerRoute(key, zone, targeted,
                ('actual_effect_target_domain_and_current_rules_must_be_checked', *conditions)))
    permanent = bool(set(types) & {'creature','artifact','enchantment','land','planeswalker','battle'})
    if permanent:
        for key in ('destroy_permanent','exile','return_permanent_to_hand'):
            if 'shroud' in keywords or key == 'destroy_permanent' and 'indestructible' in keywords:
                continue
            add(key, 'battlefield', True, *(['targeter_is_controller'] if 'hexproof' in keywords else []))
    if 'creature' in types:
        if 'indestructible' not in keywords: add('destroy_all_creatures', 'battlefield', False)
        add('exile_all_creatures', 'battlefield', False)
    if types and 'land' not in types and not uncounterable:
        add('counter_spell', 'stack', True, 'object_is_genuine_spell')
    return tuple(routes)


def _face(raw, index, curve):
    types = tuple(sorted(printed_card_types(raw.get('type_line', ''), raw.get('types'))))
    text, name = raw.get('oracle_text') or '', raw.get('name') or ''
    metadata = mechanic_metadata(raw)
    tags = tuple(canonical_tactical_tags(raw)['tactical_tags'])
    limits = {'heuristic_estimate_not_measured_strength','priority_timing_costs_targets_not_evaluated',
              'incoming_source_quality_and_protection_must_be_checked','printed_not_current_continuous_characteristics',
              'no_known_gap_is_not_rules_certification'}
    clauses = tactical_clauses(text, raw.get('type_line', ''), raw.get('types'))
    cursor, accounted = 0, True
    for clause in clauses:
        if text[cursor:clause['start']].strip(): accounted = False
        cursor = clause['end']
    if text[cursor:].strip(): accounted = False
    if not accounted: limits.add('unaccounted_raw_paragraph')
    keywords, specs = set(), []
    etb, engine = 0.0, False
    for clause in clauses:
        if clause['kind'] == 'static_or_keyword':
            keywords.update(_attached_keywords(_rules_surface(clause['text']).lower().strip().rstrip('.')) or [])
            keywords.update(hexproof_variants(clause['text']))
            keywords.update(extract_protection_keywords(clause['text']))
        body = clause['text'].strip()
        if clause['kind'] == 'triggered': body = body.partition(',')[2].strip()
        elif clause['kind'] == 'activated': body = body.partition(':')[2].strip()
        effects = _effects(body, name, limits) if accounted and clause['kind'] in ('spell_effect','triggered','activated') else []
        spec = {'kind': clause['kind'], 'condition': clause['condition'], 'cost': clause['cost'],
                'source_span': [clause['start'], clause['end']], 'effects': effects}
        specs.append(spec)
        if clause['kind'] == 'triggered':
            engine |= bool(effects)
            limits.add('trigger_conditions_and_frequency_not_evaluated')
            own_entry = {f'when {source} enters{suffix}' for source in (
                name.lower(), 'this creature','this permanent','this artifact','this enchantment')
                for suffix in ('', ' the battlefield')}
            if clause['condition'].strip() in own_entry:
                etb = etb + _impact(effects) if effects and etb is not None else None
    # Same complete self-prohibition scope as targeting.spell_cant_be_countered;
    # no battlefield/global permissions or conditions are inferred from this trait.
    uncounterable = any(c['text'].strip().lower().rstrip('.') in {
        f"{source} {verb} be countered" for source in ('this spell', name.lower())
        for verb in ("can't", 'cannot')} for c in clauses)
    routes = _routes(types, keywords, uncounterable)
    available = tuple(sorted({r.effect_key for r in routes if 'targeter_is_controller' not in r.conditions}))
    land = 'land' in types
    windows = ('land_play',) if land else ('main_phase','instant_window') if 'instant' in types or 'flash' in keywords else ('main_phase',) if types else ()
    mv = _cmc(raw.get('mana_cost') or '')
    pt = sum(max(0, n) for value in (raw.get('power'), raw.get('toughness')) if (n := _number(value)) is not None)
    payoff = sum(_impact(s['effects']) for s in specs)
    fit = 1.0 if curve is None else 2.0-min(2.0, abs(mv-curve))
    score = 0.0 if land and 'creature' not in types else round(min(10.0, 3+fit+.15*pt+min(3.0, payoff/max(1,mv))+.5*engine), 3)
    threat = 0 if land and 'creature' not in types or not types else 3 if set(tags)&{'sweeper','mill','drain'} else 2 if mv >= 4 or (etb or 0) >= 4 else 1
    gaps = tuple(known_unsupported_mechanics(text, card_name=name, canonical_context=raw))
    if any(e['family']=='cast_permission' for e in metadata['evidence']): limits.add('contextual_cast_permission_not_evaluated')
    return FaceProfile(index, types, tags, score, threat, available, windows, etb,
        'haste' in keywords, routes, tuple(specs), gaps, tuple(sorted(limits)))


def derive_profile(card, corpus=(), *, archetype=None):
    raw = _raw(card)
    corpus = tuple(corpus)
    if len(corpus) > MAX_CORPUS: raise ValueError('Corpus limit exceeded')
    deck = [{'quantity': item.get('quantity', 1), 'card_metadata': _raw(item.get('card_metadata') or item)} for item in corpus]
    if any(type(item['quantity']) is not int or not 0 <= item['quantity'] <= 1000 for item in deck):
        raise ValueError('Invalid corpus quantity')
    analysis = analyze_deck(deck) if deck else None
    costs = [(_cmc(item['card_metadata'].get('mana_cost') or ''), item['quantity']) for item in deck
             if 'land' not in printed_card_types(item['card_metadata'].get('type_line', ''))]
    count = sum(q for _, q in costs)
    curve = sum(mv*q for mv,q in costs)/count if count else None
    context = {'mode': 'supplied_archetype' if archetype and deck else 'supplied_corpus' if deck else 'printed_only',
        'archetype': archetype, 'archetype_verification': 'caller_declared_not_verified',
        'corpus_fingerprint': _hash(deck), 'curve_nonland_mean': curve,
        'deck_analysis_primary_archetype_estimate': analysis['primary_archetype'] if analysis else None}
    faces = tuple(_face(_raw(face), i, curve) for i,face in enumerate(raw.get('card_faces') or []))
    root_types = printed_card_types(raw.get('type_line', ''), raw.get('types'))
    combined_parent = '//' in (raw.get('type_line') or '')
    main = faces[0] if faces and (combined_parent or not root_types) else _face(raw, None, curve)
    return TacticalProfile(**vars(main), faces=faces, context=context, input_sha256=_hash(raw))


def profile_payload(profile):
    """Copied JSON primitives, including lists for existing repository fields."""
    return json.loads(json.dumps(asdict(profile), sort_keys=True, allow_nan=False))


def merge_profile_payload(existing_profiles, derived):
    if not isinstance(existing_profiles, dict):
        raise ValueError('Existing profiles must be an object')
    result = deepcopy(existing_profiles)
    namespace = result.get('tactical_profile', {})
    if not isinstance(namespace, dict):
        raise ValueError('Existing tactical namespace is opaque')
    namespace.update(profile_payload(derived))
    result['tactical_profile'] = namespace
    return result


merge_profile = merge_profile_payload


def play_value(card, corpus=(), *, archetype=None):
    return derive_profile(card, corpus, archetype=archetype).play_value


def threat_level(card): return derive_profile(card).threat_level
def answerable_by(card): return derive_profile(card).answerable_by
def cast_windows(card): return derive_profile(card).cast_windows
def etb_impact(card): return derive_profile(card).etb_impact
