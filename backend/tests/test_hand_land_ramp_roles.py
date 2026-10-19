"""Role recognition only, not execution certification of these cards."""
import json
from pathlib import Path

import pytest

from card_data.tactical import canonical_tactical_tags, tactical_tags


FIXTURES = Path(__file__).parent / 'fixtures'
ROWS = [json.loads((FIXTURES / 'optional_land_compiler' / name).read_text())
        for name in ('growth-spiral.json', 'arboreal-grazer.json')]
ROWS += [json.loads((FIXTURES / 'activated_handland' / name).read_text())
         for name in ('sakura-tribe-scout.json', 'walking-atlas.json')]


@pytest.mark.parametrize('raw', ROWS, ids=lambda raw: raw['name'])
def test_spell_entry_and_activated_hand_land_roles_share_canonical_metadata(raw):
    assert raw['oracle_id'] and raw['oracle_text']
    assert 'ramp' in tactical_tags(raw['oracle_text'], raw['type_line'])
    assert 'ramp' in canonical_tactical_tags(raw)['tactical_tags']


@pytest.mark.parametrize('text', [
    'You cannot put a land card from your hand onto the battlefield.',
    'You may not put a land card from your hand onto the battlefield.',
    '(You may put a land card from your hand onto the battlefield.)',
    'Creatures have "You may put a land card from your hand onto the battlefield."',
    'Return a land card from your hand to your graveyard.',
])
def test_negative_reminder_and_granted_role_surface_is_not_self_deployment(text):
    assert 'ramp' not in tactical_tags(text)
