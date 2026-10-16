"""Full pinned inputs unique to the oracle-effects semantic correction."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Zone
from tests.oracle_effects_positive_fixtures_8d import raw_card
from tests.canonical_positive_fixtures import raw_card as seed_raw_card


HERE = Path(__file__).parent / 'fixtures/oracle_effects_semantics_8d'
PURIFY_SHA256 = '418213d937ca862d8d281ec7303c2f7cbdc361d1b5a4208d45ac4270e0c11f50'


def full_raw(name):
    if name == 'Purify':
        data = (HERE / 'purify.json').read_bytes()
        assert hashlib.sha256(data).hexdigest() == PURIFY_SHA256
        value = json.loads(data)
        assert value['object'] == 'card' and value['name'] == name
        return value
    if name == 'Ossification':
        return seed_raw_card(name)
    return raw_card(name)


def purify_card(**physical):
    assert set(physical) == {'id', 'owner', 'controller', 'zone'}
    raw = full_raw('Purify')
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=100)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, instance_order=0, summoning_sick=True, **physical)
