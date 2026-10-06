"""Full-Oracle paid magecraft controls; retained setup is not natural gameplay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.targeting import stack_object_kind
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, restart, snap
from tests.test_trigger_instruction_compilation_audit import passes
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, public_private_restore, main_controller_snapshot
from tests.test_trigger_instruction_compilation_http_audit import submit, responses
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/canonical_magecraft_audit'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    data = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['oracle_id'] == entry['oracle_id'] and row['object'] == 'card'
    ROWS[row['name']] = row


def position(seat, actor=None, stimulus='Opt'):
    actor = actor or seat
    deck = [{**ROWS['Island'], 'card_name': 'Island', 'quantity': 32}]
    state = MatchFactory.from_decks(deck, deck, seed=8951)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = actor
    state.step = Step.PRECOMBAT_MAIN
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    source = raw_card(state, ROWS['Clever Lumimancer'], seat, Zone.BATTLEFIELD)
    spell = raw_card(state, ROWS[stimulus], actor, Zone.HAND)
    state.players[actor].mana_pool = {'U': 1} if stimulus == 'Opt' else {'C': 1, 'G': 1}
    return state, source.id, spell.id, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}}


def buffs(state, source):
    return [item for item in state.stack if item.source_card_id == source and stack_object_kind(state, item) == 'triggered']


def stats(state, source):
    return effective_power(state, source), effective_toughness(state, source)


def ref(state, source):
    card = state.cards[source]
    return [source, object_incarnation(card), card.zone_change_sequence]


def require_buff(state, source, seat):
    items = buffs(state, source)
    assert len(items) == 1, 'Actual canonical cast/copy must admit exactly one self-pump trigger'
    item = items[0]
    assert item.controller == seat and item.effect_key == 'temporary_pt_buff'
    assert item.payload['target_card_id'] == source
    assert (item.payload['power'], item.payload['toughness']) == (2, 2)
    return item


def finish_stack(state):
    # Actual checked priority and explicit keep-all scry; no direct effect calls.
    for _ in range(20):
        if not state.stack and not state.pending_mechanic_choice:
            return state
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['kind'] == 'scry'
            state = act(state, pending['player_id'], {'type': 'choose_mechanic', 'card_ids': []})
        else:
            state = passes(state)
    pytest.fail('Bounded canonical Opt stack did not finish')


def cleanup(state):
    turn = state.turn
    for _ in range(40):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
        if state.turn > turn:
            return state
    pytest.fail('Checked empty-combat turn did not reach cleanup')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_opt_two_two_snapshot_cleanup(seat, tmp_path):
    state, source, spell, action = position(seat)
    old_ref = ref(state, source)
    state = act(state, seat, action)
    assert sum(state.players[seat].mana_pool.values()) == 0
    require_buff(state, source, seat)
    state = passes(restart(state, tmp_path, 'pending-two-two'))
    assert stats(state, source) == (2, 3), 'Printed 0/1 plus exact +2/+2'
    state = finish_stack(restart(state, tmp_path, 'resolved-buff'))
    assert state.cards[spell].zone == Zone.GRAVEYARD
    state = cleanup(state)
    assert stats(state, source) == (0, 1) and ref(state, source) == old_ref
    assert state.cards[source].counters.get('__eot_power', 0) == 0
    assert state.cards[source].counters.get('__eot_toughness', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_twincast_cast_and_copy_separate_magecraft(seat, tmp_path):
    state, source, spell, action = position(seat)
    state = act(state, seat, action)
    require_buff(state, source, seat)
    state = passes(state)
    assert stats(state, source) == (2, 3)
    twin = raw_card(state, ROWS['Twincast'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': twin.id,
                             'targets': {'target_stack_id': state.stack[-1].id}})
    require_buff(state, source, seat)
    state = passes(state)
    assert stats(state, source) == (4, 5)
    state = passes(state)
    require_buff(state, source, seat)
    assert state.stack[-2].payload['__stack_copy_kind'] == 'spell'
    state = passes(restart(state, tmp_path, 'real-spell-copy-trigger'))
    assert stats(state, source) == (6, 7)
    state = finish_stack(state)
    assert len(state.players[seat].hand) == 2
    state = cleanup(state)
    assert stats(state, source) == (0, 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('actor_kind', ['own_creature', 'opponent_creature', 'opponent_instant'])
def test_actual_paid_subject_controller_negatives(seat, actor_kind):
    actor = seat if actor_kind == 'own_creature' else 3-seat
    stimulus = 'Opt' if actor_kind == 'opponent_instant' else 'Grizzly Bears'
    state, source, spell, action = position(seat, actor, stimulus)
    state = act(state, actor, action)
    assert not buffs(state, source)
    state = finish_stack(state)
    assert not buffs(state, source) and stats(state, source) == (0, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_opponent_spell_copy_not_our_magecraft(seat):
    state, source, spell, action = position(seat)
    state = act(state, seat, action)
    require_buff(state, source, seat)
    state = passes(state)
    state = act(state, seat, {'type': 'pass_priority'})
    actor = 3-seat
    twin = raw_card(state, ROWS['Twincast'], actor, Zone.HAND)
    state.players[actor].mana_pool = {'U': 2}
    state = act(state, actor, {'type': 'cast_spell', 'card_id': twin.id,
                              'targets': {'target_stack_id': state.stack[-1].id}})
    assert not buffs(state, source)
    state = passes(state)
    assert state.stack[-1].payload['__stack_copy_kind'] == 'spell'
    assert state.stack[-1].controller == actor
    assert not buffs(state, source) and stats(state, source) == (2, 3)
    state = cleanup(finish_stack(state))
    assert stats(state, source) == (0, 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_self_buff_reference_contract_roundtrip(seat, tmp_path):
    state, source, spell, action = position(seat)
    expected = ref(state, source)
    state = act(state, seat, action)
    item = require_buff(state, source, seat)
    assert item.payload.get('__self_buff_reference') == expected, 'Retain actual source object reference at trigger creation'
    restored = restart(state, tmp_path, 'reference-contract')
    assert buffs(restored, source)[0].payload['__self_buff_reference'] == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_trusted_zone_reentry_old_trigger_cannot_buff_new_object(seat, tmp_path):
    state, source, spell, action = position(seat)
    before = ref(state, source)
    state = act(state, seat, action)
    require_buff(state, source, seat)
    # Explicit trusted transition probe, NOT an actual spell/event/HTTP reentry.
    card = state.cards[source]
    state.players[seat].battlefield.remove(source)
    card.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source)
    state.players[seat].hand.remove(source)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(source)
    assert ref(state, source) != before
    state = passes(restart(state, tmp_path, 'trusted-reentered-source'))
    assert stats(state, source) == (0, 1), 'Pending old-incarnation buff must not attach to reentered same ID'


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_unsummon_old_buff_cannot_modify_hand_source(seat, tmp_path):
    state, source, spell, action = position(seat)
    state = act(state, seat, action)
    require_buff(state, source, seat)
    bounce = raw_card(state, ROWS['Unsummon'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bounce.id, 'targets': {'target_card_id': source}})
    require_buff_count = len(buffs(state, source))
    assert require_buff_count == 2
    state = passes(state)  # Magecraft from the real Unsummon cast.
    state = passes(state)  # Actual Unsummon departure; old Opt trigger remains.
    assert state.cards[source].zone == Zone.HAND
    assert len(buffs(state, source)) == 1
    state = passes(restart(state, tmp_path, 'real-departed-source'))
    assert state.cards[source].counters.get('__eot_power', 0) == 0
    assert state.cards[source].counters.get('__eot_toughness', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_bounce_recast_setup_blocked_without_supported_flash_permission(seat):
    state, source, spell, action = position(seat)
    raw_card(state, ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    state = act(state, seat, action)
    require_buff(state, source, seat)
    bounce = raw_card(state, ROWS['Unsummon'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': bounce.id, 'targets': {'target_card_id': source}})
    state = passes(passes(state))
    state.players[seat].mana_pool = {'W': 1}
    assert state.cards[source].zone == Zone.HAND and buffs(state, source)
    # Characterizes a separate actual flash permission gap, not engine acceptance.
    offered = RulesEngine().legal_moves(state, seat)
    assert not any(m['type'] == 'cast_spell' and m.get('card_id') == source for m in offered)


@pytest.mark.parametrize('seat', [1, 2])
def test_http_paid_opt_buff_private_snapshot_atomic_cleanup(repo, client, seat, tmp_path):
    for row in ROWS.values(): repo.upsert_card(normalize(row))
    state, source, spell, action = position(seat)
    controller = install(repo, client, state)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    bad = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat, 'action': action})
    assert bad.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    submit(client, controller, seat, action)
    require_buff(controller.state, source, seat)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    responses(client, controller)
    assert stats(controller.state, source) == (2, 3)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    controller.state = cleanup(finish_stack(controller.state))
    assert stats(controller.state, source) == (0, 1)
