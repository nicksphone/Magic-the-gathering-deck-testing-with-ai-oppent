"""Strict surviving-inventory access requirements on pinned canonical cards."""
import json
from pathlib import Path

import pytest

from ai import mana_resource_policy as policy
from ai.information import decision_view
from ai.pending_effects import planning_copy
from game_state.state import Zone, draw_card
from rules_engine.mana_abilities import activate_mana_ability, mana_ability_specs
from tests.test_ai_recurring_engines import add as add_raw
from tests.test_spell_cost_overlap_investigation import add, position, unchanged_root


def discard(state, seat, familiar, card):
    index = mana_ability_specs(state.cards[familiar.id], state)[0][0]
    assert activate_mana_ability(
        state, seat, familiar.id, index, 'B',
        payment_choices={'discard_card_ids': [card.id]})


def capacity_delta(before, after, seat):
    held = [before.cards[cid] for cid in before.players[seat].hand
            if 'Land' not in before.cards[cid].types]
    public = {p: [before.cards[cid] for zone in ('battlefield', 'graveyard', 'exile')
                  for cid in getattr(before.players[p], zone)
                  if not before.cards[cid].exile_face_down
                  and 'Land' not in before.cards[cid].types] for p in (seat, 3-seat)}
    _, old = policy._resource_value(before, seat, held + public[seat])
    _, new = policy._resource_value(after, seat, held + public[seat])
    _, enemy_old = policy._resource_value(before, 3-seat, public[3-seat], public_only=True)
    _, enemy_new = policy._resource_value(after, 3-seat, public[3-seat], public_only=True)
    return new-old+enemy_old-enemy_new


def assert_access_delta(before, after, seat, expected):
    with unchanged_root(before), unchanged_root(after):
        capacity = capacity_delta(before, after, seat)
        score = policy.resource_delta(before, after, seat)
    # Measure the actual resource_delta return, not a replacement score helper.
    assert score == pytest.approx(capacity + 3.0 * expected)


@pytest.mark.parametrize('seat', [1, 2])
def test_discarded_duplicate_cannot_stand_for_unpayable_survivor(seat):
    before = position(seat)
    familiar = add(before, 'Skirge Familiar', seat)
    survivor = add(before, 'Cling to Dust', seat, Zone.HAND)
    victim = add(before, 'Cling to Dust', seat, Zone.HAND)
    with unchanged_root(before):
        after = planning_copy(before)
        discard(after, seat, familiar, victim)
        assert after.players[seat].hand == [survivor.id]
        assert after.players[seat].mana_pool['B'] == 1
        assert policy._can_pay(after, seat, survivor.mana_cost, after.cards[survivor.id])
        assert not policy._can_pay(policy._ready_board(after, seat), seat,
                                   survivor.mana_cost, after.cards[survivor.id])
        assert_access_delta(before, after, seat, -1)


@pytest.mark.parametrize('seat', [1, 2])
def test_surviving_alternative_uses_ready_state_instance(seat, monkeypatch):
    before = position(seat)
    familiar = add(before, 'Skirge Familiar', seat)
    add(before, 'Swamp', seat)
    survivor = add(before, 'Cling to Dust', seat, Zone.HAND)
    victim = add(before, 'Cling to Dust', seat, Zone.HAND)
    after = planning_copy(before)
    discard(after, seat, familiar, victim)
    calls = []
    original = policy._can_pay

    def checked(state, player, cost, card=None):
        if card is not None:
            calls.append(card.id)
            assert card.id in state.players[player].hand
            assert card is state.cards[card.id]
            assert cost == card.mana_cost
        return original(state, player, cost, card)

    monkeypatch.setattr(policy, '_can_pay', checked)
    assert_access_delta(before, after, seat, 0)
    assert survivor.id in calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('draw_replacement', [False, True])
def test_vanished_original_class_has_no_access_even_after_same_name_draw(seat, draw_replacement):
    before = position(seat)
    familiar = add(before, 'Skirge Familiar', seat)
    add(before, 'Swamp', seat)
    victim = add(before, 'Cling to Dust', seat, Zone.HAND)
    drawn = add(before, 'Cling to Dust', seat, Zone.LIBRARY)
    with unchanged_root(before):
        after = planning_copy(before)
        discard(after, seat, familiar, victim)
        if draw_replacement:
            draw_card(after, seat)
            assert drawn.id in after.players[seat].hand
            assert policy._can_pay(after, seat, drawn.mana_cost, after.cards[drawn.id])
        assert_access_delta(before, after, seat, -1)


@pytest.mark.parametrize('seat', [1, 2])
def test_newly_drawn_class_is_not_added(seat):
    before = position(seat)
    add(before, 'Swamp', seat)
    drawn = add(before, 'Cling to Dust', seat, Zone.LIBRARY)
    with unchanged_root(before):
        after = planning_copy(before)
        draw_card(after, seat)
        assert drawn.id in after.players[seat].hand
        assert_access_delta(before, after, seat, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_duplicate_class_gain_is_weighted_once(seat):
    before = position(seat)
    add(before, 'Cling to Dust', seat, Zone.HAND)
    add(before, 'Cling to Dust', seat, Zone.HAND)
    with unchanged_root(before):
        after = planning_copy(before)
        add(after, 'Swamp', seat)
        assert_access_delta(before, after, seat, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_excluded_original_is_not_reintroduced_by_its_class(seat, monkeypatch):
    before = position(seat)
    add(before, 'Swamp', seat)
    excluded = add(before, 'Cling to Dust', seat, Zone.HAND)
    survivor = add(before, 'Cling to Dust', seat, Zone.HAND)
    original = policy._can_pay
    calls = []

    def checked(state, player, cost, card=None):
        if card is not None:
            calls.append(card.id)
            assert card.id != excluded.id
        return original(state, player, cost, card)

    monkeypatch.setattr(policy, '_can_pay', checked)
    with unchanged_root(before):
        after = planning_copy(before)
        with unchanged_root(after):
            assert policy.resource_delta(before, after, seat,
                                         excluded_card_ids={excluded.id}) == 0
    assert calls == [survivor.id, survivor.id]


@pytest.mark.parametrize('seat', [1, 2])
def test_any_surviving_original_after_first_original_leaves(seat):
    before = position(seat)
    familiar = add(before, 'Skirge Familiar', seat)
    add(before, 'Swamp', seat)
    victim = add(before, 'Cling to Dust', seat, Zone.HAND)
    add(before, 'Cling to Dust', seat, Zone.HAND)
    with unchanged_root(before):
        after = planning_copy(before)
        discard(after, seat, familiar, victim)
        assert_access_delta(before, after, seat, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_private_copies_and_anonymous_capacity_remain_distinct(seat):
    before = position(seat)
    add(before, 'Skirge Familiar', seat)
    own = add(before, 'Cling to Dust', seat, Zone.HAND)
    enemy = add(before, 'Cling to Dust', 3-seat, Zone.HAND)
    with unchanged_root(before):
        view, _ = decision_view(before, seat, [])
        ready = policy._ready_board(view, seat)
        assert ready.cards[own.id] is not before.cards[own.id]
        assert ready.cards[own.id].id == own.id
        assert ready.cards[enemy.id].ai_unknown and not ready.cards[enemy.id].oracle_text
        assert policy._can_pay(ready, seat, '{B}')
        assert not policy._can_pay(ready, seat, own.mana_cost, ready.cards[own.id])
        assert policy.resource_delta(view, planning_copy(view), seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_state_cost_modifiers_are_used_without_changing_class_weight(seat):
    before = position(seat)
    mountain = next(row for row in json.loads(
        (Path(__file__).parent / 'fixtures/ward.json').read_text())
        if row['name'] == 'Mountain')
    add_raw(before, 'Mountain', seat, cards={'Mountain': {
        **mountain, 'power': mountain.get('power'), 'toughness': mountain.get('toughness')}})
    spell = add(before, 'Tormenting Voice', seat, Zone.HAND)
    raw = json.loads((Path(__file__).parent / 'fixtures/announced_costs/goblin-electromancer.json').read_text())
    cards = {raw['name']: {**raw, 'power': raw.get('power'), 'toughness': raw.get('toughness')}}
    with unchanged_root(before):
        after = planning_copy(before)
        add_raw(after, raw['name'], seat, cards=cards)
        assert not policy._can_pay(before, seat, spell.mana_cost, before.cards[spell.id])
        assert policy._can_pay(after, seat, spell.mana_cost, after.cards[spell.id])
        assert_access_delta(before, after, seat, 1)
