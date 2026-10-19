"""Canonical Flying combat after an actual paid cast and normal untap."""
import json
import pytest

import test_three_paid_originals as g
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected

@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = g.inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    names = ['Chrome Host Seedshark', 'Torrential Gearhulk', 'Arboreal Grazer']
    for name in names:
        assert raws[name]['oracle_text'] == seed[name]['oracle_text']
    with (g.OUT / ('facts-flying-' + g.PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'cards': {name: raws[name] for name in names}}, stream, indent=2)
    return raws


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_seedshark_flying_blocks_and_actual_damage(facts, seat):
    state = g.position(facts, seat)
    shark = g.add(state, facts, 'Chrome Host Seedshark', seat, Zone.HAND)
    ground = g.add(state, facts, 'Torrential Gearhulk', 3-seat)
    reach = g.add(state, facts, 'Arboreal Grazer', 3-seat)
    state.players[seat].mana_pool = {'C': 2, 'U': 1}
    state = g.cast(state, seat, shark)
    assert sum(state.players[seat].mana_pool.values()) == 0
    g.resolve(state)
    assert state.cards[shark].zone == Zone.BATTLEFIELD
    assert state.cards[shark].summoning_sick
    passes = 0
    while not (state.active_player == seat and state.step == Step.DECLARE_ATTACKERS
               and not state.cards[shark].summoning_sick):
        assert passes < 150
        state = g.act(state, state.priority_player, 'pass_priority')
        passes += 1
    state = g.act(state, seat, 'attack', attackers=[shark])
    assert state.attackers == [shark] and state.cards[shark].tapped
    while state.step != Step.DECLARE_BLOCKERS:
        assert passes < 150
        state = g.act(state, state.priority_player, 'pass_priority')
        passes += 1
    state = g.respond(state, 3-seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, 3-seat, 'block', blocks={shark: [ground]})
    assert serialize_match_snapshot(state) == before
    reached = g.act(g.restore(state), 3-seat, 'block', blocks={shark: [reach]})
    assert reached.blocks[shark] == [reach]
    state = g.act(g.restore(state), 3-seat, 'block', blocks={})
    old_life = state.players[3-seat].life
    while not state.combat_damage_resolved:
        assert passes < 150
        state = g.act(state, state.priority_player, 'pass_priority')
        passes += 1
    assert state.players[3-seat].life == old_life - 2
    g.receipt(f'seedshark-flying-{seat}', facts,
              ['Chrome Host Seedshark', 'Torrential Gearhulk', 'Arboreal Grazer'], state,
              paid_C=2, paid_U=1, normal_passes=passes, unblocked_damage=2,
              ground_block_rejected=True, reach_block_accepted=True)
