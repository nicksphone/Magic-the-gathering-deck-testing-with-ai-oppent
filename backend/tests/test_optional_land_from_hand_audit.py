"""Paid canonical spell/ETB paths; desired missing continuations remain RED."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from persistence.repository import Repository
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.ai_knowledge_consumer_fixture import position, take

FAMILIES = ['Growth Spiral', 'Arboreal Grazer']


def save(name, state, ledger, **details):
    root = os.environ.get('MTG_LAND_AUDIT_EVIDENCE')
    if root:
        target = Path(root).resolve()
        assert str(target).startswith('/home/nick/.hermes/cache/scratch/mtg-ownhand-land-evidence-')
        (target / (name + '.json')).write_text(json.dumps({
            'snapshot': serialize_match_snapshot(state), 'ledger': ledger, **details,
        }, indent=2, sort_keys=True) + '\n')


def setup(name, seat, *, eligible=True, drawn_land=False, shock=False):
    state = position('Ramp', 'Tempo', seat)
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    source = take(state, name, seat, Zone.HAND)
    # Real paid casts use their exact canonical costs, never injected stack items.
    take(state, 'Forest', seat, Zone.BATTLEFIELD)
    take(state, 'Tropical Island', seat, Zone.BATTLEFIELD)
    land = None
    if eligible:
        if shock:
            from tests.test_contextual_cost_prohibitions import canonical
            land = canonical(state, 'sacred-foundry', seat, Zone.HAND)
        else:
            land = take(state, 'Forest', seat, Zone.HAND)
    take(state, 'Delver of Secrets', 3-seat, Zone.HAND)
    # This is a rules fixture's predetermined draw, NOT an AI policy input.
    draw = next(cid for cid in state.players[seat].library
                if state.cards[cid].name == ('Forest' if drawn_land else 'Ugin, the Spirit Dragon'))
    state.players[seat].library.remove(draw)
    state.players[seat].library.append(draw)
    player = state.players[seat]
    player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1
    player.last_land_play_turn = state.turn
    return state, source, land, draw


def action(state, actor, payload, ledger):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), actor, payload)
    assert serialize_match_snapshot(state) == before
    ledger.append({'actor': actor, 'action': deepcopy(payload),
                   'stack': [{'source': i.source_card_id, 'effect': i.effect_key,
                              'payload': deepcopy(i.payload)} for i in result.stack],
                   'pending': deepcopy(result.pending_mechanic_choice),
                   'trigger_order': deepcopy(result.pending_trigger_order)})
    return result


def cast(state, source, seat, ledger):
    moves = RulesEngine().legal_moves(state, seat)
    move = next(m for m in moves if m['type'] == 'cast_spell' and m.get('card_id') == source.id)
    option = next(o for o in move['cost_options'] if o['id'] == 'base')
    assert option['mana_cost'] == source.mana_cost
    result = action(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                                'cost_choice': {'id': option['id']}}, ledger)
    assert result.stack and result.stack[-1].source_card_id == source.id
    assert result.stack[-1].payload['mana_spent'] == (2 if source.name == 'Growth Spiral' else 1)
    return result


def advance(state, ledger):
    for _ in range(12):
        if state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order or not state.stack:
            return state
        state = action(state, state.priority_player, {'type': 'pass_priority'}, ledger)
    raise AssertionError('Fixture continuation exceeded twelve priority passes')


def land_choice(state, seat, ledger, selected=None):
    moves = RulesEngine().legal_moves(state, seat)
    optional = [m for m in moves if m['type'] == 'choose_optional_effect']
    if optional:
        chosen = next(m for m in optional if m['accept'] is (selected is not None))
        state = action(state, seat, chosen, ledger)
        if selected is None:
            return advance(state, ledger)
        state = advance(state, ledger)
        moves = RulesEngine().legal_moves(state, seat)
    choice = next((m for m in moves if m['type'] == 'choose_mechanic'), None)
    assert choice is not None, 'No authoritative optional land identity/decline continuation'
    own_lands = {cid for cid in state.players[seat].hand if 'Land' in state.cards[cid].types}
    candidates = set(choice.get('options') or []).intersection(state.cards)
    assert candidates and candidates <= own_lands
    assert not RulesEngine().legal_moves(state, 3-seat), 'Wrong seat can act on a private choice'
    if selected is not None:
        assert selected in candidates
    # Existing typed public MechanicChoice card_ids; never fabricated option IDs.
    return action(state, seat, {'type': 'choose_mechanic', 'card_ids': [] if selected is None else [selected]}, ledger)


def roundtrip(state, path):
    before = serialize_match_snapshot(state)
    controller = {'kind': 'synthetic-rules-audit', 'seats': [1, 2]}
    database = create_engine('sqlite:///' + str(path))
    SQLModel.metadata.create_all(database)
    with Session(database) as session:
        Repository(session).save_active_match(state.id, json.dumps(before), json.dumps(controller))
    database.dispose()
    restarted = create_engine('sqlite:///' + str(path))
    with Session(restarted) as session:
        row = Repository(session).get_active_match(state.id)
        restored = deserialize_match_snapshot(json.loads(row.state_json))
        assert json.loads(row.controller_json) == controller
    restarted.dispose()
    assert serialize_match_snapshot(restored) == before
    for seat in [1, 2]:
        assert RulesEngine().legal_moves(restored, seat) == RulesEngine().legal_moves(state, seat)
    return restored


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_real_path_root_draw_entry_zero_eligible_and_restart_controls(seat, name, tmp_path):
    state, source, _, draw = setup(name, seat, eligible=False)
    before = serialize_match_snapshot(state)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    assert state.pending_mechanic_choice is None and not state.stack
    assert state.players[seat].lands_played_this_turn == 1
    assert state.players[seat].land_plays_recorded_on_turn == 1
    if name == 'Growth Spiral':
        assert draw in state.players[seat].hand
        assert source.id in state.players[seat].graveyard
        assert state.draws_this_turn[seat] == 1
    else:
        assert source.id in state.players[seat].battlefield
        assert draw in state.players[seat].library
        assert state.cards[source.id].power == 0 and state.cards[source.id].toughness == 3
        assert 'reach' in state.cards[source.id].keywords
    restored = roundtrip(state, tmp_path / 'closed-local.sqlite')
    save(f'control-{name}-{seat}', restored, ledger, input=before)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('branch', ['select', 'decline'])
def test_optional_actual_hand_identity_or_explicit_decline_desired(seat, name, branch):
    state, source, land, draw = setup(name, seat)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    save(f'desired-{name}-{seat}-{branch}', state, ledger, own_land_id=land.id, drawn_id=draw)
    assert land.id in state.players[seat].hand, 'Effect chose a human land automatically'
    if name == 'Growth Spiral':
        assert draw in state.players[seat].hand, 'Optional selection must be after actual draw'
    state = land_choice(state, seat, ledger, land.id if branch == 'select' else None)
    state = advance(state, ledger)
    assert state.players[seat].lands_played_this_turn == 1
    assert state.players[seat].land_plays_recorded_on_turn == 1
    if branch == 'decline':
        assert land.id in state.players[seat].hand
    else:
        assert land.id not in state.players[seat].hand and land.id in state.players[seat].battlefield
        assert state.cards[land.id].tapped is (name == 'Arboreal Grazer')
        assert state.land_entries_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_growth_drawn_land_is_actual_eligible_choice_desired(seat):
    state, source, _, draw = setup('Growth Spiral', seat, eligible=False, drawn_land=True)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    assert draw in state.players[seat].hand
    save(f'desired-drawn-land-{seat}', state, ledger, drawn_id=draw)
    state = land_choice(state, seat, ledger, draw)
    assert draw in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_optional_private_context_and_stale_wrongseat_desired(seat, name, tmp_path):
    state, source, land, _ = setup(name, seat)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    save(f'desired-private-{name}-{seat}', state, ledger, own_land_id=land.id)
    assert state.pending_mechanic_choice or state.pending_trigger_order, 'Missing private optional choice'
    # If trigger yes/no comes first, accept the actual offered action, not a helper.
    optional = [m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'choose_optional_effect']
    if optional:
        state = advance(action(state, seat, next(m for m in optional if m['accept']), ledger), ledger)
    assert state.pending_mechanic_choice, 'Missing own-hand identity selection'
    state = roundtrip(state, tmp_path / 'pending-local.sqlite')
    own = RulesEngine().legal_moves(state, seat)
    other = serialize_match(state, look_players=(3-seat,))
    assert land.id in json.dumps(own)
    assert land.id not in json.dumps(other.get('pending_mechanic_choice'))
    before = serialize_match_snapshot(state)
    for wrong in [{'type': 'choose_mechanic', 'card_ids': [land.id]},
                  {'type': 'choose_mechanic', 'card_ids': [source.id]}]:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3-seat, wrong)
    assert serialize_match_snapshot(state) == before
    state = land_choice(state, seat, ledger, land.id)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [land.id]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_selected_shock_entry_uses_supported_entry_replacement_desired(seat, name):
    state, source, land, _ = setup(name, seat, shock=True)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    save(f'desired-entry-{name}-{seat}', state, ledger, own_land_id=land.id)
    state = land_choice(state, seat, ledger, land.id)
    assert state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] == 'land_entry'
    offered = RulesEngine().legal_moves(state, seat)[0]
    assert 'pay_two_life' in offered['options']
    state = action(state, seat, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'}, ledger)
    assert land.id in state.players[seat].battlefield
    assert state.players[seat].life == 18
    assert state.cards[land.id].tapped is (name == 'Arboreal Grazer')
    assert state.players[seat].lands_played_this_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_real_source_departure_preserves_old_grazer_trigger_desired(seat):
    state, source, land, _ = setup('Arboreal Grazer', seat)
    enemy = 3-seat
    answer = take(state, 'Brazen Borrower', enemy, Zone.HAND)
    take(state, 'Island', enemy, Zone.BATTLEFIELD)
    take(state, 'Island', enemy, Zone.BATTLEFIELD)
    ledger = []
    state = cast(state, source, seat, ledger)
    while source.id not in state.players[seat].battlefield:
        state = action(state, state.priority_player, {'type': 'pass_priority'}, ledger)
    assert state.stack and state.stack[-1].source_card_id == source.id
    incarnation = object_incarnation(state.cards[source.id])
    zone_sequence = state.cards[source.id].zone_change_sequence
    if state.priority_player != enemy:
        state = action(state, state.priority_player, {'type': 'pass_priority'}, ledger)
    bounce = next(m for m in RulesEngine().legal_moves(state, enemy)
                  if m.get('card_id') == answer.id and m.get('selected_face_index') == 1)
    state = action(state, enemy, {'type': 'cast_spell', 'card_id': answer.id,
                   'selected_face_index': bounce['selected_face_index'], 'cost_choice': {'id': 'base'},
                   'targets': {'target_card_id': source.id}}, ledger)
    while source.id in state.players[seat].battlefield:
        state = action(state, state.priority_player, {'type': 'pass_priority'}, ledger)
    assert source.id in state.players[seat].hand
    assert state.cards[source.id].zone_change_sequence != zone_sequence
    assert object_incarnation(state.cards[source.id]) == incarnation
    assert state.stack and state.stack[-1].source_card_id == source.id
    state = advance(state, ledger)
    save(f'desired-departure-{seat}', state, ledger, old_incarnation=incarnation)
    state = land_choice(state, seat, ledger, land.id)
    assert land.id in state.players[seat].battlefield and state.cards[land.id].tapped


def test_verbatim_canonical_profiles_and_declared_source_provenance():
    root = Path(__file__).parents[1]
    directory = Path(__file__).parent / 'fixtures/optional_land_from_hand'
    provenance = json.loads((directory / 'provenance.json').read_text())
    source = root / 'card_data/builtin_oracle_seed.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == provenance['source_sha256']
    profiles = json.loads((directory / 'canonical.json').read_text())
    seed = json.loads(source.read_text())['cards']
    assert profiles == {name: seed[name] for name in provenance['card_names']}
    for name in FAMILIES:
        state, card, _, _ = setup(name, 1)
        assert card.oracle_text == profiles[name]['oracle_text']
        assert card.mana_cost == profiles[name]['mana_cost']
        assert profiles[name]['scryfall_id']
