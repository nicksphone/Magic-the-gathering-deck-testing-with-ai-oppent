"""Canonical changeling identities keep layer-four subtypes through ability loss."""
import json
from pathlib import Path

import pytest

from effects.handlers import create_token_copy
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.affinity import _matches
from rules_engine.card_types import CREATURE_SUBTYPES
from rules_engine.continuous import has_keyword, printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_permissions import ordinary_graveyard_cast
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.library_permissions import creature_types, top_library_creature_for_type
from tests.test_affinity import PERMANENTS
from tests.test_announced_spell_costs import add
from tests.test_graveyard_play_permissions import ROWS, position

STATIC = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/static_ability_suppression.json').read_text())}
QUALIFIED = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/qualified_spell_costs.json').read_text())}


@pytest.mark.parametrize('seat', [1, 2])
def test_humility_keeps_affinity_subtype_counts_and_gravecrawler_permission(seat):
    state = position(seat)
    automaton = add(state, 'Universal Automaton', seat, cards=PERMANENTS)
    add(state, 'Humility', 3-seat, cards=PERMANENTS)
    crawler = add(state, 'Gravecrawler', seat, Zone.GRAVEYARD, cards=ROWS)
    before = serialize_match_snapshot(state)
    assert printed_abilities_suppressed(state, automaton.id)
    assert not has_keyword(state, automaton.id, 'changeling')
    assert CREATURE_SUBTYPES <= creature_types(automaton)
    # Exercise affinity's real per-instance aggregation without invented Oracle.
    for subject in ('elves', 'outlaws'):
        assert sum(_matches(state, state.cards[cid], subject)
                   for cid in state.players[seat].battlefield) == 1
    assert ordinary_graveyard_cast(state, seat, crawler.id)
    assert serialize_match_snapshot(state) == before
    restored = deserialize_match_snapshot(before)
    assert CREATURE_SUBTYPES <= creature_types(restored.cards[automaton.id])
    assert ordinary_graveyard_cast(restored, seat, crawler.id)
    cast = checked_action(restored, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': crawler.id, 'from_graveyard': True})
    assert cast.cards[crawler.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.HAND, Zone.LIBRARY, Zone.GRAVEYARD, Zone.EXILE, Zone.STACK])
def test_printed_changeling_subtypes_work_outside_battlefield_without_keyword_metadata(seat, zone):
    state = position(seat)
    automaton = add(state, 'Universal Automaton', seat,
                    Zone.HAND if zone == Zone.STACK else zone, cards=PERMANENTS)
    automaton.keywords = []
    if zone == Zone.STACK:
        state.players[seat].mana_pool = {'C': 1}
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'cast_spell', 'card_id': automaton.id})
        automaton = state.cards[automaton.id]
        assert automaton.zone == Zone.STACK
    assert CREATURE_SUBTYPES <= creature_types(automaton)


@pytest.mark.parametrize('seat', [1, 2])
def test_library_permission_uses_printed_subtypes_but_suppressed_source_stays_suppressed(seat):
    state = position(seat)
    walker = add(state, 'Realmwalker', seat, cards=STATIC)
    walker.chosen_creature_type = 'Elf'
    automaton = add(state, 'Universal Automaton', seat, Zone.LIBRARY, cards=PERMANENTS)
    automaton.keywords = []
    assert top_library_creature_for_type(state, seat) is automaton
    add(state, 'Humility', 3-seat, cards=PERMANENTS)
    assert top_library_creature_for_type(state, seat) is None
    assert CREATURE_SUBTYPES <= creature_types(automaton)


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_printed_changeling_survives_humility(seat):
    state = position(seat)
    automaton = add(state, 'Universal Automaton', seat, cards=PERMANENTS)
    add(state, 'Humility', 3-seat, cards=PERMANENTS)
    before = set(state.cards)
    create_token_copy(state, seat, {'target_card_id': automaton.id})
    token, = [state.cards[cid] for cid in set(state.cards) - before]
    assert token.oracle_text == automaton.oracle_text
    assert not has_keyword(state, token.id, 'changeling')
    assert CREATURE_SUBTYPES <= creature_types(token)


@pytest.mark.parametrize('seat', [1, 2])
def test_kindred_changeling_and_current_noncreature_type_boundary(seat):
    state = position(seat)
    spell = add(state, 'Crib Swap', seat, Zone.HAND, cards=QUALIFIED)
    spell.keywords = []
    assert CREATURE_SUBTYPES <= creature_types(spell)
    automaton = add(state, 'Universal Automaton', seat, cards=PERMANENTS)
    # Core layer-four boundary packet, not a replacement card/Oracle definition.
    automaton.types = ['Artifact']
    assert creature_types(automaton) == {'shapeshifter'}


@pytest.mark.parametrize('seat', [1, 2])
def test_layer_six_changeling_grant_does_not_become_a_printed_cda(seat):
    state = position(seat)
    thopter = add(state, 'Ornithopter', seat, cards=PERMANENTS)
    add_keyword_effect(state, thopter.id, ['changeling'])
    assert has_keyword(state, thopter.id, 'changeling')
    assert creature_types(thopter) == {'thopter'}
    thopter.keywords.append('changeling')
    assert creature_types(thopter) == {'thopter'}
