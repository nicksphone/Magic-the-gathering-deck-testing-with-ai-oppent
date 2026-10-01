"""Only immutable Oracle instructions are reused; live state remains authoritative."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rules_engine import continuous
from rules_engine.continuous import effective_power, effective_keywords
from game_state.state import Zone
from tests.test_ai_recurring_engines import add as add_card
from tests.test_restricted_mana import clean

CARDS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/static_parser_cache.json').read_text())}
for row in CARDS.values():
    for field in ('power', 'toughness', 'keywords', 'colors'):
        row.setdefault(field, None)

PARSERS = [('_iter_pt_modifiers', 'Elvish Clancaller'), ('_iter_pt_setters', 'Octopus Umbra'),
           ('_iter_keyword_grants', 'Archetype of Imagination'), ('_iter_keyword_removals', 'Archetype of Imagination'),
           ('_iter_keyword_cant_removals', 'Archetype of Imagination')]


def add(state, name, player=1, zone=Zone.BATTLEFIELD):
    return add_card(state, name, player, zone, cards=CARDS)


@pytest.mark.parametrize('parser_name,card_name', PARSERS)
def test_cache_reuses_text_not_object_identity_and_keeps_iterator_fresh(parser_name, card_name):
    # Keep cache counters local even when other API/job tests have live readers.
    parser = continuous._static_parser(getattr(continuous, parser_name).__wrapped__)
    source = SimpleNamespace(oracle_text=CARDS[card_name]['oracle_text'])
    expected = list(parser.uncached(source))
    assert expected and list(parser(source)) == expected
    same_text = SimpleNamespace(oracle_text=source.oracle_text)
    returned = list(parser(same_text))
    assert returned == expected and parser.cache_info().hits == 1
    returned.clear()
    assert list(parser(source)) == expected
    source.oracle_text = CARDS['Grizzly Bears']['oracle_text']
    assert list(parser(source)) == [] and parser.cache_info().misses == 2
    assert parser.cache_info().maxsize == 4096


@pytest.mark.parametrize('parser_name,card_name', PARSERS)
def test_cached_payload_has_no_mutable_containers_or_card_references(parser_name, card_name):
    parser = getattr(continuous, parser_name)
    source = SimpleNamespace(oracle_text=CARDS[card_name]['oracle_text'])
    def immutable(value):
        return (type(value) in (str, int, bool, type(None))
                or (type(value) in (tuple, frozenset) and all(immutable(item) for item in value)))
    assert all(immutable(row) for row in parser(source))


def test_control_change_counter_and_zone_updates_are_not_cached():
    state = clean()
    lord = add(state, 'Elvish Clancaller')
    own = add(state, 'Llanowar Elves')
    other = add(state, 'Llanowar Elves', 2)
    assert (effective_power(state, own.id), effective_power(state, other.id)) == (2, 1)
    state.players[1].battlefield.remove(lord.id)
    state.players[2].battlefield.append(lord.id)
    lord.controller = 2
    assert (effective_power(state, own.id), effective_power(state, other.id)) == (1, 2)
    other.counters['+1/+1'] = 3
    assert effective_power(state, other.id) == 5
    state.players[2].battlefield.remove(lord.id)
    lord.move_to_zone(Zone.GRAVEYARD)
    state.players[1].graveyard.append(lord.id)
    assert effective_power(state, other.id) == 4


def test_attached_base_setter_reassignment_and_dynamic_scaling_use_live_state():
    state = clean()
    first = add(state, 'Grizzly Bears')
    second = add(state, 'Llanowar Elves')
    aura = add(state, 'Octopus Umbra')
    aura.attached_to = first.id
    assert (effective_power(state, first.id), effective_power(state, second.id)) == (8, 1)
    aura.attached_to = second.id
    assert (effective_power(state, first.id), effective_power(state, second.id)) == (2, 8)
    aura.attached_to = None
    scaling = add(state, 'All That Glitters')
    scaling.attached_to = first.id
    before = effective_power(state, first.id)
    add(state, 'Sol Ring')
    assert effective_power(state, first.id) == before + 1


def test_keyword_cant_override_and_grant_control_changes_remain_dynamic():
    state = clean()
    source = add(state, 'Archetype of Imagination')
    own = add(state, 'Grizzly Bears')
    other = add(state, 'Grizzly Bears', 2)
    other.keywords.append('flying')
    assert 'flying' in effective_keywords(state, own.id)
    assert 'flying' not in effective_keywords(state, other.id)
    source.controller = 2
    assert 'flying' not in effective_keywords(state, own.id)
    assert 'flying' in effective_keywords(state, other.id)


@pytest.mark.parametrize('name,keyword', [('Archetype of Imagination', 'flying'),
                                       ('Archetype of Courage', 'first strike'),
                                       ('Archetype of Endurance', 'hexproof'),
                                       ('Archetype of Aggression', 'trample'),
                                       ('Archetype of Finality', 'deathtouch')])
@pytest.mark.parametrize('newer_grant', [False, True])
def test_canonical_composed_cant_override_wins_over_opponents_grant(name, keyword, newer_grant):
    from game_state.state import assign_static_order_on_battlefield_entry
    state = clean()
    suppressor = add(state, name, 1)
    grant = add(state, name, 2)
    for source in ([suppressor, grant] if newer_grant else [grant, suppressor]):
        assign_static_order_on_battlefield_entry(state, source.id)
    target = add(state, 'Grizzly Bears', 2)
    assert keyword not in effective_keywords(state, target.id)
    # Removing the prohibition restores the same printed grant immediately.
    state.players[1].battlefield.remove(suppressor.id)
    suppressor.move_to_zone(Zone.GRAVEYARD)
    state.players[1].graveyard.append(suppressor.id)
    assert keyword in effective_keywords(state, target.id)


def test_parallel_readers_get_identical_instructions_without_shared_mutable_results():
    parser = continuous._iter_keyword_grants
    source = SimpleNamespace(oracle_text=CARDS['Archetype of Imagination']['oracle_text'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: list(parser(source)), range(16)))
    assert all(row == rows[0] for row in rows)
    rows[0].clear()
    assert rows[1] == list(parser(source))
