"""Canonical paid complete attached transformations and independent layer controls."""
import hashlib
import json
from pathlib import Path

import pytest

import test_suncleanser_desired as s
from rules_engine.attached_characteristics import attached_compound, effects_on
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness
from rules_engine.colors import card_color_symbols
from rules_engine.library_permissions import creature_types
from rules_engine.query_context import rule_query_scope
from rules_engine.type_effects import effective_types
from game_state.serializers import serialize_match_snapshot


facts = s.facts


@pytest.fixture(scope='module')
def expanded(facts):
    root = Path(__file__).parent / 'fixtures/attached_characteristics'
    proof = json.loads((root / 'provenance.json').read_text())
    result = dict(facts)
    for name, entry in proof['cards'].items():
        data = (root / entry['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
        raw = json.loads(data)
        assert raw['id'] == entry['raw_id'] and raw['name'] == name
        result[name] = raw
    return result


def paid(state, facts, seat, name, pool, target=None):
    state, card = s.paid(state, facts, seat, name, pool,
                        **({'target_card_id': target} if target is not None else {}))
    s.drain(state)
    return state, card


def projection(state, target):
    before = serialize_match_snapshot(state)
    with rule_query_scope(state):
        first = (tuple(effective_types(state, target)), frozenset(creature_types(state.cards[target], state)),
                 frozenset(card_color_symbols(state.cards[target], state)),
                 tuple(effective_keywords(state, target)), s.printed_abilities_suppressed(state, target),
                 effective_power(state, target), effective_toughness(state, target), effects_on(state, target))
        assert first == (tuple(effective_types(state, target)), frozenset(creature_types(state.cards[target], state)),
                         frozenset(card_color_symbols(state.cards[target], state)),
                         tuple(effective_keywords(state, target)), s.printed_abilities_suppressed(state, target),
                         effective_power(state, target), effective_toughness(state, target), effects_on(state, target))
    assert serialize_match_snapshot(state) == before
    return first


def assert_frog(state, target, power=1, toughness=1, keywords=()):
    row = projection(state, target)
    assert row[:7] == (('Creature',), frozenset({'frog'}), frozenset({'U'}),
                       tuple(sorted(keywords)), True, power, toughness)
    assert row[7]
    return row


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('scenario', [
    'mixed-counter', 'two-setters-forward', 'two-setters-reverse',
    'grant-before', 'grant-after', 'other-aura-before', 'other-aura-after',
    'source-departure', 'target-bounce', 'target-blink', 'target-control',
])
def test_real_paid_attached_characteristic_layers(expanded, seat, restore, scenario):
    state = s.g.position(expanded, seat)
    state, target = paid(state, expanded, seat, 'Ornithopter', {})
    assert set(effective_types(state, target)) == {'Artifact', 'Creature'}
    assert creature_types(state.cards[target], state) == {'thopter'}
    assert 'flying' in effective_keywords(state, target)
    other = s.g.add(state, expanded, 'Monastery Swiftspear', 3 - seat)
    other_before = projection(state, other)
    if scenario == 'mixed-counter':
        state, _ = paid(state, expanded, seat, 'Battlegrowth', {'G': 1}, target)
    if scenario == 'grant-before':
        state, _ = paid(state, expanded, seat, 'Snakeskin Veil', {'G': 1}, target)
    if scenario == 'other-aura-before':
        state, _ = paid(state, expanded, seat, 'Rancor', {'G': 1}, target)
    if scenario == 'two-setters-forward':
        state, _ = paid(state, expanded, seat, 'Ichthyomorphosis', {'C': 2, 'U': 1}, target)
        assert projection(state, target)[:7] == (('Creature',), frozenset({'fish'}), frozenset({'U'}), (), True, 0, 1)
    state, aura = paid(state, expanded, seat, 'Frogify', {'C': 1, 'U': 1}, target)
    assert state.cards[aura].attached_to == target and state.cards[aura].zone == s.Zone.BATTLEFIELD
    state = s.cold(state) if restore else state
    if scenario in {'grant-after', 'other-aura-after', 'two-setters-reverse'}:
        name, pool = {'grant-after': ('Snakeskin Veil', {'G': 1}),
                      'other-aura-after': ('Rancor', {'G': 1}),
                      'two-setters-reverse': ('Ichthyomorphosis', {'C': 2, 'U': 1})}[scenario]
        state, _ = paid(state, expanded, seat, name, pool, target)
    if scenario == 'two-setters-reverse':
        assert projection(state, target)[:7] == (('Creature',), frozenset({'fish'}), frozenset({'U'}), (), True, 0, 1)
    else:
        bonus = 1 if scenario in {'mixed-counter', 'grant-before', 'grant-after'} else 0
        power = 1 + bonus + (2 if scenario.startswith('other-aura') else 0)
        keywords = ('hexproof',) if scenario == 'grant-after' else ('trample',) if scenario == 'other-aura-after' else ()
        assert_frog(state, target, power, 1 + bonus, keywords)
    assert projection(state, other) == other_before
    if scenario == 'source-departure':
        state, _ = paid(state, expanded, seat, 'Abrupt Decay', {'B': 1, 'G': 1}, aura)
        assert state.cards[aura].zone == s.Zone.GRAVEYARD
    elif scenario == 'target-bounce':
        state, _ = paid(state, expanded, seat, 'Unsummon', {'U': 1}, target)
        assert state.cards[target].zone == s.Zone.HAND
    elif scenario == 'target-blink':
        incarnation = s.object_incarnation(state.cards[target])
        state, _ = paid(state, expanded, seat, 'Flicker', {'C': 1, 'W': 1}, target)
        assert s.object_incarnation(state.cards[target]) != incarnation
        assert state.cards[aura].zone == s.Zone.GRAVEYARD
    elif scenario == 'target-control':
        state = s.advance_main(state, 3 - seat)
        state, _ = paid(state, expanded, 3 - seat, 'Claim the Firstborn', {'R': 1}, target)
        assert state.cards[target].controller == 3 - seat and state.cards[target].owner == seat
        assert_frog(state, target, keywords=('haste',))
    if scenario in {'source-departure', 'target-bounce', 'target-blink'}:
        assert set(effective_types(state, target)) == {'Artifact', 'Creature'}
        assert not effects_on(state, target) and not s.printed_abilities_suppressed(state, target)
        assert card_color_symbols(state.cards[target], state) == set()
        assert 'flying' in effective_keywords(state, target)
    state = s.cold(state)
    projection(state, target)
    s.record(f'layers-{scenario}-{seat}-{restore}', state, actual_paid=True, no_injected_frame=True)


@pytest.mark.parametrize('suffix', [
    ' Then invent an unknown reward.', ' If an unspecified condition holds.',
    '\nDraw a card.', '\n{T}: Draw a card.',
])
def test_complete_attached_parser_unknown_remainder_fail_closed(facts, suffix):
    # These are compiler negatives, not claimed canonical card episodes.
    assert attached_compound(facts['Frogify']['oracle_text'] + suffix) is None


def test_existing_other_aura_body_is_not_reinterpreted(expanded):
    assert attached_compound(expanded['Rancor']['oracle_text']) is None
