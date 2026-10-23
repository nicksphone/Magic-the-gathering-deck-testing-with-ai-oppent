"""Complete pinned RAW admissions for exactly two existing fixture families."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_types import printed_card_types


FIXTURES = Path(__file__).parent / 'fixtures/pending_permanent_fullraw'
RAW_SHA = 'bbc868c335b6f5bc7e5a02f5aafe92bf16e25ede7652a0f2e7d5ae5428c5048a'
PROVENANCE_SHA = '88f6eb74e1ddf6334f988eebf983b10788c62919a42d4035f7c5a5ceb82eba5f'
PENDING_NAMES = frozenset((
    'Sprite Dragon', 'Go for the Throat', 'Fatal Push', 'Mind Stone', 'Naturalize',
    'Phyrexian Arena', 'Counterspell', 'Lightning Bolt', 'Giant Growth', 'Darksteel Myr',
    'Darksteel Colossus', 'Doom Blade', 'Abrade', 'Thrashing Brontodon', 'Slice in Twain',
    'Bastion of Remembrance', 'Blood Artist', 'Leyline of the Void', 'Murder',
))
PERMANENT_NAMES = frozenset((
    'Prodigal Pyromancer', 'Wall of Omens', 'Soul Warden', 'Curiosity',
    "Smuggler's Copter", 'Reclamation Sage', 'Sol Ring', 'Ulamog, the Infinite Gyre',
    'Monastery Swiftspear', 'Lightning Bolt',
))


def raw_card(name):
    if name not in PENDING_NAMES | PERMANENT_NAMES:
        raise KeyError(name)
    provenance = (FIXTURES / 'PROVENANCE.json').read_bytes()
    if hashlib.sha256(provenance).hexdigest() != PROVENANCE_SHA:
        raise ValueError('Canonical fixture provenance changed')
    manifest = json.loads(provenance)
    body = (FIXTURES / 'canonical.jsonl').read_bytes()
    if (hashlib.sha256(body).hexdigest() != RAW_SHA
            or manifest['raw_dataset_sha256'] != RAW_SHA):
        raise ValueError('Complete canonical fixture source changed')
    rows = [json.loads(line) for line in body.splitlines()]
    cards = {row['name']: row for row in rows}
    if len(cards) != len(rows) or set(cards) != PENDING_NAMES | PERMANENT_NAMES:
        raise ValueError('Canonical fixture family changed')
    raw, record = cards[name], manifest['sources'][name]
    digest = hashlib.sha256(json.dumps(
        raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if (raw.get('object') != 'card' or raw.get('id') != record['id']
            or raw.get('oracle_id') != record['oracle_id']
            or len(raw) != record['field_count'] or digest != record['complete_object_sha256']):
        raise ValueError('Complete canonical fixture identity changed')
    return raw


def printed_kwargs(name, claimed, *, catalog_keywords=False):
    raw = raw_card(name)
    # Same-name protocol overrides retain the legacy constructor, not guessed printing.
    fields = ('name', 'id', 'oracle_id', 'mana_cost', 'oracle_text', 'type_line', 'power', 'toughness',
              'loyalty', 'keywords', 'colors', 'layout', 'card_faces')
    if not isinstance(claimed, dict) or any(
            key in claimed and (type(claimed[key]) is not type(raw.get(key))
                                or claimed[key] != raw.get(key)) for key in fields):
        return None
    # A truthy display-only operand prevents placeholder art writes.
    cached = ScryfallSyncService._normalize_payload(raw, 'unused:task13-fixture-display')
    types = ([kind for kind in ['Creature', 'Artifact', 'Enchantment', 'Instant', 'Sorcery']
              if kind in cached['type_line'].split()] if catalog_keywords
             else printed_card_types(cached['type_line']))
    return dict(
        name=cached['name'], types=types, mana_cost=cached['mana_cost'],
        oracle_text=cached['oracle_text'], type_line=cached['type_line'],
        power=_infer_power(cached['name'], cached.get('power'), types),
        toughness=_infer_toughness(cached['name'], cached.get('toughness'), types),
        printed_power=cached.get('power'), printed_toughness=cached.get('toughness'),
        loyalty=int(cached['loyalty']) if cached.get('loyalty') is not None else None,
        keywords=deepcopy(raw['keywords']) if catalog_keywords else _infer_keywords(cached['oracle_text']),
        colors=deepcopy(raw['colors']), layout=cached['layout'],
        card_faces=json.loads(cached['card_faces_json']), selected_face_index=None, image_uri=None,
    )
