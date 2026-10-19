"""Genuine paid canonical rules fixtures; no injected stack items or cast events."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine
from rules_engine import events
from tests import test_soulscar_preflight_rules_audit as base


FIXTURES = Path(__file__).parent / 'fixtures'
ROWS = {row['name']: row for row in json.loads((FIXTURES / 'aura_costs.json').read_text())}
ROWS.update(base.CARDS)
for relative in ('announced_target_references/pyrotechnics.json',
                 'announced_target_references/twincast.json',
                 'trigger_instruction_product/counterspell.json',
                 'favor_target_lifecycle/unsummon.json',
                 'favor_target_lifecycle/cloudshift.json',
                 'soulscar_protection_boundaries/dress-down.json'):
    raw = json.loads((FIXTURES / relative).read_text())
    ROWS[raw['name']] = raw


def snap(state):
    return serialize_match_snapshot(state)


def reload(state):
    before = snap(state)
    result = deserialize_match_snapshot(before)
    assert snap(result) == before
    return result


def add(state, name, owner, zone=Zone.HAND):
    raw = ROWS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7107)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = owner
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[owner], zone.value).append(card.id)
    return card.id


def act(state, seat, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before
    return result


def priority(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return state


def cast(state, seat, name, targets=None):
    state = priority(state, seat)
    cid = add(state, name, seat)
    before_pool = deepcopy(state.players[seat].mana_pool)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid,
                              'targets': targets or {}, 'cost_choice': {'id': 'base'}})
    assert state.cards[cid].zone == Zone.STACK
    assert state.players[seat].mana_pool != before_pool
    return reload(state), cid


def passes(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return reload(state)


def board(seat):
    state = base.position(seat)  # Explicit starting resources, not a natural game.
    state, hero = cast(state, seat, 'Hero of Iroas')
    state = passes(state)
    assert state.cards[hero].zone == Zone.BATTLEFIELD
    return state, hero


def triggers(state, hero):
    return [item for item in state.stack if item.source_card_id == hero and
            item.effect_key == 'add_counters' and item.payload.get('__trigger_event') == 'spell_cast']


def announcement(state, spell):
    return next(item for item in state.stack if item.source_card_id == spell)


def test_full_existing_canonical_provenance_is_preserved():
    provenance = json.loads((FIXTURES / 'heroic_cast_target_contract/provenance.json').read_text())
    for row in provenance['sources']:
        path = Path(__file__).parents[1] / row['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    assert ROWS['Hero of Iroas']['oracle_text'].endswith(
        'Whenever you cast a spell that targets this creature, put a +1/+1 counter on this creature.')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spirit Mantle', 'Unholy Heat'])
def test_paid_aura_and_instant_publish_counter_before_original_resolution(seat, name):
    state, hero = board(seat)
    state, spell = cast(state, seat, name, {'target_card_id': hero})
    frame = announcement(state, spell)
    reference = frame.payload['__announced_target_references']['targets']['target_card_id']
    assert reference == {'card_id': hero, 'incarnation': object_incarnation(state.cards[hero]),
                         'zone_change_sequence': state.cards[hero].zone_change_sequence}
    assert len(triggers(state, hero)) == 1 and state.stack[-1] in triggers(state, hero)
    state = passes(state)
    assert state.cards[hero].counters.get('+1/+1') == 1
    assert state.cards[spell].zone == Zone.STACK
    state = passes(state)
    assert state.cards[hero].zone == Zone.BATTLEFIELD
    assert state.cards[hero].counters.get('+1/+1') == 1
    assert state.cards[spell].zone == (Zone.BATTLEFIELD if name == 'Spirit Mantle' else Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_divided_spell_uses_matching_receipt_slot_once(seat):
    state, hero = board(seat)
    other = add(state, 'Colossal Dreadmaw', 3-seat, Zone.BATTLEFIELD)
    state, spell = cast(state, seat, 'Pyrotechnics', {'target_distribution': {hero: 1, other: 3}})
    references = announcement(state, spell).payload['__announced_target_references']['targets']
    assert references['target_distribution'][hero]['card_id'] == hero
    assert references['target_distribution'][other]['card_id'] == other
    assert len(triggers(state, hero)) == 1
    state = passes(state)
    assert state.cards[hero].counters.get('+1/+1') == 1
    state = passes(state)
    assert state.cards[hero].zone == Zone.BATTLEFIELD
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opponent', [False, True])
def test_other_target_or_opponent_cast_does_not_trigger(seat, opponent):
    state, hero = board(seat)
    other = add(state, 'Colossal Dreadmaw', seat, Zone.BATTLEFIELD)
    actor = 3-seat if opponent else seat
    state, _ = cast(state, actor, 'Unholy Heat', {'target_card_id': hero if opponent else other})
    assert not triggers(state, hero)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_copy_does_not_retrigger_cast_only_clause(seat):
    state, hero = board(seat)
    state.mechanic_choice_players = {1, 2}
    add(state, 'Colossal Dreadmaw', 3-seat, Zone.BATTLEFIELD)
    state, original = cast(state, seat, 'Unholy Heat', {'target_card_id': hero})
    assert len(triggers(state, hero)) == 1
    state = passes(state)
    assert state.cards[hero].counters.get('+1/+1') == 1
    original_frame = announcement(state, original)
    state, _ = cast(state, seat, 'Twincast', {'target_stack_id': original_frame.id})
    assert not triggers(state, hero)
    state = passes(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'copy_target' and 'keep' in pending['options']
    state = act(state, pending['player_id'], {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert not triggers(state, hero)
    assert state.cards[hero].counters.get('+1/+1') == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_counter_original_spell_does_not_remove_existing_trigger(seat):
    state, hero = board(seat)
    state, original = cast(state, seat, 'Spirit Mantle', {'target_card_id': hero})
    assert len(triggers(state, hero)) == 1
    original_frame = announcement(state, original)
    state, _ = cast(state, 3-seat, 'Counterspell', {'target_stack_id': original_frame.id})
    state = passes(state)
    assert state.cards[original].zone == Zone.GRAVEYARD
    assert len(triggers(state, hero)) == 1
    state = passes(state)
    assert state.cards[hero].counters.get('+1/+1') == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blink', [False, True])
def test_paid_source_departure_reentry_does_not_reward_later_same_id(seat, blink):
    state, hero = board(seat)
    old_incarnation = object_incarnation(state.cards[hero])
    state, original = cast(state, seat, 'Unholy Heat', {'target_card_id': hero})
    assert len(triggers(state, hero)) == 1
    state, _ = cast(state, seat if blink else 3-seat,
                    'Cloudshift' if blink else 'Unsummon', {'target_card_id': hero})
    if blink:
        assert len(triggers(state, hero)) == 2
        state = passes(state)  # Heroic from casting Cloudshift, before blink itself.
    state = passes(state)
    if not blink:
        assert state.cards[hero].zone == Zone.HAND
        state = passes(state)  # Old trigger resolves while its source is absent.
        assert state.cards[hero].zone == Zone.HAND
        state = passes(state)  # Resolve original before a non-flash creature can be recast.
        assert state.cards[original].zone == Zone.GRAVEYARD
        state = priority(state, seat)
        state = act(state, seat, {'type': 'cast_spell', 'card_id': hero, 'cost_choice': {'id': 'base'}})
        state = passes(state)
    assert state.cards[hero].zone == Zone.BATTLEFIELD
    assert object_incarnation(state.cards[hero]) != old_incarnation
    assert not state.cards[hero].counters.get('+1/+1')
    if blink:
        state = passes(state)  # Old Heroic cannot put a counter on the returned object.
        assert not state.cards[hero].counters.get('+1/+1')
        state = passes(state)  # Original spell's old target reference no longer matches.
    assert state.cards[hero].zone == Zone.BATTLEFIELD
    assert state.cards[original].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('before', [False, True])
def test_actual_paid_suppression_admission_and_published_ability_independence(seat, before):
    state, hero = board(seat)
    if not before:
        state, _ = cast(state, seat, 'Spirit Mantle', {'target_card_id': hero})
        assert len(triggers(state, hero)) == 1
    state, _ = cast(state, 3-seat, 'Dress Down')
    state = passes(state)
    assert printed_abilities_suppressed(state, hero)
    if state.stack and state.stack[-1].effect_key == 'draw_cards':
        state = passes(state)
    if before:
        state, _ = cast(state, seat, 'Spirit Mantle', {'target_card_id': hero})
        assert not triggers(state, hero)
    else:
        assert len(triggers(state, hero)) == 1
        state = passes(state)
        assert state.cards[hero].counters.get('+1/+1') == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_malformed_actual_spell_target_receipt_rejects_before_pop_root_pure(seat):
    state, hero = board(seat)
    state, spell = cast(state, seat, 'Unholy Heat', {'target_card_id': hero})
    assert len(triggers(state, hero)) == 1
    state = passes(state)
    announcement(state, spell).payload['__announced_target_references']['targets']['target_card_id']['extra'] = True
    before = snap(state)
    candidate = act(state, state.priority_player, {'type': 'pass_priority'})
    with pytest.raises(ActionRejected):
        act(candidate, candidate.priority_player, {'type': 'pass_priority'})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['missing', 'extra_key', 'wrong_shape', 'bool_incarnation'])
def test_actual_cast_observer_query_rejects_no_proof_or_malformed_before_mutation(seat, kind):
    state, hero = board(seat)
    state, spell = cast(state, seat, 'Unholy Heat', {'target_card_id': hero})
    frame = announcement(state, spell)
    actual_payload = {'source_card_id': spell, 'controller': seat,
                      'stack_payload': deepcopy(frame.payload)}
    stack_payload = actual_payload['stack_payload']
    if kind == 'missing':
        del stack_payload['__announced_target_references']
    elif kind == 'wrong_shape':
        stack_payload['__announced_target_references']['targets'] = []
    else:
        reference = stack_payload['__announced_target_references']['targets']['target_card_id']
        reference['extra' if kind == 'extra_key' else 'incarnation'] = True
    before = snap(state)
    with pytest.raises(ActionRejected):
        events._matched_cast_trigger_clauses(state, state.cards[hero],
            state.cards[hero].oracle_text.lower(), 'spell_cast', actual_payload)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_same_id_wrong_native_incarnation_does_not_match_readonly_query(seat):
    state, hero = board(seat)
    state, spell = cast(state, seat, 'Unholy Heat', {'target_card_id': hero})
    frame = announcement(state, spell)
    payload = {'source_card_id': spell, 'controller': seat, 'stack_payload': deepcopy(frame.payload)}
    payload['stack_payload']['__announced_target_references']['targets']['target_card_id']['incarnation'] += 1
    before = snap(state)
    assert events._matched_cast_trigger_clauses(state, state.cards[hero],
        state.cards[hero].oracle_text.lower(), 'spell_cast', payload) == []
    assert snap(state) == before


@pytest.mark.parametrize('tail', [' Draw a card.', ' if you control an Island.', ' unless you control a Forest.'])
def test_new_subject_unknown_body_diagnostic_not_partial_reward(tail):
    # Fault-injection compiler input only, not altered playable canonical Oracle.
    state, hero = board(1)
    source = state.cards[hero]
    body = 'put a +1/+1 counter on this creature.' + tail
    clause = 'whenever you cast a spell that targets this creature, ' + body
    before = snap(state)
    trigger = events._cast_clause_trigger(state, source, clause, body, 'spell_cast', {})
    assert trigger['effect_key'] == 'noop'
    assert '__unsupported_trigger_instruction' in trigger['payload']
    assert snap(state) == before


@pytest.mark.parametrize('prefix', ['If you control an Island, ', 'Draw a card. ',
                                  'Whenever a creature enters, '])
@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_clause_prefix_does_not_reward_embedded_supported_subject(seat, prefix):
    state, hero = board(seat)
    body = 'put a +1/+1 counter on this creature.'
    clause = prefix + 'whenever you cast a spell that targets this creature, ' + body
    before = snap(state)
    trigger = events._cast_clause_trigger(state, state.cards[hero], clause, body, 'spell_cast', {})
    assert trigger['effect_key'] == 'noop'
    assert '__unsupported_trigger_instruction' in trigger['payload']
    assert snap(state) == before
