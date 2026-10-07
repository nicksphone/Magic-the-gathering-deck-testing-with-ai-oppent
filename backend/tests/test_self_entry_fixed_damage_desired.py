"""Unexecuted canonical desired controls; no synthetic Oracle, frames or events."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.observations import public_card_ids, remembered_hand_card
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.oracle_effects import compile_self_entry_damage_clause
from rules_engine.targeting import stack_object_kind
from tests import test_hand_source_incarnation_causal_audit as original
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_generic_protection_damage import CANONICAL
from tests.test_kozilek_graveyard_trigger_audit import FRESH
from tests.test_linked_damage_targets import raw_card


SCENARIOS = (
    'opponent-player', 'own-player', 'opponent-creature', 'own-source',
    'target-choice-json-restart', 'source-bounce', 'target-bounce',
    'stifle-trigger', 'source-control-change', 'channel-control',
    'canonical-bolt-control', 'humility-entry-control',
)


def assert_closed_paragraph_contract():
    """Malformed strings are parser protocols, never substituted game Oracle."""
    name = 'Twinshot Sniper'
    clause = next(line for line in original.ROWS[name]['oracle_text'].splitlines()
                  if line.startswith('When this creature enters,'))
    key, data = compile_self_entry_damage_clause(clause, name)
    assert key == 'deal_damage' and data['amount'] == 2
    assert not any(key.startswith('target_') for key in data)
    malformed = (
        clause + ' Draw a card.', clause + '\nDraw a card.', clause + '\n' + clause,
        clause.replace('it deals', 'if you control an artifact, it deals'),
        clause.replace('deals 2', 'deals 0'), clause.replace('deals 2', 'deals X'),
        clause.replace('it deals', 'target creature deals'),
        clause + ' (Only if you control an artifact.)',
    )
    for text in malformed:
        key, diagnostic = compile_self_entry_damage_clause(text, name)
        assert key == 'noop' and diagnostic['__unsupported_trigger_instruction']
        assert 'amount' not in diagnostic and '__trigger_resolution_text' not in diagnostic
    assert compile_self_entry_damage_clause('Reach', name) is None
    channel = original.ROWS[name]['oracle_text'].splitlines()[-1]
    assert compile_self_entry_damage_clause(channel, name) is None


def prepare(seat, *, suppressed=False):
    state, source, creature, spells = original.setup(
        seat, 'sniper', suppress_entry=suppressed)
    # Declared human-choice configuration, not a game-state or Oracle repair.
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    return state, source, creature, spells


def restore_private(state):
    state = original.reload_exact(state)
    before = original.serialize_match_snapshot(state)
    assert_private(state)
    assert original.serialize_match_snapshot(state) == before
    return state


def restore_public_return(state, witness):
    state = original.reload_exact(state)
    before = original.serialize_match_snapshot(state)
    cid = witness['public_before']['id']
    card = state.cards[cid]
    assert card.zone == Zone.HAND and cid in state.players[card.owner].hand
    assert original.object_incarnation(card) == witness['returned_reference']['incarnation']
    assert card.zone_change_sequence == witness['returned_reference']['zone_change_sequence']
    for viewer in (1, 2):
        record = state.card_observations[viewer][cid]
        assert record == witness['observed_records'][viewer]
        assert record['zone'] == Zone.HAND.value
        assert record['zone_change_sequence'] == witness['public_before']['zone_change_sequence'] + 1
        for key in ('id', 'owner', 'name', 'oracle_text'):
            assert record[key] == witness['public_before'][key]
        remembered = remembered_hand_card(state, viewer, card)
        assert remembered is not None and remembered.name == record['name']
        assert remembered.oracle_text == record['oracle_text']
        view, _ = decision_view(state, viewer, original.RULES.legal_moves(state, viewer))
        assert all(is_unknown(view.cards[hidden]) for player in state.players.values()
                   for hidden in player.library)
        for hidden in state.players[3-viewer].hand:
            if hidden == cid:
                assert view.cards[hidden].name == record['name']
                assert view.cards[hidden].oracle_text == record['oracle_text']
                assert original.object_incarnation(view.cards[hidden]) == witness['returned_reference']['incarnation']
            else:
                assert is_unknown(view.cards[hidden])
        # Hypothetical hidden mutations/permutations must not manufacture knowledge.
        probe = deepcopy(state)
        hidden_ids = set(probe.players[3-viewer].hand)
        for player in probe.players.values():
            hidden_ids.update(player.library)
            player.library.reverse()
        probe.players[3-viewer].hand.reverse()
        for hidden in hidden_ids:
            probe.cards[hidden].name = 'Unobserved hidden identity'
            probe.cards[hidden].oracle_text = 'Unobserved hidden text'
        projected, _ = decision_view(probe, viewer, [])
        for hidden in hidden_ids:
            if hidden == cid:
                assert projected.cards[hidden].name == record['name']
                assert projected.cards[hidden].oracle_text == record['oracle_text']
            else:
                assert is_unknown(projected.cards[hidden])
    assert original.serialize_match_snapshot(state) == before
    return state


def enter_over_channel(seat):
    state, source, creature, spells = prepare(seat)
    state, channel, channel_ref = original.announce(state, source, creature, seat)
    state, spell = original.cast(
        state, spells['Zombify'], seat, {'target_card_id': source})
    state = original.until(state, lambda s: any(
        item.source_card_id == source
        and item.payload.get('__trigger_event') == 'enters_battlefield'
        for item in s.stack))
    assert all(item.id != spell for item in state.stack)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    entry = next(item for item in state.stack if item.source_card_id == source
                 and item.payload.get('__trigger_event') == 'enters_battlefield')
    assert entry.id != channel and entry.controller == seat
    assert stack_object_kind(state, entry) == 'triggered'
    assert entry.effect_key == 'deal_damage', 'Complete canonical self-entry body must compile'
    assert entry.payload['amount'] == 2
    clause = next(line for line in original.ROWS['Twinshot Sniper']['oracle_text'].splitlines()
                  if line.startswith('When this creature enters,'))
    assert entry.payload['__trigger_full_clause'].casefold() == clause.casefold()
    pending = state.pending_trigger_order
    assert pending and pending['phase'] == 'targets'
    assert pending['current_stack_id'] == entry.id
    assert pending['current_controller'] == seat
    lower = next(item for item in state.stack if item.id == channel)
    assert lower.payload['__activation_source_reference'] == channel_ref
    assert lower.payload['__activation_source_context']['origin_zone'] == 'hand'
    return state, source, creature, spells, channel, channel_ref, entry.id


def select_offered(state, seat, frame, target):
    moves = original.RULES.legal_moves(state, seat)
    action = next(move for move in moves if move.get('type') == 'choose_trigger_target'
                  and move.get('stack_id') == frame
                  and all(move.get(key) == value for key, value in target.items()))
    # An actual card still in hand is not an any-target battlefield recipient.
    unoffered = next(cid for cid in state.players[seat].hand)
    before = original.serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        original.act(state, seat, {'type': 'choose_trigger_target', 'stack_id': frame,
                                  'target_card_id': unoffered})
    assert original.serialize_match_snapshot(state) == before
    state = original.act(state, seat, deepcopy(action))
    assert state.pending_trigger_order is None
    item = next(item for item in state.stack if item.id == frame)
    assert all(item.payload.get(key) == value for key, value in target.items())
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_actual_canonical_self_entry_and_independent_controls(seat, scenario):
    if scenario == 'channel-control':
        assert_closed_paragraph_contract()
        state, source, creature, _ = prepare(seat)
        state, channel, _ = original.announce(state, source, creature, seat)
        state = original.until(restore_private(state),
                               lambda s: all(item.id != channel for item in s.stack))
        assert state.players[3-seat].life == 18 and state.players[seat].life == 20
        assert state.cards[source].zone == Zone.GRAVEYARD
        return
    if scenario == 'canonical-bolt-control':
        state, source, _, _ = prepare(seat)
        bolt = raw_card(state, CANONICAL['Lightning Bolt'], seat, Zone.HAND)
        state, frame = original.cast(state, bolt.id, seat, {'target_player': 3-seat})
        state = original.until(restore_private(state),
                               lambda s: all(item.id != frame for item in s.stack))
        assert state.players[3-seat].life == 17 and state.players[seat].life == 20
        assert state.cards[bolt.id].zone == Zone.GRAVEYARD
        assert state.cards[source].zone == Zone.HAND
        return
    if scenario == 'humility-entry-control':
        state, source, creature, spells = prepare(seat, suppressed=True)
        state, channel, ref = original.announce(state, source, creature, seat)
        state, spell = original.cast(state, spells['Zombify'], seat, {'target_card_id': source})
        state = original.until(state, lambda s: all(item.id != spell for item in s.stack))
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert not any(item.source_card_id == source and item.id != channel for item in state.stack)
        assert next(item for item in state.stack if item.id == channel).payload['__activation_source_reference'] == ref
        state = original.until(restore_private(state),
                               lambda s: all(item.id != channel for item in s.stack))
        assert state.players[3-seat].life == 18 and state.players[seat].life == 20
        return

    state, source, creature, spells, channel, ref, entry = enter_over_channel(seat)
    target = ({'target_card_id': creature} if scenario in ('opponent-creature', 'target-bounce')
              else {'target_card_id': source} if scenario == 'own-source'
              else {'target_player': seat if scenario == 'own-player' else 3-seat})
    if scenario == 'target-choice-json-restart':
        state = restore_private(state)
        assert state.pending_trigger_order['current_stack_id'] == entry
    state = select_offered(state, seat, entry, target)

    restorer = restore_private
    if scenario in ('source-bounce', 'target-bounce'):
        bounced = source if scenario == 'source-bounce' else creature
        public_before = deepcopy(state.cards[bounced])
        assert public_before.zone == Zone.BATTLEFIELD and bounced in public_card_ids(state)
        state, response = original.cast(state, spells['Unsummon'], seat, {'target_card_id': bounced})
        actual_response = next(item for item in state.stack if item.id == response)
        assert actual_response.source_card_id == spells['Unsummon'] and actual_response.controller == seat
        assert actual_response.effect_key == 'return_permanent_to_hand'
        assert actual_response.payload['target_card_id'] == bounced
        assert actual_response.payload['__announced_targets']['target_card_id'] == bounced
        assert actual_response.payload['mana_spent'] == 1
        assert state.cards[spells['Unsummon']].oracle_text == original.ROWS['Unsummon']['oracle_text']
        state = original.until(state, lambda s: all(item.id != response for item in s.stack))
        assert state.cards[bounced].zone == Zone.HAND
        assert any(item.id == entry for item in state.stack)
        returned = state.cards[bounced]
        assert returned.zone_change_sequence == public_before.zone_change_sequence + 1
        witness = {'scenario': scenario, 'actor': seat, 'response': asdict(actual_response),
                   'public_before': asdict(public_before), 'turn': state.turn, 'step': state.step.value,
                   'returned_reference': {'incarnation': original.object_incarnation(returned),
                                          'zone_change_sequence': returned.zone_change_sequence},
                   'observed_records': {viewer: deepcopy(state.card_observations[viewer][bounced])
                                        for viewer in (1, 2)}}
        restorer = lambda current: restore_public_return(current, witness)
        state = restorer(state)
        trace = os.environ.get('MTG_PUBLIC_RETURN_TRACE')
        if trace:
            with Path(trace).open('a') as output:
                output.write(json.dumps(witness, sort_keys=True) + '\n')
    elif scenario == 'stifle-trigger':
        stifle = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
        state, response = original.cast(state, stifle.id, 3-seat, {'target_stack_id': entry})
        state = original.until(state, lambda s: all(item.id != response for item in s.stack))
        assert all(item.id != entry for item in state.stack)
        assert state.cards[stifle.id].zone == Zone.GRAVEYARD
    elif scenario == 'source-control-change':
        state, response = original.cast(state, spells['Ray of Command'], 3-seat,
                                        {'target_card_id': source})
        state = original.until(state, lambda s: all(item.id != response for item in s.stack))
        assert state.cards[source].controller == 3-seat
        assert next(item for item in state.stack if item.id == entry).controller == seat

    state = original.until(restorer(state),
                           lambda s: all(item.id != entry for item in s.stack))
    assert next(item for item in state.stack if item.id == channel).payload['__activation_source_reference'] == ref
    if scenario in ('target-bounce', 'stifle-trigger'):
        assert state.players[1].life == state.players[2].life == 20
        assert state.cards[creature].counters.get('__damage_marked', 0) == 0
    elif 'target_card_id' in target:
        assert state.cards[target['target_card_id']].counters.get('__damage_marked') == 2
        assert state.players[1].life == state.players[2].life == 20
    else:
        assert state.players[target['target_player']].life == 18
        assert state.players[3-target['target_player']].life == 20
