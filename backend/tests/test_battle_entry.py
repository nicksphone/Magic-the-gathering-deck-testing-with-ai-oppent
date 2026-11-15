"""Paid canonical Battle entry and explicitly scoped native entry-policy inputs.

Complete original printing readers own their inputs. Typed mixed/subtypeless
positions and direct effect packets below are core-policy controls, not claims
that an unplayed card produced those positions. No synthetic printing is used.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.copiable_values import values, apply
from rules_engine.type_effects import add_type_effect
from rules_engine.state_based_actions import apply_state_based_actions
from effects.registry import resolve_effect
from tests.test_conditional_graveyard_self_copy import row as ordinary_row, place, act
from tests.counter_family_canonical091 import raw_card as counter_raw
from tests.test_battle_characteristics import mark

BATTLE = 'Invasion of Zendikar // Awakened Skyclave'
COUNTER_PARENTS = {'Doubling Season', 'Vorinclex, Monstrous Raider'}


def row(name, count):
    if name == 'Blood Moon':
        mark('full-Blood-Moon-printing-reader-request-started')
        data = (Path(__file__).parent / 'fixtures/battle_mixed_full_printing/blood-moon-2xm-118.json').read_bytes()
        assert hashlib.sha256(data).hexdigest() == 'a1017ed41fa6af2a22221ec413f752679fe91c316845fbdd6ff5627460495653'
        raw = json.loads(data)
        assert raw['object'] == 'card' and raw['name'] == name and len(raw) == 63
        assert raw['id'] == 'd072e9ca-aae7-45dc-8025-3ce590bae63f'
        assert raw['oracle_id'] == '94fac5fe-97d5-4c12-a80c-8efff9d853ae'
        mark('full-Blood-Moon-printing-reader-returned')
        return {**raw, 'card_name': name, 'quantity': count}
    if name == 'Humility':
        mark('original-Humility-printing-reader-request-started')
        from tests.test_ability_suppression import CARDS
        raw = deepcopy(CARDS[name])
        full = (raw.get('object') == 'card' and len(raw) >= 50
                and all(raw.get(k) for k in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout')))
        if not full: mark('original-Humility-reader-is-not-a-full-printing')
        assert full
        mark('original-Humility-printing-reader-returned')
        return {**raw, 'card_name': name, 'quantity': count}
    if name == 'Solemnity':
        raw = next(r for r in json.loads((Path(__file__).parent / 'fixtures/counter_prohibitions.json').read_text())
                   if r['name'] == 'Solemnity')
        assert raw['object'] == 'card' and len(raw) == 65
        assert raw['id'] == '0a71fb62-acbd-49f5-842f-0fc9fa48afea'
        assert raw['oracle_id'] == 'f0b4331b-ddd3-4f11-ba16-67c651c8954c'
        return {**raw, 'card_name': name, 'quantity': count}
    if name == BATTLE:
        data = (Path(__file__).parent / 'fixtures/battle_full_printing/invasion-of-zendikar-mom-194.json').read_bytes()
        assert hashlib.sha256(data).hexdigest() == '1e49bb006e579e3a88052ab773f5974f761e4a8fedd6fda669768d92f2b82d74'
        raw = json.loads(data)
        assert raw['object'] == 'card' and raw['name'] == BATTLE and len(raw) == 60
        return {**raw, 'card_name': name, 'quantity': count}
    if name in COUNTER_PARENTS:
        raw = counter_raw(name)
        return {**raw, 'card_name': name, 'quantity': count}
    return ordinary_row(name, count)


def position(seat, extra=()):
    counts = Counter((BATTLE, 'Shifting Woodland', *extra))
    counts['Forest'] += 60-sum(counts.values())
    deck = [row(name, count) for name, count in counts.items()]
    state = MatchFactory.from_decks(deck, deck, seed=71203)
    state.pregame_pending = False; state.kept_hands = {1, 2}; state.turn = 5
    state.active_player = state.priority_player = seat; state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY); player.library.append(cid)
        player.hand.clear(); player.mana_pool = {}
        player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1
        player.last_land_play_turn = state.turn
    for _ in range(6): place(state, seat, 'Forest', Zone.BATTLEFIELD)
    battle = place(state, seat, BATTLE, Zone.HAND)
    return state, battle


def move(state, cid, zone, controller=None):
    card = state.cards[cid]
    for player in state.players.values():
        for key in ('hand', 'library', 'battlefield', 'graveyard', 'exile'):
            ids = getattr(player, key)
            if cid in ids: ids.remove(cid)
    card.move_to_zone(zone)
    card.controller = card.owner if controller is None else controller
    getattr(state.players[card.controller if zone == Zone.BATTLEFIELD else card.owner], zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, cid)
        card.summoning_sick = False
    return card


def announce(state, seat, cid, cost=4):
    before = sum(state.cards[x].tapped for x in state.players[seat].battlefield)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid})
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.cards[x].tapped for x in state.players[seat].battlefield)-before == cost
    assert sum(state.players[seat].mana_pool.values()) == 0
    return state


def resolve_until_entry_or_choice(state, cid):
    for _ in range(8):
        if state.cards[cid].zone != Zone.STACK or state.pending_replacement_choice or state.pending_mechanic_choice:
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native entry did not reach its declared boundary')


def choose_replacement(state, operation, seat):
    option = next(x for x in state.pending_replacement_choice['options'] if x['operation'] == operation)
    return act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})


def battle_ready(state, cid, protector, count=3):
    card = move(state, cid, Zone.BATTLEFIELD)
    card.counters['defense'] = count
    card.battle_protector = protector
    return card


def prepare_only(state, seat, card):
    from rules_engine.entry_counters import prepare_entry_counters
    payload = {'entry_payload': {}, 'entry_prepared': {}, 'entry_index': 0}
    assert prepare_entry_counters(state, seat, payload, card, 'permanent_entry_counters')
    return payload['entry_prepared']


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_four_mana_cast_enters_with_printed_defense_and_protector(seat):
    state, cid = position(seat)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    mark('actual-paid-Battle-entry-defense-and-protector-assertion-reached')
    card = state.cards[cid]
    assert card.zone == Zone.BATTLEFIELD and card.counters.get('defense', 0) == 3
    assert card.printed_defense == '3' and card.battle_protector == 3-seat
    assert state.players[seat].battlefield.count(cid) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_battle_entry_uses_complete_doubling_season_parent(seat):
    state, cid = position(seat, ('Doubling Season',))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    mark('Battle-entry-doubling-replacement-assertion-reached')
    assert state.cards[cid].counters.get('defense', 0) == 6
    assert state.cards[cid].battle_protector == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_battle_entry_opposing_vorinclex_halves_defense(seat):
    state, cid = position(seat, ('Vorinclex, Monstrous Raider',))
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    mark('Battle-entry-halving-replacement-assertion-reached')
    assert state.cards[cid].counters.get('defense', 0) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_solemnity_does_not_prohibit_counters_on_a_pure_battle(seat):
    state, cid = position(seat, ('Solemnity',))
    place(state, 3-seat, 'Solemnity', Zone.BATTLEFIELD)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    mark('pure-Battle-Solemnity-type-scope-assertion-reached')
    assert state.cards[cid].counters.get('defense', 0) == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_entry_replacement_order_survives_snapshot_and_commits_once(seat):
    for first, expected in (('half', 2), ('double', 3)):
        state, cid = position(seat, ('Doubling Season', 'Vorinclex, Monstrous Raider'))
        place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
        place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
        state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
        mark('Battle-entry-native-replacement-order-choice-assertion-reached')
        assert state.pending_replacement_choice['player_id'] == seat
        assert state.cards[cid].zone == Zone.STACK and not state.cards[cid].counters
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose_replacement(state, first, seat)
        assert not state.pending_replacement_choice
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert state.cards[cid].counters.get('defense', 0) == expected
        assert state.players[seat].battlefield.count(cid) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_prospective_battle_creature_intrinsic_ability_is_lost_under_humility(seat):
    state, cid = position(seat, ('Humility',))
    place(state, 3-seat, 'Humility', Zone.BATTLEFIELD)
    card = state.cards[cid]
    # Declared prospective mixed-type input, not a modified canonical printing.
    card.types = ['Battle', 'Creature']
    mark('prospective-Battle-creature-ability-loss-assertion-reached')
    assert prepare_only(state, seat, card).get('defense', 0) == 0
    assert card.zone == Zone.HAND and not card.counters


@pytest.mark.parametrize('seat', [1, 2])
def test_prospective_battle_creature_obeys_solemnity_counter_prohibition(seat):
    state, cid = position(seat, ('Solemnity',))
    place(state, 3-seat, 'Solemnity', Zone.BATTLEFIELD)
    card = state.cards[cid]; card.types = ['Battle', 'Creature']
    mark('prospective-Battle-creature-counter-prohibition-assertion-reached')
    assert prepare_only(state, seat, card).get('defense', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_native_as_entry_copy_uses_battle_defense_not_target_counters(seat):
    state, cid = position(seat, ('Sculpting Steel',))
    battle = battle_ready(state, cid, 3-seat, count=1)
    add_type_effect(state, cid, ['Artifact'])
    steel = place(state, seat, 'Sculpting Steel', Zone.HAND)
    state = resolve_until_entry_or_choice(announce(state, seat, steel, cost=3), steel)
    mark('paid-native-Battle-as-entry-copy-choice-assertion-reached')
    assert state.pending_mechanic_choice['kind'] == 'entry_copy'
    assert cid in state.pending_mechanic_choice['options']
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [cid]})
    copied = state.cards[steel]
    assert copied.zone == Zone.BATTLEFIELD and copied.printed_defense == '3'
    assert copied.counters.get('defense', 0) == 3 and copied.battle_protector == 3-seat
    assert not copied.card_faces and copied.characteristic_record['physical']['name'] == 'Sculpting Steel'
    assert state.cards[cid].counters['defense'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_native_token_copy_entry_keeps_printed_defense_and_places_new_counters(seat):
    state, cid = position(seat)
    battle_ready(state, cid, 3-seat, count=1)
    add_type_effect(state, cid, ['Creature'])
    before = set(state.cards)
    resolve_effect(state, seat, 'create_token_copy', {'target_card_id': cid})
    tokens = [c for key, c in state.cards.items() if key not in before]
    mark('native-Battle-token-entry-defense-assertion-reached')
    assert len(tokens) == 1 and tokens[0].is_token
    assert tokens[0].printed_defense == '3' and tokens[0].counters.get('defense', 0) == 3
    assert tokens[0].battle_protector == 3-seat and state.cards[cid].counters['defense'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_batch_return_places_fresh_defense_for_both_owners(seat):
    from rules_engine.linked_exile import record_linked_exile, flush_linked_exile_returns
    state, cid = position(seat)
    other = next(x for x in state.players[3-seat].library if 'Battle' in state.cards[x].types)
    battle_ready(state, cid, 3-seat, count=1)
    battle_ready(state, other, seat, count=2)
    source = place(state, seat, 'Shifting Woodland', Zone.BATTLEFIELD)
    for target in (cid, other):
        resolve_effect(state, seat, 'exile', {'target_card_id': target})
        assert state.cards[target].zone == Zone.EXILE and not state.cards[target].counters
    record_linked_exile(state, source, object_incarnation(state.cards[source]), [cid, other], Zone.BATTLEFIELD)
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source})
    flush_linked_exile_returns(state)
    mark('linked-Battle-batch-return-entry-assertion-reached')
    for target, owner in ((cid, seat), (other, 3-seat)):
        card = state.cards[target]
        if card.zone != Zone.BATTLEFIELD: mark('linked-Battle-return-remains-outside-battlefield')
        elif card.controller != owner: mark('linked-Battle-return-controller-mismatch')
        elif card.counters.get('defense', 0) != 3: mark('linked-Battle-return-defense-counter-mismatch')
        elif card.battle_protector != 3-owner: mark('linked-Battle-return-protector-mismatch')
        assert card.zone == Zone.BATTLEFIELD and card.controller == owner
        assert card.counters.get('defense', 0) == 3 and card.battle_protector == 3-owner


@pytest.mark.parametrize('seat', [1, 2])
def test_native_immediate_return_reassigns_protector_and_fresh_defense(seat):
    state, cid = position(seat)
    card = battle_ready(state, cid, seat, count=1)
    ref = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    resolve_effect(state, seat, 'exile_return_immediate', {
        'target_card_id': cid, '__announced_reference': ref, 'return_control': 'owner'})
    mark('native-Battle-immediate-return-entry-assertion-reached')
    assert card.zone == Zone.BATTLEFIELD and card.counters.get('defense', 0) == 3
    assert card.battle_protector == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_permanent_copy_keeps_counters_and_gets_sba_protector(seat):
    state, cid = position(seat)
    land = place(state, seat, 'Shifting Woodland', Zone.BATTLEFIELD)
    state.cards[land].counters['defense'] = 2
    apply(state.cards[land], values(state.cards[cid]))
    apply_state_based_actions(state)
    mark('existing-permanent-Battle-copy-protector-assertion-reached')
    assert state.cards[land].counters['defense'] == 2
    assert state.cards[land].battle_protector == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_declared_typeless_battle_uses_controller_as_protector(seat):
    state, cid = position(seat)
    card = battle_ready(state, cid, None, count=2)
    descriptor = values(card); descriptor['type_line'] = 'Battle'
    apply(card, descriptor)
    apply_state_based_actions(state)
    mark('typeless-Battle-protector-policy-assertion-reached')
    assert card.battle_protector == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_change_repairs_illegal_siege_protector(seat):
    from rules_engine.control_effects import record_control_effect
    state, cid = position(seat)
    card = battle_ready(state, cid, 3-seat)
    record_control_effect(state, card, 3-seat)
    apply_state_based_actions(state)
    mark('control-changed-Battle-protector-repair-assertion-reached')
    assert card.controller == 3-seat and card.battle_protector == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_protector_persists_through_nonbattle_form_then_repairs_when_needed(seat):
    from rules_engine.control_effects import record_control_effect
    state, cid = position(seat)
    card = battle_ready(state, cid, 3-seat)
    original = values(card)
    forest = next(state.cards[x] for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    apply(card, values(forest))
    record_control_effect(state, card, 3-seat)
    apply_state_based_actions(state)
    assert card.battle_protector == 3-seat
    apply(card, original)
    apply_state_based_actions(state)
    mark('Battle-protector-type-loss-and-return-assertion-reached')
    assert card.battle_protector == seat
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': cid})
    assert card.battle_protector is None


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_printed_battle_metadata_refuses_entry_preparation(seat):
    from rules_engine.entry_counters import prepare_counter_entries
    state, cid = position(seat)
    card = state.cards[cid]
    mark('missing-Battle-defense-before-native-snapshot')
    before = serialize_match_snapshot(state); rejected = False
    known = (card.printed_defense, deepcopy(card.characteristic_record), deepcopy(card.card_faces))
    card.printed_defense = None; card.characteristic_record = {}; card.card_faces = []
    mark('missing-Battle-defense-before-entry-preparation')
    try: prepare_counter_entries(state, seat, [card], 'create_token', {})
    except ActionRejected: rejected = True
    mark('missing-Battle-defense-metadata-entry-rejection-assertion-reached')
    assert rejected and card.printed_defense is None and card.characteristic_record == {} and card.card_faces == []
    card.printed_defense, card.characteristic_record, card.card_faces = known
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_defense_query_distinguishes_printed_live_and_nonbattle_values(seat):
    from rules_engine.battles import defense
    state, cid = position(seat)
    card = state.cards[cid]
    assert defense(state, card) == 3
    battle_ready(state, cid, 3-seat, count=2)
    assert defense(state, card) == 2
    forest = next(state.cards[x] for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    apply(card, values(forest))
    assert defense(state, card) is None and card.counters['defense'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_stale_printed_defense_cannot_rebind_a_paused_entry(seat):
    state, cid = position(seat, ('Doubling Season', 'Vorinclex, Monstrous Raider'))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    assert state.pending_replacement_choice
    # Negative retained-data fault; not an action available during the choice.
    state.cards[cid].printed_defense = '9'
    before = serialize_match_snapshot(state); rejected = False
    try: choose_replacement(state, 'half', seat)
    except ActionRejected: rejected = True
    mark('stale-Battle-entry-defense-binding-assertion-reached')
    assert rejected and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_generic_topdeck_permanent_entry_includes_battles(seat):
    state, cid = position(seat)
    card = move(state, cid, Zone.LIBRARY)
    state.players[seat].library.remove(cid); state.players[seat].library.append(cid)
    resolve_effect(state, seat, 'topdeck_put_permanents_battlefield', {
        'top_n': 1, 'max_permanents': 1, 'selected_card_ids': [cid]})
    mark('generic-topdeck-Battle-permanent-entry-assertion-reached')
    assert card.zone == Zone.BATTLEFIELD and card.counters.get('defense', 0) == 3
    assert card.battle_protector == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_player_cannot_commit_battle_entry_counter_choice(seat):
    state, cid = position(seat, ('Doubling Season', 'Vorinclex, Monstrous Raider'))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    state = resolve_until_entry_or_choice(announce(state, seat, cid), cid)
    assert state.pending_replacement_choice
    before = serialize_match_snapshot(state); rejected = False
    try: choose_replacement(state, 'half', 3-seat)
    except ActionRejected: rejected = True
    assert rejected and serialize_match_snapshot(state) == before
    state = choose_replacement(deserialize_match_snapshot(before), 'half', seat)
    assert state.cards[cid].counters.get('defense', 0) == 2
    mark('Battle-entry-whole-native-module-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_known_ordinary_absent_defense_uses_zero_for_prospective_battle_entry(seat):
    from rules_engine.battles import defense, entry_proof_matches
    from rules_engine.entry_counters import prepare_entry_counters
    state, _ = position(seat, ('Blood Moon',))
    cid = next(x for x in state.players[seat].library if state.cards[x].name == 'Forest')
    card = move(state, cid, Zone.HAND)
    # Declared noncopy type projection: retained ordinary printing remains intact.
    card.types = ['Land', 'Battle']
    data = {'entry_payload': {}, 'entry_prepared': {}, 'entry_index': 0}
    rejected = False
    try: ready = prepare_entry_counters(state, seat, data, card, 'permanent_entry_counters')
    except ActionRejected: rejected = True
    mark('known-absent-ordinary-defense-entry-assertion-reached')
    assert not rejected and ready and data['entry_prepared']['defense'] == 0
    assert card.printed_defense is None and defense(state, card) == 0
    proof = data['__battle_entry_counter']
    assert proof['version'] == 2 and proof['printed_defense'] is None
    assert entry_proof_matches(state, card, seat, proof)
    assert 'Battle' not in values(card)['types'] and card.counters == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_known_v3_back_face_absence_does_not_use_physical_front_defense(seat):
    from rules_engine.card_faces import select_cast_face
    from rules_engine.battles import defense
    state, cid = position(seat)
    card = select_cast_face(state.cards[cid], 1)
    state.cards[cid] = card
    card.types = ['Creature', 'Battle']  # Declared prospective noncopy type input.
    mark('known-v3-back-face-defense-absence-assertion-reached')
    assert card.characteristic_record['physical']['printed_defense'] == '3'
    assert values(card)['printed_defense'] is None
    assert prepare_only(state, seat, card)['defense'] == 0 and defense(state, card) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_battle_missing_defense_stays_unknown_instead_of_zero(seat):
    from rules_engine.copiable_values import FIELDS, PHYSICAL
    from rules_engine.battles import defense
    state, cid = position(seat)
    card = state.cards[cid]
    descriptor = {key: deepcopy(getattr(card, key)) for key in FIELDS}
    physical = {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
    card.characteristic_record = {'version': 1, 'physical': physical, 'values': descriptor}
    card.printed_defense = None
    rejected = False
    try: prepare_only(state, seat, card)
    except ActionRejected: rejected = True
    mark('legacy-Battle-defense-stays-unknown-assertion-reached')
    assert rejected and defense(state, card) is None and card.counters == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_nullable_absence_receipt_rejects_forgery_and_changed_characteristics(seat):
    from rules_engine.battles import entry_proof_matches
    from rules_engine.entry_counters import prepare_entry_counters
    state, battle = position(seat)
    cid = next(x for x in state.players[seat].library if state.cards[x].name == 'Forest')
    card = move(state, cid, Zone.HAND); card.types = ['Land', 'Battle']
    data = {'entry_payload': {}, 'entry_prepared': {}, 'entry_index': 0}
    assert prepare_entry_counters(state, seat, data, card, 'permanent_entry_counters')
    proof = json.loads(json.dumps(data['__battle_entry_counter']))
    assert entry_proof_matches(state, card, seat, proof)
    for key, value in (('version', 1), ('version', True), ('printed_defense', '0'),
                       ('controller', 3-seat), ('intrinsic_present', 1)):
        wrong = deepcopy(proof); wrong[key] = value
        assert not entry_proof_matches(state, card, seat, wrong)
    wrong = deepcopy(proof); wrong['reference']['zone_change_sequence'] = True
    assert not entry_proof_matches(state, card, seat, wrong)
    apply(card, values(state.cards[battle]))
    assert card.printed_defense == '3' and not entry_proof_matches(state, card, seat, proof)
    mark('known-absence-receipt-forgery-and-rebinding-controls-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_prospective_battle_land_keeps_intrinsic_entry_through_blood_moon(seat):
    from rules_engine.entry_counters import prospective_entry_ability_view
    state, cid = position(seat, ('Blood Moon',))
    place(state, 3-seat, 'Blood Moon', Zone.BATTLEFIELD)
    card = state.cards[cid]; card.types = ['Battle', 'Land']
    mark('prospective-Battle-Land-printed-versus-intrinsic-loss-assertion-reached')
    assert prospective_entry_ability_view(state, card, seat)['printed_suppressed']
    assert not prospective_entry_ability_view(state, card, seat, include_land_types=False)['printed_suppressed']
    assert prepare_only(state, seat, card)['defense'] == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_battle_land_intrinsic_consumer_survives_snapshot_and_printed_loss(seat):
    from rules_engine.battles import intrinsic_abilities_present
    from rules_engine.continuous import printed_abilities_suppressed
    state, cid = position(seat, ('Blood Moon',))
    place(state, 3-seat, 'Blood Moon', Zone.BATTLEFIELD)
    card = battle_ready(state, cid, 3-seat, count=2)
    add_type_effect(state, cid, ['Land'])
    mark('direct-Battle-Land-intrinsic-consumer-assertion-reached')
    assert printed_abilities_suppressed(state, cid) and intrinsic_abilities_present(state, cid)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert printed_abilities_suppressed(restored, cid) and intrinsic_abilities_present(restored, cid)
    assert restored.cards[cid].counters['defense'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_true_all_ability_loss_removes_battle_land_intrinsics_and_departure_restores(seat):
    from rules_engine.battles import intrinsic_abilities_present
    from rules_engine.continuous import printed_abilities_suppressed
    state, cid = position(seat, ('Blood Moon', 'Humility'))
    place(state, 3-seat, 'Blood Moon', Zone.BATTLEFIELD)
    humility = place(state, 3-seat, 'Humility', Zone.BATTLEFIELD)
    battle_ready(state, cid, 3-seat, count=2)
    add_type_effect(state, cid, ['Land', 'Creature'])
    mark('true-all-ability-loss-on-Battle-Land-assertion-reached')
    assert printed_abilities_suppressed(state, cid) and not intrinsic_abilities_present(state, cid)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert not intrinsic_abilities_present(state, cid)
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': humility})
    assert printed_abilities_suppressed(state, cid) and intrinsic_abilities_present(state, cid)
    assert state.cards[cid].counters['defense'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_known_absent_defense_is_bound_in_native_paused_counter_choice(seat):
    from rules_engine.battles import entry_proof_matches
    state, _ = position(seat, ('Doubling Season', 'Vorinclex, Monstrous Raider'))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    cid = next(x for x in state.players[seat].library if state.cards[x].name == 'Forest')
    card = state.cards[cid]; card.types = ['Land', 'Battle']
    state.players[seat].library.remove(cid); state.players[seat].library.append(cid)
    resolve_effect(state, seat, 'topdeck_put_permanents_battlefield', {
        'top_n': 1, 'max_permanents': 1, 'selected_card_ids': [cid], 'counters': {'+1/+1': 1}})
    mark('known-absent-defense-native-counter-choice-assertion-reached')
    assert state.pending_replacement_choice['player_id'] == seat and card.zone == Zone.LIBRARY
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    payload = state.pending_replacement_choice['counter_payload']
    proof = payload['__battle_entry_counter']
    assert proof['version'] == 2 and proof['printed_defense'] is None
    assert entry_proof_matches(state, state.cards[cid], seat, proof)
    proof['version'] = 1  # Negative retained-data fault, not a client permission.
    before = serialize_match_snapshot(state); rejected = False
    option = state.pending_replacement_choice['options'][0]
    try: checked_action(state, RulesEngine(), seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    except ActionRejected: rejected = True
    assert rejected and serialize_match_snapshot(state) == before
    mark('expanded-Battle-entry-whole-native-module-passed')
