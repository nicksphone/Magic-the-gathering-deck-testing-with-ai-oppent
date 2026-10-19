"""Current cost admission and isolated hint diagnostics, not paid March support."""
from copy import deepcopy
import json
import os

import pytest

import inventory as inv
import domain_paid_support as g
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.costs import collect_cost_options
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.mana import mana_value
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.spell_cost_clauses import spell_additional_costs

OUT = inv.ROOT.parent / 'evidence'
PHASE = os.environ['ADMISSION_PHASE']
MARCH = 'March of Otherworldly Light'


@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    assert raws[MARCH]['id'] == seed[MARCH]['scryfall_id']
    assert raws[MARCH]['oracle_text'] == seed[MARCH]['oracle_text']
    with (OUT / ('march-facts-' + PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'march': raws[MARCH]}, stream, indent=2)
    return raws


def record(label, **observations):
    with (OUT / (PHASE + '-' + label + '.json')).open('x') as stream:
        json.dump(observations, stream, indent=2, sort_keys=True)


def zero_artifact_from_paid_sunfall(state, facts, seat):
    sunfall = g.add(state, facts, 'Sunfall', seat, Zone.HAND)
    creature = g.add(state, facts, 'Monastery Swiftspear', 3-seat)
    state.players[seat].mana_pool = {'C': 3, 'W': 2}
    state = g.cast(state, seat, sunfall)
    assert sum(state.players[seat].mana_pool.values()) == 0
    g.resolve(state)
    assert state.cards[creature].zone == Zone.EXILE
    token = next(c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD)
    assert token.counters == {'+1/+1': 1} and 'Artifact' in token.types and 'Creature' not in token.types
    assert mana_value(token.mana_cost) == 0
    return state, token.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
@pytest.mark.parametrize('target_type', ['artifact', 'creature', 'enchantment'])
def test_current_full_canonical_march_cost_block_is_atomic(facts, seat, x_value, target_type):
    state = g.position(facts, seat)
    if x_value == 0 and target_type == 'artifact':
        state, target = zero_artifact_from_paid_sunfall(state, facts, seat)
    else:
        name = ({'artifact': "Witch's Oven", 'creature': 'Dryad Arbor', 'enchantment': "Urza's Saga"}
                if x_value == 0 else
                {'artifact': "Witch's Oven", 'creature': 'Monastery Swiftspear', 'enchantment': 'Intangible Virtue'})[target_type]
        target = g.add(state, facts, name, 3-seat)
    assert mana_value(state.cards[target].mana_cost) <= x_value
    source = g.add(state, facts, MARCH, seat, Zone.HAND)
    white = g.add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    nonwhite = g.add(state, facts, 'Searing Blaze', seat, Zone.HAND)
    state = g.respond(state, seat)
    state.players[seat].mana_pool = {'C': x_value, 'W': 1}
    before = serialize_match_snapshot(state)
    assert spell_additional_costs(state.cards[source].oracle_text, MARCH) is None
    assert collect_cost_options(state, seat, state.cards[source]) == []
    assert 'unsupported spell additional cost' in known_unsupported_mechanics(
        state.cards[source].oracle_text, card_name=MARCH)
    action = {'type': 'cast_spell', 'card_id': source, 'cost_choice': {'id': 'base'},
              'targets': {'x_value': x_value, 'target_card_id': target}}
    with pytest.raises(ActionRejected) as rejected:
        g.act(state, seat, 'cast_spell', card_id=source, cost_choice=action['cost_choice'],
              targets=action['targets'])
    assert serialize_match_snapshot(state) == before
    assert state.cards[source].zone == state.cards[white].zone == state.cards[nonwhite].zone == Zone.HAND
    assert state.players[seat].mana_pool == {'C': x_value, 'W': 1}
    record(f'current-{seat}-{x_value}-{target_type}', raw_sha256=inv.canonical_hash(facts[MARCH]),
           action=action, rejection=str(rejected.value), target_mana_value=mana_value(state.cards[target].mana_cost),
           full_root_unchanged=True, mana_spent=0, cards_exiled_as_march_cost=0,
           parser_contract=None, actual_cost_options=[], scope='current unsupported cost blocker; no March resolution executed')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
def test_current_fullbody_hint_diagnostic_does_not_enforce_announced_x_cap(facts, seat, x_value):
    state = g.position(facts, seat)
    source = g.add(state, facts, MARCH, seat, Zone.HAND)
    creature_artifact = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    enchantment = g.add(state, facts, 'Leyline Binding', 3-seat)
    assert mana_value(state.cards[creature_artifact].mana_cost) == mana_value(state.cards[enchantment].mana_cost) == 6
    before = serialize_match_snapshot(state)
    hints = inspect_target_hints(state, state.cards[source], seat, {'x_value': x_value})
    ids = {row['id'] for key, rows in hints.items() if key.endswith('_targets') and isinstance(rows, list)
           for row in rows if isinstance(row, dict) and 'id' in row}
    assert {creature_artifact, enchantment} <= ids
    assert serialize_match_snapshot(state) == before
    record(f'hint-{seat}-{x_value}', raw_sha256=inv.canonical_hash(facts[MARCH]), selected_x=x_value,
           above_x_target_ids=[creature_artifact, enchantment], hints=hints, full_root_unchanged=True,
           scope='pure public compiler hint diagnostic only; cost admission blocks actual casting')


@pytest.mark.parametrize('suffix', [' Unknown diagnostic instruction.',
                                  '\nUnknown diagnostic instruction.', ' (Unknown diagnostic instruction.)'])
def test_current_unsupported_fullbody_suffix_remains_cost_blocked(facts, suffix):
    raw = deepcopy(facts[MARCH])
    raw['oracle_text'] += suffix
    assert spell_additional_costs(raw['oracle_text'], MARCH) is None
    assert 'unsupported spell additional cost' in known_unsupported_mechanics(raw['oracle_text'], card_name=MARCH)
