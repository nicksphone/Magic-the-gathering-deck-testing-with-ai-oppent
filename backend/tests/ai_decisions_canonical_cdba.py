"""Complete canonical printed facts for this AI-test module, not a rules adapter."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

from game_state.state import CardInstance, Zone, _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types
from tests import canonical_positive_fixtures as shared


EXTRA = {'Opt': {'file': 'global_flash_timing_audit/opt.json', 'sha256': '4c1d4b713ae2884e8475dad6c93239d564eb3edfacec3969615df623d40fa3db'}, 'Divination': {'file': 'global_flash_timing_audit/divination.json', 'sha256': 'b4027892ddae4183a1107d169a27a6197bf338dec1ce71283575e1d3618036f2'}, 'Disenchant': {'file': 'shuffle_observer_fix/canonical.jsonl', 'sha256': 'b2940c590f40c0377c5e6abdf5e2459abd4e1c45fdc75fd300b0e450b4e15e71'}, 'Merfolk Looter': {'file': 'ai_decisions_canonical_cdba/merfolk-looter-scryfall-raw.json', 'sha256': 'c896efbb4ed3088cce6f0c811c45d78f64a193a4e34c4a17625a2d055a4b4f62'}, 'Dream Trawler': {'file': 'ai_decisions_canonical_cdba/dream-trawler-scryfall-raw.json', 'sha256': 'b8e6ac8d14c0de9f6053ec6ca803bd7ae83f411f1396cc3c1b96493aaf32a07a'}, 'Runeclaw Bear': {'file': 'ai_decisions_canonical_cdba/runeclaw-bear-scryfall-raw.json', 'sha256': 'f8b88dbd8f0ba783b974472488baf04d04753772a8d6e196eab470b192cce29e'}, 'Rhystic Study': {'file': 'ai_decisions_canonical_cdba/rhystic-study-scryfall-raw.json', 'sha256': 'fd71db57f2d28040ab3c64b949422e8edda5a6f92d9790160043f5c81473e85d'}, 'Explore': {'file': 'ai_decisions_canonical_cdba/explore-scryfall-raw.json', 'sha256': 'eecf27130f92e54ca15fbc8931daee4db1f801905fa8dd0560cd5008f8d512c0'}, 'Grim Haruspex': {'file': 'ai_decisions_canonical_cdba/grim-haruspex-scryfall-raw.json', 'sha256': '5efbfd06276f3bdc9f81f43e58342604f4573cf024852b0e872d96854277d47e'}}
PRINTED_FIELDS = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power',
    'toughness', 'printed_power', 'printed_toughness', 'loyalty', 'colors', 'keywords',
    'layout', 'card_faces', 'selected_face_index', 'printed_characteristics', 'image_uri')


def raw_card(name):
    """Only exact, explicitly admitted names; no fuzzy/short-label resolution."""
    if name not in EXTRA:
        return shared.raw_card(name)
    source = EXTRA[name]
    data = (shared.FIXTURES / source['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == source['sha256']
    rows = list(map(json.loads, data.splitlines())) if source['file'].endswith('.jsonl') else [json.loads(data)]
    found = [row for row in rows if row.get('name') == name and row.get('object') == 'card']
    assert len(found) == 1
    return found[0]


def canonical_card(name, *, as_instance=False, **physical):
    """Printed projection is canonical; callers supply only physical/runtime fields."""
    assert not set(physical).intersection(PRINTED_FIELDS)
    raw = raw_card(name)
    from card_data.sync import ScryfallSyncService
    cached = ScryfallSyncService._normalize_payload(raw, shared.CACHED_IMAGE_URI)
    types = printed_card_types(cached['type_line'])
    projected = CardInstance('printed-projection', cached['name'], 1, 1, Zone.HAND,
        types=types, oracle_text=cached['oracle_text'], mana_cost=cached['mana_cost'],
        type_line=cached['type_line'], power=_infer_power(cached['name'], cached['power'], types),
        toughness=_infer_toughness(cached['name'], cached['toughness'], types),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=int(cached['loyalty']) if cached['loyalty'] is not None else None,
        colors=cached['colors'].split(',') if cached['colors'] else [],
        keywords=_infer_keywords(cached['oracle_text']), layout=cached['layout'],
        card_faces=json.loads(cached['card_faces_json']), image_uri=cached['image_uri'])
    if projected.card_faces and projected.layout in {'transform', 'modal_dfc'}:
        apply_transform_face(projected, 0)
    printed = {field: deepcopy(getattr(projected, field)) for field in PRINTED_FIELDS}
    return CardInstance(**printed, **physical) if as_instance else SimpleNamespace(**printed, **physical)


def canonical_deck_entry(name, quantity):
    """Factory consumes flattened raw fields, not the service's card_metadata wrapper."""
    return {**raw_card(name), 'quantity': quantity, 'card_name': name,
            'image_uri': shared.CACHED_IMAGE_URI}


def set_printed(card, name):
    """Retag the existing stack object while retaining every physical/runtime field."""
    printed = canonical_card(name)
    for field in PRINTED_FIELDS:
        setattr(card, field, deepcopy(getattr(printed, field)))


def add_canonical(state, name, player=1, zone=Zone.BATTLEFIELD):
    """Retain the existing helper's object allocation and placement, not partial facts."""
    from tests.test_ai_recurring_engines import add
    card = add(state, name, player, zone)
    set_printed(card, name)
    return card
