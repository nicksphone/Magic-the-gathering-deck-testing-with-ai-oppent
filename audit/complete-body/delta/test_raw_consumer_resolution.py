"""Independent paid raw-consumer and single-target sequence controls."""
from copy import deepcopy
import pytest
import test_generic_prerequisite_repairs as p
from game_state.state import Zone, object_incarnation
from rules_engine.type_effects import effective_types

e, c = p.e, p.c
basefacts = p.basefacts
existingfacts = p.existingfacts
facts = p.facts
action_receipt = p.action_receipt


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body', ['canonical', 'wrong-count', 'unknown', 'ambiguous'])
def test_paid_raw_energy(facts, seat, body, request):
    derived = deepcopy(facts)
    lines = derived['Dynavolt Tower']['oracle_text'].splitlines()
    if body == 'wrong-count':
        lines[0] = lines[0].replace('two energy counters', 'three energy counters')
    elif body == 'unknown':
        lines[0] = lines[0].replace('two energy counters', 'UNPARSED-SUFFIX')
    elif body == 'ambiguous':
        lines.insert(1, lines[0].replace('two energy counters', 'UNPARSED-SUFFIX'))
    derived['Dynavolt Tower']['oracle_text'] = '\n'.join(lines)
    state = c.g.position(facts, seat)
    tower = e.add(state, derived, 'Dynavolt Tower', seat)
    state, frame = c.paid(state, seat, tower, {'C': 3})
    state = e.frame_done(state, frame)
    bolt = e.add(state, facts, 'Lightning Bolt', seat)
    state, frame = c.paid(state, seat, bolt, {'R': 1}, {'target_player': 3-seat})
    state = e.drain(e.frame_done(c.cold(state), frame))
    p.record(request, state, derived, ['Dynavolt Tower', 'Lightning Bolt'],
             synthetic_probe=body != 'canonical', body=body)
    assert state.players[seat].counters.get('energy', 0) == (2 if body == 'canonical' else 0)
    assert not state.players[3-seat].counters.get('energy', 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body', ['canonical', 'unknown', 'ambiguous'])
def test_paid_raw_enchant(facts, seat, body, request):
    derived = deepcopy(facts)
    lines = derived['Imprisoned in the Moon']['oracle_text'].splitlines()
    if body == 'unknown':
        lines[0] += ' (UNPARSED-SUFFIX)'
    elif body == 'ambiguous':
        lines.insert(1, lines[0] + ' (UNPARSED-SUFFIX)')
    derived['Imprisoned in the Moon']['oracle_text'] = '\n'.join(lines)
    state = c.g.position(facts, seat)
    target = e.add(state, facts, 'Raging Goblin', 3-seat, Zone.BATTLEFIELD)
    moon = e.add(state, derived, 'Imprisoned in the Moon', seat)
    state = c.priority(c.cold(state), seat)
    state.players[seat].mana_pool = {'C': 2, 'U': 1}
    c.offers(state, seat)
    if body != 'canonical':
        e.reject(state, seat, {'type': 'cast_spell', 'card_id': moon,
                 'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': target}})
    else:
        state, frame = c.paid(state, seat, moon, {'C': 2, 'U': 1},
                              {'target_card_id': target})
        state = e.frame_done(c.cold(state), frame)
        assert state.cards[moon].attached_to == target
        assert set(effective_types(state, state.cards[target])) == {'Land'}
    p.record(request, state, derived, ['Imprisoned in the Moon', 'Raging Goblin'],
             synthetic_probe=body != 'canonical', body=body)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('episode', ['legal', 'untap', 'target-departure', 'source-departure'])
def test_paid_sequence_target_legality(facts, seat, episode, request):
    state = c.g.position(facts, seat)
    target = e.add(state, facts, 'Raging Goblin', 3-seat, Zone.BATTLEFIELD)
    state = p.tap_paid(state, facts, seat, target)
    emperor = e.add(state, facts, 'The Wandering Emperor', seat)
    state, frame = c.paid(state, seat, emperor, {'C': 2, 'W': 2})
    state = c.priority(c.cold(e.frame_done(state, frame)), seat)
    c.offers(state, seat)
    state = c.act(state, seat, {'type': 'activate_loyalty', 'card_id': emperor,
                  'ability_index': 2, 'targets': {'target_card_id': target}})
    assert state.cards[emperor].loyalty == 1
    incarnation = object_incarnation(state.cards[target])
    modes = []
    if episode == 'untap':
        charm = e.add(state, facts, 'Emerald Charm', 3-seat)
        state = c.priority(c.cold(state), 3-seat)
        state.players[3-seat].mana_pool = {'G': 1}
        offered = next(m for m in c.offers(state, 3-seat)
                       if m['type'] == 'cast_spell' and m.get('card_id') == charm)
        modes = offered['target_hints']['modes']
        mode = next(m for m in modes if m.casefold().rstrip('.') == 'untap target permanent')
        state, frame = c.paid(state, 3-seat, charm, {'G': 1},
                              {'mode_text': mode, 'target_card_id': target})
        state = e.frame_done(c.cold(state), frame)
        assert not state.cards[target].tapped
        assert object_incarnation(state.cards[target]) == incarnation
    elif episode in {'target-departure', 'source-departure'}:
        bolt = e.add(state, facts, 'Lightning Bolt', 3-seat)
        victim = target if episode == 'target-departure' else emperor
        state, frame = c.paid(state, 3-seat, bolt, {'R': 1}, {'target_card_id': victim})
        state = e.frame_done(c.cold(state), frame)
        assert state.cards[victim].zone == Zone.GRAVEYARD
    state = e.drain(c.cold(state))
    p.record(request, state, facts,
             ['The Wandering Emperor', 'Icy Manipulator', 'Emerald Charm', 'Lightning Bolt'],
             episode=episode, public_modes=modes)
    legal = episode in {'legal', 'source-departure'}
    assert state.players[seat].life == (22 if legal else 20)
    assert state.cards[target].zone == (Zone.EXILE if legal else
           Zone.GRAVEYARD if episode == 'target-departure' else Zone.BATTLEFIELD)
