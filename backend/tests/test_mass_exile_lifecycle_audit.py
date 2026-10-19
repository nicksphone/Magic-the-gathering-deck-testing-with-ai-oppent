"""Full canonical paid mass exile; controlled starting boards, not fabricated events."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from effects import handlers

FIXTURE = Path(__file__).parent / 'fixtures/mass_exile_audit'
ROWS = {json.loads(p.read_text())['name']: json.loads(p.read_text())
        for p in FIXTURE.glob('*.json') if p.name != 'provenance.json'}
SPELLS = ['Final Judgment', 'Sunfall']


def add(state, name, seat, zone):
    raw = ROWS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 8}], [], seed=831)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card.id


def act(state, seat, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before
    return result


def resolve(state):
    assert state.stack
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def restore(state):
    result = deserialize_match_snapshot(snap(state))
    assert snap(result) == snap(state)
    return result


def fund(state, seat, amount, color='W'):
    name = 'Plains' if color == 'W' else 'Island'
    candidates = [cid for cid in state.players[seat].battlefield
                  if state.cards[cid].name == name and not state.cards[cid].tapped]
    assert len(candidates) >= amount
    for cid in candidates[:amount]:
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': cid, 'color': color})
    return state


def cast(state, seat, cid, amount, targets=None, color='W'):
    state = fund(state, seat, amount, color)
    request = {'type': 'cast_spell', 'card_id': cid, 'cost_choice': {'id': 'base'}}
    if targets is not None:
        request['targets'] = targets
    state = act(state, seat, request)
    assert state.stack[-1].payload['mana_spent'] == amount
    return state


def board(seat, spell, foreign=False, static=None):
    raw = ROWS['Island']
    deck = [{**raw, 'card_name': 'Island', 'quantity': 30}]
    state = MatchFactory.from_decks(deck, deck, seed=4317)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    for pid in (1, 2):
        for cid in list(state.players[pid].hand):
            state.players[pid].hand.remove(cid)
            state.players[pid].library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
    for _ in range(14):
        add(state, 'Plains', seat, Zone.BATTLEFIELD)
    for _ in range(4):
        add(state, 'Island', seat, Zone.BATTLEFIELD)
    cid = add(state, spell, seat, Zone.HAND)
    target = add(state, 'Darksteel Colossus', 3-seat, Zone.BATTLEFIELD)
    elf = add(state, 'Llanowar Elves', seat, Zone.BATTLEFIELD)
    artist = add(state, 'Blood Artist', 3-seat, Zone.BATTLEFIELD)
    if foreign:
        # Explicit controlled starting board: opponent owns a creature controlled by actor.
        state.players[3-seat].battlefield.remove(target)
        state.players[seat].battlefield.append(target)
        state.cards[target].controller = seat
    if static:
        add(state, static, seat, Zone.BATTLEFIELD)
    return state, cid, [target, elf, artist]


@pytest.mark.parametrize('name', list(ROWS))
def test_official_full_raw_receipt(name):
    entries = json.loads((FIXTURE / 'provenance.json').read_text())['raw_rows']
    entry = next(e for e in entries.values() if e['name'] == name)
    path = next(FIXTURE / f for f, e in entries.items() if e['name'] == name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    assert entry['complete_oracle'] == ROWS[name]['oracle_text']
    assert not entry['oracle_modified'] and not entry['raw_response_modified']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_exile_changes_object_sequence_owner_inventory_and_restart(seat, spell, foreign):
    state, cid, creatures = board(seat, spell, foreign)
    before = {x: state.cards[x].zone_change_sequence for x in creatures}
    state = resolve(restore(cast(state, seat, cid, 6 if spell == 'Final Judgment' else 5)))
    state = restore(state)
    for x in creatures:
        card = state.cards[x]
        assert card.zone == Zone.EXILE and x in state.players[card.owner].exile
        assert all(x not in p.battlefield for p in state.players.values())
        assert card.zone_change_sequence == before[x] + 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
@pytest.mark.parametrize('static', ['Glorious Anthem', 'Humility'])
def test_actual_lki_preserves_static_predeparture_state_without_false_dies(seat, spell, static):
    state, cid, creatures = board(seat, spell, static=static)
    lives = {p: state.players[p].life for p in (1, 2)}
    state = resolve(cast(state, seat, cid, 6 if spell == 'Final Judgment' else 5))
    assert not state.stack
    assert {p: state.players[p].life for p in (1, 2)} == lives
    elf = state.cards[creatures[1]]
    assert elf.last_known_battlefield['controller'] == seat
    assert elf.last_known_battlefield['power'] == (2 if static == 'Glorious Anthem' else 1)
    assert elf.last_known_battlefield['printed_abilities_suppressed'] == (static == 'Humility')
    assert any(state.cards[x].name == static for x in state.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
def test_paid_tokens_and_complete_sunfall_incubation(seat, spell):
    state, cid, creatures = board(seat, spell)
    alarm = add(state, 'Raise the Alarm', seat, Zone.HAND)
    state = resolve(cast(state, seat, alarm, 2))
    tokens = [x for x in state.players[seat].battlefield if state.cards[x].name == 'Soldier']
    assert len(tokens) == 2
    state = resolve(cast(state, seat, cid, 6 if spell == 'Final Judgment' else 5))
    assert all(state.cards[x].zone != Zone.BATTLEFIELD for x in tokens)
    incubators = [state.cards[x] for x in state.players[seat].battlefield
                  if state.cards[x].name == 'Incubator']
    assert len(incubators) == int(spell == 'Sunfall')
    if incubators:
        assert incubators[0].counters['+1/+1'] == len(creatures) + len(tokens)
        assert incubators[0].owner == incubators[0].controller == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
def test_real_ray_departure_consumes_delayed_record_and_preserves_pre_event(seat, spell, monkeypatch, tmp_path):
    state, cid, creatures = board(seat, spell)
    ray = add(state, 'Ray of Command', seat, Zone.HAND)
    state = resolve(cast(state, seat, ray, 4, {'target_card_id': creatures[0]}, 'U'))
    assert state.cards[creatures[0]].controller == seat
    assert len(state.delayed_triggers) == 1
    pre = deepcopy(state.delayed_triggers[0])
    trace = []
    original = handlers.emit_event_batch
    def observe(current, event, payloads):
        if event == 'leaves_battlefield':
            trace.append({'payloads': deepcopy(payloads), 'states': {
                x['card_id']: {'zone': current.cards[x['card_id']].zone.value,
                              'sequence': current.cards[x['card_id']].zone_change_sequence,
                              'lki': deepcopy(current.cards[x['card_id']].last_known_battlefield)}
                for x in payloads}})
        return original(current, event, payloads)
    monkeypatch.setattr(handlers, 'emit_event_batch', observe)
    state = resolve(restore(cast(state, seat, cid, 6 if spell == 'Final Judgment' else 5)))
    (tmp_path / 'actual-leave-publication.json').write_text(json.dumps({
        'trace': trace, 'retained_pre_record': pre,
        'remaining_delayed': state.delayed_triggers}, default=str, indent=2))
    assert trace and creatures[0] in trace[0]['states']
    assert trace[0]['states'][creatures[0]]['lki']['controller'] == seat
    assert trace[0]['states'][creatures[0]]['lki']['battlefield_incarnation'] == pre['payload']['incarnation']
    # Late event collection must still recognize the genuine departed controlled object.
    assert not state.delayed_triggers


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
def test_wrong_actor_rejected_without_root_payment_or_rng_change(seat, spell):
    state, cid, _ = board(seat, spell)
    state = fund(state, seat, 6 if spell == 'Final Judgment' else 5)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'cast_spell', 'card_id': cid})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', SPELLS)
def test_paid_exile_public_identity_does_not_reveal_unseen_hand_or_library(seat, spell):
    from ai.information import decision_view, is_unknown
    state, cid, creatures = board(seat, spell)
    hidden = add(state, 'Ray of Command', 3-seat, Zone.HAND)
    state = resolve(cast(state, seat, cid, 6 if spell == 'Final Judgment' else 5))
    before = snap(state)
    view, _ = decision_view(state, seat, [])
    assert is_unknown(view.cards[hidden])
    assert all(is_unknown(view.cards[x]) for player in state.players.values() for x in player.library)
    assert all(view.cards[x].name == state.cards[x].name for x in creatures)
    assert snap(state) == before
