"""Strict canonical shuffle goldens, not accepted missing-trigger behavior."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.readiness_rules_seam_support import normalize
from tests.spell_admission_safety_support import seed_cache
from tests.test_spell_admission_safety_http import sql_facts


FIXTURE = Path(__file__).parent / 'fixtures/shuffle_observer_audit/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
assert len(ROWS) == 4 and all(row['object'] == 'card' and row['oracle_id'] for row in ROWS.values())
OBSERVERS = ['Psychogenic Probe', "Cosi's Trickster"]


def snap(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def restore(state):
    before = snap(state)
    result = deserialize_match_snapshot(before)
    assert snap(result) == before
    return result


def act(state, actor, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), actor, action)
    repeat = checked_action(deserialize_match_snapshot(before), RulesEngine(), actor, action)
    assert snap(state) == before and snap(result) == snap(repeat)
    return result


def record(tmp_path, label, state):
    (tmp_path / (label + '.json')).write_text(json.dumps(snap(state), sort_keys=True))


def prepare(name, seat, observer, size=8, observer_seat=None):
    state, spell = setup(name, seat, size)
    # Canonical retained board setup; subsequent spell/payment/choices are actual actions.
    card = raw_card(state, ROWS[observer], observer_seat or 3-seat, Zone.BATTLEFIELD)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    assert card.oracle_text == ROWS[observer]['oracle_text']
    return state, spell.id, card.id


def order_prompt(state, seat, spell_id):
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell_id})
    assert state.players[seat].mana_pool.get('U', 0) == 0
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return restore(state)


def finish(state, seat, selection='keep'):
    pending = state.pending_mechanic_choice
    if pending['kind'] != 'library_shuffle':
        state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(pending['options']))})
    if state.pending_mechanic_choice:
        state = act(restore(state), seat, {'type': 'choose_mechanic', 'card_ids': [selection]})
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('observer', OBSERVERS)
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_real_index_and_declined_ponder_do_not_shuffle_or_grant_observer_reward(seat, observer, name):
    state, spell, cid = prepare(name, seat, observer)
    life = state.players[seat].life
    counters = deepcopy(state.cards[cid].counters)
    state = order_prompt(state, seat, spell)
    rng = deepcopy(state.rng.getstate())
    state = finish(state, seat)
    assert state.rng.getstate() == rng
    assert not state.stack and not state.pending_trigger_order
    assert state.players[seat].life == life and state.cards[cid].counters == counters
    assert not any('shuffles their library' in line for line in state.log)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert len(state.players[seat].hand) == int(name == 'Ponder')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('observer', OBSERVERS)
@pytest.mark.parametrize('size', [1, 8])
def test_actual_accepted_ponder_shuffle_requires_observer_receipt_after_draw(seat, observer, size, tmp_path):
    state, spell, cid = prepare('Ponder', seat, observer, size)
    state = order_prompt(state, seat, spell)
    record(tmp_path, 'order-pending', state)
    if state.pending_mechanic_choice['kind'] != 'library_shuffle':
        state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(state.pending_mechanic_choice['options']))})
    record(tmp_path, 'shuffle-pending', state)
    library = list(state.players[seat].library)
    rng = deepcopy(state.rng)
    rng.shuffle(library)
    expected_draw = library.pop()
    life = state.players[seat].life
    counters = deepcopy(state.cards[cid].counters)
    state = finish(restore(state), seat, 'shuffle')
    record(tmp_path, 'after-actual-shuffle-and-draw', state)
    assert state.players[seat].library == library and state.players[seat].hand == [expected_draw]
    assert state.rng.getstate() == rng.getstate()
    assert state.cards[spell].zone == Zone.GRAVEYARD and state.pending_mechanic_choice is None
    assert sum('shuffles their library' in line for line in state.log) == 1
    assert state.players[seat].life == life and state.cards[cid].counters == counters
    assert restore(state).rng.getstate() == rng.getstate()
    receipts = [item for item in state.stack if item.source_card_id == cid]
    assert len(receipts) == 1, 'Actual shuffle/draw completed but canonical observer has no receipt'
    assert receipts[0].controller == 3-seat and receipts[0].effect_key != 'noop'
    if observer == "Cosi's Trickster":
        assert receipts[0].payload.get('__may'), 'Optional counter must not be automatically granted'


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_own_shuffle_is_not_opponent_shuffle_for_cosi(seat):
    state, spell, cid = prepare('Ponder', seat, "Cosi's Trickster", observer_seat=seat)
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    assert not state.stack and not state.cards[cid].counters


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_probe_also_triggers_on_controller_own_shuffle_then_deals_two(seat, tmp_path):
    state, spell, cid = prepare('Ponder', seat, 'Psychogenic Probe', observer_seat=seat)
    life = state.players[seat].life
    state = finish(order_prompt(state, seat, spell), seat, 'shuffle')
    record(tmp_path, 'after-controller-actual-shuffle-and-draw', state)
    assert state.cards[spell].zone == Zone.GRAVEYARD and len(state.players[seat].hand) == 1
    assert state.players[seat].life == life
    receipts = [item for item in state.stack if item.source_card_id == cid]
    assert len(receipts) == 1, 'Probe observes its controller too, not only opponents'
    assert receipts[0].controller == seat and not receipts[0].payload.get('__may')
    state = restore(state)
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.players[seat].life == life-2 and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_private_inspection_hidden_metadata_invariance_and_wrong_seat_atomic_rejection(seat):
    state, spell, _ = prepare('Ponder', seat, 'Psychogenic Probe')
    state = order_prompt(state, seat, spell)
    before = snap(state)
    moves = RulesEngine().legal_moves(state, seat)
    view, hints = decision_view(state, seat, moves)
    inspected = set(state.pending_mechanic_choice['options'])
    assert all(not is_unknown(view.cards[cid]) for cid in inspected)
    foreign_view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(foreign_view.cards[cid]) for cid in inspected)
    changed = deepcopy(state)
    for cid in changed.players[3-seat].hand + changed.players[3-seat].library:
        # Explicit privacy perturbation, not a gameplay/card/Oracle alteration episode.
        changed.cards[cid].name = 'private metadata probe'
        changed.cards[cid].oracle_text = 'private metadata probe'
    repeated, repeated_hints = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert snap(view) == snap(repeated) and hints == repeated_hints
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'choose_mechanic', 'card_ids': list(inspected)})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_actual_village_rites_sacrifice_requires_self_shuffle_replacement_not_death(seat, foreign_owner, tmp_path):
    state, _, probe = prepare('Index', seat, 'Psychogenic Probe')
    colossus = raw_card(state, ROWS['Darksteel Colossus'], seat, Zone.BATTLEFIELD)
    if foreign_owner:
        colossus.owner = 3-seat  # Controlled valid owner/controller retained position.
    owner = colossus.owner
    spell = raw_card(state, ROWS['Village Rites'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'B': 1}
    library = list(state.players[owner].library)
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'sacrifice_card_ids': [colossus.id]}}
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {**action, 'cost_choice': {'id': 'base', 'sacrifice_card_ids': [probe]}})
    assert snap(state) == before
    record(tmp_path, 'before-actual-sacrifice-payment', state)
    state = act(state, seat, action)
    record(tmp_path, 'after-actual-sacrifice-payment', state)
    assert state.players[seat].mana_pool.get('B', 0) == 0
    assert spell.id in [item.source_card_id for item in state.stack]
    assert colossus.id not in state.players[seat].battlefield
    assert restore(state).cards[colossus.id].zone == state.cards[colossus.id].zone
    assert state.cards[colossus.id].zone == Zone.LIBRARY, 'Replacement should shuffle sacrificed Colossus into owner library'
    assert sorted(state.players[owner].library) == sorted(library + [colossus.id])
    assert colossus.id not in state.players[owner].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('flow', [('Index', 'keep'), ('Ponder', 'keep'), ('Ponder', 'shuffle')])
def test_actual_http_shuffle_or_negative_control_private_restart_and_root_sql_purity(repo, client, seat, flow, tmp_path):
    import main
    name, selection = flow
    seed_cache(repo)
    from tests.test_library_reorder import FIXTURES
    repo.upsert_card(normalize(json.loads((FIXTURES / (name.lower()+'.json')).read_text())))
    deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': name, 'quantity': 1}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck, 'sandbox': True,
                           'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    identifier = response.json()['id']
    controller = main.ACTIVE_MATCHES[identifier]
    state, spell, probe = prepare(name, seat, 'Psychogenic Probe')
    state.id = identifier
    controller.state = state
    main._persist_active_match(repo, controller)

    def post(actor, action):
        revision = main.ACTIVE_MATCHES[identifier].revision
        value = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': action},
                            headers={'Idempotency-Key': f'shuffle-audit-{revision}', 'X-Match-Revision': str(revision)})
        assert value.status_code == 200, value.text

    def reload():
        expected = snap(main.ACTIVE_MATCHES[identifier].state)
        main.ACTIVE_MATCHES.clear()
        main._restore_active_matches(repo, identifier)
        assert snap(main.ACTIVE_MATCHES[identifier].state) == expected

    post(seat, {'type': 'cast_spell', 'card_id': spell})
    for _ in range(2):
        post(main.ACTIVE_MATCHES[identifier].state.priority_player, {'type': 'pass_priority'})
    current = main.ACTIVE_MATCHES[identifier]
    order = list(reversed(current.state.pending_mechanic_choice['options']))
    baseline = (snap(current.state), deepcopy(main._controller_snapshot(current)), sql_facts(repo))
    wrong = client.post(f'/matches/{identifier}/action', json={
        'player_id': 3-seat, 'action': {'type': 'choose_mechanic', 'card_ids': order}})
    assert wrong.status_code == 422
    assert (snap(current.state), main._controller_snapshot(current), sql_facts(repo)) == baseline
    foreign_view = client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert foreign_view.status_code == 200 and 'inspected_cards' not in foreign_view.text
    reload()
    post(seat, {'type': 'choose_mechanic', 'card_ids': order})
    if name == 'Ponder':
        reload()
        post(seat, {'type': 'choose_mechanic', 'card_ids': [selection]})
    reload()
    final = main.ACTIVE_MATCHES[identifier].state
    record(tmp_path, 'durably-restored-final', final)
    assert final.cards[spell].zone == Zone.GRAVEYARD and final.pending_mechanic_choice is None
    receipts = [item for item in final.stack if item.source_card_id == probe]
    assert len(receipts) == int(selection == 'shuffle'), 'Real HTTP shuffle must enqueue canonical Probe observer'
