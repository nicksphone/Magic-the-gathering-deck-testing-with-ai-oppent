"""Explicit noncard layer packets, not canonical-card or gameplay witnesses."""
from copy import deepcopy
import json

import pytest

from rules_engine.basic_land_layer import _resolve


@pytest.mark.parametrize('line,base,operations,expected_types,expected_line', [
    pytest.param('Land Creature \u2014 Forest Elf', ('Land', 'Creature'),
        ((2, 'creature_subtypes', ('time lord',)),), ('Land', 'Creature'),
        'Land Creature \u2014 Forest Time Lord', id='mixed-land-creature'),
    pytest.param('Land \u2014 Forest', ('Land',),
        ((2, 'creature_subtypes', ('time lord',)),), ('Land',),
        'Land \u2014 Forest', id='plain-land-masks-creature-subtypes'),
    pytest.param('Artifact \u2014 Equipment', ('Artifact',),
        ((2, 'creature_subtypes', ('spirit',)),), ('Artifact',),
        'Artifact \u2014 Equipment', id='equipment-category-survives'),
    pytest.param('Enchantment \u2014 Aura', ('Enchantment',),
        ((2, 'creature_subtypes', ('spirit',)),), ('Enchantment',),
        'Enchantment \u2014 Aura', id='aura-category-survives'),
    pytest.param('Kindred Enchantment \u2014 Aura Elf', ('Kindred', 'Enchantment'),
        ((2, 'creature_subtypes', ('time lord',)),), ('Kindred', 'Enchantment'),
        'Kindred Enchantment \u2014 Aura Time Lord', id='kindred-correlates'),
    pytest.param('Tribal Enchantment \u2014 Aura Elf', ('Tribal', 'Enchantment'),
        ((2, 'creature_subtypes', ('time lord',)),), ('Tribal', 'Enchantment'),
        'Tribal Enchantment \u2014 Aura Time Lord', id='legacy-tribal-correlates'),
    pytest.param('Land Creature \u2014 Forest Elf', ('Land', 'Creature'),
        ((2, 'creature_subtypes', ('time lord',)), (3, 'remove', ('Creature',))), ('Land',),
        'Land \u2014 Forest', id='later-type-loss-final-correlation'),
    pytest.param('Land Creature \u2014 Forest Elf', ('Land', 'Creature'),
        ((2, 'creature_subtypes', ('time lord',)), (3, 'remove', ('Creature',)),
         (4, 'add', ('Creature',))), ('Land', 'Creature'),
        'Land Creature \u2014 Forest Time Lord', id='later-regain-retains-latent-overlay'),
    pytest.param('Creature \u2014 Time Lord Elf', ('Creature',),
        ((2, 'creature_subtypes', ('kithkin', 'spirit')),), ('Creature',),
        'Creature \u2014 Kithkin Spirit', id='replace-complete-multiword-phrase'),
    pytest.param('Creature \u2014 Elf', ('Creature',),
        ((2, 'creature_subtypes', ('time lord', 'warrior')),), ('Creature',),
        'Creature \u2014 Time Lord Warrior', id='multiword-display-not-time-lord-fragments'),
    pytest.param('Kindred Artifact \u2014 Equipment Elf', ('Kindred', 'Artifact'),
        ((2, 'creature_subtypes', ('spirit',)), (3, 'remove', ('Kindred',))), ('Artifact',),
        'Artifact \u2014 Equipment', id='later-kindred-loss'),
    pytest.param('Tribal Enchantment \u2014 Aura Elf', ('Tribal', 'Enchantment'),
        ((2, 'creature_subtypes', ('spirit',)), (3, 'remove', ('Tribal',))), ('Enchantment',),
        'Enchantment \u2014 Aura', id='later-tribal-loss'),
])
def test_final_correlation_masks_view_without_erasing_latent_operations(
        line, base, operations, expected_types, expected_line):
    rows = (('protocol-object', line, '', 1, base, 1, None,
             'noncard layer packet', operations, base, 1, 0),)
    before = deepcopy(rows)

    def frozen(value):
        return tuple(frozen(item) for item in value) if isinstance(value, list) else value

    restored = frozen(json.loads(json.dumps(rows)))
    for candidate in (rows, restored):
        view = _resolve(candidate)
        assert view[0].get('protocol-object', line) == expected_line
        assert view[2].get('protocol-object', base) == expected_types
        assert _resolve(candidate) == view
        with pytest.raises(TypeError):
            view[0]['protocol-object'] = 'mutated'
    assert rows == before
    assert rows[0][8] == operations
