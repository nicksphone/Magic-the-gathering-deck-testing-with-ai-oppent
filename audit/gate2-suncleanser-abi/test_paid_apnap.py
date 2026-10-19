"""Real Company batch, two modal entries and an opposing entry observer."""
import json

import pytest
import inventory as inv
import test_suncleanser_desired as s
from canonical_controls import load_controls

facts = s.facts


@pytest.fixture(scope='module')
def company_facts(facts):
    seed, selected, proof = inv.load_inputs()
    extra, auxiliary = load_controls(['Soul Warden'])
    raw = {**facts, **extra, 'Collected Company': selected[seed['Collected Company']['scryfall_id']]}
    with (s.OUT / (s.PHASE + '-company-facts.json')).open('x') as stream:
        json.dump({'source': proof, 'auxiliary': auxiliary,
                   'full_extra_cards': {name: raw[name] for name in ('Collected Company', 'Soul Warden')}}, stream, sort_keys=True, indent=2)
    return raw


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_simultaneous_modal_apnap_and_resume_exactly_once(company_facts, seat):
    state, target = s.prepare(company_facts, seat, 'creature')
    observer = s.g.add(state, company_facts, 'Soul Warden', 3-seat)
    sources = [s.g.add(state, company_facts, s.SOURCE, seat, s.Zone.LIBRARY) for _ in range(2)]
    company = s.g.add(state, company_facts, 'Collected Company', seat, s.Zone.HAND)
    state.players[seat].mana_pool = {'C': 3, 'G': 1}
    state = s.g.cast(s.g.respond(state, seat), seat, company)
    assert next(item for item in state.stack if item.source_card_id == company).payload['mana_spent'] == 4
    assert sum(state.players[seat].mana_pool.values()) == 0
    for _ in range(2):
        state = s.g.act(state, state.priority_player, 'pass_priority')
    assert state.pending_mechanic_choice['kind'] == 'topdeck_put'
    assert set(sources) <= set(state.pending_mechanic_choice['options'])
    state = s.g.act(s.cold(state), seat, 'choose_mechanic', card_ids=sources)
    assert all(state.cards[cid].zone == s.Zone.BATTLEFIELD for cid in sources)
    assert state.cards[company].zone == s.Zone.GRAVEYARD
    actors = []
    for _ in range(2):
        pending = state.pending_trigger_order
        assert pending and pending.get('phase') != 'targets'
        actor = pending['current_controller']
        actors.append(actor)
        move = s.g.RulesEngine().legal_moves(state, actor)[-1]
        assert move['type'] == 'choose_trigger_order'
        state = s.g.act(s.cold(state), actor, 'choose_trigger_order', trigger_order=move['trigger_order'])
    assert actors == [seat, 3-seat]
    modal_ids = []
    for index in range(2):
        pending = state.pending_mechanic_choice
        assert pending['kind'] == 'entry_mode' and pending['player_id'] == seat
        modal_ids.append(pending['__stack_id'])
        assert s.count(state, 'creature', target) == 1
        moves = s.g.RulesEngine().legal_moves(state, seat)
        choice = s.public_mode_options(moves, seat, 'creature')
        assert len(choice) == 1
        state = s.g.act(s.cold(state), seat, 'choose_mechanic', choice_id=choice[0])
    assert len(set(modal_ids)) == 2
    assert len(state.stack) == 4
    assert [item.controller for item in state.stack] == [seat, seat, 3-seat, 3-seat]
    assert sum(item.source_card_id == observer for item in state.stack) == 2
    for frame_id in modal_ids:
        move = next(move for move in s.g.RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == target)
        assert move['stack_id'] == frame_id
        state = s.g.act(s.cold(state), seat, 'choose_trigger_target', stack_id=frame_id, target_card_id=target)
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    s.drain(state)
    assert state.players[3-seat].life == 22
    assert s.count(state, 'creature', target) == 0
    assert len(state.retained_counter_prohibitions) == 2
    assert {row['source_ref']['card_id'] for row in state.retained_counter_prohibitions} == set(sources)
    s.record('apnap-' + str(seat), state, actual_batch=True, explicit_actors=actors, modal_ids=modal_ids)
