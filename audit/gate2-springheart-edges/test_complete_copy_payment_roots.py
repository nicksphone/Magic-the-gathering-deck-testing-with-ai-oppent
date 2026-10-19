"""Strict whole roots for copy faces, legend, entry continuations and paid sacrifice."""
import hashlib
import json
from pathlib import Path

import pytest
import domain_paid_support as g
import test_springheart_paid_body as original
import test_springheart_departure_body as departure
from free_owner_support import fund
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, serialize_match
from rules_engine.card_faces import apply_transform_face
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action, ActionRejected


@pytest.fixture(scope='module')
def complete_facts():
    path = Path(__file__).resolve().parent/'fixtures'
    facts = json.loads((path/'canonical.json').read_bytes())
    proof = json.loads((path/'provenance.json').read_bytes())
    for name, raw in facts.items():
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert digest == proof['cards'][name]['canonical_fullrow_sha256']
    return facts


def cast_position(facts, seat, name, request, *, face=None, residents=()):
    state = g.position(facts, seat)
    host = g.add(state, facts, name, seat, Zone.BATTLEFIELD)
    # Explicit canonical starting-face fixture, NOT a played transform certificate.
    # The complete raw row and both faces remain unchanged in fixture provenance.
    if face is not None:
        apply_transform_face(state.cards[host], face)
    for resident in residents:
        g.add(state, facts, resident, seat, Zone.BATTLEFIELD)
    source = g.add(state, facts, 'Springheart Nantuko', seat, Zone.HAND)
    land = g.add(state, facts, 'Forest', seat, Zone.HAND)
    original.record(request, state, 'declared-complete-position',
                    canonical_starting_host=name, declared_face=face,
                    declared_residents=list(residents), paid_host_history_claim=False)
    fund(state, seat, G=2)
    state = original.announced(request, state, source, host, seat, 'bestow')
    return state, source, host, land


def payment_ready(state, seat, land, request, restore):
    state, _ = departure.native_land_frame(state, seat, land, request)
    state = departure.reach_payment(g.restore(state) if restore else state, request)
    assert state.pending_trigger_order and not state.pending_mechanic_choice
    return state


def complete_public_choices(state, request, restore, *, keeper=None):
    receipts = []
    for index in range(48):
        pending = state.pending_replacement_choice or state.pending_mechanic_choice
        if pending:
            actor = pending['player_id']
            before = serialize_match_snapshot(state)
            moves = RulesEngine().legal_moves(state, actor)
            public = serialize_match(state, look_players=(actor,))
            assert serialize_match_snapshot(state) == before
            assert moves
            if state.pending_replacement_choice:
                action = {key: moves[0][key] for key in ('type', 'replacement_source_id')}
            else:
                assert pending['kind'] == 'legend_keeper'
                selected = keeper if keeper is not None else pending['options'][0]
                assert selected in pending['options']
                action = {'type': 'choose_mechanic', 'card_ids': [selected]}
            original.record(request, state, f'actual-public-continuation-{index}',
                            actual_moves=moves, actual_public_view=public, actual_action=action)
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), 3-actor, action)
            assert serialize_match_snapshot(state) == before
            receipts.append({'kind': pending.get('kind', pending.get('resume_kind')),
                             'actor': actor, 'action': action})
            state = checked_action(state, RulesEngine(), actor, action)
            state = g.restore(state) if restore else state
        elif state.stack:
            assert not state.pending_trigger_order
            state = g.act(state, state.priority_player, 'pass_priority')
        else:
            original.record(request, state, 'complete-public-terminal', actual_choices=receipts)
            return state, receipts
    raise AssertionError('Public entry/legend continuation exceeded bounded actions')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('face', [0, 1])
def test_copy_declared_canonical_face_retains_both_faces_and_current_face(complete_facts, seat, restore, face, request):
    name = 'Delver of Secrets // Insectile Aberration'
    state, _, host, land = cast_position(complete_facts, seat, name, request, face=face)
    expected = state.cards[host]
    expected_faces = json.loads(json.dumps(expected.card_faces))
    expected_face = {'name': expected.name, 'oracle_text': expected.oracle_text,
                     'power': expected.power, 'toughness': expected.toughness,
                     'colors': expected.colors, 'mana_cost': expected.mana_cost}
    fund(state, seat, G=2)
    state = payment_ready(state, seat, land, request, restore)
    before = sum(state.players[seat].mana_pool.values())
    state = original.choice(request, state, seat, True)
    state, _ = complete_public_choices(state, request, restore)
    tokens = departure.owned_tokens(state, seat)
    original.record(request, state, 'strict-copy-face-terminal', expected_copiable_faces=expected_faces)
    assert len(tokens) == 1
    token = tokens[0]
    for key, value in expected_face.items():
        assert getattr(token, key) == value
    assert token.card_faces == expected_faces, 'Token copy must retain both copiable faces'
    assert token.layout == 'double_faced_token'
    assert token.selected_face_index == face
    assert token.owner == token.controller == seat
    assert sum(state.players[seat].mana_pool.values()) == before-2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_legendary_copy_created_then_actual_keeper_choice_completes(complete_facts, seat, restore, request):
    name = 'Isamaru, Hound of Konda'
    state, source, host, land = cast_position(complete_facts, seat, name, request)
    fund(state, seat, G=2)
    state = payment_ready(state, seat, land, request, restore)
    before = sum(state.players[seat].mana_pool.values())
    state = original.choice(request, state, seat, True)
    original.record(request, state, 'actual-legendary-copy-before-keeper')
    tokens = departure.owned_tokens(state, seat)
    assert len(tokens) == 1 and tokens[0].name == name
    token_id = tokens[0].id
    assert tokens[0].power == tokens[0].toughness == 2
    assert state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] == 'legend_keeper'
    state, choices = complete_public_choices(g.restore(state) if restore else state, request, restore, keeper=token_id)
    assert any(row['kind'] == 'legend_keeper' for row in choices)
    assert state.cards[host].zone == Zone.GRAVEYARD
    assert state.cards[token_id].zone == Zone.BATTLEFIELD
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].attached_to is None
    assert sum(state.players[seat].mana_pool.values()) == before-2
    assert len([cid for cid in state.players[seat].battlefield if state.cards[cid].name == name]) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('pay', [False, True])
def test_token_doubling_and_paused_entry_choices_eventually_create_exact_branch(complete_facts, seat, restore, pay, request):
    residents = ('Renata, Called to the Hunt', 'Hardened Scales', 'Doubling Season')
    state, _, host, land = cast_position(complete_facts, seat, 'Raging Goblin', request, residents=residents)
    fund(state, seat, G=2)
    state = payment_ready(state, seat, land, request, restore)
    before = sum(state.players[seat].mana_pool.values())
    state = original.choice(request, state, seat, pay)
    original.record(request, state, 'real-token-entry-pause')
    assert state.pending_replacement_choice, 'Require actual entry replacement continuation, not invented pending state'
    state, choices = complete_public_choices(g.restore(state) if restore else state, request, restore)
    tokens = departure.owned_tokens(state, seat)
    original.record(request, state, 'strict-eventual-creation-terminal')
    assert choices and len(tokens) == 2
    assert len({token.id for token in tokens}) == 2
    for token in tokens:
        assert token.owner == token.controller == seat
        assert token.power == token.toughness == 1
        assert token.counters.get('+1/+1') in (3, 4)
        if pay:
            assert token.name == state.cards[host].name and token.oracle_text == complete_facts['Raging Goblin']['oracle_text']
        else:
            assert 'Insect' in token.type_line and token.colors == ['G']
    assert sum(state.players[seat].mana_pool.values()) == before-(2 if pay else 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_payment_sacrifices_enchanted_mana_creature_then_copies_its_actual_lki(complete_facts, seat, restore, request):
    state, source, host, land = cast_position(complete_facts, seat, 'Wild Cantor', request)
    fund(state, seat)
    state = payment_ready(state, seat, land, request, restore)
    assert sum(state.players[seat].mana_pool.values()) == 0
    moves = original.actual_choices(request, state, seat)
    assert any(move.get('accept') is True for move in moves)
    state = original.choice(request, state, seat, True)
    state, _ = complete_public_choices(g.restore(state) if restore else state, request, restore)
    original.record(request, state, 'strict-paid-host-sacrifice-terminal')
    assert state.cards[host].zone == Zone.GRAVEYARD
    assert state.cards[land].tapped
    assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].attached_to is None
    tokens = departure.owned_tokens(state, seat)
    assert len(tokens) == 1 and tokens[0].name == 'Wild Cantor'
    assert tokens[0].oracle_text == complete_facts['Wild Cantor']['oracle_text']
    assert tokens[0].power == tokens[0].toughness == 1
    assert tokens[0].colors == ['R', 'G'] or tokens[0].colors == ['G', 'R']
    assert sum(state.players[seat].mana_pool.values()) == 0
