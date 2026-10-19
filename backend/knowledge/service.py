"""Match-frozen printed tags, not rules permissions or a source authority registry."""
from copy import deepcopy
from dataclasses import dataclass
import math
import re

from card_data.tactical import printed_card_types, tactical_tags
from knowledge.profiles import (AnswerRoute, ESTIMATOR_VERSION, MAX_FACES, MAX_TEXT,
                               SCHEMA_VERSION, _face, _hash, _number, derive_profile, profile_payload)


SURFACE_FIELDS = {'oracle_text', 'type_line', 'mana_cost', 'types', 'tags'}
SNAPSHOT_FIELDS = {'schema_version', 'estimator_version', 'scryfall_id', 'oracle_id',
                   'source_sha256', 'layout', 'root', 'faces', 'rulings_pending',
                   'limitations', 'snapshot_sha256'}
FRONT_LAYOUTS = {'transform', 'modal_dfc', 'adventure', 'reversible_card', 'meld', 'flip'}
IDENTITY = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
DIGEST = re.compile(r'[0-9a-f]{64}')
PRINTED_INPUTS = {'name', 'oracle_text', 'type_line', 'mana_cost', 'power', 'toughness', 'layout'}


@dataclass(frozen=True)
class TagResult:
    tags: frozenset[str]
    source: str
    reason: str = ''
    face_index: int | None = None


@dataclass(frozen=True)
class ThreatEstimate:
    tier: int
    routes: tuple[AnswerRoute, ...]
    limits: tuple[str, ...]
    play_value: float | None = None
    context: dict | None = None


def _printed_inputs(raw):
    # Typed coverage (e.g. paired kicker) needs actual layout/printed PT too.
    return {key: deepcopy(raw[key]) for key in PRINTED_INPUTS if key in raw} | {
        key: raw.get(key) or '' for key in ('name', 'oracle_text', 'type_line', 'mana_cost')}


def _estimate_fields(profile):
    return {'tier': profile['threat_level'], 'routes': deepcopy(profile['answer_routes']),
            'limits': sorted(set(profile['limitations']) | {'known_gap:' + gap for gap in profile['known_gaps']})}


def _valid_estimates(value, surfaces, semantic):
    if (type(value) is not dict or type(value.get('transport_version')) is not int
            or value['transport_version'] not in (1, 2)
            or set(value) != ({'transport_version', 'root', 'faces'} |
                             ({'context'} if value['transport_version'] == 2 else set()))
            or type(value['faces']) is not list or len(value['faces']) != len(surfaces) - 1):
        return False
    context = value.get('context')
    if value['transport_version'] == 2:
        if (type(context) is not dict or set(context) != {'mode', 'archetype', 'archetype_verification',
                'corpus_fingerprint', 'curve_nonland_mean', 'deck_analysis_primary_archetype_estimate'}
                or type(context['mode']) is not str or context['mode'] not in ('printed_only', 'supplied_corpus', 'supplied_archetype')
                or type(context['archetype_verification']) is not str or context['archetype_verification'] != 'caller_declared_not_verified'
                or any(item is not None and (type(item) is not str or len(item) > MAX_TEXT)
                       for item in (context['archetype'], context['deck_analysis_primary_archetype_estimate']))
                or type(context['corpus_fingerprint']) is not str
                or not DIGEST.fullmatch(context['corpus_fingerprint'])):
            return False
        curve = context['curve_nonland_mean']
        if curve is not None:
            try:
                if type(curve) not in (int, float) or not math.isfinite(curve) or curve < 0:
                    return False
            except OverflowError:
                return False
        if context['mode'] == 'printed_only':
            if curve is not None or context['corpus_fingerprint'] != _hash([]) or context['deck_analysis_primary_archetype_estimate'] is not None:
                return False
        elif (context['corpus_fingerprint'] == _hash([])
              or bool(context['archetype']) != (context['mode'] == 'supplied_archetype')):
            return False
    for entry, surface in zip([value['root'], *value['faces']], surfaces):
        if type(entry) is not dict or set(entry) != ({'tier', 'routes', 'limits', 'printed_inputs'} |
                ({'play_value'} if value['transport_version'] == 2 else set())):
            return False
        if value['transport_version'] == 2 and (type(entry['play_value']) is not float
                or not math.isfinite(entry['play_value']) or not 0 <= entry['play_value'] <= 10):
            return False
        if type(entry['tier']) is not int or not 0 <= entry['tier'] <= 3:
            return False
        inputs = entry['printed_inputs']
        if (type(inputs) is not dict or not {'name', 'oracle_text', 'type_line', 'mana_cost'} <= set(inputs)
                or not set(inputs) <= PRINTED_INPUTS
                or any(type(item) is not str and item is not None for item in inputs.values())
                or any(len(item) > MAX_TEXT for item in inputs.values() if type(item) is str)):
            return False
        if any(inputs[key] != surface[key] for key in ('oracle_text', 'type_line', 'mana_cost')):
            return False
        if semantic and _surface(inputs) != surface:
            return False
        limits = entry['limits']
        if (type(limits) is not list or len(limits) > 128
                or any(type(item) is not str or len(item) > 256 for item in limits)
                or limits != sorted(set(limits))):
            return False
        routes = entry['routes']
        if type(routes) is not list or len(routes) > 16:
            return False
        for route in routes:
            if (type(route) is not dict or set(route) != {'effect_key', 'target_zone', 'targeted', 'conditions'}
                    or any(type(route[key]) is not str or len(route[key]) > 64 for key in ('effect_key', 'target_zone'))
                    or type(route['targeted']) is not bool or type(route['conditions']) is not list
                    or len(route['conditions']) > 16
                    or any(type(item) is not str or len(item) > 128 for item in route['conditions'])):
                return False
        if semantic:
            try:
                expected = _estimate_fields(profile_payload(derive_profile(inputs)))
                if expected != {key: entry[key] for key in ('tier', 'routes', 'limits')}:
                    return False
                if context is not None and entry['play_value'] != _face(inputs, None, context['curve_nonland_mean']).play_value:
                    return False
            except (KeyError, TypeError, ValueError, AttributeError):
                return False
    return True


def _estimates_for(raw, stored, surfaces):
    # The same estimator, not a second rules parser or a row's numeric authority.
    canonical = profile_payload(derive_profile(raw))
    faces = raw.get('card_faces') or []
    main = faces[0] if faces and canonical['face_index'] == 0 else raw
    entries = []
    for inputs, cached, expected in zip([main, *faces], [stored, *stored['faces']],
                                       [canonical, *canonical['faces']]):
        entry = _estimate_fields(cached)
        if _hash(entry) != _hash(_estimate_fields(expected)):
            return None
        entry['printed_inputs'] = _printed_inputs(inputs)
        entries.append(entry)
    result = {'transport_version': 1, 'root': entries[0], 'faces': entries[1:]}
    if not _valid_estimates(result, surfaces, True):
        return None
    # Context is existing caller-declared provenance, not a corpus certificate.
    # Invalid additive advice leaves the valid v1 tier/routes carrier intact.
    candidate = deepcopy(result)
    candidate.update(transport_version=2, context=deepcopy(stored.get('context')))
    for entry, cached in zip([candidate['root'], *candidate['faces']], [stored, *stored['faces']]):
        entry['play_value'] = deepcopy(cached.get('play_value'))
    if _valid_estimates(candidate, surfaces, True):
        curve = candidate['context']['curve_nonland_mean']
        if all(entry['play_value'] == _face(inputs, None, curve).play_value
               for entry, inputs in zip([candidate['root'], *candidate['faces']], [main, *faces])):
            return candidate
    return result


def _surface(raw):
    fields = {key: raw.get(key) or '' for key in ('oracle_text', 'type_line', 'mana_cost')}
    fields['types'] = sorted(printed_card_types(fields['type_line']))
    fields['tags'] = sorted(tactical_tags(fields['oracle_text'], fields['type_line']))
    return fields


def _valid_surface(surface, semantic):
    if type(surface) is not dict or set(surface) != SURFACE_FIELDS:
        return False
    if any(type(surface[key]) is not str or len(surface[key]) > MAX_TEXT
           for key in ('oracle_text', 'type_line', 'mana_cost')):
        return False
    for key in ('types', 'tags'):
        value = surface[key]
        if type(value) is not list or len(value) > 32 or any(type(item) is not str or len(item) > 64 for item in value):
            return False
        if value != sorted(set(value)):
            return False
    return not semantic or surface == _surface(surface)


def _valid_snapshot(value, semantic=False):
    if type(value) is not dict or set(value) not in (SNAPSHOT_FIELDS, SNAPSHOT_FIELDS | {'estimates'}):
        return False
    if type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION:
        return False
    if value['estimator_version'] != ESTIMATOR_VERSION:
        return False
    for key, pattern in (('scryfall_id', IDENTITY), ('oracle_id', IDENTITY),
                         ('source_sha256', DIGEST), ('snapshot_sha256', DIGEST)):
        if type(value[key]) is not str or not pattern.fullmatch(value[key]):
            return False
    if type(value['layout']) is not str or len(value['layout']) > 64 or type(value['rulings_pending']) is not bool:
        return False
    limits = value['limitations']
    if type(limits) is not list or len(limits) > 128 or any(type(item) is not str or len(item) > 256 for item in limits):
        return False
    faces = value['faces']
    if type(faces) is not list or len(faces) > MAX_FACES:
        return False
    if not all(_valid_surface(surface, semantic) for surface in [value['root'], *faces]):
        return False
    if 'estimates' in value and not _valid_estimates(value['estimates'], [value['root'], *faces], semantic):
        return False
    return value['snapshot_sha256'] == _hash({key: item for key, item in value.items() if key != 'snapshot_sha256'})


def copy_snapshot(value, *, semantic=False):
    """Private snapshot compatibility: malformed/unknown carriers become empty."""
    return deepcopy(value) if _valid_snapshot(value, semantic) else {}


def _matches(surface, card):
    get = card.get if isinstance(card, dict) else lambda key: getattr(card, key, None)
    if any((get(key) or '') != surface[key] for key in ('oracle_text', 'type_line', 'mana_cost')):
        return False
    types = get('types')
    return types is None or sorted(printed_card_types('', types)) == surface['types']


def snapshot_for(row, requested_name, hydrated_card):
    """Called after cache overrides; only canonical rows can create a carrier."""
    from card_data.sync import ScryfallSyncService
    profile = ScryfallSyncService.canonical_local_profile(row, requested_name)
    if profile is None:
        return None
    raw, derived = profile['card_data'], profile.get('tactical_profile')
    if type(derived) is not dict or type(derived.get('schema_version')) is not int:
        return None
    if derived['schema_version'] != SCHEMA_VERSION or derived.get('estimator_version') != ESTIMATOR_VERSION:
        return None
    try:
        if derived.get('input_sha256') != _hash(raw):
            return None
        faces = [_surface(face) for face in raw.get('card_faces', [])]
        main = raw
        if faces and ('//' in (raw.get('type_line') or '') or not printed_card_types(raw.get('type_line', ''))):
            main = raw['card_faces'][0]
        root = _surface(main)
        if derived.get('tags') != root['tags']:
            return None
        stored_faces = derived.get('faces')
        if type(stored_faces) is not list or len(stored_faces) != len(faces):
            return None
        if any(type(face) is not dict or type(face.get('face_index')) is not int
               or face['face_index'] != index or face.get('tags') != faces[index]['tags']
               for index, face in enumerate(stored_faces)):
            return None
        if not _matches(root, hydrated_card) or (hydrated_card.get('layout') or '') != raw.get('layout', ''):
            return None
        live_faces = hydrated_card.get('card_faces') or []
        if len(live_faces) != len(faces) or any(not _matches(face, live_faces[index]) for index, face in enumerate(faces)):
            return None
        snapshot = {'schema_version': SCHEMA_VERSION, 'estimator_version': ESTIMATOR_VERSION,
                    'scryfall_id': raw['id'], 'oracle_id': raw['oracle_id'],
                    'source_sha256': derived['input_sha256'], 'layout': raw.get('layout', ''),
                    'root': root, 'faces': faces, 'rulings_pending': profile.get('rulings_verified') is not True,
                    'limitations': list(derived.get('limitations', []))}
        try:
            estimates = _estimates_for(raw, derived, [root, *faces])
        except (KeyError, TypeError, ValueError, AttributeError):
            estimates = None  # Valid legacy tags need not have numeric profile fields.
        if estimates is not None:
            snapshot['estimates'] = estimates
        # A consistency seal for a trusted private snapshot, never an HTTP grant.
        snapshot['snapshot_sha256'] = _hash(snapshot)
        return snapshot if _valid_snapshot(snapshot, semantic=True) else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _fallback(card, reason):
    return TagResult(frozenset(tactical_tags(getattr(card, 'oracle_text', ''),
        getattr(card, 'type_line', ''), getattr(card, 'types', None))), 'fallback', reason)


def tags_for(card):
    """Lookup already-validated printed tags without SQL, IO, or re-derivation."""
    if card is None or getattr(card, 'ai_unknown', False) or (not getattr(card, 'name', '') and not getattr(card, 'types', [])):
        return TagResult(frozenset(), 'opaque')
    snapshot = getattr(card, 'knowledge_snapshot', {})
    if not snapshot:
        return _fallback(card, 'missing')
    if not _valid_snapshot(snapshot):
        return _fallback(card, 'shape')
    faces = snapshot['faces']
    live_faces = getattr(card, 'card_faces', []) or []
    if getattr(card, 'layout', '') != snapshot['layout'] or len(live_faces) != len(faces):
        return _fallback(card, 'face')
    if any(not _matches(face, live_faces[index]) for index, face in enumerate(faces)):
        return _fallback(card, 'face')
    index = getattr(card, 'selected_face_index', None)
    if faces:
        if index is None:
            if snapshot['layout'] not in FRONT_LAYOUTS:
                return _fallback(card, 'face')
            index = 0
        if type(index) is not int or not 0 <= index < len(faces):
            return _fallback(card, 'face')
        surface = faces[index]
    else:
        if index is not None:
            return _fallback(card, 'face')
        surface = snapshot['root']
    if not _matches(surface, card):
        return _fallback(card, 'surface')
    return TagResult(frozenset(surface['tags']), 'persisted', face_index=index)


def estimate_for(card):
    """Printed advisory estimates, never permission or guaranteed live answers.

    Scalars are revalidated against the printed estimator and caller-declared
    context before bounded scoring; this is not a rules or corpus certificate.
    """
    result = tags_for(card)
    if result.source != 'persisted':
        return None
    snapshot = card.knowledge_snapshot
    estimates = snapshot.get('estimates')
    if not _valid_estimates(estimates, [snapshot['root'], *snapshot['faces']], True):
        return None
    entry = estimates['root'] if result.face_index is None else estimates['faces'][result.face_index]
    play_value, context = None, None
    if estimates['transport_version'] == 2:
        try:
            # Missing/dynamic/incoherent literal PT cannot authorize new advice;
            # keep the already validated legacy tier/routes for these objects.
            coherent = ('creature' not in printed_card_types(entry['printed_inputs']['type_line'])
                        or all(entry['printed_inputs'].get(key) not in (None, '') for key in ('power', 'toughness')))
            for key in ('power', 'toughness'):
                printed = entry['printed_inputs'].get(key)
                literal = getattr(card, key, None)
                if printed in (None, ''):
                    coherent &= literal is None
                else:
                    coherent &= (_number(printed) is not None and type(literal) in (int, float)
                                 and math.isfinite(literal) and _number(printed) == literal)
            if coherent:
                play_value = entry['play_value']
                context = deepcopy(estimates['context'])
        except (TypeError, ValueError, OverflowError):
            pass
    return ThreatEstimate(entry['tier'], tuple(AnswerRoute(route['effect_key'], route['target_zone'],
                         route['targeted'], tuple(route['conditions'])) for route in entry['routes']),
                         tuple(entry['limits']), play_value, context)


def _answer_route_for(card, effect_key, source_controller):
    """Printed advice after native target checks, never target permission."""
    if effect_key not in {'destroy_permanent', 'exile', 'return_permanent_to_hand'}:
        return None
    estimate = estimate_for(card)
    if estimate is None:
        return None
    required = 'actual_effect_target_domain_and_current_rules_must_be_checked'
    for route in estimate.routes:
        if (not isinstance(route, AnswerRoute) or route.effect_key != effect_key
                or route.target_zone != 'battlefield' or route.targeted is not True
                or type(route.conditions) is not tuple
                or any(type(condition) is not str for condition in route.conditions)):
            continue
        conditions = set(route.conditions)
        if (required not in conditions
                or conditions - {required, 'targeter_is_controller'}
                or 'targeter_is_controller' in conditions
                and getattr(card, 'controller', None) != source_controller):
            continue
        return route
    return None
