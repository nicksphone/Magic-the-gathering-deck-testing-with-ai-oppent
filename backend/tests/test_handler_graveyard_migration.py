"""Lawful canonical handler seams; keyword and combat routes are not migrated."""
from copy import deepcopy

import pytest

from effects import handlers
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_direct_graveyard_bypass_audit import ROWS, board, cast
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, act, restart, snap


@pytest.fixture
def trace(monkeypatch):
    from rules_engine import events
    original = events._collect_triggers
    rows = []

    def record(state, event, payload):
        rows.append((event, deepcopy(payload)))
        return original(state, event, payload)

    monkeypatch.setattr(events, '_collect_triggers', record)
    return rows


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('spell', ['Lightning Bolt', 'Murder'])
def test_actual_paid_damage_or_targeted_destruction_commits_once(seat, foreign, spell, trace, tmp_path):
    state, victim, _ = board(seat, 'Doomed Traveler', foreign)
    sequence = victim.zone_change_sequence
    _, action = cast(state, seat, spell, victim)
    result = act(state, seat, action)
    assert resolve_top_of_stack(result)
    result = restart(result, tmp_path, 'ordinary-death')
    assert result.cards[victim.id].zone == Zone.GRAVEYARD
    assert result.cards[victim.id].zone_change_sequence == sequence + 1
    assert result.players[victim.owner].graveyard.count(victim.id) == 1
    for event in ['leaves_battlefield', 'enters_graveyard', 'permanent_dies', 'creature_dies']:
        assert len([p for e, p in trace if e == event and p.get('card_id') == victim.id]) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('name', ['Darksteel Colossus', 'Progenitus'])
def test_trusted_controller_sacrifice_routes_static_replacement(seat, foreign, name, trace, tmp_path):
    state, victim, _ = board(seat, name, foreign)
    owner = victim.owner
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-owner, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(victim), 'zone_change_sequence': victim.zone_change_sequence}
    # A deliberate trusted sacrifice effect, not destruction or a claimed paid spell.
    handlers.sacrifice(state, seat, {'target_card_id': victim.id})
    state = restart(state, tmp_path, 'handler-sacrifice')
    assert state.cards[victim.id].zone == Zone.LIBRARY
    assert state.players[owner].library.count(victim.id) == 1
    assert state.cards[victim.id].zone_change_sequence == reference['zone_change_sequence'] + 1
    receipts = [item for item in state.stack if item.source_card_id == probe.id]
    assert len(receipts) == 1
    cause = receipts[0].payload['__shuffle_cause']
    assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
    assert cause['source_card_id'] == victim.id and cause['source_reference'] == reference
    assert cause['source_owner'] == owner and cause['controller'] == seat and 'stack_id' not in cause
    assert cause['ability_clause'] == ROWS[name]['oracle_text'].splitlines()[cause['ability_index']]
    assert len([p for e, p in trace if e == 'sacrifice' and p.get('card_id') == victim.id]) == 1
    assert not any(e in {'enters_graveyard', 'permanent_dies', 'creature_dies'}
                   and p.get('card_id') == victim.id for e, p in trace)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Darksteel Colossus', 'Progenitus'])
@pytest.mark.parametrize('rival', [None, 'Rest in Peace', 'Leyline of the Void'])
def test_humility_sacrifice_uses_only_active_replacements(seat, name, rival, trace, tmp_path):
    state, victim, _ = board(seat, name)
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    if rival:
        raw_card(state, ROWS[rival], 3-seat, Zone.BATTLEFIELD)
    handlers.sacrifice(state, seat, {'target_card_id': victim.id})
    state = restart(state, tmp_path, 'suppressed-sacrifice')
    expected = Zone.EXILE if rival else Zone.GRAVEYARD
    assert state.cards[victim.id].zone == expected
    assert victim.id in getattr(state.players[victim.owner], expected.value)
    entries = [p for e, p in trace if e == 'enters_graveyard' and p.get('card_id') == victim.id]
    assert len(entries) == int(expected == Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_actual_untargeted_wrath_prepares_all_static_sources_before_departure(seat, foreign, monkeypatch, tmp_path):
    from rules_engine import shuffle_actions
    state, first, _ = board(seat, 'Progenitus', foreign)
    second = raw_card(state, ROWS['Progenitus'], 3-seat, Zone.BATTLEFIELD)
    probe = raw_card(state, ROWS['Psychogenic Probe'], seat, Zone.BATTLEFIELD)
    references = {c.id: {'incarnation': object_incarnation(c), 'zone_change_sequence': c.zone_change_sequence}
                  for c in [first, second]}
    original = shuffle_actions.prepare_static_replacement_cause
    prepared = []

    def observe(current, plan):
        assert all(current.cards[cid].zone == Zone.BATTLEFIELD for cid in references)
        prepared.append(plan.card_id)
        return original(current, plan)

    monkeypatch.setattr(shuffle_actions, 'prepare_static_replacement_cause', observe)
    _, action = cast(state, seat, 'Wrath of God')
    result = act(state, seat, action)
    assert resolve_top_of_stack(result)
    result = restart(result, tmp_path, 'two-replacement-wrath')
    assert set(prepared) == set(references) and len(prepared) == 2
    receipts = [item for item in result.stack if item.source_card_id == probe.id]
    assert len(receipts) == 2
    for receipt in receipts:
        cause = receipt.payload['__shuffle_cause']
        assert cause['source_reference'] == references[cause['source_card_id']]
        assert cause['kind'] == 'static' and 'stack_id' not in cause
    for card in [first, second]:
        assert result.cards[card.id].zone == Zone.LIBRARY
        assert result.players[card.owner].library.count(card.id) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('rival', ['Rest in Peace', 'Leyline of the Void'])
def test_competing_batch_plan_rejects_before_shield_log_lbf_or_any_move(seat, rival, trace):
    state, ordinary, _ = board(seat, 'Doomed Traveler')
    ordinary.counters['shield'] = 1  # Controlled counter fixture, not a claimed cast.
    raw_card(state, ROWS['Progenitus'], seat, Zone.BATTLEFIELD)
    raw_card(state, ROWS[rival], 3-seat, Zone.BATTLEFIELD)
    trace.clear()
    before = snap(state)
    with pytest.raises(ActionRejected, match='competing graveyard replacement'):
        handlers.destroy_all_creatures(state, seat, {})
    assert snap(state) == before and not trace


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_unstaged_lethal_damage_helper_commits_actual_transition(seat, foreign, trace, tmp_path):
    state, victim, _ = board(seat, 'Doomed Traveler', foreign)
    source = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.HAND)
    state.players[seat].hand.remove(source.id)
    source.move_to_zone(Zone.STACK)
    sequence = victim.zone_change_sequence
    # Trusted complete damage instruction with the genuine canonical source.
    # This is NOT a paid stack-resolution episode or an SBA migration claim.
    assert handlers.deal_damage(state, seat, {'target_card_id': victim.id,
                'amount': 3, '__source_card_id': source.id}) == 3
    state = restart(state, tmp_path, 'unstaged-lethal-helper')
    assert state.cards[victim.id].zone == Zone.GRAVEYARD
    assert state.cards[victim.id].zone_change_sequence == sequence + 1
    assert state.players[victim.owner].graveyard.count(victim.id) == 1
    assert len([p for e, p in trace if e == 'enters_graveyard' and p.get('card_id') == victim.id]) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_typed_artifact_batch_preserves_shield_and_noncreature_death(seat, trace, tmp_path):
    state, _, _ = board(seat, 'Doomed Traveler')
    shielded = raw_card(state, BASE['Millstone'], seat, Zone.BATTLEFIELD)
    shielded.counters['shield'] = 1
    ordinary = raw_card(state, BASE['Millstone'], 3-seat, Zone.BATTLEFIELD)
    sequence = ordinary.zone_change_sequence
    handlers._destroy_all_permanents_of_types(state, {'Artifact'}, 'All artifacts are destroyed.')
    state = restart(state, tmp_path, 'artifact-destruction')
    assert state.cards[shielded.id].zone == Zone.BATTLEFIELD and not state.cards[shielded.id].counters.get('shield')
    assert state.cards[ordinary.id].zone == Zone.GRAVEYARD
    assert state.cards[ordinary.id].zone_change_sequence == sequence + 1
    assert not any(e == 'creature_dies' and p.get('card_id') == ordinary.id for e, p in trace)


@pytest.mark.parametrize('seat', [1, 2])
def test_indestructible_with_competing_plan_does_not_require_death_choice(seat):
    state, victim, _ = board(seat, 'Darksteel Colossus')
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    sequence = victim.zone_change_sequence
    handlers.destroy_all_creatures(state, seat, {})
    assert victim.zone == Zone.BATTLEFIELD and victim.zone_change_sequence == sequence
