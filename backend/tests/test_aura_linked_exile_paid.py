"""Canonical paid Aura entry/link/return; controlled fixtures, not game quality."""
from copy import deepcopy
import hashlib
import json
import random
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import (
    MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry,
)
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


FIXTURES = Path(__file__).parent / 'fixtures'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
STATIC_SHA = 'c7b76c9c901d1f584bcb0791c4ee677f88eca6d95845638d5a48a0d66fb87ece'
PROVENANCE_SHA = 'ef18259ed15d08928a98e6b6b38e278521f2ae2534e734d1e71872a3b02d78ab'
PLANESWALKER = 'Nissa, Who Shakes the World'


@pytest.fixture(scope='module')
def facts():
    seed = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    static = (FIXTURES / 'static_global_keywords/canonical.json').read_bytes()
    provenance = (FIXTURES / 'static_global_keywords/provenance.json').read_bytes()
    assert hashlib.sha256(seed).hexdigest() == SEED_SHA
    assert hashlib.sha256(static).hexdigest() == STATIC_SHA
    assert hashlib.sha256(provenance).hexdigest() == PROVENANCE_SHA
    names = {'Ossification', 'Plains', 'Recruitment Officer', PLANESWALKER, 'Lay Down Arms'}
    rows = {row['name']: row for line in seed.splitlines()
            if (row := json.loads(line))['name'] in names}
    rows['Disenchant'] = json.loads(static)['Disenchant']
    proof = next(row for row in json.loads(provenance)['cards'] if row['name'] == 'Disenchant')
    assert rows['Disenchant']['id'] == proof['id']
    assert rows['Disenchant']['oracle_id'] == proof['oracle_id']
    assert set(rows) == names | {'Disenchant'}
    assert all(row['object'] == 'card' and row['oracle_id'] for row in rows.values())
    return rows


def entry(raw, count):
    normalized = ScryfallSyncService._normalize_payload(raw, 'canonical-regression')
    return {**deepcopy(raw), **normalized, 'card_name': raw['name'], 'quantity': count,
            'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
            'card_faces': deepcopy(raw.get('card_faces', []))}


def pose(facts, seat, *, enemy=True, target_name='Recruitment Officer',
         foreign_owner=False, source_name='Ossification', synthetic_tail=''):
    rows = deepcopy(facts)
    if synthetic_tail:
        # Deliberately noncanonical parser-negative specimen, never printed evidence.
        rows[source_name]['oracle_text'] += synthetic_tail
    own = [entry(rows['Plains'], 53 if foreign_owner else 54),
           entry(rows[source_name], 3), entry(rows['Disenchant'], 3)]
    if foreign_owner:
        own.append(entry(rows[target_name], 1))
    other = ([entry(rows['Plains'], 60)] if foreign_owner else
             [entry(rows['Plains'], 59), entry(rows[target_name], 1)])
    state = MatchFactory.from_decks(own if seat == 1 else other,
                                    other if seat == 1 else own, seed=941)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step, state.turn = Step.PRECOMBAT_MAIN, 5
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = dict.fromkeys('WUBRGC', 0)
        player.snow_mana_pool.clear()
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)

    def move(name, owner, controller, zone):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        card = state.cards[cid]
        card.move_to_zone(zone)
        card.controller = controller
        getattr(state.players[controller], zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            card.summoning_sick, card.tapped = False, False
            if 'Planeswalker' in card.types:
                card.loyalty = int(rows[name]['loyalty'])
            assign_static_order_on_battlefield_entry(state, cid)
        return cid

    # Trusted initial fixture relocation/control, not a claimed played prefix.
    lands = [move('Plains', seat, seat, Zone.BATTLEFIELD) for _ in range(4)]
    source = move(source_name, seat, seat, Zone.HAND)
    removal = move('Disenchant', seat, seat, Zone.HAND)
    target = (move(target_name, seat if foreign_owner else 3 - seat,
                   3 - seat, Zone.BATTLEFIELD) if enemy else None)
    assert len(state.cards) == 120
    assert all(card.oracle_text == rows[card.name]['oracle_text'] for card in state.cards.values())
    assert facts['Ossification']['oracle_text'].endswith('until this Aura leaves the battlefield.')
    return state, source, lands[0], target, removal


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def act(state, seat, action):
    before, request, rng = serialize_match_snapshot(state), deepcopy(action), random.getstate()
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert action == request and random.getstate() == rng
    return result


def reload(state):
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(wire(before)))
    assert wire(serialize_match_snapshot(restored)) == wire(before)
    assert serialize_match_snapshot(state) == before
    return restored


def cast(state, seat, source, target):
    old_pool = sum(state.players[seat].mana_pool.values())
    untapped = {cid for cid in state.players[seat].battlefield if not state.cards[cid].tapped}
    result = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                               'targets': {'target_card_id': target}})
    item = next(item for item in result.stack if item.source_card_id == source)
    assert result.cards[source].zone == Zone.STACK
    assert item.payload['mana_spent'] > 0
    assert (sum(result.players[seat].mana_pool.values()) < old_pool
            or any(result.cards[cid].tapped for cid in untapped))
    return result


def enter(state, source):
    for _ in range(8):
        if state.cards[source].zone != Zone.STACK:
            break
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order)
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.cards[source].zone == Zone.BATTLEFIELD
    return state


def choose_target(state, seat, target):
    before, rng = serialize_match_snapshot(state), random.getstate()
    choices = [move for move in RulesEngine().legal_moves(state, seat)
               if move.get('type') == 'choose_trigger_target'
               and move.get('target_card_id') == target]
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    assert len(choices) == 1, 'Use the actual native target offer, not a fabricated trigger'
    return act(state, seat, deepcopy(choices[0]))


def settle(state):
    for _ in range(32):
        if not state.stack:
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order)
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native stack settlement exceeded the declared bound')


def linked(state, source, target):
    assert state.cards[target].zone == Zone.EXILE
    assert target in state.players[state.cards[target].owner].exile
    assert any(link['source_id'] == source and target in link['card_ids']
               for link in state.linked_exiles)


def destroy_and_return(state, seat, source, target, removal):
    owner = state.cards[target].owner
    assert state.priority_player == seat
    state = settle(cast(state, seat, removal, source))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].controller == owner
    assert target in state.players[owner].battlefield
    assert all(target not in player.exile for player in state.players.values())
    assert not state.linked_exiles
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_entry_exposes_and_accepts_actual_creature_target(facts, seat):
    from rules_engine.oracle_effects import inspect_target_hints
    from rules_engine.targeting import stack_object_kind

    state, source, land, target, _ = pose(facts, seat)
    state = enter(cast(state, seat, source, land), source)
    item = next(item for item in state.stack if item.source_card_id == source)
    assert item.effect_key == 'exile_until_source_leaves'
    before, rng = serialize_match_snapshot(state), random.getstate()
    proxy = deepcopy(state.cards[source])
    proxy.oracle_text = item.payload['__trigger_target_clause']
    proxy.card_faces, proxy.selected_face_index = [], None
    hints = inspect_target_hints(state, proxy, seat, source_kind=stack_object_kind(state, item))
    assert hints['target_restrictions']['allowed_types'] == ['Creature', 'Planeswalker']
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    state = choose_target(state, seat, target)
    linked(settle(state), source, target)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_removal_returns_the_actual_exiled_original(facts, seat):
    state, source, land, target, removal = pose(facts, seat)
    state = settle(choose_target(enter(cast(state, seat, source, land), source), seat, target))
    linked(state, source, target)
    destroy_and_return(state, seat, source, target, removal)


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_opponent_entry_and_attachment_query_preserve_private_root(facts, seat):
    from ai.agent import AIAgent
    from ai.information import decision_view, is_unknown

    state, source, land, _, _ = pose(facts, seat, enemy=False)
    before, rng = serialize_match_snapshot(state), random.getstate()
    moves = RulesEngine().legal_moves(state, seat)
    move = next(move for move in moves if move.get('type') == 'cast_spell'
                and move.get('card_id') == source)
    view, supplied = decision_view(state, seat, [move])
    assert view.ai_information_player == seat and supplied == [move]
    assert not view.sideboard_facts and set(view.starting_decks) <= {seat}
    assert all(is_unknown(view.cards[cid]) for player in view.players.values()
               for cid in player.library)
    AIAgent(difficulty='master', learned_binding=None)._attachment_projection(state, move, seat)
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    state = settle(enter(cast(state, seat, source, land), source))
    assert state.cards[source].attached_to == land and not state.linked_exiles
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_snapshot_roundtrip_retains_link_and_native_paid_return(facts, seat):
    state, source, land, target, removal = pose(facts, seat)
    state = settle(choose_target(enter(cast(state, seat, source, land), source), seat, target))
    linked(state, source, target)
    restored = reload(state)
    linked(restored, source, target)
    destroy_and_return(restored, seat, source, target, removal)


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_planeswalker_union_target_is_exiled_and_returns(facts, seat):
    state, source, land, target, removal = pose(facts, seat, target_name=PLANESWALKER)
    assert state.cards[target].loyalty == int(facts[PLANESWALKER]['loyalty'])
    state = settle(choose_target(enter(cast(state, seat, source, land), source), seat, target))
    linked(state, source, target)
    destroy_and_return(reload(state), seat, source, target, removal)


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_controlled_fixture_returns_to_owner_not_previous_controller(facts, seat):
    state, source, land, target, removal = pose(facts, seat, foreign_owner=True)
    assert state.cards[target].owner == seat and state.cards[target].controller == 3 - seat
    state = settle(choose_target(enter(cast(state, seat, source, land), source), seat, target))
    linked(state, source, target)
    destroy_and_return(reload(state), seat, source, target, removal)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_disenchant_before_etb_resolution_prevents_exile(facts, seat):
    state, source, land, target, removal = pose(facts, seat)
    state = choose_target(enter(cast(state, seat, source, land), source), seat, target)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    state = settle(cast(state, seat, removal, source))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert target in state.players[3 - seat].battlefield and not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' Unknown instruction.', '\nUnknown instruction.',
                                 ' (Unknown instruction.)'])
def test_synthetic_unknown_complete_body_is_noop_not_plain_exile(facts, seat, tail):
    state, source, land, target, _ = pose(facts, seat, synthetic_tail=tail)
    state = enter(cast(state, seat, source, land), source)
    triggers = [item for item in state.stack if item.source_card_id == source]
    assert triggers and all(item.effect_key == 'noop' for item in triggers)
    assert all(item.payload.get('__unsupported_trigger_instruction') for item in triggers)
    state = settle(state)
    assert state.cards[target].zone == Zone.BATTLEFIELD and not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_paid_primitive_exile_stays_unlinked(facts, seat):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    old_life = state.players[3 - seat].life
    state = settle(cast(state, seat, source, target))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.EXILE
    assert state.players[3 - seat].life == old_life + 3
    assert not state.linked_exiles
