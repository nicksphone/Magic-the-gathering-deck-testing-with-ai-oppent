"""Target-only compiler controls; no assertion of supported March payment."""
from copy import copy
import json
import os

import pytest

import inventory as inv
import domain_paid_support as g
import test_march_desired_paid as desired
from ai.information import decision_view, is_unknown
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints
from rules_engine.type_effects import effective_types

MARCH = 'March of Otherworldly Light'
PHASE = os.environ['ADMISSION_PHASE']


@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    assert raws[MARCH]['id'] == seed[MARCH]['scryfall_id']
    assert raws[MARCH]['oracle_text'] == seed[MARCH]['oracle_text']
    with (inv.ROOT.parent / 'evidence' / ('target-facts-' + PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'march': raws[MARCH]}, stream, indent=2)
    return raws


def ids(hints):
    return {row['id'] for key, rows in hints.items() if key.endswith('_targets') and isinstance(rows, list)
            for row in rows if isinstance(row, dict) and 'id' in row}


def compiled(state, source, seat, target, x_value):
    return infer_effect_from_oracle(state, source, seat,
        {'target_card_id': target, 'x_value': x_value}, report_unsupported=False)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
@pytest.mark.parametrize('target_type', ['artifact', 'creature', 'enchantment'])
def test_complete_body_valid_type_mv_compiles_without_query_mutation(facts, seat, x_value, target_type):
    state, source, target, _ = desired.prepare(facts, seat, x_value, target_type)
    before = serialize_match_snapshot(state)
    assert compiled(state, state.cards[source], seat, target, x_value) == ('exile', {'target_card_id': target})
    assert target in ids(inspect_target_hints(state, state.cards[source], seat, {'x_value': x_value}))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [0, 2, 4])
def test_above_x_has_no_compiled_exile_or_public_target(facts, seat, x_value):
    state, source, _, _ = desired.prepare(facts, seat, x_value, 'creature')
    targets = [g.add(state, facts, 'Torrential Gearhulk', 3-seat),
               g.add(state, facts, 'Leyline Binding', 3-seat)]
    before = serialize_match_snapshot(state)
    hints = inspect_target_hints(state, state.cards[source], seat, {'x_value': x_value})
    for target in targets:
        key, payload = compiled(state, state.cards[source], seat, target, x_value)
        assert key == 'noop' and '__unsupported_instruction' in payload
        assert target not in ids(hints)
    assert serialize_match_snapshot(state) == before


TAILS = [' Unknown diagnostic instruction.', '\nUnknown diagnostic instruction.',
         ' (Unknown diagnostic instruction.)', '\n{W}: Draw a card.',
         '\nExile target land.', '\nForetell {W}']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', TAILS)
def test_unknown_full_raw_tail_never_becomes_partial_exile(facts, seat, tail):
    state, source, target, _ = desired.prepare(facts, seat, 2, 'artifact')
    diagnostic = copy(state.cards[source])
    diagnostic.oracle_text += tail
    before = serialize_match_snapshot(state)
    key, payload = compiled(state, diagnostic, seat, target, 2)
    assert key == 'noop' and '__unsupported_instruction' in payload
    assert not ids(inspect_target_hints(state, diagnostic, seat, {'x_value': 2}))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x_value', [None, True, -1, 1.5, '2', [], {}])
def test_announced_x_is_strict_integer_without_coercion(facts, seat, x_value):
    state, source, target, _ = desired.prepare(facts, seat, 2, 'artifact')
    before = serialize_match_snapshot(state)
    key, payload = compiled(state, state.cards[source], seat, target, x_value)
    assert key == 'noop' and '__unsupported_instruction' in payload
    assert not ids(inspect_target_hints(state, state.cards[source], seat, {'x_value': x_value}))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_body_contract_is_not_a_card_name_branch(facts, seat):
    state, source, target, _ = desired.prepare(facts, seat, 2, 'artifact')
    diagnostic = copy(state.cards[source])
    diagnostic.name = 'Diagnostic generic complete body'
    before = serialize_match_snapshot(state)
    assert compiled(state, diagnostic, seat, target, 2) == ('exile', {'target_card_id': target})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_public_target_queries_do_not_expose_or_mutate_private_hand(facts, seat):
    state, source, target, _ = desired.prepare(facts, seat, 2, 'artifact')
    secret = g.add(state, facts, 'Sunfall', 3-seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    def public_snapshots():
        snapshots = {}
        for viewer in (1, 2):
            view, moves = decision_view(state, viewer, g.RulesEngine().legal_moves(state, viewer))
            if viewer == seat:
                assert is_unknown(view.cards[secret])
                assert not view.cards[secret].name and not view.cards[secret].oracle_text
            # MatchState equality compares Random identity; snapshots retain RNG state.
            snapshots[viewer] = (serialize_match_snapshot(view), moves)
        return snapshots
    views = public_snapshots()
    hints = inspect_target_hints(state, state.cards[source], seat, {'x_value': 2})
    assert target in ids(hints) and secret not in ids(hints)
    assert secret not in json.dumps(hints)
    assert compiled(state, state.cards[source], seat, target, 2)[0] == 'exile'
    assert serialize_match_snapshot(state) == before
    assert public_snapshots() == views


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_nissa_animation_changes_effective_target_type(facts, seat):
    state = g.position(facts, seat)
    source = g.add(state, facts, MARCH, seat, Zone.HAND)
    forest = g.add(state, facts, 'Forest', seat)
    assert 'Creature' not in effective_types(state, state.cards[forest])
    assert forest not in ids(inspect_target_hints(state, state.cards[source], seat, {'x_value': 0}))
    nissa = g.add(state, facts, 'Nissa, Who Shakes the World', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 3, 'G': 2}
    state = g.cast(state, seat, nissa)
    assert sum(state.players[seat].mana_pool.values()) == 0
    g.resolve(state)
    loyalty = state.cards[nissa].loyalty
    state = g.act(g.respond(state, seat), seat, 'activate_loyalty', card_id=nissa,
                  ability_index=0, targets={'target_card_id': forest})
    assert state.cards[nissa].loyalty == loyalty + 1
    g.resolve(state)
    assert {'Land', 'Creature'} <= set(effective_types(state, state.cards[forest]))
    before = serialize_match_snapshot(state)
    assert forest in ids(inspect_target_hints(state, state.cards[source], seat, {'x_value': 0}))
    assert compiled(state, state.cards[source], seat, forest, 0) == ('exile', {'target_card_id': forest})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['land-only', 'planeswalker', 'hand-zone', 'unknown-id'])
def test_wrong_type_zone_or_missing_object_cannot_compile_exile(facts, seat, fault):
    state, source, _, _ = desired.prepare(facts, seat, 4, 'artifact')
    if fault == 'land-only':
        target = g.add(state, facts, 'Forest', 3-seat)
    elif fault == 'planeswalker':
        target = g.add(state, facts, 'Nissa, Who Shakes the World', 3-seat)
    elif fault == 'hand-zone':
        target = g.add(state, facts, 'Torrential Gearhulk', 3-seat, Zone.HAND)
    else:
        target = 'missing-owned-diagnostic-object'
    before = serialize_match_snapshot(state)
    key, payload = compiled(state, state.cards[source], seat, target, 6)
    assert key == 'noop' and '__unsupported_instruction' in payload
    assert target not in ids(inspect_target_hints(state, state.cards[source], seat, {'x_value': 6}))
    assert serialize_match_snapshot(state) == before
