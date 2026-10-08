"""Evidence-first loyalty entry witnesses against real reusable entry contracts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.observations import public_card_ids
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.optional_reveal import public_choice
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_restricted_mana import clean
from tests.test_linked_damage_targets import raw_card
import test_paid_context_goldens as paid
from tests.test_counter_replacements import ROWS as COUNTER_ROWS

ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT/'backend/tests/fixtures'
AURAS = {r['name']: r for r in json.loads((FIX/'aura_costs.json').read_bytes())}
SHOCK = json.loads((FIX/'contextual_cost_prohibitions/sacred-foundry.json').read_bytes())
SEED = json.loads((ROOT/'backend/card_data/builtin_oracle_seed.json').read_bytes())['cards']
facts = paid.facts
LAND_LAYERS = {r['name']: r for r in json.loads((FIX/'basic_land_layer_goldens/cards.json').read_bytes())}


def position(seat):
    state = clean(seat)
    state.mechanic_choice_players = {1, 2}
    return state


def cold(state):
    snapshot = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(snapshot)
    assert serialize_match_snapshot(result) == snapshot
    return result


def action(state, seat, **fields):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', **fields})
    assert serialize_match_snapshot(state) == before
    return cold(result)


def hand_entry(state, seat, ids):
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': len(ids)})
    if state.pending_mechanic_choice:
        assert state.pending_mechanic_choice['kind'] == 'loyalty_cards'
        state = action(cold(state), seat, card_ids=ids)
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life'])
def test_hand_entry_uses_actual_shock_land_choice_and_payment(seat, choice):
    state = position(seat)
    card = raw_card(state, SHOCK, seat, Zone.HAND)
    state = hand_entry(state, seat, [card.id])
    assert state.cards[card.id].zone == Zone.HAND
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    state = action(state, seat, choice_id=choice)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].tapped == (choice == 'tapped')
    assert state.players[seat].life == (18 if choice == 'pay_two_life' else 20)
    assert state.players[seat].lands_played_this_turn == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('hexproof', [False, True])
def test_uncast_aura_chooses_legal_attachment_not_a_target(seat, hexproof):
    state = position(seat)
    target = raw_card(state, AURAS['Colossal Dreadmaw'], 3-seat, Zone.BATTLEFIELD)
    if hexproof:
        add_keyword_effect(state, target.id, ['hexproof'])
    aura = raw_card(state, AURAS['Octopus Umbra'], seat, Zone.HAND)
    state = hand_entry(state, seat, [aura.id])
    assert state.cards[aura.id].zone == Zone.HAND
    assert state.pending_mechanic_choice['kind'] == 'loyalty_attachment'
    assert target.id in state.pending_mechanic_choice['options']
    state = action(state, seat, choice_id=target.id)
    assert state.cards[aura.id].zone == Zone.BATTLEFIELD
    assert state.cards[aura.id].attached_to == target.id
    assert not state.stack, 'noncast attachment must not create targeting/ward triggers'


@pytest.mark.parametrize('seat', [1, 2])
def test_aura_without_legal_attachment_remains_private_in_hand(seat):
    state = position(seat)
    aura = raw_card(state, AURAS['Octopus Umbra'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 1})
    if state.pending_mechanic_choice:
        state = action(state, seat, card_ids=[aura.id])
    assert state.cards[aura.id].zone == Zone.HAND
    assert aura.id in state.players[seat].hand
    assert aura.id not in public_card_ids(state)
    assert aura.id not in state.card_observations.get(3-seat, {})


@pytest.mark.parametrize('seat', [1, 2])
def test_offered_hand_reference_cannot_follow_leave_and_return(seat):
    state = position(seat)
    card = raw_card(state, AURAS['Colossal Dreadmaw'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 1})
    card.move_to_zone(Zone.GRAVEYARD)
    card.move_to_zone(Zone.HAND)
    state = cold(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, card_ids=[card.id])
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_command_emblem_is_public_and_persisted_not_a_battlefield_target(seat):
    state = position(seat)
    resolve_effect(state, seat, 'loyalty_emblem', {'kind': 'static',
        'text': 'Creatures you control get +2/+2 and have flying.'})
    cid = state.emblems[-1]
    assert cid in public_card_ids(state)
    assert cid in state.card_observations[1] and cid in state.card_observations[2]
    view = serialize_match(cold(state))
    assert [e['id'] for e in view['emblems']] == [cid]
    assert view['emblems'][0]['controller'] == seat and view['emblems'][0]['zone'] == 'command'
    assert all(cid not in p.battlefield for p in state.players.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_hand_entry_public_receipt_hides_private_options_and_program(seat):
    state = position(seat)
    card = raw_card(state, AURAS['Colossal Dreadmaw'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 1})
    public = public_choice(state.pending_mechanic_choice)
    assert card.id not in json.dumps(public)
    assert 'effect_payload' not in public and 'options' not in public
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert card.id in moves[0]['options']
    assert 'effect_payload' not in moves[0]
    assert RulesEngine().legal_moves(state, 3-seat) == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_land_entry_rechecks_life_availability_without_free_payment(seat):
    state = position(seat)
    card = raw_card(state, SHOCK, seat, Zone.HAND)
    state.players[seat].life = 1
    state = hand_entry(state, seat, [card.id])
    assert state.pending_mechanic_choice['options'] == ['tapped']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, choice_id='pay_two_life')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_already_offered_land_payment_rechecks_current_affordability(seat):
    state = position(seat)
    card = raw_card(state, SHOCK, seat, Zone.HAND)
    state = hand_entry(state, seat, [card.id])
    assert 'pay_two_life' in state.pending_mechanic_choice['options']
    state.players[seat].life = 1
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, choice_id='pay_two_life')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_dynamic_blood_moon_entry_view_loses_printed_tapped_and_payment_abilities(seat):
    state = position(seat)
    raw_card(state, LAND_LAYERS['Blood Moon'], 3-seat, Zone.BATTLEFIELD)
    cards = [raw_card(state, SEED[name], seat, Zone.HAND) for name in ('Breeding Pool', "Jetmir's Garden")]
    state = hand_entry(state, seat, [card.id for card in cards])
    assert state.pending_mechanic_choice is None
    assert all(state.cards[c.id].zone == Zone.BATTLEFIELD and not state.cards[c.id].tapped for c in cards)
    assert state.players[seat].life == 20
    from rules_engine.mana import mana_source_outputs
    assert all(mana_source_outputs(state, seat, c.id) == {'R': 1} for c in cards)


@pytest.mark.parametrize('seat', [1, 2])
def test_already_offered_payment_rechecks_new_ability_loss(seat):
    state = position(seat)
    card = raw_card(state, SHOCK, seat, Zone.HAND)
    state = hand_entry(state, seat, [card.id])
    raw_card(state, LAND_LAYERS['Blood Moon'], 3-seat, Zone.BATTLEFIELD)
    state = cold(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, choice_id='pay_two_life')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_attachment_choice_cannot_follow_departed_returned_target(seat):
    state = position(seat)
    target = raw_card(state, AURAS['Colossal Dreadmaw'], 3-seat, Zone.BATTLEFIELD)
    aura = raw_card(state, AURAS['Octopus Umbra'], seat, Zone.HAND)
    state = hand_entry(state, seat, [aura.id])
    target = state.cards[target.id]
    target.move_to_zone(Zone.GRAVEYARD)
    target.move_to_zone(Zone.BATTLEFIELD)
    state = cold(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        action(state, seat, choice_id=target.id)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_up_to_entry_may_select_zero_without_revealing_hand(seat):
    state = position(seat)
    card = raw_card(state, AURAS['Colossal Dreadmaw'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 7})
    state = action(state, seat, card_ids=[])
    assert state.pending_mechanic_choice is None
    assert state.cards[card.id].zone == Zone.HAND
    assert card.id not in state.card_observations.get(3-seat, {})


@pytest.mark.parametrize('seat', [1, 2])
def test_new_hand_creature_is_not_an_already_existing_aura_attachment(seat):
    state = position(seat)
    creature = raw_card(state, AURAS['Colossal Dreadmaw'], seat, Zone.HAND)
    aura = raw_card(state, AURAS['Octopus Umbra'], seat, Zone.HAND)
    resolve_effect(state, seat, 'loyalty_hand_entry', {'count': 2})
    assert aura.id not in state.pending_mechanic_choice['options']
    state = action(state, seat, card_ids=[creature.id])
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD
    assert state.cards[aura.id].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_real_emblem_draw_trigger_and_opponent_decision_view(seat):
    state = position(seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for _ in range(3):
        raw_card(state, SEED['Forest'], seat, Zone.LIBRARY)
    target = raw_card(state, AURAS['Colossal Dreadmaw'], 3-seat, Zone.BATTLEFIELD)
    resolve_effect(state, seat, 'loyalty_emblem', {'kind': 'draw_exile',
        'text': 'Whenever you draw a card, exile target permanent an opponent controls.'})
    emblem = state.emblems[-1]
    from ai.information import decision_view
    before = serialize_match_snapshot(state)
    view, _ = decision_view(state, 3-seat, [])
    assert view.cards[emblem].name == 'Emblem'
    assert serialize_match_snapshot(state) == before
    resolve_effect(state, seat, 'draw_cards', {'amount': 1})
    for _ in range(24):
        state = cold(state)
        if state.pending_trigger_order:
            actor = state.pending_trigger_order['current_controller']
            moves = RulesEngine().legal_moves(state, actor)
            move = next((m for m in moves if m.get('target_card_id') == target.id), moves[0])
        elif state.stack:
            actor = state.priority_player
            move = {'type': 'pass_priority'}
        else:
            break
        before = serialize_match_snapshot(state)
        result = checked_action(state, RulesEngine(), actor, move)
        assert serialize_match_snapshot(state) == before
        state = result
    else:
        raise AssertionError('24 public actions for emblem trigger')
    assert state.cards[target.id].zone == Zone.EXILE
    assert state.cards[emblem].zone == Zone.COMMAND


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('land_choice', ['tapped', 'pay_two_life'])
def test_real_paid_ugin_ultimate_mixed_permanent_batch(facts, seat, land_choice, request):
    rows = deepcopy(facts)
    rows.update(deepcopy(AURAS))
    for name in ('Ugin, the Spirit Dragon', 'Breeding Pool', "Jetmir's Garden", 'Teferi, Hero of Dominaria'):
        rows[name] = deepcopy(SEED[name])
    rows.update(deepcopy(COUNTER_ROWS))
    state = paid.g.position(rows, seat)
    paid.g.add(state, rows, 'Doubling Season', seat)
    target = paid.g.add(state, rows, 'Colossal Dreadmaw', 3-seat)
    chosen = [paid.g.add(state, rows, name, seat, Zone.HAND) for name in
              ('Breeding Pool', "Jetmir's Garden", 'Octopus Umbra', 'Teferi, Hero of Dominaria')]
    source = paid.g.add(state, rows, 'Ugin, the Spirit Dragon', seat, Zone.HAND)
    state, _ = paid.paid(state, seat, source, {'C': 8})
    for _ in range(8):
        if not state.stack:
            break
        state = paid.act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[source].zone == Zone.BATTLEFIELD
    paid.g.add(state, rows, "Lae'zel, Vlaakith's Champion", seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state = paid.priority(state, seat)
    state = paid.act(state, seat, {'type': 'activate_loyalty', 'card_id': source,
        'ability_index': 2, 'targets': {}})
    kinds = []
    for _ in range(96):
        state = paid.cold(state)
        pending = state.pending_mechanic_choice
        if pending:
            kinds.append(pending['kind'])
            if pending['kind'] == 'loyalty_cards':
                assert all(state.cards[cid].zone == Zone.HAND for cid in chosen)
                move = {'type': 'choose_mechanic', 'card_ids': chosen}
            elif pending['kind'] == 'loyalty_attachment':
                move = {'type': 'choose_mechanic', 'choice_id': target}
            else:
                assert pending['kind'] == 'land_entry'
                assert all(state.cards[cid].zone == Zone.HAND for cid in chosen)
                move = {'type': 'choose_mechanic', 'choice_id': land_choice}
            state = paid.act(state, pending['player_id'], move)
        elif state.pending_replacement_choice:
            assert all(state.cards[cid].zone == Zone.HAND for cid in chosen)
            actor = state.pending_replacement_choice['player_id']
            state = paid.act(state, actor, paid.offers(state, actor)[0])
        elif state.pending_trigger_order:
            actor = state.pending_trigger_order['current_controller']
            state = paid.act(state, actor, paid.offers(state, actor)[0])
        elif state.stack:
            state = paid.act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            break
    else:
        raise AssertionError('96 actual public-action bound')
    assert 'loyalty_attachment' in kinds and 'land_entry' in kinds
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in chosen)
    assert state.cards[chosen[0]].tapped == (land_choice == 'tapped')
    assert state.cards[chosen[1]].tapped
    assert state.cards[chosen[2]].attached_to == target
    assert state.cards[chosen[3]].loyalty in (9, 10)
    assert state.players[seat].life == (25 if land_choice == 'pay_two_life' else 27)
    assert state.players[seat].lands_played_this_turn == 0
    assert state.stack == [] and state.pending_mechanic_choice is None
    assert all(state.players[seat].battlefield.count(cid) == 1 for cid in chosen)
    (Path(__import__('os').environ['GAP6_EVIDENCE']) / (request.node.name.replace('/', '_')+'.json')).write_text(
        json.dumps({'node':request.node.nodeid,'declared_rows':{n:rows[n] for n in
            ('Ugin, the Spirit Dragon', 'Breeding Pool', "Jetmir's Garden", 'Octopus Umbra', 'Teferi, Hero of Dominaria')},
            'snapshot':serialize_match_snapshot(state),'actual_actions':paid.ACTIONS,'choice_kinds':kinds}, indent=2)+'\n')
