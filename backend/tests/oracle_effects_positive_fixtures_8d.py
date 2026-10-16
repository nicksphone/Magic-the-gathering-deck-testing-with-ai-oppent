"""Pinned whole official inputs for this module's remaining named positives."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from game_state.state import MatchFactory, Zone
from tests.rules_printed_facts_e4 import raw_card as existing_raw_card


HERE = Path(__file__).parent / 'fixtures/oracle_effects_positive_8d'
EXTRA = {
    'Rings of Brighthearth': ('rings-of-brighthearth.json', '3405a77d30471442d68cceb9421c33d235b1a5cc0fe431ea1bcfedf848492acb'),
    'Vindicate': ('vindicate.json', 'f2a8274eff30900f86f160dfb2b7e03a3e2e9ab29837afbe584cde5b474a2408'),
    'Open the Vaults': ('open-the-vaults.json', '63ecee11189985ca5f54312d2236c4ff14237013576add301d62330b39442913'),
    'Steel Hellkite': ('steel-hellkite.json', '596eddca6e605d3f4137db403b580b90b55ccde8eb793440968c233b6a625e34'),
}


def raw_card(name):
    if name not in EXTRA:
        return existing_raw_card(name)
    filename, digest = EXTRA[name]
    data = (HERE / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    raw = json.loads(data)
    assert raw['name'] == name and raw['object'] == 'card'
    return raw


def remaining_card(name, **physical):
    """Materialize full RAW through the real factory, preserving local runtime."""
    assert set(physical) == {'id', 'owner', 'controller', 'zone'}
    raw = raw_card(name)
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 8}], [], seed=100)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    # The never-drawn eighth card retains the old CardInstance zone-visit default.
    return replace(template, instance_order=0, summoning_sick=True, **physical)
