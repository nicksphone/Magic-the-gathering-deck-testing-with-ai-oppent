"""Offline canonical facts and isolated API helpers; no collected-test dependency."""
from collections import Counter
import hashlib
import json

from ai.deck_analysis import analyze_deck
from card_data import hydration
from card_data.fallback_cards import fallback_card_payload
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from decks.service import DeckService
from decks.catalog import load_catalog

FAMILIES = [('LEA', 'Kumano Faces Kakkazan', 'Burn'), ('ARN', 'Delver of Secrets', 'Tempo')]


def wire(value):
    return json.loads(json.dumps(value))


def entry(code):
    return next(item for item in EXPANSION_TOP_DECKS if item['code'] == code)


def rows(repo):
    return {str(row.id): row.model_dump(mode='json') for row in repo.list_decks()}


def cards(repo):
    return [row.model_dump(mode='json') for row in repo.list_cards()]


def facts_inventory(board):
    """Fixture identity equivalence, not access to a future game library."""
    result = Counter()
    for card in board:
        raw = fallback_card_payload(card['card_name'])
        if raw is None:
            # Catalog facts bind inventory identity, not global runtime admission.
            key = card['card_name'].replace('\u2019', "'").casefold()
            canonical = next((r for r in load_catalog()['cards'].values()
                if key in {n.replace('\u2019', "'").casefold()
                    for n in [r['name'], *(f['name'] for f in r.get('card_faces', []))]}), None)
            if canonical is not None:
                raw = {**canonical, 'scryfall_id': canonical['id']}
        assert raw and raw['scryfall_id']
        result[raw['scryfall_id']] += card['quantity']
    return dict(sorted(result.items()))


def full_name(front):
    raw = fallback_card_payload(front)
    assert raw and raw['name'].startswith(front + ' // ')
    return raw['name']


def alias_text(text, front, full):
    lines = []
    for line in text.splitlines():
        bits = line.split(' ', 1)
        if len(bits) == 2 and bits[0].isdigit() and bits[1] in {front, full}:
            line = bits[0] + ' ' + full
        lines.append(line)
    return '\n'.join(lines)


def seed_cache(repo, board):
    for item in board:
        raw = fallback_card_payload(item['card_name'])
        assert raw and raw.get('scryfall_id')
        repo.upsert_card({'scryfall_id': raw['scryfall_id'], 'name': raw['name'],
            'type_line': raw['type_line'], 'oracle_text': raw.get('oracle_text', ''),
            'mana_cost': raw.get('mana_cost', ''), 'colors': ','.join(raw.get('colors') or []),
            'layout': raw.get('layout', ''), 'power': raw.get('power'), 'toughness': raw.get('toughness'),
            'loyalty': raw.get('loyalty'), 'card_faces_json': json.dumps(raw.get('card_faces') or [])})


def prepare(repo, monkeypatch, code, front, mode):
    item = entry(code)
    parsed = DeckService(repo).parser.parse(item['deck_text'])
    assert not parsed.errors
    if mode in {'cache', 'partial_faces'}:
        seed_cache(repo, parsed.mainboard + parsed.sideboard)
    if mode == 'partial_faces':
        row = repo.get_cached_card_by_name(full_name(front))
        assert row
        row.card_faces_json = '[]'
        repo.session.commit()
    if mode != 'offline':
        monkeypatch.setattr(hydration, 'fallback_card_payload', lambda _: None)
    return item


def assert_provenance(repo, result):
    canonical = hydration.hydrate_deck_cards(repo, result['mainboard'])
    analysis = analyze_deck(canonical)
    admitted = (bool(canonical) and all(c.get('card_data_sources') and hydration.ready_for_match(c) for c in canonical)
        and analysis['type_metadata_coverage'] == 1 and analysis['confidence'] > 0
        and not {'missing_card_metadata', 'partial_card_metadata', 'fallback_midrange'}.intersection(analysis['signals']))
    assert result['analysis'] == analysis
    assert result['classification_status'] == ('resolved' if admitted else 'unknown')
    assert result['archetype_guess'] == (analysis['primary_archetype'] if admitted else 'unknown')
    p = result['classification_provenance']
    assert p['admission'] == 'complete-local-canonical-v1'
    assert p['method'] == 'ai.deck_analysis.analyze_deck'
    assert p['facts_method'] == 'card_data.hydration.hydrate_deck_cards'
    assert p['sources'] == sorted({s for c in canonical for s in c.get('card_data_sources', [])})
    assert p['cards'] == [{'card_name': c['card_name'], 'sources': c['card_data_sources'],
        'ready_for_match': bool(hydration.ready_for_match(c))} for c in canonical]
    assert p['resolved_board_sha256'] == hashlib.sha256(json.dumps(canonical, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return admitted
