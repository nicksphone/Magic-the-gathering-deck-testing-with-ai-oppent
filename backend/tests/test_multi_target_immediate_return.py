"""Canonical two-target blink through actual checked payment and resolution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from tests.scheduler_fixture_position import ordinary_position
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'
GHOSTLY_BYTES = (FIXTURES / 'canonical_land_animation_response/ghostly-flicker.json').read_bytes()
assert hashlib.sha256(GHOSTLY_BYTES).hexdigest() == json.loads(
    (FIXTURES / 'canonical_land_animation_response/provenance.json').read_text())['sha256']
GHOSTLY = json.loads(GHOSTLY_BYTES)
ISLAND = json.loads((FIXTURES / 'canonical_land_animation_audit/island.json').read_text())
FERTILID = json.loads((FIXTURES / 'targeted_search/fertilid.json').read_text())


def case(seat, foreign=False):
    deck = [{**ISLAND, 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=8173)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    ordinary_position(state)
    state.priority_stops = {pid: set(Step) for pid in state.players}
    creature = raw_card(state, FERTILID, seat, Zone.BATTLEFIELD)
    creature.counters['+1/+1'] = 5
    land = raw_card(state, ISLAND, seat, Zone.BATTLEFIELD)
    if foreign:
        creature.owner = land.owner = 3-seat  # Explicit lawful stolen starting board.
    spell = raw_card(state, GHOSTLY, seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1, 'C': 2}
    return state, [creature.id, land.id], spell.id


def resolve(state):
    for _ in range(2):
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    return state


def cast(state, seat, spell, targets):
    return checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell, 'targets': targets})


def restored(state):
    saved = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(saved)
    assert serialize_match_snapshot(result) == saved
    return result


def canonical(relative):
    return json.loads((FIXTURES / relative).read_text())


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_plural_body_and_exact_public_candidate_count(seat):
    state, targets, spell = case(seat)
    before = serialize_match_snapshot(state)
    hints = inspect_target_hints(state, state.cards[spell], seat)
    spec = build_ability_spec(state, state.cards[spell], seat,
                             {'target_card_ids': targets}, report_unsupported=False)
    assert spec.effect.key == 'exile_return_batch'
    assert hints['required_distinct_target_count'] == 2
    assert set(targets) <= {entry['id'] for entry in hints['permanent_targets']}
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_both_targets_return_new_objects_under_resolving_controller(seat, foreign):
    state, targets, spell = case(seat, foreign)
    before = serialize_match_snapshot(state)
    refs = {cid: (object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence)
            for cid in targets}
    current = checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': targets}})
    assert sum(current.players[seat].mana_pool.values()) == 0
    current = resolve(current)
    for cid in targets:
        card = current.cards[cid]
        assert card.zone == Zone.BATTLEFIELD and card.controller == seat
        assert card.owner == (3-seat if foreign else seat)
        assert card.zone_change_sequence == refs[cid][1] + 2
        assert object_incarnation(card) > refs[cid][0]
        assert cid in current.players[seat].battlefield
        assert cid not in current.players[card.owner].exile
    assert current.cards[targets[0]].counters['+1/+1'] == 2
    assert current.cards[targets[1]].counters.get('+1/+1', 0) == 0
    assert current.cards[spell].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before
    saved = serialize_match_snapshot(current)
    assert serialize_match_snapshot(deserialize_match_snapshot(saved)) == saved


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_bounce_removes_only_one_announced_target(seat):
    state, targets, spell = case(seat)
    bounce = raw_card(state, canonical('immediate_return_product/unsummon.json'), seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 2, 'C': 2}
    sequences = {cid: state.cards[cid].zone_change_sequence for cid in targets}
    state = cast(state, seat, spell, {'target_card_ids': targets})
    state = cast(state, seat, bounce, {'target_card_id': targets[0]})
    state = resolve(state)
    assert state.cards[targets[0]].zone == Zone.HAND
    state = resolve(restored(state))
    assert state.cards[targets[0]].zone == Zone.HAND
    assert state.cards[targets[0]].zone_change_sequence == sequences[targets[0]] + 1
    assert state.cards[targets[1]].zone == Zone.BATTLEFIELD
    assert state.cards[targets[1]].zone_change_sequence == sequences[targets[1]] + 2
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_single_blink_cannot_make_old_target_legal_again(seat):
    state, targets, spell = case(seat)
    blink = raw_card(state, canonical('cloudshift_compound_audit/cloudshift.json'), seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 1, 'W': 1, 'C': 2}
    sequences = {cid: state.cards[cid].zone_change_sequence for cid in targets}
    state = cast(state, seat, spell, {'target_card_ids': targets})
    state = cast(state, seat, blink, {'target_card_id': targets[0]})
    state = resolve(state)
    assert state.cards[targets[0]].zone_change_sequence == sequences[targets[0]] + 2
    state = resolve(restored(state))
    assert all(state.cards[cid].zone_change_sequence == sequences[cid] + 2 for cid in targets)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_second_ghostly_makes_both_original_targets_illegal(seat):
    state, targets, spell = case(seat)
    second = raw_card(state, GHOSTLY, seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 2, 'C': 4}
    sequences = {cid: state.cards[cid].zone_change_sequence for cid in targets}
    for current in (spell, second):
        state = cast(state, seat, current, {'target_card_ids': targets})
    state = resolve(state)
    state = resolve(restored(state))
    assert all(state.cards[cid].zone_change_sequence == sequences[cid] + 2 for cid in targets)
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in (spell, second))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_collectors_see_all_pre_departures_and_all_committed_entries(seat, monkeypatch):
    from rules_engine import events
    original = events._collect_triggers
    observed = []
    state, targets, spell = case(seat)

    def collect(current, event, packet):
        if event in {'leaves_battlefield', 'enters_battlefield'} and packet.get('card_id') in targets:
            observed.append((current, event, packet['card_id'],
                [(current.cards[cid].zone, current.cards[cid].zone_change_sequence,
                  cid in current.players[seat].battlefield) for cid in targets]))
        return original(current, event, packet)

    monkeypatch.setattr(events, '_collect_triggers', collect)
    current = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    rows = [(event, cid, cards) for candidate, event, cid, cards in observed if candidate is current]
    assert [event for event, _, _ in rows] == ['leaves_battlefield'] * 2 + ['enters_battlefield'] * 2
    assert all(all(zone == Zone.BATTLEFIELD and member for zone, _, member in cards)
               for _, _, cards in rows)
    assert all(seq == state.cards[targets[index]].zone_change_sequence for event, _, cards in rows
               if event == 'leaves_battlefield' for index, (_, seq, _) in enumerate(cards))
    assert all(seq == state.cards[targets[index]].zone_change_sequence + 2 for event, _, cards in rows
               if event == 'enters_battlefield' for index, (_, seq, _) in enumerate(cards))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['add', 'double'])
def test_two_recipients_counter_choices_stay_exiled_until_every_choice_commits(seat, first):
    state, targets, spell = case(seat)
    second = raw_card(state, FERTILID, seat, Zone.BATTLEFIELD).id
    state.cards[second].counters['+1/+1'] = 2
    targets = [targets[0], second]
    for name in ('hardened-scales', 'doubling-season'):
        raw_card(state, canonical(f'immediate_return_product/{name}.json'), seat, Zone.BATTLEFIELD)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    assert state.pending_replacement_choice
    choices = 0
    while state.pending_replacement_choice:
        assert all(state.cards[cid].zone == Zone.EXILE for cid in targets)
        state = restored(state)
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_replacement', 'replacement_source_id': 'invalid'})
        assert serialize_match_snapshot(state) == before
        options = state.pending_replacement_choice['options']
        option = next((row for row in options if row['operation'] == first), options[0])
        state = checked_action(state, RulesEngine(), seat,
            {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
        choices += 1
        assert choices <= 4
    assert choices == 2
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in targets)
    assert all(state.cards[cid].counters['+1/+1'] == (6 if first == 'add' else 5) for cid in targets)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert not state.trigger_staging


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first_pay', [False, True])
def test_two_foreign_owned_shocks_reserve_life_and_resume_all_entries_once(seat, first_pay):
    state, _, spell = case(seat)
    targets = [raw_card(state, canonical('targeted_search_resolver/breeding-pool.json'), seat, Zone.BATTLEFIELD).id
               for _ in range(2)]
    for cid in targets:
        state.cards[cid].owner = 3-seat
    state.players[seat].life = 2
    opponent_life = state.players[3-seat].life
    state = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    for index, cid in enumerate(targets):
        assert all(state.cards[target].zone == Zone.EXILE for target in targets)
        assert state.pending_mechanic_choice['entry_card_id'] == cid
        assert state.pending_mechanic_choice['player_id'] == seat
        state = restored(state)
        pay = first_pay if index == 0 else not first_pay
        if first_pay and index == 1:
            assert 'pay_two_life' not in state.pending_mechanic_choice['options']
        state = checked_action(state, RulesEngine(), seat,
            {'type': 'choose_mechanic', 'choice_id': 'pay_two_life' if pay else 'tapped'})
    assert state.players[seat].life == 0 and state.players[3-seat].life == opponent_life
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].controller == seat
               and state.cards[cid].owner == 3-seat for cid in targets)
    assert [state.cards[cid].tapped for cid in targets] == [not first_pay, first_pay]
    assert state.cards[spell].zone == Zone.GRAVEYARD and not state.pending_mechanic_choice
    assert not state.trigger_staging


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('all_tokens', [False, True])
def test_actual_paid_tokens_never_return_but_other_card_still_does(seat, all_tokens):
    state, old, spell = case(seat)
    maker = raw_card(state, canonical('immediate_return_product/raise-the-alarm.json'), seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 1, 'W': 1, 'C': 3}
    state = resolve(cast(state, seat, maker, {}))
    tokens = [cid for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2
    targets = tokens if all_tokens else [tokens[0], old[1]]
    state = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    for cid in tokens if all_tokens else tokens[:1]:
        assert cid not in state.players[seat].battlefield
        assert cid not in state.cards or state.cards[cid].zone != Zone.BATTLEFIELD
    if not all_tokens:
        assert state.cards[old[1]].zone == Zone.BATTLEFIELD
        assert state.cards[old[1]].zone_change_sequence == 3
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selection', ['one', 'duplicate', 'three', 'opponent'])
def test_invalid_count_or_controller_is_rejected_before_payment(seat, selection):
    state, targets, spell = case(seat)
    third = raw_card(state, ISLAND, 3-seat if selection == 'opponent' else seat, Zone.BATTLEFIELD)
    chosen = {'one': targets[:1], 'duplicate': targets[:1] * 2,
              'three': targets + [third.id], 'opponent': [targets[0], third.id]}[selection]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
            {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': chosen}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Draw a card.', ' If you do, gain 2 life.'])
def test_plural_unknown_tail_has_no_partial_exile_reward(seat, suffix):
    state, targets, spell = case(seat)
    card = deepcopy(state.cards[spell])
    card.oracle_text += suffix  # Labeled grammar probe, never an executed card.
    card.card_faces = []
    before = serialize_match_snapshot(state)
    spec = build_ability_spec(state, card, seat, {'target_card_ids': targets}, report_unsupported=False)
    assert spec.effect.key == 'noop'
    assert spec.effect.payload.get('__unsupported_immediate_return')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.parametrize('counter_original', [False, True])
def test_real_paid_copy_can_retarget_each_slot_under_its_actual_controller(seat, opposing, counter_original):
    state, original_targets, spell = case(seat)
    copier = 3-seat if opposing else seat
    creature = raw_card(state, FERTILID, copier, Zone.BATTLEFIELD)
    creature.counters['+1/+1'] = 2
    land = raw_card(state, ISLAND, copier, Zone.BATTLEFIELD)
    new_targets = [creature.id, land.id]
    state = cast(state, seat, spell, {'target_card_ids': original_targets})
    original_id = state.stack[-1].id
    if copier != state.priority_player:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    twincast = raw_card(state, canonical('announced_target_references/twincast.json'), copier, Zone.HAND).id
    state.players[copier].mana_pool = {'U': 2}
    state = resolve(cast(state, copier, twincast, {'target_stack_id': original_id}))
    copied_id = state.stack[-1].id
    assert copied_id != original_id and state.stack[-1].controller == copier
    for index, cid in enumerate(new_targets):
        pending = state.pending_mechanic_choice
        assert pending and pending['player_id'] == copier
        assert pending['ordered_target_index'] == index
        assert f'target_card_id:{cid}' in pending['options']
        if index:
            assert f'target_card_id:{new_targets[0]}' not in pending['options']
        state = checked_action(restored(state), RulesEngine(), copier,
            {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{cid}']})
    assert not state.pending_mechanic_choice
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__announced_targets']['target_card_ids'] == new_targets
    if counter_original:
        counter = raw_card(state, canonical('trigger_instruction_product/counterspell.json'), copier, Zone.HAND).id
        state.players[copier].mana_pool = {'U': 2}
        if state.priority_player != copier:
            state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
        state = resolve(cast(state, copier, counter, {'target_stack_id': original_id}))
        assert state.cards[spell].zone == Zone.GRAVEYARD
    state = resolve(restored(state))
    for cid in new_targets:
        assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].controller == copier
        assert state.cards[cid].zone_change_sequence == 3
    assert all(state.cards[cid].zone_change_sequence == 1 for cid in original_targets)
    if not counter_original:
        state = resolve(state)
        assert all(state.cards[cid].zone_change_sequence == 3 for cid in original_targets)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('moon_first', [False, True])
@pytest.mark.parametrize('pay', [False, True])
def test_incoming_land_type_effect_cannot_change_another_simultaneous_entry_choice(seat, moon_first, pay):
    state, _, spell = case(seat)
    rows = {row['name']: row for row in canonical('land_types.json')}
    moon = raw_card(state, rows['Magus of the Moon'], seat, Zone.BATTLEFIELD).id
    fountain = raw_card(state, rows['Hallowed Fountain'], seat, Zone.BATTLEFIELD).id
    targets = [moon, fountain] if moon_first else [fountain, moon]
    life = state.players[seat].life
    state = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    assert state.pending_mechanic_choice['entry_card_id'] == fountain
    assert all(state.cards[cid].zone == Zone.EXILE for cid in targets)
    state = checked_action(restored(state), RulesEngine(), seat,
        {'type': 'choose_mechanic', 'choice_id': 'pay_two_life' if pay else 'tapped'})
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in targets)
    assert state.cards[fountain].tapped == (not pay)
    assert state.players[seat].life == life - (2 if pay else 0)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('saga_first', [False, True])
def test_saga_counter_collectors_see_the_complete_returned_counter_batch(seat, saga_first, monkeypatch):
    from rules_engine import events
    state, targets, spell = case(seat)
    saga_row = next(row for row in canonical('land_types.json') if row['name'] == "Urza's Saga")
    saga = raw_card(state, saga_row, seat, Zone.BATTLEFIELD)
    saga.counters['__lore'] = 1
    creature = targets[0]
    targets = [saga.id, creature] if saga_first else [creature, saga.id]
    collect = events._collect_triggers
    observed = []

    def trace(current, event, packet):
        if event == 'saga_lore_added' and packet.get('card_id') == saga.id:
            observed.append((current, [(current.cards[cid].zone,
                cid in current.players[seat].battlefield,
                dict(current.cards[cid].counters)) for cid in targets]))
        return collect(current, event, packet)

    monkeypatch.setattr(events, '_collect_triggers', trace)
    current = resolve(cast(state, seat, spell, {'target_card_ids': targets}))
    rows = [row for candidate, row in observed if candidate is current]
    assert len(rows) == 1
    assert all(zone == Zone.BATTLEFIELD and member for zone, member, _ in rows[0])
    assert rows[0][targets.index(creature)][2]['+1/+1'] == 2
    assert rows[0][targets.index(saga.id)][2]['__lore'] == 1
    assert current.cards[saga.id].counters['__lore'] == 1
    assert any(item.source_card_id == saga.id for item in current.stack)
    restored(current)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stale', [False, True])
def test_real_paid_copy_keep_retains_original_target_references(seat, stale):
    state, targets, spell = case(seat)
    raw_card(state, ISLAND, seat, Zone.BATTLEFIELD)  # An alternative makes each keep choice explicit.
    sequences = {cid: state.cards[cid].zone_change_sequence for cid in targets}
    state = cast(state, seat, spell, {'target_card_ids': targets})
    original_id = state.stack[-1].id
    refs = deepcopy(state.stack[-1].payload['__announced_references'])
    if stale:
        blink = raw_card(state, canonical('cloudshift_compound_audit/cloudshift.json'), seat, Zone.HAND).id
        state.players[seat].mana_pool = {'W': 1}
        state = resolve(cast(state, seat, blink, {'target_card_id': targets[0]}))
    twincast = raw_card(state, canonical('announced_target_references/twincast.json'), seat, Zone.HAND).id
    state.players[seat].mana_pool = {'U': 2}
    state = resolve(cast(state, seat, twincast, {'target_stack_id': original_id}))
    copied_id = state.stack[-1].id
    for index in range(2):
        assert state.pending_mechanic_choice['ordered_target_index'] == index
        assert 'keep' in state.pending_mechanic_choice['options']
        state = checked_action(restored(state), RulesEngine(), seat,
            {'type': 'choose_mechanic', 'card_ids': ['keep']})
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__announced_references'] == refs
    state = resolve(state)
    assert state.cards[targets[0]].zone_change_sequence == sequences[targets[0]] + 2
    assert state.cards[targets[1]].zone_change_sequence == sequences[targets[1]] + 2
    state = resolve(state)
    assert all(state.cards[cid].zone_change_sequence == sequences[cid] + 2 for cid in targets)
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['target_player', 'target_stack_id', 'target_distribution'])
def test_batch_card_targets_reject_conflicting_target_representations_before_payment(seat, field):
    state, targets, spell = case(seat)
    values = {'target_player': seat, 'target_stack_id': spell,
              'target_distribution': {targets[0]: 1}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, spell, {'target_card_ids': targets, field: values[field]})
    assert serialize_match_snapshot(state) == before
