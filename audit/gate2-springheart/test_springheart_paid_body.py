"""Full canonical Springheart body goldens; never inject stack/trigger/choice state."""
import hashlib
import json
import os
from pathlib import Path

import pytest
import domain_paid_support as g
from free_owner_support import fund
from game_state.state import Zone
from rules_engine.card_types import is_token_card
from game_state.serializers import serialize_match_snapshot, serialize_match
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.bestow import is_bestowed
from rules_engine.coverage import known_unsupported_mechanics

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ['MTG_SPRINGHEART_EVIDENCE']).resolve()


@pytest.fixture(scope='module')
def facts():
    rows = json.loads((HERE/'fixtures/canonical.json').read_bytes())
    proof = json.loads((HERE/'fixtures/provenance.json').read_bytes())
    for name, raw in rows.items():
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert digest == proof['cards'][name]['canonical_fullrow_sha256']
    return rows


def record(request, state, phase, **extra):
    label = hashlib.sha256(request.node.nodeid.encode()).hexdigest()
    (OUT/(label+'-'+phase+'.json')).write_text(json.dumps({
        'node':request.node.nodeid, 'phase':phase,
        'actual_complete_root':serialize_match_snapshot(state), **extra}, indent=2)+'\n')


def position(facts, seat, restore):
    state = g.position(facts, seat)
    # Declared canonical starting host, not a claimed paid creature cast.
    host = g.add(state, facts, 'Raging Goblin', seat, Zone.BATTLEFIELD)
    source = g.add(state, facts, 'Springheart Nantuko', seat, Zone.HAND)
    land = g.add(state, facts, 'Forest', seat, Zone.HAND)
    fund(state, seat, G=2)
    return (g.restore(state) if restore else state), source, host, land


def proposal(source, host, variant):
    return {'type':'cast_spell', 'card_id':source, 'cost_choice':{'id':variant},
            'targets':{'target_card_id':host} if variant=='bestow' else {}}


def announced(request, state, source, host, seat, variant):
    action = proposal(source, host, variant)
    before = serialize_match_snapshot(state)
    offers = [m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id')==source]
    record(request, state, 'before-cast', actual_offers=offers, actual_action=action,
           unchanged_full_oracle=state.cards[source].oracle_text,
           diagnostic_labels=known_unsupported_mechanics(state.cards[source].oracle_text, card_name=state.cards[source].name))
    try:
        paid = checked_action(state, RulesEngine(), seat, action)
    except ActionRejected:
        record(request, state, 'cast-rejected', actual_action=action)
        raise
    assert serialize_match_snapshot(state)==before
    frame = next(f for f in paid.stack if f.source_card_id==source)
    record(request, paid, 'paid', actual_action=action, actual_native_frame_id=frame.id)
    assert frame.payload['mana_spent']==2
    assert is_bestowed(paid.cards[source])==(variant=='bestow')
    for _ in range(24):
        if paid.cards[source].zone!=Zone.STACK:break
        assert not paid.pending_mechanic_choice and not paid.pending_trigger_order
        paid = g.act(paid, paid.priority_player, 'pass_priority')
    record(request, paid, 'entered')
    assert paid.cards[source].zone==Zone.BATTLEFIELD
    assert paid.cards[source].attached_to==(host if variant=='bestow' else None)
    return paid


def land_entry(request, state, seat, land):
    state = g.respond(state, seat)
    before = serialize_match_snapshot(state)
    moves = [m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id')==land]
    record(request, state, 'before-land', actual_land_offers=moves)
    state = g.act(state, seat, 'play_land', card_id=land)
    assert state.cards[land].zone==Zone.BATTLEFIELD
    assert before['cards'][land]['zone']=='hand'
    record(request, state, 'land-entered')
    for _ in range(24):
        if state.pending_mechanic_choice or state.pending_trigger_order or not state.stack:break
        assert not state.pending_trigger_order
        state = g.act(state, state.priority_player, 'pass_priority')
    record(request, state, 'land-trigger-boundary')
    return state


def actual_choices(request, state, seat):
    moves = [m for m in RulesEngine().legal_moves(state, seat)
             if m['type'] in {'choose_mechanic', 'choose_optional_effect'}]
    record(request, state, 'choice-consumer', actual_public_choices=moves)
    assert state.pending_mechanic_choice or state.pending_trigger_order, 'Expected actual native optional choice'
    assert moves, 'Actual native pending choice must have public consumer actions'
    return moves


def choice(request, state, seat, pay):
    moves = actual_choices(request, state, seat)
    matching = [m for m in moves if m.get('accept') is pay]
    record(request, state, 'choice-route', requested_pay=pay, matching_actual_offers=matching)
    assert matching, 'Missing advertised accept/decline action; never invent a pending protocol'
    return checked_action(state, RulesEngine(), seat, matching[0])


def finish(state):
    for _ in range(24):
        if not state.stack and not state.pending_mechanic_choice:return state
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Actual landfall did not finish within bounded public passes')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
@pytest.mark.parametrize('route',['ordinary','bestow-decline','bestow-pay'])
def test_actual_paid_cast_land_enters_full_body(facts, seat, restore, route, request):
    state, source, host, land = position(facts, seat, restore)
    state = announced(request, state, source, host, seat, 'base' if route=='ordinary' else 'bestow')
    fund(state, seat, G=1, C=1)
    state = g.restore(state) if restore else state
    state = land_entry(request, state, seat, land)
    before_choice = sum(state.players[seat].mana_pool.values())
    if route!='ordinary':
        state = choice(request, state, seat, route=='bestow-pay')
    elif state.pending_trigger_order:
        # Consume the engine's actual optional-publication offer, without treating
        # its optional label as proof of canonical whole-body semantics.
        state = choice(request, state, seat, True)
    state = finish(g.restore(state) if restore else state)
    record(request, state, 'terminal')
    tokens = [state.cards[c] for c in state.players[seat].battlefield if is_token_card(state.cards[c])]
    assert len(tokens)==1, 'Exactly the printed landfall reward, not any premature spell-resolution token'
    token = tokens[0]
    if route=='bestow-pay':
        assert token.name==state.cards[host].name
        assert token.oracle_text==facts['Raging Goblin']['oracle_text']
        assert token.power==token.toughness==1
        assert sum(state.players[seat].mana_pool.values())==before_choice-2
    else:
        assert 'Insect' in token.type_line
        assert token.power==token.toughness==1 and token.colors==['G']
        assert sum(state.players[seat].mana_pool.values())==before_choice
    assert state.cards[source].oracle_text==facts['Springheart Nantuko']['oracle_text']


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
def test_bestow_missing_mana_rejects_complete_root_atomically(facts, seat, restore, request):
    state, source, host, _ = position(facts, seat, restore)
    fund(state, seat, G=1)
    before = serialize_match_snapshot(state)
    action = proposal(source, host, 'bestow')
    record(request, state, 'missing-mana-before', actual_action=action)
    with pytest.raises(ActionRejected):checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state)==before
    record(request, state, 'missing-mana-rejected', complete_root_equal=True)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
def test_actual_optional_choice_invalid_id_root_purity(facts, seat, restore, request):
    state, source, host, land = position(facts, seat, restore)
    state = announced(request, state, source, host, seat, 'bestow')
    fund(state, seat, G=1, C=1)
    state = land_entry(request, g.restore(state) if restore else state, seat, land)
    moves = actual_choices(request, state, seat)
    assert all(m.get('stack_id')!='not-an-advertised-choice' for m in moves)
    invalid = {**moves[0], 'stack_id':'not-an-advertised-choice'}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, invalid)
    assert serialize_match_snapshot(state)==before
    record(request, state, 'invalid-choice-rejected', complete_root_equal=True)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
def test_full_public_cast_hints_and_restore_never_expose_private_ids(facts, seat, restore, request):
    state, source, host, _ = position(facts, seat, restore)
    before = serialize_match_snapshot(state)
    moves = [m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id')==source]
    public = serialize_match(state, look_players=(seat,))
    record(request, state, 'private-full-hints', actual_public_cast_moves=moves, actual_public_view=public)
    assert moves, 'Both printed casting alternatives require actual advertised public menus'
    assert {m.get('cast_variant', 'base') for m in moves} >= {'base', 'bestow'}
    hidden = set(state.players[3-seat].hand+state.players[3-seat].library+state.players[seat].library)
    assert not any(cid in json.dumps({'offers':moves,'view':public}) for cid in hidden)
    assert serialize_match_snapshot(state)==before
    assert serialize_match_snapshot(g.restore(state))==before
    assert state.cards[source].oracle_text==facts['Springheart Nantuko']['oracle_text']


@pytest.mark.parametrize('seat',[1,2])
def test_ordinary_landfall_publication_is_mandatory_not_global_optional(facts, seat, request):
    state, source, host, land = position(facts, seat, False)
    state = announced(request, state, source, host, seat, 'base')
    fund(state, seat, G=1, C=1)
    state = g.respond(state, seat)
    state = g.act(state, seat, 'play_land', card_id=land)
    frames = [f for f in state.stack if f.source_card_id==source and f.payload.get('__trigger_event')=='enters_battlefield']
    before_hint = serialize_match_snapshot(state)
    offers = RulesEngine().legal_moves(state, seat)
    public = serialize_match(state, look_players=(seat,))
    record(request, state, 'strict-mandatory-publication', actual_offers=offers,
           actual_public_view=public, actual_source_trigger_ids=[f.id for f in frames])
    assert serialize_match_snapshot(state)==before_hint
    assert serialize_match_snapshot(g.restore(state))==before_hint
    assert frames, 'Genuine land play must publish the complete mandatory landfall frame'
    assert all(not f.payload.get('__may', False) for f in frames), 'Later conditional optional payment cannot make the whole Insect trigger optional'
    assert not any(m['type']=='choose_optional_effect' and m.get('accept') is False for m in offers)
    hidden = set(state.players[3-seat].hand+state.players[3-seat].library+state.players[seat].library)
    assert not any(cid in json.dumps({'offers':offers,'view':public}) for cid in hidden)
    before_payment = sum(state.players[seat].mana_pool.values())
    state = finish(state)
    tokens = [state.cards[c] for c in state.players[seat].battlefield if is_token_card(state.cards[c])]
    record(request, state, 'strict-mandatory-terminal')
    assert len(tokens)==1 and tokens[0].controller==seat
    assert 'Insect' in tokens[0].type_line and tokens[0].colors==['G']
    assert tokens[0].power==tokens[0].toughness==1
    assert sum(state.players[seat].mana_pool.values())==before_payment
