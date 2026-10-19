"""Independent canonical pre/post controls; assert original desired contracts."""
import pytest
import test_suncleanser_desired as s
from rules_engine.stack_engine import resolve_top_of_stack

facts = s.facts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['safekeeper', 'frogify', 'growth-spiral'])
def test_original_desired_upstream_contract(facts, seat, control):
    state = s.g.position(facts, seat)
    target = s.g.add(state, facts, 'Monastery Swiftspear', seat)
    if control == 'safekeeper':
        protector = s.g.add(state, facts, 'Sylvan Safekeeper', seat)
        land = s.g.add(state, facts, 'Forest', seat)
        s.record('upstream-' + control + '-' + str(seat) + '-before', state,
                 offered=s.g.RulesEngine().legal_moves(state, seat))
        state = s.g.act(state, seat, 'activate_ability', card_id=protector, ability_index=0,
                        targets={'target_card_id': target}, payment_choices={'sacrifice_card_ids': [land]})
        s.drain(state)
        assert state.cards[land].zone == s.Zone.GRAVEYARD
    elif control == 'frogify':
        state, aura = s.paid(state, facts, seat, 'Frogify', {'C': 1, 'U': 1}, target_card_id=target)
        s.drain(state)
        assert state.cards[aura].zone == s.Zone.BATTLEFIELD
        assert state.cards[aura].attached_to == target
        s.record('upstream-' + control + '-' + str(seat) + '-after', state,
                 aura=aura, target=target, actual_suppressed=s.printed_abilities_suppressed(state, target))
        assert s.printed_abilities_suppressed(state, target)
    else:
        land = s.g.add(state, facts, 'Forest', seat, s.Zone.HAND)
        source = s.g.add(state, facts, 'Growth Spiral', seat, s.Zone.HAND)
        state.players[seat].mana_pool = {'G': 1, 'U': 1}
        state = s.g.cast(state, seat, source)
        assert next(item for item in state.stack if item.source_card_id == source).payload['mana_spent'] == 2
        while state.stack[-1].source_card_id != source:
            assert resolve_top_of_stack(state)
        returned = resolve_top_of_stack(state)
        s.record('upstream-' + control + '-' + str(seat) + '-after', state,
                 actual_returned=returned, real_optional_land=land)
        assert returned, 'Original paid-helper successful-resolution receipt'
