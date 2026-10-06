"""Historical catalog context and read-only canonical import projection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
import unicodedata

from api_contracts import InputModel
from card_data.fallback_cards import fallback_card_payload
from card_data.hydration import local_knowledge, ready_for_match

DATA_PATH = Path(__file__).with_name('historical_event_catalog.json')
DATA_SHA256 = '2c589f58596f09b3d3b2e7387e5bebe23030fa5c5c11c510f48f655e2c200277'


class CatalogImportRequest(InputModel):
    format_scope: Literal['historical', 'current'] = 'historical'


def _key(name):
    return unicodedata.normalize('NFC', name).replace('\u2019', "'").casefold().strip()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def load_catalog(path=DATA_PATH):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != DATA_SHA256:
        raise ValueError('Historical catalog source digest mismatch')
    packet = json.loads(data)
    if packet['schema_version'] != 1 or packet['runtime_effect_certificate'] is not False:
        raise ValueError('Unsupported catalog provenance schema')
    for code, event in packet['events'].items():
        if code != event['associated_set_code'] or event['runtime_effect_certificate'] is not False:
            raise ValueError('Invalid event identity or certification claim')
        for section in ['mainboard', 'sideboard']:
            rows = event[section]
            if (any(type(r['quantity']) is not int or r['quantity'] <= 0 for r in rows)
                    or len({_key(r['source_name']) for r in rows}) != len(rows)):
                raise ValueError('Invalid published quantities')
            total = sum(r['quantity'] for r in rows)
            if ((section == 'mainboard' and total < 60)
                    or (section == 'sideboard' and total > 15)):
                raise ValueError('Published list outside supported sizes')
            for row in rows:
                raw = packet['cards'][row['scryfall_id']]
                aliases = {_key(raw['name']), *(_key(f['name']) for f in raw.get('card_faces', []))}
                if (raw['object'] != 'card' or raw['id'] != row['scryfall_id']
                        or raw['oracle_id'] != row['oracle_id']
                        or raw['name'] != row['canonical_name']
                        or _digest(raw) != row['canonical_raw_sha256']
                        or _key(row['source_name']) not in aliases):
                    raise ValueError('Canonical catalog fact join mismatch')
    return packet


_PACKET = load_catalog()


def event_record(code):
    return deepcopy(_PACKET['events'][code])


def historical_entry(code, expansion, year):
    event = event_record(code)
    lines = lambda rows: '\n'.join(f"{r['quantity']} {r['source_name']}" for r in rows)
    rank = event['finish']['rank']
    suffix = 'th' if 10 < rank % 100 < 14 else {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')
    return {
        'code': code, 'expansion': expansion, 'release_year': year,
        'deck_name': f"{event['player_name']} - {event['published_archetype']} ({event['event']['name']} {year})",
        'archetype': event['published_archetype'], 'kind': 'tournament',
        'format': f"{event['format']['name']} ({event['event']['start_date']})",
        'event_name': event['event']['name'], 'player_name': event['player_name'],
        'finish': f'{rank}{suffix}', 'decklist_source_url': event['provenance']['decklist_page'],
        'event_source_url': event['finish']['source_url'], 'reference_builtin': None,
        'deck_text': lines(event['mainboard']) + '\n\nSideboard:\n' + lines(event['sideboard']),
    }


def catalog_context(item):
    event = _PACKET['events'].get(item['code']) if item['kind'] == 'tournament' else None
    return {
        'catalog_schema_version': 1,
        'catalog_record_id': event['record_id'] if event else f"archetype-template:{item['code']}",
        'source_kind': 'official_event_submission' if event else 'archetype_template',
        'format_context': {
            'scope': 'historical_event' if event else 'archetype_template',
            'format_name': event['format']['name'] if event else None,
            'event_start_date': event['event']['start_date'] if event else None,
            'event_end_date': event['event']['end_date'] if event else None,
            'historical_legality_evidence': 'official_published_submission' if event else None,
            'independent_legality_certificate': False,
            'current_format_admission': 'unsupported',
            'current_legality': 'unverified',
        },
        'finish_scope': 'overall_event' if event else None,
        'constructed_best_claim': False,
        'runtime_effect_certificate': False,
        'provenance': deepcopy(event['provenance']) if event else None,
        'offline_facts': {
            'scope': 'catalog_import_projection' if event else None,
            'global_match_hydration_certified': False,
            'source': deepcopy(_PACKET['card_facts_provenance']) if event else None,
        },
    }


class CatalogFacts:
    """Forward existing repository operations; never persist card metadata."""
    def __init__(self, repo, item):
        self.repo = repo
        event = _PACKET['events'][item['code']]
        self.rows = event['mainboard'] + event['sideboard']
        self.raw = {_key(alias): raw for row in self.rows
                    for raw in [_PACKET['cards'][row['scryfall_id']]]
                    for alias in [raw['name'], *(f['name'] for f in raw.get('card_faces', []))]}

    def __getattr__(self, name):
        return getattr(self.repo, name)

    def list_card_knowledge_names(self):
        names = list(self.repo.list_card_knowledge_names()) if hasattr(self.repo, 'list_card_knowledge_names') else []
        existing = {_key(r.name) for r in self.repo.list_cards()} | {_key(n) for n in names}
        # Preserve existing root/face lookup priority and exact printed aliases.
        names.extend(row['source_name'].replace('\u2019', "'") for row in self.rows
                     if _key(row['canonical_name']) not in existing)
        return names

    def get_card_knowledge_by_names(self, names):
        result = dict(local_knowledge(self.repo, names))
        for name in names:
            raw = self.raw.get(_key(name))
            seed = fallback_card_payload(name)
            if (name.casefold() in result or raw is None
                    or seed and ready_for_match(seed)):
                continue
            result[name.casefold()] = SimpleNamespace(
                name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
                profiles_json=json.dumps({'oracle_id': raw['oracle_id'], 'card_data': raw,
                    'card_data_provenance': {'source': 'shipped_historical_catalog',
                        'record_sha256': _digest(raw), 'dataset_sha256': DATA_SHA256}}))
        return result
