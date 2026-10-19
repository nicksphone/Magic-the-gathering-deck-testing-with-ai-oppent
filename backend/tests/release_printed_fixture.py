"""One complete pinned Anthem birth; retain the release test's old scene pose."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Zone


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
