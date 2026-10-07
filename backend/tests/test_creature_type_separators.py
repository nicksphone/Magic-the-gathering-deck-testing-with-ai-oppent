"""Type-line separator ABI probes, not invented canonical card fixtures."""
from types import SimpleNamespace

import pytest

from rules_engine.library_permissions import creature_types


@pytest.mark.parametrize('separator', [' - ', ' \u2013 ', ' \u2014 ', '  -  '])
def test_supported_type_line_separators_preserve_subtypes(separator):
    card = SimpleNamespace(type_line=f'Creature{separator}Elf Druid',
                           types=['Creature'], oracle_text='')
    assert creature_types(card) == {'elf', 'druid'}


@pytest.mark.parametrize('line', ['Creature Elf Druid', 'Creature-Elf', 'Elf Creature'])
def test_unseparated_words_are_not_creature_subtypes(line):
    card = SimpleNamespace(type_line=line, types=['Creature'], oracle_text='')
    assert creature_types(card) == set()
