"""Paid existing-contract lifetimes; no hand-installed effect frames."""
from pathlib import Path
import json

import pytest
import inventory as inv
import test_suncleanser_desired as s
import test_paid_modal as m
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import effective_types

facts = s.facts


@pytest.fixture(scope='module')
def extended(facts):
    seed, selected, proof = inv.load_inputs()
    raw = dict(facts)
    raw['Claim the Firstborn'] = selected[seed['Claim the Firstborn']['scryfall_id']]
    directory = inv.ROOT / 'backend/tests/fixtures/cloudshift_compound_audit'
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split()
        assert inv.sha(directory / Path(filename).name) == digest
    flicker = json.loads((directory / 'flicker-of-fate.json').read_text())
    assert flicker['name'] == 'Flicker of Fate' and flicker['oracle_id']
    raw[flicker['name']] = flicker
    with (s.OUT / (s.PHASE + '-extended-facts.json')).open('x') as stream:
        json.dump({'seed_source': proof, 'auxiliary_fixture_sha256': inv.sha(directory / 'flicker-of-fate.json'),
                   'full_extra_cards': {name: raw[name] for name in ('Claim the Firstborn', 'Flicker of Fate')}}, stream, sort_keys=True, indent=2)
    return raw


def ban(state, mode, target):
    return counter_placement_forbidden(state, '+1/+1' if mode == 'creature' else 'experience',
                                       **({'target_card_id': target} if mode == 'creature' else {'target_player': target}))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['creature', 'player'])
@pytest.mark.parametrize('scenario', ['dress-down', 'source-control', 'source-blink', 'source-entry-receipt'])
def test_actual_paid_lifetime_extensions(extended, seat, mode, scenario):
    if scenario == 'source-entry-receipt':
        state, target = s.prepare(extended, seat, mode)
        state = s.g.respond(state, seat)
        source = s.g.add(state, extended, s.SOURCE, seat, s.Zone.HAND)
        state.players[seat].mana_pool = {'C': 1, 'W': 1}
        state = s.g.cast(state, seat, source)
        spell = next(item for item in state.stack if item.source_card_id == source)
        assert spell.payload['mana_spent'] == 2
        returned = resolve_top_of_stack(state)
        assert returned
        assert state.cards[source].zone == s.Zone.BATTLEFIELD
        assert not any(item.id == spell.id for item in state.stack)
        actual = next(item for item in state.stack if item.id == state.pending_mechanic_choice['__stack_id'])
        assert actual.effect_key == 'modal_entry' and actual.source_card_id == source
        state = m.select(s.cold(state), seat, mode, target)
        s.drain(state)
        assert ban(state, mode, target)
    else:
        state, source, target = m.resolved(extended, seat, mode)
        before = s.object_incarnation(state.cards[source])
        if scenario == 'dress-down':
            state, _ = s.paid(state, extended, seat, 'Dress Down', {'C': 1, 'U': 1})
            s.drain(state)
            assert s.printed_abilities_suppressed(state, source)
            assert ban(s.cold(state), mode, target)
            state = s.placement(state, extended, seat, mode, target)
            assert s.count(state, mode, target) == 0
        elif scenario == 'source-control':
            state = s.advance_main(state, 3-seat)
            state, _ = s.paid(state, extended, 3-seat, 'Claim the Firstborn', {'R': 1}, target_card_id=source)
            s.record('extended-source-control-' + mode + '-' + str(seat) + '-paid-before-drain', state)
            s.drain(state)
            assert state.cards[source].controller == 3-seat and state.cards[source].owner == seat
            assert ban(s.cold(state), mode, target)
            assert state.retained_counter_prohibitions[0]['trigger_controller'] == seat
        else:
            state, _ = s.paid(state, extended, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, target_card_id=source)
            assert state.cards[source].zone == s.Zone.BATTLEFIELD
            assert s.object_incarnation(state.cards[source]) != before
            assert not ban(s.cold(state), mode, target), 'Old duration never reactivates on same-ID blink'
            assert len(state.retained_counter_prohibitions) == 1
            state = m.select(state, seat, 'player' if mode == 'creature' else 'creature',
                             3-seat if mode == 'creature' else source)
            s.drain(state)
            assert not ban(s.cold(state), mode, target)
    s.record('extended-' + scenario + '-' + mode + '-' + str(seat), state,
             paid_source_cause=True, no_manual_frame=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', ['target-blink-after', 'target-blink-before', 'target-control'])
def test_real_target_incarnation_and_control(extended, seat, scenario):
    if scenario == 'target-blink-before':
        state, target = s.prepare(extended, seat, 'creature')
        state, source = m.source_entry(state, extended, seat)
        state = m.select(state, seat, 'creature', target)
    else:
        state, source, target = m.resolved(extended, seat, 'creature')
    before = s.object_incarnation(state.cards[target])
    if scenario == 'target-control':
        state, _ = s.paid(state, extended, seat, 'Claim the Firstborn', {'R': 1}, target_card_id=target)
        assert state.cards[target].controller == seat and state.cards[target].owner == 3-seat
        assert ban(s.cold(state), 'creature', target)
    else:
        state, _ = s.paid(state, extended, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, target_card_id=target)
        assert state.cards[target].controller == state.cards[target].owner == 3-seat
        assert s.object_incarnation(state.cards[target]) != before
        s.drain(state)
        assert not ban(s.cold(state), 'creature', target)
        if scenario == 'target-blink-before':
            assert not state.retained_counter_prohibitions
            assert any('target is illegal' in line for line in state.log)
        state = s.placement(state, extended, seat, 'creature', target)
        assert s.count(state, 'creature', target) > 0
    s.record('extended-' + scenario + '-' + str(seat), state, paid_foreign_owner=True)
