"""Canonical zero-entry goldens; native layer/retained-context probes are labelled."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.entry_counters import (entry_counter_modifier,
    resident_entry_counter_options, entry_counter_context_matches, prepare_counter_entries)
from tests.test_graveyard_self_activation_product import (
    ROWS, FAMILIES, position, paid, resolve, act, snapshot, raw_card)

RENATA = 'Renata, Called to the Hunt'
SEASON = 'Doubling Season'
LAEZEL = "Lae'zel, Vlaakith's Champion"
CLAUSE = 'Each other creature you control enters with an additional +1/+1 counter on it.'
FIXTURES = Path(__file__).parent / 'fixtures/resident_entry_counter_provider'
BALLISTA_BYTES = (FIXTURES / 'walking-ballista.json').read_bytes()
BALLISTA_PROVENANCE = json.loads((FIXTURES / 'provenance.json').read_text())
assert hashlib.sha256(BALLISTA_BYTES).hexdigest() == BALLISTA_PROVENANCE['line_sha256']
BALLISTA = json.loads(BALLISTA_BYTES)


def resident(state, name, seat):
    card = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def pending_position(seat):
    state, card = position(seat, FAMILIES[0])
    residents = [resident(state, name, seat).id for name in (RENATA, SEASON, LAEZEL)]
    state.replacement_choice_players = {seat}
    return resolve(paid(state, seat, card)), card.id, residents


def finish_choices(state, preference):
    choices = []
    for _ in range(8):
        if not state.pending_replacement_choice:
            return state, choices
        restored = deserialize_match_snapshot(snapshot(state))
        assert snapshot(restored) == snapshot(state)
        state = restored
        pending = state.pending_replacement_choice
        options = pending['options']
        option = next((value for value in options if value['operation'] == preference), options[0])
        choices.append(option['source_id'])
        state = act(state, pending['player_id'], {
            'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    raise AssertionError('Entry replacement failed to terminate')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('names,preference,expected', [
    ((RENATA,), 'add', 1), ((RENATA, SEASON), 'add', 2),
    ((RENATA, LAEZEL), 'add', 2),
    ((RENATA, SEASON, LAEZEL), 'add', 4),
    ((RENATA, SEASON, LAEZEL), 'double', 3),
    # Real checked payment runs the legend rule: only one Renata survives.
    ((RENATA, RENATA, SEASON), 'add', 2),
    ((RENATA, RENATA, SEASON), 'double', 2),
])
def test_canonical_zero_entry_order_and_each_source_once(seat, names, preference, expected):
    state, card = position(seat, FAMILIES[0])
    for name in names:
        resident(state, name, seat)
    state.replacement_choice_players = {seat}
    before = snapshot(state)
    state = resolve(paid(state, seat, card))
    if state.pending_replacement_choice:
        pending = state.pending_replacement_choice
        assert pending['player_id'] == seat
        assert state.cards[card.id].zone == Zone.GRAVEYARD
        assert not state.cards[card.id].counters.get('+1/+1')
    result, choices = finish_choices(state, preference)
    assert len(choices) == len(set(choices))
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert result.cards[card.id].controller == seat and result.cards[card.id].tapped
    assert result.cards[card.id].counters['+1/+1'] == expected
    assert result.players[seat].battlefield.count(card.id) == 1
    assert not any(result.players[seat].mana_pool.values())
    if names.count(RENATA) == 2:
        assert sum(result.cards[cid].name == RENATA for cid in result.players[seat].battlefield) == 1
        assert sum(result.cards[cid].name == RENATA for cid in result.players[seat].graveyard) == 1
        assert any('legend rule' in message for message in result.log)
    repeated_root = deserialize_match_snapshot(before)
    repeat = resolve(paid(repeated_root, seat, repeated_root.cards[card.id]))
    repeat, repeated_choices = finish_choices(repeat, preference)
    assert snapshot(repeat) == snapshot(result) and repeated_choices == choices


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('names', [(), (SEASON,), (LAEZEL,), (SEASON, LAEZEL)])
def test_modifiers_without_entry_producer_do_not_manufacture_counters(seat, names):
    state, card = position(seat, FAMILIES[0])
    for name in names:
        resident(state, name, seat)
    result = resolve(paid(state, seat, card))
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert not result.cards[card.id].counters.get('+1/+1')
    assert not result.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('failure', ['source_aba', 'season_aba', 'laezel_aba', 'recipient_aba', 'source_gone',
    'source_controller', 'source_clause', 'season_clause_index', 'missing_receipts', 'forged_producer'])
def test_retained_context_rejects_stale_snapshot_atomically(seat, failure):
    state, cid, sources = pending_position(seat)
    assert state.pending_replacement_choice
    state = deserialize_match_snapshot(snapshot(state))
    payload = state.pending_replacement_choice['counter_payload']
    if failure in {'source_aba', 'season_aba', 'laezel_aba', 'recipient_aba'}:
        chosen = {'source_aba': sources[0], 'season_aba': sources[1],
                  'laezel_aba': sources[2], 'recipient_aba': cid}[failure]
        card = state.cards[chosen]
        zone = card.zone
        card.move_to_zone(Zone.EXILE)
        card.move_to_zone(zone)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
    elif failure == 'source_gone':
        state.cards[sources[0]].move_to_zone(Zone.EXILE)
    elif failure == 'source_controller':
        state.cards[sources[0]].controller = 3-seat
    elif failure == 'source_clause':
        # Deliberately corrupted snapshot, not invented canonical semantics.
        state.cards[sources[0]].oracle_text += ' Unknown tail.'
    elif failure == 'season_clause_index':
        state.cards[sources[1]].oracle_text = '\n'.join(reversed(state.cards[sources[1]].oracle_text.splitlines()))
    elif failure == 'missing_receipts':
        payload['__counter_entry_context']['source_references'] = []
    else:
        payload['__counter_entry_producers'][0]['operand'] = 99
    before = snapshot(state)
    assert not entry_counter_context_matches(state, payload)
    option = state.pending_replacement_choice['options'][0]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_actor_choice_is_root_atomic(seat):
    state, _, _ = pending_position(seat)
    before = snapshot(state)
    option = state.pending_replacement_choice['options'][0]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {
            'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_resident_and_prospective_noncreature_query_purity(seat):
    state, card = position(seat, FAMILIES[0])
    foreign = resident(state, RENATA, 3-seat)
    before = snapshot(state)
    assert not resident_entry_counter_options(state, card, seat)
    assert resident_entry_counter_options(state, card, 3-seat)
    assert not resident_entry_counter_options(state, foreign, 3-seat)
    assert snapshot(state) == before
    other = raw_card(state, ROWS[SEASON], seat, Zone.GRAVEYARD)
    with_other = snapshot(state)
    assert not resident_entry_counter_options(state, other, 3-seat)
    assert snapshot(state) == with_other


@pytest.mark.parametrize('seat', [1, 2])
def test_simultaneous_batch_sources_are_not_residents(seat):
    state, card = position(seat, FAMILIES[0])
    provider = raw_card(state, ROWS[RENATA], seat, Zone.GRAVEYARD)
    before = snapshot(state)
    # Real generic batch preparation/handler route; no forged pending/options.
    prepare_counter_entries(state, seat, [provider, card], 'noop', {})
    assert not state.pending_replacement_choice
    assert snapshot(state)['cards'] == before['cards']


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_prohibition_outranks_entry_producer(seat):
    from tests.test_counter_prohibitions import source
    state, card = position(seat, FAMILIES[0])
    resident(state, RENATA, seat)
    source(state, 'Solemnity', 3-seat)
    result = resolve(paid(state, seat, card))
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert result.cards[card.id].tapped and not result.cards[card.id].counters.get('+1/+1')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_canonical_ovinize_suppresses_resident_instruction(seat):
    from rules_engine.continuous import printed_abilities_suppressed
    rows = json.loads((Path(__file__).parent / 'fixtures/temporary_ability_loss.json').read_text())
    state, card = position(seat, FAMILIES[0])
    provider = resident(state, RENATA, seat)
    spell = raw_card(state, next(row for row in rows if row['name'] == 'Ovinize'), seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1, 'C': 1}
    state = resolve(act(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                        'targets': {'target_card_id': provider.id}}))
    assert printed_abilities_suppressed(state, provider.id)
    before = snapshot(state)
    assert not resident_entry_counter_options(state, state.cards[card.id], seat)
    assert snapshot(state) == before
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    result = resolve(paid(state, seat, state.cards[card.id]))
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert not result.cards[card.id].counters.get('+1/+1')


@pytest.mark.parametrize('tail', [' Draw a card.', ' if you gained life.',
                                ' (Activate only during your turn.)'])
def test_complete_clause_unknown_tail_is_not_admitted(tail):
    assert entry_counter_modifier(CLAUSE) == {'operation': 'add', 'operand': 1}
    assert entry_counter_modifier(CLAUSE + tail) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_artifact_creature_prospective_query_is_pure(seat):
    state, _ = position(seat, FAMILIES[0])
    resident(state, RENATA, seat)
    card = raw_card(state, BALLISTA, seat, Zone.HAND)
    before = snapshot(state)
    options = resident_entry_counter_options(state, card, seat)
    assert len(options) == 1 and options[0]['clause'] == CLAUSE
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('preference', ['add', 'double'])
def test_intrinsic_entry_observation_is_not_complete_order_certificate(seat, preference):
    state, _ = position(seat, FAMILIES[0])
    resident(state, RENATA, seat)
    resident(state, SEASON, seat)
    card = raw_card(state, BALLISTA, seat, Zone.HAND)
    printed = deepcopy((card.oracle_text, card.types, card.mana_cost))
    state.replacement_choice_players = {seat}
    state.players[seat].mana_pool = {'C': 4}
    before = snapshot(state)
    state = resolve(act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                                    'targets': {'x_value': 2}}))
    pending = deepcopy(state.pending_replacement_choice)
    assert pending and state.cards[card.id].zone == Zone.STACK
    # Intrinsic and resident producers are selectable before positive counters exist.
    assert pending['counter_payload']['amount'] == 0
    assert pending['counter_payload']['__intrinsic_entry_counter']['locked_x'] == 2
    assert {option['name'] for option in pending['options']} == {RENATA, BALLISTA['name']}
    assert any(option.get('intrinsic_entry') for option in pending['options'])
    result, choices = finish_choices(state, preference)
    assert result.cards[card.id].zone == Zone.BATTLEFIELD
    assert not any(result.players[seat].mana_pool.values())
    assert (result.cards[card.id].oracle_text, result.cards[card.id].types,
            result.cards[card.id].mana_cost) == printed
    report = {'scope': 'paid canonical observation, NOT complete intrinsic-entry ordering',
              'seat': seat, 'preference': preference, 'before': before,
              'pending': pending, 'after': snapshot(result), 'choices': choices,
              'observed_counters': result.cards[card.id].counters.get('+1/+1'),
              'intrinsic_entry_replacement_option_exposed': any(
                  option.get('intrinsic_entry') for option in pending['options']),
              'source_provenance': BALLISTA_PROVENANCE}
    path = Path(os.environ['MTG_GY_SELF_EVIDENCE']) / f'intrinsic-{seat}-{preference}.json'
    with path.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
