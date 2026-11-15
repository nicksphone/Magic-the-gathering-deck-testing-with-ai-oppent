"""Native Siege exile/cast permissions with complete original printing inputs.

Counter removal and trigger resolution are real native producers. Initial zones,
counter counts, controller changes and direct copy/effect packets are declared
core-policy positions, not unplayed card histories. Graveyard cost/X controls
exercise the shared waiver path; they do not invent DFC back-face printings.
Tests inspect only their own state. No HTTP family is filtered into this module.
"""
from collections import Counter
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.copiable_values import apply, values
from effects.registry import resolve_effect
from tests.test_battle_entry import row as battle_row, place, move, battle_ready, BATTLE
from tests.test_battle_defeat import remove, ref
from tests.test_battle_characteristics import mark

DELVER = 'Delver of Secrets // Insectile Aberration'
VALKI = 'Valki, God of Lies // Tibalt, Cosmic Impostor'
BALA = 'Bala Ged Recovery // Bala Ged Sanctuary'


def row(name, count):
    if name in {VALKI, BALA, 'Secure the Wastes'}:
        from tests.canonical_positive_fixtures import raw_card
        raw = raw_card(name)
    elif name == 'Wandering Archaic // Explore the Vastlands':
        from tests.remaining_named_birth_fixtures import raw_card
        raw = raw_card(name)
    elif name == 'Sphere of Resistance':
        from tests.test_announced_spell_costs import ROWS
        raw = deepcopy(ROWS[name])
    elif name in {'Bitter Triumph', 'Drannith Magistrate'}:
        import hashlib, json
        from pathlib import Path
        root = Path(__file__).parent / 'fixtures/battle_cast_full_printing'
        provenance = json.loads((root / 'PROVENANCE.json').read_text())
        source = next(r for r in provenance['exact_complete_public_printings'] if r['name'] == name)
        encoded = (root / source['local_file']).read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == source['sha256']
        raw = json.loads(encoded)
        assert len(raw) == source['fields'] and raw['id'] == source['id'] and raw['oracle_id'] == source['oracle_id']
    else:
        return battle_row(name, count)
    full = (raw.get('object') == 'card' and len(raw) >= 50
            and all(raw.get(key) for key in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout')))
    if not full: mark('Task4-original-reader-not-a-full-printing')
    assert full
    return {**raw, 'card_name': name, 'quantity': count}


def position(seat, source=BATTLE, extra=()):
    counts = Counter((BATTLE, source, *extra))
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
    original = place(state, seat, BATTLE, Zone.GRAVEYARD)
    cid = place(state, seat, source, Zone.BATTLEFIELD)
    if source != BATTLE:
        apply(state.cards[cid], values(state.cards[original]))
    state.cards[cid].counters['defense'] = 3; state.cards[cid].battle_protector = 3-seat
    return state, cid


def cold(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def defeated(seat, source=BATTLE, *, extra=(), human=True):
    state, cid = position(seat, source, extra)
    state.mechanic_choice_players = {seat} if human else set()
    assert remove(state, cid, 3) == 3
    assert state.stack[-1].effect_key == 'battle_defeat'
    resolve_top_of_stack(state)
    return state, cid


def cast_action(cid, **extra):
    return {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
            'selected_face_index': 1, **extra}


def casts(state, seat):
    return [m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'cast_spell']


def reject(state, seat, action):
    before = serialize_match_snapshot(state)
    try: checked_action(state, RulesEngine(), seat, action)
    except ActionRejected: pass
    else: raise AssertionError('Invalid transformed announcement was accepted')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_native_defeat_exiles_then_offers_exact_physical_back(seat):
    state, cid = defeated(seat)
    mark('Task4-native-defeat-exile-assertion-reached')
    assert state.cards[cid].zone == Zone.EXILE and cid in state.players[seat].exile
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'effect_cast' and pending['player_id'] == seat
    assert pending['effect_payload'] == {
        'permission_kind': 'battle_transformed', 'target_card_id': cid,
        'reference': ref(state.cards[cid]), 'face_index': 1}
    assert len(casts(state, seat)) == 1
    assert casts(state, seat)[0]['selected_face_index'] == 1
    assert not RulesEngine().legal_moves(state, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_human_cast_after_snapshot_is_a_real_back_spell(seat):
    state, cid = defeated(seat)
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert not state.pending_mechanic_choice
    assert state.cards[cid].zone == Zone.STACK and state.cards[cid].name == 'Awakened Skyclave'
    assert state.cards[cid].selected_face_index == 1
    assert state.spells_cast_this_turn[seat] == 1
    assert state.stack[-1].source_card_id == cid and state.stack[-1].controller == seat
    assert not any(state.cards[x].tapped for x in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
def test_decline_is_durable_and_cannot_reuse_the_permission(seat):
    state, cid = defeated(seat)
    state = checked_action(cold(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[cid].zone == Zone.EXILE and not state.spells_cast_this_turn.get(seat)
    reject(cold(state), seat, cast_action(cid))


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_ai_uses_the_same_transformed_announcement(seat):
    state, cid = defeated(seat, human=False)
    assert state.cards[cid].zone == Zone.STACK and state.cards[cid].name == 'Awakened Skyclave'
    assert state.spells_cast_this_turn[seat] == 1 and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_ai_choice_preserves_state_and_casts_the_back(seat):
    state, cid = defeated(seat)
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='strong').choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell' and decision.action['selected_face_index'] == 1
    state = checked_action(state, RulesEngine(), seat, decision.action)
    assert state.cards[cid].name == 'Awakened Skyclave' and state.cards[cid].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_does_not_exile_a_new_battlefield_incarnation(seat):
    state, cid = position(seat)
    state.mechanic_choice_players = {seat}; remove(state, cid, 3)
    move(state, cid, Zone.HAND); battle_ready(state, cid, 3-seat)
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_departed_original_is_not_cast_from_its_new_zone(seat):
    state, cid = position(seat)
    state.mechanic_choice_players = {seat}; remove(state, cid, 3)
    move(state, cid, Zone.HAND)
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.HAND and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_single_faced_copied_siege_stays_exiled(seat):
    state, cid = defeated(seat, 'Shifting Woodland')
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].name == 'Shifting Woodland'
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_nonmodal_copy_casts_its_own_physical_back(seat):
    state, cid = defeated(seat, DELVER)
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert state.cards[cid].name == 'Insectile Aberration' and state.cards[cid].zone == Zone.STACK
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].name == 'Insectile Aberration'


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_copy_casts_its_own_back_under_current_rules(seat):
    state, cid = defeated(seat, VALKI)
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert state.cards[cid].name == 'Tibalt, Cosmic Impostor' and state.cards[cid].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_land_back_cannot_be_cast_or_played_through_siege_permission(seat):
    state, cid = defeated(seat, BALA)
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_mechanic_choice
    assert not casts(state, seat)
    reject(state, seat, {'type': 'play_land', 'card_id': cid, 'from_exile': True, 'selected_face_index': 1})


@pytest.mark.parametrize('seat', [1, 2])
def test_real_native_token_copy_cannot_be_cast_after_departure(seat):
    state, original = position(seat)
    state.mechanic_choice_players = {seat}
    from rules_engine.type_effects import add_type_effect
    add_type_effect(state, original, ['Creature'])
    before = set(state.cards)
    resolve_effect(state, seat, 'create_token_copy', {'target_card_id': original})
    cid, = set(state.cards)-before
    assert state.cards[cid].is_token and state.cards[cid].counters['defense'] == 3
    remove(state, cid, 3)
    # The copied entry trigger is independent; resolve the actual defeat first.
    assert state.stack[-1].effect_key == 'battle_defeat'
    resolve_top_of_stack(state)
    assert not state.pending_mechanic_choice
    assert not any(item.source_card_id == cid and item.effect_key != 'search_library' for item in state.stack)
    assert state.cards[cid].zone != Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_face_or_zone_flags_reject_without_mutation(seat):
    state, cid = defeated(seat)
    for action in (cast_action(cid, selected_face_index=0), cast_action(cid, selected_face_index=True),
                   cast_action(cid, selected_face_index=2), cast_action(cid, from_graveyard=True),
                   cast_action(cid, from_library=True), cast_action(cid, from_exile=False),
                   cast_action(cid, targets={'selected_face_index': 0})):
        reject(state, seat, action)


@pytest.mark.parametrize('seat', [1, 2])
def test_forged_permission_shape_or_reference_rejects_atomically(seat):
    state, cid = defeated(seat)
    for change in ({'face_index': 0}, {'face_index': True}, {'permission_kind': 'unknown'},
                   {'exile_after_cast': True}, {'from_graveyard': True},
                   {'reference': {'incarnation': True, 'zone_change_sequence': 0}},
                   {'reference': {'incarnation': 0, 'zone_change_sequence': 0}}):
        copy = cold(state)
        copy.pending_mechanic_choice['effect_payload'].update(change)
        reject(copy, seat, cast_action(cid))


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_leave_and_return_invalidates_saved_permission(seat):
    state, cid = defeated(seat)
    previous = ref(state.cards[cid])
    move(state, cid, Zone.HAND); move(state, cid, Zone.EXILE)
    assert ref(state.cards[cid]) != previous and not casts(state, seat)
    reject(state, seat, cast_action(cid))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_player_cannot_use_or_decline_permission(seat):
    state, cid = defeated(seat)
    reject(state, 3-seat, cast_action(cid))
    reject(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})


@pytest.mark.parametrize('seat', [1, 2])
def test_client_action_flag_does_not_create_an_effect_permission(seat):
    state, cid = position(seat)
    move(state, cid, Zone.EXILE)
    reject(state, seat, cast_action(cid, effect_cast=True, suspend_cast=True,
                                  permission_kind='battle_transformed', reference=ref(state.cards[cid])))


@pytest.mark.parametrize('seat', [1, 2])
def test_stolen_battle_exiles_to_owner_but_ability_controller_casts(seat):
    state, cid = position(3-seat)
    move(state, cid, Zone.BATTLEFIELD, controller=seat)
    state.cards[cid].counters['defense'] = 3; state.cards[cid].battle_protector = 3-seat
    state.active_player = state.priority_player = seat; state.mechanic_choice_players = {seat}
    remove(state, cid, 3); resolve_top_of_stack(state)
    assert cid in state.players[3-seat].exile and cid not in state.players[seat].exile
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert state.cards[cid].zone == Zone.STACK and state.cards[cid].controller == seat
    assert state.cards[cid].owner == 3-seat and state.spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_waiver_still_pays_real_spell_tax(seat):
    state, cid = defeated(seat, extra=('Sphere of Resistance',))
    place(state, 3-seat, 'Sphere of Resistance', Zone.BATTLEFIELD)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.cards[x].tapped for x in state.players[seat].battlefield) == 1
    assert state.stack[-1].payload['mana_spent'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_unpayable_tax_blocks_cast_but_preserves_decline(seat):
    state, cid = defeated(seat, extra=('Sphere of Resistance',))
    place(state, 3-seat, 'Sphere of Resistance', Zone.BATTLEFIELD)
    for x in state.players[seat].battlefield: state.cards[x].tapped = True
    assert not casts(state, seat)
    reject(state, seat, cast_action(cid))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_back_spell_can_be_countered_by_actual_paid_counterspell(seat):
    state, cid = defeated(seat, extra=('Counterspell',))
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    spell = state.stack[-1].id
    counter = place(state, 3-seat, 'Counterspell', Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 2}
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'cast_spell', 'card_id': counter, 'targets': {'target_stack_id': spell}})
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.cards[cid].name == 'Invasion of Zendikar'
    assert state.cards[cid].selected_face_index in (None, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_decline_resumes_later_native_instructions_exactly_once(seat):
    state, cid = position(seat); state.mechanic_choice_players = {seat}
    add_to_stack(state, cid, seat, 'Declared core-policy sequence', 'effect_sequence', {'effects': [
        {'effect_key': 'battle_defeat', 'payload': {'target_card_id': cid, '__trigger_source_reference': ref(state.cards[cid])}},
        {'effect_key': 'gain_life', 'payload': {'amount': 2, 'target_player': seat}},
    ], '__trigger_source_reference': ref(state.cards[cid])}, is_spell=False)
    assert not resolve_top_of_stack(state)
    assert state.players[seat].life == 20 and state.pending_mechanic_choice.get('resolving_item')
    state = checked_action(cold(state), RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.players[seat].life == 22 and not state.pending_mechanic_choice and not state.stack
    assert cold(state).players[seat].life == 22


@pytest.mark.parametrize('seat', [1, 2])
def test_nonmodal_back_keeps_front_mana_value_on_stack_and_battlefield(seat):
    from rules_engine.card_faces import card_mana_value
    state, cid = defeated(seat)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    assert card_mana_value(state.cards[cid]) == 4
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and card_mana_value(state.cards[cid]) == 4
    assert card_mana_value(cold(state).cards[cid]) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_back_uses_its_own_mana_value(seat):
    from rules_engine.card_faces import card_mana_value
    state, cid = defeated(seat, VALKI)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    assert card_mana_value(state.cards[cid]) == 7
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and card_mana_value(state.cards[cid]) == 7


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_of_nonmodal_back_has_zero_value_even_on_a_physical_dfc(seat):
    from rules_engine.card_faces import card_mana_value
    state, cid = defeated(seat, DELVER, extra=(BATTLE,))
    state = checked_action(state, RulesEngine(), seat, cast_action(cid)); assert resolve_top_of_stack(state)
    other = place(state, seat, BATTLE, Zone.BATTLEFIELD)
    apply(state.cards[other], values(state.cards[cid]))
    assert card_mana_value(state.cards[other]) == 0
    assert card_mana_value(state.cards[cid]) == 1
    assert card_mana_value(cold(state).cards[other]) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_mana_value_target_filter_sees_physical_transformed_value(seat):
    from rules_engine.oracle_effects import _target_card_matches_restrictions
    state, cid = defeated(seat, DELVER)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid)); assert resolve_top_of_stack(state)
    assert not _target_card_matches_restrictions(state, state.cards[cid], {'mana_value_max': 0}, seat)
    assert _target_card_matches_restrictions(state, state.cards[cid], {'mana_value_max': 1}, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_waiver_requires_real_target_and_additional_discard(seat):
    state, _ = position(seat, extra=('Bitter Triumph', 'Island', 'Grizzly Bears'))
    shards = place(state, seat, 'Bitter Triumph', Zone.GRAVEYARD)
    fodder = place(state, seat, 'Island', Zone.HAND)
    target = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': shards})
    reject(state, seat, {'type': 'cast_spell', 'card_id': shards, 'from_graveyard': True})
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': shards, 'from_graveyard': True,
        'cost_choice': {'id': 'base_discard', 'discard_card_ids': [fodder]},
        'targets': {'target_card_id': target}})
    assert state.cards[shards].zone == Zone.STACK and state.cards[fodder].zone == Zone.GRAVEYARD
    assert resolve_top_of_stack(state) and state.cards[target].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_waiver_enforces_zero_for_actual_printed_x(seat):
    state, _ = position(seat, extra=('Secure the Wastes',))
    cid = place(state, seat, 'Secure the Wastes', Zone.GRAVEYARD)
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': cid})
    reject(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_graveyard': True, 'targets': {'x_value': 1}})
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': cid, 'from_graveyard': True, 'targets': {'x_value': 0}})
    assert state.stack[-1].payload['__announced_targets']['x_value'] == 0
    assert resolve_top_of_stack(state)
    assert not any(state.cards[x].is_token for x in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_magistrate_restriction_blocks_human_cast_but_allows_decline(seat):
    state, cid = defeated(seat, extra=('Drannith Magistrate',))
    place(state, 3-seat, 'Drannith Magistrate', Zone.BATTLEFIELD)
    assert not casts(state, seat)
    reject(state, seat, cast_action(cid))
    state = checked_action(cold(state), RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_magistrate_restriction_also_blocks_automatic_cast(seat):
    state, cid = position(seat, extra=('Drannith Magistrate',))
    place(state, 3-seat, 'Drannith Magistrate', Zone.BATTLEFIELD)
    state.mechanic_choice_players = set()
    remove(state, cid, 3); assert resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_mechanic_choice
    assert not state.spells_cast_this_turn.get(seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_transformed_cast_publishes_actual_noncreature_cast_trigger(seat):
    mark('Task4-cast-event-input-position-started')
    state, cid = position(seat, 'Wandering Archaic // Explore the Vastlands')
    from dataclasses import replace
    from game_state.state import assign_static_order_on_battlefield_entry
    from tests.test_announced_spell_costs import ROWS
    raw = deepcopy(ROWS['Young Pyromancer'])
    assert raw['object'] == 'card' and len(raw) >= 50
    assert all(raw.get(key) for key in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout'))
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 8}], [], seed=0)
    printed = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    actor = replace(printed, id=state.allocate_object_id(), owner=seat, controller=seat,
                    zone=Zone.BATTLEFIELD, summoning_sick=False, instance_order=0)
    state.cards[actor.id] = actor; state.players[seat].battlefield.append(actor.id)
    assign_static_order_on_battlefield_entry(state, actor.id)
    mark('Task4-cast-event-full-input-position-created')
    state.mechanic_choice_players = {seat}
    remove(state, cid, 3); resolve_top_of_stack(state)
    mark('Task4-cast-event-defeat-resolution-returned')
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    mark('Task4-cast-event-checked-announcement-returned')
    assert state.spells_cast_this_turn[seat] == 1 and state.cards[cid].zone == Zone.STACK
    assert state.cards[cid].name == 'Explore the Vastlands'
    assert len([item for item in state.stack if item.source_card_id == actor.id and item.effect_key == 'create_token']) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_resumes_later_instructions_once_without_resolving_the_back_spell(seat):
    state, cid = position(seat); state.mechanic_choice_players = {seat}
    add_to_stack(state, cid, seat, 'Declared core-policy sequence', 'effect_sequence', {'effects': [
        {'effect_key': 'battle_defeat', 'payload': {'target_card_id': cid, '__trigger_source_reference': ref(state.cards[cid])}},
        {'effect_key': 'gain_life', 'payload': {'amount': 2, 'target_player': seat}},
    ], '__trigger_source_reference': ref(state.cards[cid])}, is_spell=False)
    assert not resolve_top_of_stack(state)
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert state.players[seat].life == 22 and not state.pending_mechanic_choice
    assert state.cards[cid].zone == Zone.STACK and len(state.stack) == 1
    assert state.stack[0].effect_key != 'effect_sequence'
    assert state.spells_cast_this_turn[seat] == 1
    assert cold(state).players[seat].life == 22


@pytest.mark.parametrize('seat', [1, 2])
def test_readding_defense_does_not_cancel_an_already_triggered_defeat(seat):
    from rules_engine.counter_placement import put_counters
    state, cid = position(seat); state.mechanic_choice_players = {seat}
    remove(state, cid, 3); put_counters(state, 'defense', 2, target_card_id=cid)
    assert state.cards[cid].counters['defense'] == 2
    resolve_top_of_stack(state)
    assert state.cards[cid].zone == Zone.EXILE and state.pending_mechanic_choice['kind'] == 'effect_cast'


@pytest.mark.parametrize('seat', [1, 2])
def test_losing_the_siege_copy_after_trigger_does_not_change_physical_back(seat):
    state, cid = position(seat); state.mechanic_choice_players = {seat}
    remove(state, cid, 3)
    forest = next(state.cards[x] for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    apply(state.cards[cid], values(forest))
    resolve_top_of_stack(state)
    state = checked_action(cold(state), RulesEngine(), seat, cast_action(cid))
    assert state.cards[cid].zone == Zone.STACK and state.cards[cid].name == 'Awakened Skyclave'


@pytest.mark.parametrize('seat', [1, 2])
def test_nonmodal_back_spell_copy_has_zero_value_after_original_departure(seat):
    from rules_engine.card_faces import card_mana_value
    from rules_engine.targeting import stack_source_card
    from rules_engine.oracle_effects import _target_card_matches_restrictions
    state, cid = defeated(seat)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    original = state.stack[-1].id
    resolve_effect(state, 3-seat, 'copy_spell', {'target_stack_id': original})
    copy = state.stack[-1]
    assert copy.id != original
    resolve_effect(state, 3-seat, 'counter_spell', {'target_stack_id': original})
    state = cold(state); copy = next(item for item in state.stack if item.id == copy.id)
    view = stack_source_card(state, copy)
    assert state.cards[cid].zone == Zone.GRAVEYARD and view.name == 'Awakened Skyclave'
    mark('Task4-nonmodal-back-spell-copy-mana-value-assertion-reached')
    assert card_mana_value(view) == 0
    assert not _target_card_matches_restrictions(state, view, {'mana_value_min': 4}, seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_back_spell_copy_keeps_face_up_value_after_original_departure(seat):
    from rules_engine.card_faces import card_mana_value
    from rules_engine.targeting import stack_source_card
    state, cid = defeated(seat, VALKI)
    state = checked_action(state, RulesEngine(), seat, cast_action(cid))
    original = state.stack[-1].id
    resolve_effect(state, 3-seat, 'copy_spell', {'target_stack_id': original})
    copy = state.stack[-1]
    resolve_effect(state, 3-seat, 'counter_spell', {'target_stack_id': original})
    state = cold(state); copy = next(item for item in state.stack if item.id == copy.id)
    view = stack_source_card(state, copy)
    assert view.name == 'Tibalt, Cosmic Impostor' and card_mana_value(view) == 7
