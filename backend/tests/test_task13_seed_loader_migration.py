"""Neutral seed API: real committed payloads, not new Oracle or admission rules."""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from card_data.hydration import ready_for_match


SEED_PATH = Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json'
SEED_BYTES = SEED_PATH.read_bytes()
CARDS = json.loads(SEED_BYTES)['cards']


def seed_api():
    assert importlib.util.find_spec('card_data.seed_cards') is not None, 'approved seed API is absent'
    return importlib.import_module('card_data.seed_cards')


@pytest.mark.parametrize('requested', sorted(CARDS))
def test_all155_actual_seed_payloads_keep_every_root_raw_and_face_field(requested):
    api = seed_api()
    before = deepcopy(api.SEED_CARD_DATA)
    actual = api.seed_card_payload(requested)
    assert actual == CARDS[requested]
    assert api.seed_card_payload(CARDS[requested]['name']) == CARDS[requested]
    assert api.SEED_CARD_DATA == before
    assert SEED_PATH.read_bytes() == SEED_BYTES


@pytest.mark.parametrize('name,requested', [
    ('  MEMORY--DELUGE  ', 'Memory Deluge'),
    ('Fable of the Mirror Breaker', 'Fable of the Mirror-Breaker'),
    ('Delver of Secrets // Insectile Aberration', 'Delver of Secrets'),
    # Historical front-lookup convenience is not an execution admission.
    ('Delver of Secrets // Bogus Face', 'Delver of Secrets'),
])
def test_existing_alias_and_front_lookup_preserves_payload_shape(name, requested):
    assert seed_api().seed_card_payload(name) == CARDS[requested]


@pytest.mark.parametrize('name', ['', '   ', 'Never Canonical Bolt Creature',
                                  'Never Canonical // Never Face', 'Insectile Aberration'])
def test_unknown_names_stay_none_without_invented_metadata(name):
    assert seed_api().seed_card_payload(name) is None


@pytest.mark.parametrize('name,missing', [('Lightning Bolt', 'oracle_text'),
                                        ('Monastery Swiftspear', 'power'),
                                        ('Monastery Swiftspear', 'toughness')])
def test_incomplete_actual_seed_copy_is_not_match_ready(name, missing):
    api = seed_api()
    original = deepcopy(api.seed_card_payload(name))
    incomplete = deepcopy(original)
    incomplete.pop(missing)
    assert ready_for_match(incomplete) is False
    assert api.seed_card_payload(name) == original


def test_committed_seed_bytes_and_inventory_are_preserved():
    api = seed_api()
    assert hashlib.sha256(SEED_BYTES).hexdigest() == '9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037'
    assert len(api.SEED_CARD_DATA) == 155
    assert api.SEED_CARD_DATA == CARDS


def test_old_module_is_removed_without_a_competing_loader():
    seed_api()
    assert importlib.util.find_spec('card_data.fallback_cards') is None
    assert not SEED_PATH.with_name('fallback_cards.py').exists()
