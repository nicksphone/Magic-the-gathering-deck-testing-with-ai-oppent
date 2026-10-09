"""NEW16: opposite paid copying, strict root errors, real same-ID blink choices."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import test_paid_force_twincast as core
from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine

basefacts = core.original.facts
receipts = core.receipts
SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def facts(basefacts):
    rows = deepcopy(basefacts)
    raw_twin = json.loads((SOURCE/'backend/tests/fixtures/coupled_targets/twincast.json').read_bytes())
    assert raw_twin['oracle_text']=='Copy target instant or sorcery spell. You may choose new targets for the copy.'
    rows['Twincast'] = raw_twin
    raw = json.loads((SOURCE/'backend/tests/fixtures/archangel_pair/flicker-of-fate.json').read_bytes())
    assert raw['object']=='card' and raw['name']=='Flicker of Fate' and raw['mana_cost']=='{1}{W}'
    assert raw['oracle_text']=="Exile target creature or enchantment, then return it to the battlefield under its owner's control."
    rows['Flicker of Fate'] = raw
    before = deepcopy(rows)
    yield rows
    assert rows==before


def frame(state, identity):
    return next(f for f in state.stack if f.id==identity)


def menu(state, actor, copy_id):
    pending = state.pending_mechanic_choice
    assert pending and pending['kind']=='copy_target', 'Strict prerequisite: public copy menu missing'
    assert pending['player_id']==actor and pending['stack_id']==copy_id
    moves = RulesEngine().legal_moves(state, actor)
    offered = next(m for m in moves if m['type']=='choose_mechanic')
    assert offered['options']==pending['options']
    assert len(offered['options'])==len(set(offered['options']))
    return offered


def opposite(facts, seat, count, rows, *, private=False):
    state, source, original_id, ids, new = core.position(facts, seat, count, rows)
    hidden = []
    if private:
        hidden = [core.paid.add(state, facts, 'Searing Blaze', seat, Zone.HAND),
                  core.paid.add(state, facts, 'Secure the Wastes', seat, Zone.LIBRARY)]
    original_payload = deepcopy(frame(state, original_id).payload)
    actor = 3-seat
    state = core.paid.respond(state, actor)
    state, twin, copy_id = core.copied(state, facts, actor, original_id, rows)
    assert frame(state, copy_id).controller==actor
    assert frame(state, original_id).controller==seat
    assert frame(state, copy_id).payload['__copied_card']['colors']==facts['Force of Vigor']['colors']
    assert frame(state, original_id).payload==original_payload
    return state, source, original_id, ids, new, twin, copy_id, actor, hidden


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[0,1,2])
def test_real_opposite_copier_paid_zero_one_two_targets(facts, seat, count, receipts):
    state, source, original_id, ids, new, twin, copy_id, actor, _ = opposite(facts, seat, count, receipts)
    original_payload = deepcopy(frame(state, original_id).payload)
    for target in new[:count]:
        menu(state, actor, copy_id)
        state = core.public_choice(state, actor, copy_id, 'target_card_id:'+target, receipts)
    assert state.pending_mechanic_choice is None
    assert frame(state, original_id).payload==original_payload
    state = core.passes(core.paid.restore(state))
    assert all(state.cards[cid].zone==Zone.GRAVEYARD for cid in new[:count])
    assert all(state.cards[cid].zone==Zone.BATTLEFIELD for cid in ids[:count])
    state = core.passes(core.paid.restore(state))
    assert not state.stack and state.cards[source].zone==state.cards[twin].zone==Zone.GRAVEYARD
    assert all(state.cards[cid].zone==Zone.GRAVEYARD for cid in ids[:count])
    core.note(receipts, 'opposite-copy-and-original-resolved', state, copier=actor, original_caster=seat)


@pytest.mark.parametrize('seat',[1,2])
def test_wrong_actor_copy_choice_rejects_without_root_change(facts, seat, receipts):
    state, _, _, _, new, _, copy_id, actor, _ = opposite(facts, seat, 1, receipts)
    offered = menu(state, actor, copy_id)
    selection = 'target_card_id:'+new[0]
    assert selection in offered['options']
    before = serialize_match_snapshot(state)
    assert not RulesEngine().legal_moves(state, seat)
    with pytest.raises(ActionRejected):
        core.paid.act(state, seat, 'choose_mechanic', card_ids=[selection])
    assert serialize_match_snapshot(state)==before
    core.note(receipts, 'wrong-actor-root-unchanged', state)


@pytest.mark.parametrize('seat',[1,2])
def test_private_unknown_and_wrong_public_type_ids_reject_atomically(facts, seat, receipts):
    state, _, _, ids, _, _, copy_id, actor, hidden = opposite(facts, seat, 1, receipts, private=True)
    offered = menu(state, actor, copy_id)
    public = json.dumps(offered)
    for cid in hidden:
        assert cid not in public and state.cards[cid].name not in public
    for cid in [*hidden, ids[2], ids[3], 'unknown-audit-object']:
        selection = 'target_card_id:'+cid
        assert selection not in offered['options']
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected) as error:
            core.paid.act(state, actor, 'choose_mechanic', card_ids=[selection])
        assert serialize_match_snapshot(state)==before
        for private_id in hidden:
            assert private_id not in str(error.value) and state.cards[private_id].name not in str(error.value)
    core.note(receipts, 'five-invalid-ids-root-unchanged', state, checks=5)


@pytest.mark.parametrize('seat',[1,2])
def test_malformed_public_copy_selection_rejects_atomically(facts, seat, receipts):
    state, _, _, _, new, _, copy_id, actor, _ = opposite(facts, seat, 1, receipts)
    offered = menu(state, actor, copy_id)
    selection = 'target_card_id:'+new[0]
    assert selection in offered['options'] and 'keep' in offered['options']
    malformed = [[], ['keep',selection], ['keep','keep'], 'keep', None, [1], ['target_player:1']]
    for choices in malformed:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            core.paid.act(state, actor, 'choose_mechanic', card_ids=choices)
        assert serialize_match_snapshot(state)==before
    core.note(receipts, 'seven-malformed-choices-root-unchanged', state, checks=7)


def reference(card):
    return {'card_id':card.id,'incarnation':object_incarnation(card),
            'zone_change_sequence':card.zone_change_sequence}


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('selection',['keep','refresh'])
def test_actual_paid_flicker_before_opposite_copy_same_id_keeps_or_refreshes(facts, seat, selection, receipts):
    state, force, _, _, ids = core.original.setup(facts, seat, 'Force of Vigor', 1)
    target = ids[1]  # Canonical enchantment; Flicker cannot target an ordinary artifact.
    old_ref = reference(state.cards[target])
    state = core.original.cast(state, seat, force, {'target_card_ids':[target]})
    original_id = state.stack[-1].id
    original_payload = deepcopy(state.stack[-1].payload)
    assert sum(state.players[seat].mana_pool.values())==0
    actor = 3-seat
    twin = core.paid.add(state, facts, 'Twincast', actor, Zone.HAND)
    state = core.paid.respond(state, actor)
    state.players[actor].mana_pool={'U':2}
    state = core.paid.act(state, actor, 'cast_spell', card_id=twin, targets={'target_stack_id':original_id})
    assert sum(state.players[actor].mana_pool.values())==0 and state.stack[-1].effect_key=='copy_spell'
    flicker = core.paid.add(state, facts, 'Flicker of Fate', seat, Zone.HAND)
    state = core.paid.respond(state, seat)
    state.players[seat].mana_pool={'C':1,'W':1}
    state = core.paid.act(state, seat, 'cast_spell', card_id=flicker, targets={'target_card_id':target})
    assert len(state.stack)==3 and sum(state.players[seat].mana_pool.values())==0
    core.note(receipts, 'three-actual-paid-spells-before-flicker', state,
              canonical_flicker_body=facts['Flicker of Fate']['oracle_text'], old_reference=old_ref)
    state = core.passes(core.paid.restore(state))
    assert state.cards[flicker].zone==Zone.GRAVEYARD and len(state.stack)==2
    assert state.cards[target].id==target and state.cards[target].zone==Zone.BATTLEFIELD
    fresh_ref = reference(state.cards[target])
    assert fresh_ref!=old_ref and state.cards[target].controller==state.cards[target].owner
    state = core.passes(core.paid.restore(state))
    copies=[f for f in state.stack if f.payload.get('__copied_from_stack_id')==original_id]
    assert len(copies)==1 and copies[0].id!=original_id and copies[0].controller==actor
    copy_id=copies[0].id
    offered=menu(state, actor, copy_id)
    assert 'keep' in offered['options'] and 'target_card_id:'+target in offered['options']
    assert copies[0].payload['__announced_target_references']['targets']['target_card_ids']==[old_ref]
    state=core.public_choice(state, actor, copy_id, 'keep' if selection=='keep' else 'target_card_id:'+target, receipts)
    expected=old_ref if selection=='keep' else fresh_ref
    copied=frame(state,copy_id)
    assert copied.payload['__announced_target_references']['targets']['target_card_ids']==[expected]
    child=copied.payload['effects'][0]['payload']
    assert child['target_card_id']==target and child['__target_incarnation']==expected['incarnation']
    assert child['__target_zone_sequence']==expected['zone_change_sequence']
    assert frame(state,original_id).payload==original_payload
    state=core.passes(core.paid.restore(state))
    assert state.cards[target].zone==(Zone.BATTLEFIELD if selection=='keep' else Zone.GRAVEYARD)
    state=core.passes(core.paid.restore(state))
    assert not state.stack and state.cards[force].zone==state.cards[twin].zone==Zone.GRAVEYARD
    assert state.cards[target].zone==(Zone.BATTLEFIELD if selection=='keep' else Zone.GRAVEYARD)
    core.note(receipts, 'same-id-flicker-copy-and-original-resolved', state,
              mode=selection, old_reference=old_ref, fresh_reference=fresh_ref)
