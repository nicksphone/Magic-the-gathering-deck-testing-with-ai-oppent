"""Full canonical Flicker, deliberate public choices, no injected effects."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.engine import RulesEngine
from tests.test_canonical_land_animation_audit import ROWS as LAND_ROWS
from tests.test_cloudshift_compound_audit import act, passes, raw_card, snap
from tests.test_cloudshift_compound_audit import ROWS as BLINK_ROWS
from tests.test_immediate_return_product import EXTRA
from tests.test_targeted_library_search_compiler import setup
from tests.test_targeted_search_resolver_contract import raw as search_raw


FIXTURES = Path(__file__).parent / 'fixtures'
FLICKER = LAND_ROWS['Flicker']
ROWS = {'Land': LAND_ROWS['Island'], 'Enchantment': EXTRA['hardened-scales']}
for directory, name, kind in [('creature_observer_fix', 'Sol Ring', 'Artifact'),
                              ('global_flash_timing_audit', 'Jace Beleren', 'Planeswalker')]:
    provenance = json.loads((FIXTURES / directory / 'provenance.json').read_text())
    entry = next(row for row in provenance['cards'] if row['name'] == name)
    data = (FIXTURES / directory / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    ROWS[kind] = json.loads(data)
KINDS = ['Creature', *ROWS]
flash_entry = next(row for row in json.loads(
    (FIXTURES / 'global_flash_timing_audit/provenance.json').read_text())['cards']
                   if row['name'] == 'Leyline of Anticipation')
flash_raw = (FIXTURES / 'global_flash_timing_audit' / flash_entry['file']).read_bytes()
assert hashlib.sha256(flash_raw).hexdigest() == flash_entry['sha256']
FLASH = json.loads(flash_raw)
black_path = FIXTURES / 'graveyard_permissions/black-knight.json'
assert hashlib.sha256(black_path.read_bytes()).hexdigest() == json.loads(
    black_path.with_name('black-knight.json.provenance.json').read_text())['sha256']
BLACK_KNIGHT = json.loads(black_path.read_text())


def position(seat, kind='Creature', foreign=False):
    state, creature, _, _ = setup('Fertilid', seat)
    target = creature if kind == 'Creature' else raw_card(state, ROWS[kind], seat, Zone.BATTLEFIELD).id
    if foreign:
        # Controlled legal stolen starting board, not a control-change episode.
        state.cards[target].owner = 3-seat
    spell = raw_card(state, FLICKER, seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 1, 'C': 1}
    return state, target, spell


def cast(state, seat, spell, target):
    return act(state, seat, {'type': 'cast_spell', 'card_id': spell,
                            'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': target}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS)
def test_full_canonical_domain_compiles_and_offers_actual_permanent(seat, kind):
    state, target, spell = position(seat, kind)
    before = snap(state)
    spec = build_ability_spec(state, state.cards[spell], seat,
                              {'target_card_id': target}, report_unsupported=False)
    assert spec.effect.key == 'exile_return_immediate' and not spec.used_fallback
    assert spec.effect.payload['requires_nontoken'] is True
    candidates = spec.target_hints.get('permanent_targets', [])
    assert target in {row['id'] for row in candidates}
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_flicker_owner_return_and_actual_new_object_replay(seat, kind, foreign):
    state, target, spell = position(seat, kind, foreign)
    before = snap(state)
    sequence = state.cards[target].zone_change_sequence
    paid = cast(state, seat, spell, target)
    assert paid.stack[-1].payload['mana_spent'] == 2
    assert paid.stack[-1].controller == seat
    results = []
    for root in (paid, deserialize_match_snapshot(snap(paid))):
        result = passes(root)
        card = result.cards[target]
        owner = 3-seat if foreign else seat
        assert card.zone == Zone.BATTLEFIELD and card.owner == card.controller == owner
        assert target in result.players[owner].battlefield
        assert card.zone_change_sequence == sequence + 2
        assert not card.is_token and card.summoning_sick
        assert result.cards[spell].zone == Zone.GRAVEYARD
        if kind == 'Creature':
            assert card.counters['+1/+1'] == 2
        results.append(snap(result))
    assert results[0] == results[1] and snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_token_creation_then_nontoken_cast_rejects_before_payment(seat):
    state, _, spell = position(seat)
    producer = raw_card(state, EXTRA['raise-the-alarm'], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    state = passes(act(state, seat, {'type': 'cast_spell', 'card_id': producer,
                                   'cost_choice': {'id': 'base'}}))
    token = next(cid for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    hints = inspect_target_hints(state, state.cards[spell], seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, spell, token)
    assert snap(state) == before
    assert token not in {row['id'] for row in hints.get('permanent_targets', [])}


@pytest.mark.parametrize('tail', [' Draw a card.', ' If you do, gain 2 life.',
                                ' at the beginning of the next end step.', '\nRebound'])
def test_new_domain_unknown_complete_tail_has_no_partial_exile(tail):
    state, target, spell = position(1)
    proxy = deepcopy(state.cards[spell])
    proxy.oracle_text += tail  # Pure compiler negative, never an executable game card.
    proxy.card_faces = []
    before = snap(state)
    spec = build_ability_spec(state, proxy, 1, {'target_card_id': target}, report_unsupported=False)
    assert spec.effect.key == 'noop' and spec.effect.payload['__unsupported_immediate_return']
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_two_paid_flickers_do_not_exile_a_fresh_returned_object(seat):
    state, target, first = position(seat)
    raw_card(state, FLASH, seat, Zone.BATTLEFIELD)
    second = raw_card(state, FLICKER, seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    sequence = state.cards[target].zone_change_sequence
    state = cast(state, seat, first, target)
    state = cast(state, seat, second, target)
    state = passes(state)
    assert state.cards[target].zone_change_sequence == sequence + 2
    state = passes(deserialize_match_snapshot(snap(state)))
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].zone_change_sequence == sequence + 2


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_protection_excluded_from_candidates_and_cost_admission(seat):
    state, _, _, _ = setup('Fertilid', seat)
    protected = raw_card(state, BLACK_KNIGHT, 3-seat, Zone.BATTLEFIELD).id
    spell = raw_card(state, FLICKER, seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 1, 'C': 1}
    assert state.cards[protected].name == 'Black Knight'
    before = snap(state)
    hints = inspect_target_hints(state, state.cards[spell], seat)
    assert protected not in {row['id'] for row in hints['permanent_targets']}
    with pytest.raises(ActionRejected):
        cast(state, seat, spell, protected)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_actual_foreign_owner_shock_entry_choice_resumes_retained_exile_once(seat, pay):
    state, _, spell = position(seat)
    land = raw_card(state, search_raw('breeding-pool'), seat, Zone.BATTLEFIELD)
    land.owner = 3-seat
    sequence = land.zone_change_sequence
    life = {pid: player.life for pid, player in state.players.items()}
    state = passes(cast(state, seat, spell, land.id))
    assert state.cards[land.id].zone == Zone.EXILE
    assert state.cards[land.id].zone_change_sequence == sequence + 1
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    state = deserialize_match_snapshot(snap(state))
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert snap(state) == before
    state = act(state, 3-seat, {'type': 'choose_mechanic',
                               'choice_id': 'pay_two_life' if pay else 'tapped'})
    assert state.pending_mechanic_choice is None
    assert state.cards[land.id].owner == state.cards[land.id].controller == 3-seat
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert state.cards[land.id].zone_change_sequence == sequence + 2
    assert state.cards[land.id].tapped == (not pay)
    assert state.players[3-seat].life == life[3-seat] - 2 * pay
    assert state.players[seat].life == life[seat]
    assert sum(land.id in player.battlefield for player in state.players.values()) == 1
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert snap(deserialize_match_snapshot(snap(state))) == snap(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_canonical_response_permutation_does_not_change_actor_input(seat):
    state, _, _ = position(seat)
    first = raw_card(state, FLICKER, 3-seat, Zone.HAND)
    second = raw_card(state, BLINK_ROWS['cloudshift'], 3-seat, Zone.LIBRARY)
    changed = deepcopy(state)
    for cid, replacement in [(first.id, second), (second.id, first)]:
        card = deepcopy(replacement)
        previous = changed.cards[cid]
        card.id, card.zone = cid, previous.zone
        card.zone_change_sequence = previous.zone_change_sequence
        changed.cards[cid] = card
    before = snap(state)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    alternate, other_moves = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert snap(view) == snap(alternate) and moves == other_moves
    assert snap(state) == before
