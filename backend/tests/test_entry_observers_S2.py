"""S2 preparation only: exact canonical entry predicates and body boundaries."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.events import emit_event, _matches_enters_battlefield_trigger
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_linked_damage_targets import raw_card
from tests.test_ninjutsu_source_identity import http_resolve, relocate
from tests.test_selected_mana_http import game, retain, restart, forbid_external_network
from tests.test_training_ninjutsu_intent_audit import scenario
from tests.test_hand_entry_bookkeeping_audit import capture


FIXTURE = Path(__file__).parent / 'fixtures/entry_observers_S2/canonical.jsonl'
assert sha256(FIXTURE.read_bytes()).hexdigest() == '8f337660b08660748a0b47d9590a40e106303e578bff37277bbda05dd89018ba'
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
assert len(ROWS) == 6 and all(row['object'] == 'card' and row['oracle_id'] for row in ROWS.values())
OBSERVERS = ["Ajani's Welcome", "Cathars' Crusade", 'Soul Warden', 'Altar of the Brood']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', OBSERVERS)
@pytest.mark.parametrize('entrant', ['own-creature', 'foreign-creature', 'own-noncreature'])
def test_exact_canonical_predicate_type_and_controller(seat, name, entrant):
    env, _, _, info = scenario(seat)
    state = env._state
    observer = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    if entrant == 'own-creature':
        cid = info['attackers'][0]
    elif entrant == 'foreign-creature':
        # Existing full canonical Ninja payload, no renamed/synthetic Oracle.
        payload = json.loads((Path(__file__).parent / 'fixtures/ninjutsu_canonical/ninja-of-the-deep-hours.json').read_bytes())
        cid = raw_card(state, payload, 3-seat, Zone.BATTLEFIELD).id
    else:
        cid = raw_card(state, ROWS['Sol Ring'], seat, Zone.BATTLEFIELD).id
    before = env.snapshot()
    expected = (entrant == 'own-creature' or
                name == 'Soul Warden' and entrant == 'foreign-creature' or
                name == 'Altar of the Brood' and entrant == 'own-noncreature')
    actual = _matches_enters_battlefield_trigger(
        state, observer, observer.oracle_text.lower(), {'card_id': cid})
    assert env.snapshot() == before
    assert actual is expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', OBSERVERS)
@pytest.mark.parametrize('departed', [False, True])
def test_real_entry_http_receipt_resolution_and_private_restart(game, tmp_path, seat, name, departed):
    env, action, _, info = scenario(seat)
    observer = raw_card(env._state, ROWS[name], seat, Zone.BATTLEFIELD)
    source_id = observer.id
    before_life = env._state.players[seat].life
    before_library = len(env._state.players[3-seat].library)
    capture(tmp_path, 'before', env._state)
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restart(identifier)
    entered = http_resolve(client, identifier)
    capture(tmp_path, 'entered', entered)
    assert len(entered.stack) == 1
    trigger = entered.stack[-1]
    assert trigger.source_card_id == source_id and trigger.controller == seat
    assert trigger.payload['__trigger_event'] == 'enters_battlefield'
    assert entered.cards[info['ninja']].zone == Zone.BATTLEFIELD
    if departed:
        # Controlled departure after receipt; not claimed as a causal HTTP spell.
        fork = deepcopy(entered)
        relocate(fork, source_id, Zone.EXILE)
        env._state = fork
        retain(restart(identifier), env)
        assert restart(identifier).state.stack[-1].source_card_id == source_id
    capture(tmp_path, 'pending', restart(identifier).state)
    resolved = http_resolve(client, identifier)
    capture(tmp_path, 'resolved', resolved)
    assert not resolved.stack
    assert resolved.players[seat].life == before_life + int(name in {"Ajani's Welcome", 'Soul Warden'})
    assert len(resolved.players[3-seat].library) == before_library - int(name == 'Altar of the Brood')
    for cid in [info['ninja'], info['attackers'][0]]:
        assert resolved.cards[cid].counters == ({'+1/+1': 1} if name == "Cathars' Crusade" else {})
    assert not resolved.cards[info['attackers'][1]].counters
    restored = restart(identifier).state
    assert restored.cards[info['ninja']].counters == resolved.cards[info['ninja']].counters
    env._state = deepcopy(restored)
    foreign = restored.players[3-seat].hand[0]
    assert foreign not in env.observe(seat)['known_cards']
    public = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert public.status_code == 200 and foreign not in public.text


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_unknown_body_keeps_diagnostic_receipt_without_free_reward(tmp_path, seat):
    env, _, _, info = scenario(seat)
    state = env._state
    observer = raw_card(state, ROWS['Pandemonium'], seat, Zone.BATTLEFIELD)
    body = observer.oracle_text.split(', ', 1)[1]
    surface = deepcopy(observer)
    surface.oracle_text = body
    effect, _ = infer_effect_from_oracle(state, surface, seat, report_unsupported=False)
    assert effect == 'noop', 'Canonical body is now supported; reassess bounded unsupported classification'
    before_life = {pid: player.life for pid, player in state.players.items()}
    capture(tmp_path, 'before', state)
    emit_event(state, 'enters_battlefield', {'card_id': info['attackers'][0]})
    capture(tmp_path, 'pending', state)
    assert {pid: player.life for pid, player in state.players.items()} == before_life
    assert len(state.stack) == 1
    item = state.stack[-1]
    assert item.effect_key == 'noop' and item.source_card_id == observer.id and item.controller == seat
    assert item.payload['__unsupported_trigger_instruction'] == body


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_core_event_noop_http_restart_preserves_source_without_reward(game, tmp_path, seat):
    env, _, _, info = scenario(seat)
    observer = raw_card(env._state, ROWS['Pandemonium'], seat, Zone.BATTLEFIELD)
    emit_event(env._state, 'enters_battlefield', {'card_id': info['attackers'][0]})
    assert len(env._state.stack) == 1
    item = env._state.stack[-1]
    assert item.effect_key == 'noop' and item.source_card_id == observer.id and item.controller == seat
    before_life = {pid: player.life for pid, player in env._state.players.items()}
    before_counters = {cid: deepcopy(card.counters) for cid, card in env._state.cards.items()}
    relocate(env._state, observer.id, Zone.EXILE)
    capture(tmp_path, 'pending', env._state)
    client, match = game
    identifier = retain(match, env)
    restored = restart(identifier).state
    assert restored.stack[-1].source_card_id == observer.id
    assert restored.stack[-1].controller == seat
    assert restored.cards[observer.id].zone == Zone.EXILE
    resolved = http_resolve(client, identifier)
    assert not resolved.stack
    assert {pid: player.life for pid, player in resolved.players.items()} == before_life
    assert {cid: card.counters for cid, card in resolved.cards.items()} == before_counters
    capture(tmp_path, 'resolved', resolved)
    env._state = deepcopy(restart(identifier).state)
    foreign = env._state.players[3-seat].hand[0]
    assert foreign not in env.observe(seat)['known_cards']
