"""24 both-seat paid canonical path checks; RED is never xfailed or converted to support."""
import pytest
from nadu_support import Position, FACTS, snapshot, restored, object_incarnation
from game_state.state import Zone, Step
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_power

CASES=['paid_setup','standalone_zero_equip','enemy_target_atomic','non_sorcery_atomic',
       'first_land','first_nonland','one_object_limit','distinct_object_limits','turn_reset',
       'new_incarnation','trigger_replay','real_shock_entry']

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('case',CASES)
def test_actual_paid_canonical_nadu_shuko(case,seat):
    branch='nonland' if case=='first_nonland' else 'shock' if case=='real_shock_entry' else 'land'
    pos=Position.__new__(Position)
    try:
        pos.__init__(seat,case,branch,nadu=case not in ['standalone_zero_equip','enemy_target_atomic','non_sorcery_atomic'])
        state=pos.state
        if case=='paid_setup':
            cid=pos.ids['nadu'];assert state.cards[cid].zone==Zone.BATTLEFIELD
            assert state.cards[cid].oracle_text==FACTS['Nadu, Winged Wisdom']['oracle_text']
            assert snapshot(restored(state))==snapshot(state)
        elif case=='standalone_zero_equip':
            pos.equip(pos.ids['elf'],False)
            assert effective_power(pos.state,pos.ids['elf'])==2
        elif case=='enemy_target_atomic':
            before=snapshot(state)
            with pytest.raises(ActionRejected):pos.act(seat,{'type':'equip','card_id':pos.ids['shuko'],'target_card_id':pos.ids['enemy_elf']})
            assert snapshot(pos.state)==before
        elif case=='non_sorcery_atomic':
            while pos.state.step==Step.PRECOMBAT_MAIN:pos.tick()
            before=snapshot(pos.state)
            with pytest.raises(ActionRejected):pos.act(seat,{'type':'equip','card_id':pos.ids['shuko'],'target_card_id':pos.ids['elf']})
            assert snapshot(pos.state)==before
        elif case in ['first_land','first_nonland']:
            top=pos.equip(pos.ids['elf'])
            assert ('Land' in pos.state.cards[top].types)==(case=='first_land')
        elif case=='one_object_limit':
            pos.equip(pos.ids['elf']);pos.equip(pos.ids['elf']);pos.equip(pos.ids['elf'],False)
        elif case=='distinct_object_limits':
            for target,trigger in [(pos.ids['elf'],True),(pos.ids['elf'],True),(pos.ids['nadu'],True),
                                   (pos.ids['nadu'],True),(pos.ids['elf'],False),(pos.ids['nadu'],False)]:pos.equip(target,trigger)
        elif case=='turn_reset':
            pos.equip(pos.ids['elf']);pos.equip(pos.ids['elf']);pos.equip(pos.ids['elf'],False)
            pos.next_own_main();pos.equip(pos.ids['elf'])
        elif case=='new_incarnation':
            pos.equip(pos.ids['nadu']);pos.equip(pos.ids['nadu']);old=object_incarnation(pos.state.cards[pos.ids['nadu']])
            # Only real Bolt death and paid Reanimate can produce this incarnation; no manual zone edits.
            for _ in range(12):
                names=[pos.state.cards[c].name for c in pos.state.players[seat].hand]
                if names.count('Lightning Bolt')>=2 and 'Reanimate' in names:
                    lands=[pos.state.cards[c].name for c in pos.state.players[seat].battlefield]
                    if lands.count('Mountain')>=2 and 'Swamp' in lands:break
                pos.next_own_main()
                need_red=sum(pos.state.cards[c].name=='Mountain' for c in pos.state.players[seat].battlefield)<2
                for name in (['Mountain','Swamp'] if need_red else ['Swamp','Mountain']):
                    if name in [pos.state.cards[c].name for c in pos.state.players[seat].hand]:
                        try:pos.act(seat,{'type':'play_land','card_id':pos.find_hand(name,seat)})
                        except ActionRejected:pass
                        else:break
            for _ in range(2):pos.cast_name('Lightning Bolt',seat,{'target_card_id':pos.ids['nadu']})
            assert pos.state.cards[pos.ids['nadu']].zone==Zone.GRAVEYARD
            pos.cast_name('Reanimate',seat,{'target_card_id':pos.ids['nadu']})
            assert object_incarnation(pos.state.cards[pos.ids['nadu']])!=old
            pos.equip(pos.ids['nadu'])
        elif case=='trigger_replay':
            pos.equip(pos.ids['elf']);pos.state=restored(pos.state)
            pos.equip(pos.ids['elf']);pos.state=restored(pos.state);pos.equip(pos.ids['elf'],False)
        elif case=='real_shock_entry':
            life=pos.state.players[seat].life;pos.shock_pay=False;top=pos.equip(pos.ids['elf'])
            assert pos.state.cards[top].name=='Breeding Pool' and pos.state.cards[top].tapped
            assert pos.state.players[seat].life==life
        pos.mark('case_all_assertions_completed')
    except BaseException as error:
        if hasattr(pos,'state'):pos.save(error)
        raise
    else:pos.save()
