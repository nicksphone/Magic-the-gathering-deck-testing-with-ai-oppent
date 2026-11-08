"""Pinned positive release prints; cache projections and scene poses stay separate."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from tests.canonical_positive_fixtures import raw_card as canonical_raw


def glorious_anthem():
    body = (Path(__file__).parent / 'fixtures/mass_exile_audit/glorious-anthem.json').read_bytes()
    if hashlib.sha256(body).hexdigest() != '475da90077f984d1b82160a7b480fae627973edbc13dd07357c6c03106dad2af':
        raise ValueError('Release Anthem RAW changed')
    raw = json.loads(body)
    if (raw.get('object'), raw.get('id'), raw.get('name')) != (
            'card', '17d154d3-7ae5-43ff-9978-d974285e2c89', 'Glorious Anthem'):
        raise ValueError('Release Anthem printing changed')
    sample = MatchFactory.from_decks(
        [{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id='anthem', owner=1, controller=1, zone=Zone.BATTLEFIELD,
                   instance_order=0, summoning_sick=True)


def cached_release_dfc(name):
    """Fresh complete cache projection for the two explicit release fixtures."""
    if name == "Jace, Vryn's Prodigy // Jace, Telepath Unbound":
        body = (Path(__file__).parent / 'fixtures/transformed_entry.json').read_bytes()
        if hashlib.sha256(body).hexdigest() != '181985b1b21e065f153502df37dbea3654bf163b0b4030af30d4aac8779e134c':
            raise ValueError('Release Jace RAW changed')
        raw = next(row for row in json.loads(body) if row['name'] == name)
        if (raw.get('object'), raw.get('id'), raw.get('oracle_id')) != (
                'card', '02d6d693-f1f3-4317-bcc0-c21fa8490d38',
                '594f6881-c059-46f8-aa4e-7151d502de73'):
            raise ValueError('Release Jace printing changed')
    elif name == 'Brutal Cathar // Moonrage Brute':
        raw = canonical_raw(name)
    else:
        raise ValueError('Unknown release DFC fixture')
    return SimpleNamespace(**ScryfallSyncService._normalize_payload(
        raw, 'unused:release-cache-display'))
