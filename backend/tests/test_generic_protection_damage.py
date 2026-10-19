"""Canonical damage protection: lawful episodes and explicit primitive controls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from effects import handlers
from effects.registry import resolve_effect
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.colors import card_color_names
from rules_engine.continuous import effective_keywords
from rules_engine.events import capture_last_known_battlefield
from tests.static_global_keyword_support import RAW
from tests.test_basic_land_hooks import attach_song_fixture
from tests.test_color_consumer_goldens import CARDS as COLOR_CARDS
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_direct_graveyard_bypass_audit import ROWS
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.scheduler_fixture_position import ordinary_position
from tests.test_self_graveyard_replacement_audit import ROWS as SELF, act, restart, snap


FIXTURES = Path(__file__).parent / 'fixtures'
BALLISTA_FILE = FIXTURES / 'graveyard_permissions/walking-ballista.json'
assert hashlib.sha256(BALLISTA_FILE.read_bytes()).hexdigest() == json.loads(
    BALLISTA_FILE.with_name('walking-ballista.json.provenance.json').read_text())['sha256']
BALLISTA = json.loads(BALLISTA_FILE.read_text())
CANONICAL = {**RAW, **ROWS, **SELF, 'Walking Ballista': BALLISTA}
FIREWALKER = next(row for row in map(json.loads, (FIXTURES / 'trigger_context/canonical.jsonl').read_text().splitlines())
                  if row['name'] == 'Kor Firewalker')


@pytest.fixture
def damage_packets(monkeypatch, tmp_path):
    original, trace = handlers.deal_damage, []

    def observe(state, controller, payload):
        source = state.cards.get(payload.get('__source_card_id'))
        trace.append({'payload': deepcopy(payload), 'source_name': source.name if source else None,
                      'source_zone': source.zone.value if source else None,
                      'source_colors': sorted(card_color_names(source, state)) if source else None})
        return original(state, controller, payload)

    monkeypatch.setattr(handlers, 'deal_damage', observe)
    yield trace
    (tmp_path / 'actual-damage-packets.json').write_text(json.dumps(trace, sort_keys=True))


def position(seat, name):
    state, _ = setup('Index', seat)
    ordinary_position(state)
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.mechanic_choice_players = {1, 2}
    target = raw_card(state, CANONICAL[name], 3-seat, Zone.BATTLEFIELD)
    return state, target.id


def dreams(state, seat, target, tmp_path):
    spell = raw_card(state, CANONICAL['Sickening Dreams'], seat, Zone.HAND)
    discard = next(cid for cid in state.players[seat].hand if cid != spell.id)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    result = act(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                 'targets': {'x_value': 1}, 'cost_choice': {'id': 'base', 'discard_card_ids': [discard]}})
    assert not sum(result.players[seat].mana_pool.values())
    assert result.cards[discard].zone == Zone.GRAVEYARD
    result = restart(result, tmp_path, 'real-dreams-stack')
    result = passes(result)
    assert result.cards[spell.id].zone == Zone.GRAVEYARD
    assert result.players[1].life == result.players[2].life == 19
    return result, spell.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Progenitus', 'White Knight'])
def test_paid_nontargeted_black_damage_actual_source(seat, name, tmp_path, damage_packets):
    state, target = position(seat, name)
    result, source = dreams(state, seat, target, tmp_path)
    assert result.cards[target].zone == Zone.BATTLEFIELD
    assert result.cards[target].counters.get('__damage_marked', 0) == 0
    packets = [row for row in damage_packets if row['payload'].get('target_card_id') == target]
    assert packets and all(row['payload']['__source_card_id'] == source for row in packets)
    assert all(row['source_name'] == 'Sickening Dreams' and row['source_zone'] == 'stack'
               and row['source_colors'] == ['black'] for row in packets)
    restart(result, tmp_path, 'real-prevented')
    assert_private(result)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Progenitus', 'White Knight'])
def test_actual_paid_humility_removes_target_protection(seat, name, tmp_path):
    state, target = position(seat, name)
    spell = raw_card(state, CANONICAL['Humility'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}})
    state = passes(state)
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD
    assert not any('protection' in keyword for keyword in effective_keywords(state, target))
    result, _ = dreams(state, seat, target, tmp_path)
    assert result.cards[target].zone == Zone.GRAVEYARD
    restart(result, tmp_path, 'humility-damage')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,blocked', [('Progenitus', True), ('White Knight', False)])
def test_paid_red_targeted_damage_or_checked_atomic_reject(seat, name, blocked, tmp_path):
    state, target = position(seat, name)
    source = raw_card(state, CANONICAL['Lightning Bolt'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    action = {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_card_id': target}}
    if blocked:
        before = snap(state)
        with pytest.raises(ActionRejected):
            act(state, seat, action)
        assert snap(state) == before
    else:
        result = passes(act(state, seat, action))
        assert result.cards[target].zone == Zone.GRAVEYARD
        assert result.cards[source.id].zone == Zone.GRAVEYARD
        assert not sum(result.players[seat].mana_pool.values())
        restart(result, tmp_path, 'real-red-bolt')
        assert_private(result)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,blocked', [('Progenitus', True), ('White Knight', False)])
def test_actual_colorless_activated_payment_or_atomic_target_rejection(seat, name, blocked, tmp_path):
    state, target = position(seat, name)
    source = raw_card(state, BALLISTA, seat, Zone.BATTLEFIELD)
    source.counters['+1/+1'] = 3  # Controlled retained counter position, not an entry episode.
    assert card_color_names(source, state) == set()
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 1,
              'targets': {'target_card_id': target}}
    if blocked:
        before = snap(state)
        with pytest.raises(ActionRejected):
            act(state, seat, action)
        assert snap(state) == before
    else:
        result = act(state, seat, action)
        assert result.cards[source.id].counters['+1/+1'] == 2
        result = passes(restart(result, tmp_path, 'paid-colorless-stack'))
        assert result.cards[target].zone == Zone.BATTLEFIELD
        assert result.cards[target].counters['__damage_marked'] == 1
        restart(result, tmp_path, 'paid-colorless-damage')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Progenitus', 'White Knight'])
@pytest.mark.parametrize('source_kind', ['black', 'colorless', 'missing'])
@pytest.mark.parametrize('locked', [False, True])
def test_primitive_source_quality_and_prevention_override(seat, name, source_kind, locked):
    state, target = position(seat, name)
    payload = {'target_card_id': target, 'amount': 1, '__defer_lethal': True}
    if source_kind != 'missing':
        raw = CANONICAL['Sickening Dreams'] if source_kind == 'black' else BALLISTA
        source = raw_card(state, raw, seat, Zone.HAND)
        payload['__source_card_id'] = source.id
    if locked:
        # Existing restriction primitive, NOT a claim of an announced spell/Oracle clause.
        resolve_effect(state, seat, 'set_turn_restriction', {'kind': 'damage_cant_be_prevented'})
    prevented = not locked and (name == 'Progenitus' or source_kind == 'black')
    assert handlers.deal_damage(state, seat, payload) == int(not prevented)
    assert state.cards[target].counters.get('__damage_marked', 0) == int(not prevented)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Progenitus', 'White Knight'])
def test_actual_untargeted_wrath_is_not_damage_protection(seat, name, tmp_path):
    state, target = position(seat, name)
    source = raw_card(state, CANONICAL['Wrath of God'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    result = passes(act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}))
    assert result.cards[target].zone == (Zone.LIBRARY if name == 'Progenitus' else Zone.GRAVEYARD)
    restart(result, tmp_path, 'untargeted-nondamage')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('humility', [False, True])
def test_canonical_matching_red_target_legality_and_actual_ability_loss(seat, humility, tmp_path):
    state, _ = position(seat, 'White Knight')
    target = raw_card(state, FIREWALKER, 3-seat, Zone.BATTLEFIELD)
    if humility:
        spell = raw_card(state, CANONICAL['Humility'], seat, Zone.HAND)
        state.players[seat].mana_pool = {'W': 2, 'C': 2}
        state = passes(act(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}}))
        assert state.cards[spell.id].zone == Zone.BATTLEFIELD
    source = raw_card(state, CANONICAL['Lightning Bolt'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    action = {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_card_id': target.id}}
    if not humility:
        before = snap(state)
        with pytest.raises(ActionRejected):
            act(state, seat, action)
        assert snap(state) == before
        assert 'protection from red' in effective_keywords(state, target.id)
    else:
        assert 'protection from red' not in effective_keywords(state, target.id)
        result = passes(act(state, seat, action))
        assert result.cards[target.id].zone == Zone.GRAVEYARD
        restart(result, tmp_path, 'actual-red-after-humility')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('converted', [False, True])
@pytest.mark.parametrize('retained', [False, True])
def test_canonical_live_or_captured_lki_source_quality(seat, converted, retained, tmp_path):
    state, _ = position(seat, 'White Knight')
    target = raw_card(state, FIREWALKER, 3-seat, Zone.BATTLEFIELD)
    source = raw_card(state, COLOR_CARDS['Prodigal Pyromancer'], seat, Zone.BATTLEFIELD)
    if converted:
        # Controlled canonical attachment seam, NOT a sorcery cast in response.
        state = attach_song_fixture(state, source.id, seat)
    payload = {'amount': 1, 'target_card_id': target.id, '__source_card_id': source.id,
               '__defer_lethal': True}
    if retained:
        capture_last_known_battlefield(state, source.id)
        receipt = deepcopy(state.cards[source.id].last_known_battlefield)
        assert receipt['color_names'] == ([] if converted else ['red'])
        # Canonical effect primitive, not a claim that the converted land was legally targeted.
        resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source.id})
        payload['__source_lki'] = receipt
        # Printed red in hand must not override a colorless PRE-departure receipt.
        assert card_color_names(state.cards[source.id], state) == {'red'}
    state = restart(state, tmp_path, 'canonical-live-or-lki')
    assert handlers.deal_damage(state, seat, payload) == int(converted)
    assert state.cards[target.id].counters.get('__damage_marked', 0) == int(converted)
    if retained:
        assert payload['__source_lki'] == receipt
