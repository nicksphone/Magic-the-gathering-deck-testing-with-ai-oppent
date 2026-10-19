"""Canonical paid batch and explicit controlled SBA commit boundary controls."""
import pytest

from game_state.state import Zone, object_incarnation
from rules_engine import state_based_actions as sba
from rules_engine.action_validation import ActionRejected
from rules_engine.query_context import query_cache
from rules_engine.zone_actions import put_into_graveyard
from tests.test_sba_graveyard_entry_audit import (
    LAYERS, ROWS, act, bolt_position, observed, passes, position, raw_card, restart, snap, target_events,
)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_sickening_dreams_simultaneous_deaths(seat, tmp_path, observed, monkeypatch):
    state = position(seat)
    victims = [raw_card(state, ROWS['Doomed Traveler'], pid, Zone.BATTLEFIELD)
               for pid in (seat, 3-seat)]
    artist = raw_card(state, ROWS['Blood Artist'], seat, Zone.BATTLEFIELD)
    spell = raw_card(state, ROWS['Sickening Dreams'], seat, Zone.HAND)
    discarded = state.players[seat].hand[0]
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    references = {card.id: card.zone_change_sequence for card in [*victims, artist]}
    calls = []
    for name in ('prepare_graveyard_entry_causes', 'execute_graveyard_entry', 'emit_event_batch'):
        original = getattr(sba, name)

        def outside(current, *args, _name=name, _original=original, **kwargs):
            assert query_cache(current) is None
            if _name == 'execute_graveyard_entry':
                assert all(cid not in player.battlefield for cid in references
                           for player in current.players.values())
                assert all(current.cards[cid].last_known_battlefield for cid in references)
            calls.append(_name)
            return _original(current, *args, **kwargs)

        monkeypatch.setattr(sba, name, outside)
    state = act(state, seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'x_value': 1},
        'cost_choice': {'id': 'base', 'discard_card_ids': [discarded]},
    })
    assert state.cards[discarded].zone == Zone.GRAVEYARD
    state = passes(state)
    assert 'prepare_graveyard_entry_causes' in calls
    assert calls.index('prepare_graveyard_entry_causes') < calls.index('emit_event_batch')
    for card in [*victims, artist]:
        assert state.cards[card.id].zone == Zone.GRAVEYARD
        assert state.cards[card.id].zone_change_sequence == references[card.id] + 1
        records = target_events(observed, state, card.id)
        assert [row['event'] for row in records] == [
            'leaves_battlefield', 'enters_graveyard', 'permanent_dies', 'creature_dies']
        assert records[0]['source_lki'] == records[-1]['source_lki']
    trace, states = observed
    index = next(i for i, current in enumerate(states) if current is state)
    events = [row['event'] for row in trace if row['state_index'] == index
              and row['payload'].get('card_id') in references]
    assert events[:3] == ['leaves_battlefield'] * 3
    assert events[3:6] == ['enters_graveyard'] * 3
    assert events[6:9] == ['permanent_dies'] * 3
    assert events[9:] == ['creature_dies'] * 3
    for card in victims:
        assert len([item for item in state.stack if item.source_card_id == card.id]) == 1
    assert len([item for item in state.stack if item.source_card_id == artist.id]) == 3
    restart(state, tmp_path, 'paid-simultaneous-sba')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_bolt_checked_single_replacement_resume(seat, tmp_path, observed):
    state, cid, _, _, action = bolt_position(seat)
    sources = [raw_card(state, LAYERS[name], seat, Zone.BATTLEFIELD).id
               for name in ('Rest in Peace', 'Leyline of the Void')]
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    state = act(state, seat, action)
    state = passes(state)
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'state_based_die' and pending['target_card_id'] == cid
    assert {row['source_id'] for row in pending['options']} == set(sources)
    state = restart(state, tmp_path, 'paid-bolt-before-checked-single-resume')
    before = snap(state)
    choice = {'type': 'choose_replacement', 'replacement_source_id': sources[0]}
    with pytest.raises(ActionRejected):
        act(state, seat, choice)
    assert snap(state) == before
    state = act(state, 3-seat, choice)
    assert state.cards[cid].zone == Zone.EXILE
    assert state.pending_replacement_choice is None
    assert [row['event'] for row in target_events(observed, state, cid)] == ['leaves_battlefield']
    restart(state, tmp_path, 'paid-bolt-after-checked-single-resume')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('path', ['single', 'batch', 'legend'])
def test_controlled_competing_plan_rejects_before_any_departure(seat, path, observed):
    # Controlled source retained on the battlefield; no claimed played control change.
    state = position(seat)
    first = raw_card(state, ROWS['Doomed Traveler'], seat, Zone.BATTLEFIELD)
    target = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    raw_card(state, LAYERS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    before = snap(state)
    event_count = len(observed[0])
    with pytest.raises(ActionRejected):
        if path == 'single':
            sba._move_lethal_creature(state, target.id, '')
        elif path == 'batch':
            sba._resolve_lethal_creature_batch(state, [first.id, target.id])
        else:
            sba.resume_legend_rule_replacement(state, seat, target.id, '')
    assert snap(state) == before
    assert len(observed[0]) == event_count


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('path', ['single', 'batch'])
def test_controlled_indestructible_zero_toughness_retains_static_cause(seat, path, tmp_path, observed):
    state = position(seat)
    target = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    probe = raw_card(state, LAYERS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    target.counters['-1/-1'] = 11  # Controlled counters, not a claimed counter-placement episode.
    assert sba.creature_has_lethal_state(state, target.id)
    assert sba.has_keyword(state, target.id, 'indestructible')
    reference = {'incarnation': object_incarnation(target), 'zone_change_sequence': target.zone_change_sequence}
    if path == 'single':
        sba._move_lethal_creature(state, target.id, '')
    else:
        sba._resolve_lethal_creature_batch(state, [target.id])
    assert target.zone == Zone.LIBRARY and target.zone_change_sequence == reference['zone_change_sequence'] + 1
    assert state.players[seat].library.count(target.id) == 1
    assert [row['event'] for row in target_events(observed, state, target.id)] == ['leaves_battlefield']
    causes = [row['payload']['cause'] for row in observed[0] if row['event'] == 'shuffle']
    assert len(causes) == 1
    assert causes[0]['source_reference'] == reference
    assert causes[0]['kind'] == 'static' and causes[0]['mechanism'] == 'replacement'
    assert causes[0]['source_card_id'] == target.id
    assert len([item for item in state.stack if item.source_card_id == probe.id]) == 1
    restart(state, tmp_path, 'sba-zero-toughness-static')


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_humility_departure_rebuilds_plan_and_classification(seat, tmp_path, observed):
    state = position(seat)
    humility = raw_card(state, LAYERS['Humility'], 3-seat, Zone.BATTLEFIELD)
    first = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    second = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    first.counters['__damage_marked'] = 1
    second.counters['-1/-1'] = 11
    assert sba.creature_has_lethal_state(state, first.id)
    sba._move_lethal_creature(state, first.id)
    assert first.zone == Zone.GRAVEYARD
    assert not any(row['event'] == 'shuffle' for row in observed[0])
    # Explicit controlled static-source departure between waves, not a cast-removal episode.
    put_into_graveyard(state, humility.id)
    assert query_cache(state) is None
    assert sba.has_keyword(state, second.id, 'indestructible')
    assert sba.creature_has_lethal_state(state, second.id)
    sba._move_lethal_creature(state, second.id)
    assert second.zone == Zone.LIBRARY
    assert len([row for row in observed[0] if row['event'] == 'shuffle']) == 1
    restart(state, tmp_path, 'source-departure-new-wave')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', ['printed', 'exile'])
def test_controlled_single_explicit_replacement_source_remains_exact(seat, selected, observed):
    state = position(seat)
    target = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    rival = raw_card(state, LAYERS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    chosen = target.id if selected == 'printed' else rival.id
    before = snap(state)
    with pytest.raises(ActionRejected):
        sba._move_lethal_creature(state, target.id, 'not-an-offered-source')
    assert snap(state) == before
    sba._move_lethal_creature(state, target.id, chosen)
    assert target.zone == (Zone.LIBRARY if selected == 'printed' else Zone.EXILE)
    assert [row['event'] for row in target_events(observed, state, target.id)] == ['leaves_battlefield']
