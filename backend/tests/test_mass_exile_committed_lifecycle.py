"""Real paid mass-exile PRE batching, immunity, replacement and lifecycle controls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from effects import handlers
from game_state.state import Zone, object_incarnation
from tests.test_mass_exile_lifecycle_audit import ROWS, SPELLS, add, board, cast, resolve, restore

FIXTURE = Path(__file__).parent / 'fixtures/mass_exile_product'
for entry in json.loads((FIXTURE/'provenance.json').read_text()):
    raw = (FIXTURE/entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_text'] == entry['oracle_text'] and entry['full_raw']
    ROWS[row['name']] = row


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
def test_genuine_entire_cohort_pre_event_reference_and_staged_commit(seat, spell, monkeypatch):
    state, cid, creatures = board(seat, spell, foreign=True, static='Humility')
    pre = {x: {'incarnation': object_incarnation(state.cards[x]), 'zone_change_sequence': state.cards[x].zone_change_sequence}
           for x in creatures}
    trace=[]
    original=handlers.emit_event_batch
    def observe(current,event,payloads):
        if event == 'leaves_battlefield':
            trace.append((deepcopy(payloads), current.trigger_staging,
                          {x: (current.cards[x].zone,
                               x in current.players[current.cards[x].controller].battlefield)
                           for x in creatures}))
        return original(current,event,payloads)
    monkeypatch.setattr(handlers,'emit_event_batch',observe)
    state=resolve(cast(state,seat,cid,6 if spell=='Final Judgment' else 5))
    assert len(trace)==1 and trace[0][1]
    assert all(value==(Zone.BATTLEFIELD,True) for value in trace[0][2].values())
    assert {item['card_id']:item['previous_reference'] for item in trace[0][0]}==pre
    assert all(state.cards[x].zone_change_sequence==pre[x]['zone_change_sequence']+1 for x in creatures)
    assert not state.trigger_staging
    assert state.cards[creatures[0]].owner==3-seat
    assert creatures[0] in state.players[3-seat].exile


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
@pytest.mark.parametrize('immune', ['Progenitus','Avacyn, Angel of Hope'])
def test_untargeted_paid_exile_ignores_protection_and_indestructibility_not_grave_replacement(seat,spell,immune):
    state,cid,creatures=board(seat,spell)
    extra=add(state,immune,3-seat,Zone.BATTLEFIELD)
    rng=state.rng.getstate()
    state=resolve(cast(state,seat,cid,6 if spell=='Final Judgment' else 5))
    assert state.cards[extra].zone==Zone.EXILE and extra in state.players[3-seat].exile
    assert state.cards[extra].zone_change_sequence==2
    assert state.rng.getstate()==rng  # Progenitus/Colossus graveyard shuffle cannot replace exile.
    assert not state.stack
    state=restore(state)
    assert state.cards[extra].zone==Zone.EXILE


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('spell',SPELLS)
def test_real_paid_tokens_under_rest_in_peace_keep_sunfall_count_no_false_death(seat,spell):
    state,cid,creatures=board(seat,spell,foreign=True)
    rip=add(state,'Rest in Peace',3-seat,Zone.BATTLEFIELD)
    alarm=add(state,'Raise the Alarm',seat,Zone.HAND)
    state=resolve(cast(state,seat,alarm,2))
    tokens=[x for x in state.players[seat].battlefield if state.cards[x].name=='Soldier']
    assert len(tokens)==2
    lives=[state.players[p].life for p in (1,2)]
    state=resolve(cast(state,seat,cid,6 if spell=='Final Judgment' else 5))
    assert rip in state.players[3-seat].battlefield
    assert all(x not in state.players[seat].battlefield for x in tokens)
    assert [state.players[p].life for p in (1,2)]==lives
    assert not state.stack
    if spell=='Sunfall':
        incubators=[state.cards[x] for x in state.players[seat].battlefield if state.cards[x].name=='Incubator']
        assert len(incubators)==1 and incubators[0].counters['+1/+1']==5


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('spell',SPELLS)
def test_real_ray_delayed_tap_publishes_after_exile_commits_then_noops_same_departed_object(seat,spell):
    state,cid,creatures=board(seat,spell)
    ray=add(state,'Ray of Command',seat,Zone.HAND)
    state=resolve(cast(state,seat,ray,4,{'target_card_id':creatures[0]},'U'))
    record=deepcopy(state.delayed_triggers[0])
    state=resolve(cast(state,seat,cid,6 if spell=='Final Judgment' else 5))
    assert not state.delayed_triggers
    assert len(state.stack)==1 and state.stack[-1].effect_key=='control_loss_tap'
    trigger=state.stack[-1]
    assert trigger.controller==seat and trigger.source_card_id==ray
    assert trigger.payload['__delayed_source_reference']==record['payload']['__delayed_source_reference']
    assert trigger.payload['zone_change_sequence']+1==state.cards[creatures[0]].zone_change_sequence
    state=resolve(restore(state))
    assert not state.stack
    assert state.cards[creatures[0]].zone==Zone.EXILE and not state.cards[creatures[0]].tapped
