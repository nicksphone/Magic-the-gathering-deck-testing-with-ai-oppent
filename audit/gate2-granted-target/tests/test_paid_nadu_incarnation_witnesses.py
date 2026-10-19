"""Additive genuine paid early-resource witnesses; original24 failures stay untouched."""
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
import nadu_support as support
from game_state.state import Zone, object_incarnation

WITNESSES = json.loads((Path(__file__).resolve().parents[1] / 'incarnation-witnesses.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['recipient_reentry', 'grant_reentry_other_recipient'])
def test_actual_paid_resource_qualified_incarnation(case, seat):
    witnesses = deepcopy(support.WITNESSES)
    witnesses['witnesses'][f'{seat}-land'] = WITNESSES['witnesses'][str(seat)]
    pos = support.Position.__new__(support.Position)
    with patch.object(support, 'WITNESSES', witnesses):
        try:
            pos.__init__(seat, 'additive_'+case, 'land')
            # Explicit choice policy for actual shock-entry menus; never a fabricated pending.
            pos.shock_pay = False
            target = pos.ids['nadu'] if case == 'recipient_reentry' else pos.ids['elf']
            pos.equip(target); pos.equip(target); pos.equip(target, False)
            old = object_incarnation(pos.state.cards[pos.ids['nadu']])
            for _ in range(8):
                hand = [pos.state.cards[c].name for c in pos.state.players[seat].hand]
                lands = [pos.state.cards[c].name for c in pos.state.players[seat].battlefield]
                if hand.count('Lightning Bolt') >= 2 and 'Reanimate' in hand and lands.count('Mountain') >= 2 and 'Swamp' in lands:
                    break
                pos.next_own_main()
                lands = [pos.state.cards[c].name for c in pos.state.players[seat].battlefield]
                choices = ['Mountain', 'Swamp'] if lands.count('Mountain') < 2 else ['Swamp', 'Mountain']
                for name in choices:
                    if name in [pos.state.cards[c].name for c in pos.state.players[seat].hand]:
                        pos.act(seat, {'type': 'play_land', 'card_id': pos.find_hand(name, seat)})
                        break
            else:
                raise AssertionError('declared bounded early-resource witness did not materialize')
            # Resource proof BEFORE death, not a StopIteration hidden as an engine defect.
            for name in ['Lightning Bolt', 'Reanimate']:
                assert name in [pos.state.cards[c].name for c in pos.state.players[seat].hand]
            pos.cast_name('Lightning Bolt', seat, {'target_card_id': pos.ids['nadu']})
            pos.cast_name('Lightning Bolt', seat, {'target_card_id': pos.ids['nadu']})
            assert pos.state.cards[pos.ids['nadu']].zone == Zone.GRAVEYARD
            pos.cast_name('Reanimate', seat, {'target_card_id': pos.ids['nadu']})
            assert object_incarnation(pos.state.cards[pos.ids['nadu']]) != old
            pos.equip(target); pos.equip(target); pos.equip(target, False)
            pos.mark('real_paid_reentry_and_new_per_instance_quota_qualified')
        except BaseException as error:
            if hasattr(pos, 'state'): pos.save(error)
            raise
        else:
            pos.save()
