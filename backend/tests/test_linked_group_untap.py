"""Canonical linked creature groups: resolve recipients, then reuse them."""
from copy import copy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_multicast_subject_audit import add, announce, position, restart
from tests.test_spell_trigger_surface_audit import cards, record


DIRECTORY = Path(__file__).parent / 'fixtures/linked_group_untap'
ROWS = {row['name']: row for row in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
cards.ROWS.update(ROWS)


def test_unchanged_canonical_rows():
    metadata = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert metadata['offline'] and not metadata['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == metadata['fixture_sha256']
    for row in metadata['rows']:
        assert ROWS[row['name']]['id'] == row['id']
        assert ROWS[row['name']]['oracle_id'] == row['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Jeskai Ascendancy', 'Rallying Roar', 'Inspired Charge'])
def test_exact_canonical_compiled_group_not_an_invented_recipient(request, seat, family):
    state, source = position(seat)
    owner = add(state, family, seat, Zone.HAND)
    proxy = copy(owner)
    if family == 'Jeskai Ascendancy':
        proxy.oracle_text = owner.oracle_text.splitlines()[0].split(', ', 1)[1]
    with cards.unchanged_root(state):
        key, payload = infer_effect_from_oracle(state, proxy, seat, report_unsupported=False)
    record(request, {'canonical': ROWS.get(family, owner.oracle_text), 'compiled': [key, payload]})
    assert key == 'temporary_pt_buff_all'
    assert bool(payload.get('untap_affected_creatures')) == (family != 'Inspired Charge')
    assert payload['controller_only'] is True
    assert 'target_card_ids' not in payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Jeskai Ascendancy', 'Rallying Roar', 'Inspired Charge'])
@pytest.mark.parametrize('stun', [0, 1])
def test_actual_cast_resolves_current_group_once_with_stun_and_foreign_controls(request, seat, family, stun):
    source_name = 'Shock' if family == 'Jeskai Ascendancy' else family
    state, source = position(seat, source_name)
    listener = add(state, family, seat) if family == 'Jeskai Ascendancy' else None
    departed = add(state, 'Raging Goblin', seat)
    ally = add(state, 'Raging Goblin', seat)
    foreign_owned = add(state, 'Raging Goblin', seat)
    foreign_owned.owner = 3-seat
    enemy = add(state, 'Raging Goblin', 3-seat)
    land = add(state, 'Forest', seat)
    arbor = add(state, 'Dryad Arbor', seat)
    for card in [departed, ally, foreign_owned, enemy, land, arbor]:
        card.tapped = True
    ally.counters['stun'] = stun
    paid, action = announce(state, seat, source)
    # Canonical fixture zone transitions before the queued group's resolution.
    paid.players[seat].battlefield.remove(departed.id)
    paid.players[seat].graveyard.append(departed.id)
    paid.cards[departed.id].move_to_zone(Zone.GRAVEYARD)
    late = add(paid, 'Raging Goblin', seat)
    late.tapped = True
    paid = restart(paid)
    for _ in range(8):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
        paid = restart(paid)
    else:
        pytest.fail('Bounded actual group resolution did not finish')
    expected_untap = family != 'Inspired Charge'
    record(request, {'family': family, 'action': action, 'stun': stun,
                     'source_id': source.id, 'listener_id': listener.id if listener else None,
                     'group_ids': [ally.id, foreign_owned.id, arbor.id, late.id],
                     'resolved': cards.serialize_match_snapshot(paid)})
    for card in [foreign_owned, arbor, late]:
        assert paid.cards[card.id].tapped is not expected_untap
        assert effective_power(paid, card.id) == (3 if family == 'Inspired Charge' else 2)
        assert effective_toughness(paid, card.id) == 2
    assert paid.cards[ally.id].tapped == (bool(stun) or not expected_untap)
    assert paid.cards[ally.id].counters.get('stun', 0) == (stun if not expected_untap else 0)
    assert paid.cards[enemy.id].tapped and effective_power(paid, enemy.id) == 1
    assert paid.cards[land.id].tapped
    assert effective_power(paid, departed.id) == 1
    after = add(paid, 'Raging Goblin', seat)
    after.tapped = True
    assert effective_power(paid, after.id) == 1 and paid.cards[after.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Jeskai Ascendancy', 'Rallying Roar'])
def test_actual_canonical_pronoun_without_antecedent_does_not_guess_a_target(request, seat, family):
    state, source = position(seat)
    owner = add(state, family, seat, Zone.HAND)
    ally = add(state, 'Raging Goblin', seat)
    ally.tapped = True
    proxy = copy(owner)
    body = owner.oracle_text.splitlines()[0].split(', ', 1)[1] if family == 'Jeskai Ascendancy' else owner.oracle_text
    # Compiler-unit projection of an unchanged canonical suffix, not a offered mode.
    proxy.oracle_text = body.split('. ', 1)[1]
    with cards.unchanged_root(state):
        compiled = infer_effect_from_oracle(state, proxy, seat, {'target_card_id': ally.id}, report_unsupported=False)
    record(request, {'canonical_suffix': proxy.oracle_text, 'compiled': compiled})
    assert compiled == ('noop', {})
    assert ally.tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_real_source_removal_does_not_reselect_or_erase_queued_group(request, seat):
    state, source = position(seat)
    listener = add(state, 'Jeskai Ascendancy', seat)
    ally = add(state, 'Raging Goblin', seat)
    ally.tapped = True
    removal = add(state, 'Naturalize', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    paid, action = announce(state, seat, source)
    with cards.unchanged_root(paid):
        paid = checked_action(paid, RulesEngine(), seat, {'type': 'pass_priority'})
    with cards.unchanged_root(paid):
        paid = checked_action(paid, RulesEngine(), 3-seat, {
            'type': 'cast_spell', 'card_id': removal.id, 'targets': {'target_card_id': listener.id}})
    paid = restart(paid)
    assert resolve_top_of_stack(paid)
    assert paid.cards[listener.id].zone == Zone.GRAVEYARD
    for _ in range(8):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
        paid = restart(paid)
    record(request, {'actual_cast': action, 'source_removal': removal.id,
                     'resolved': cards.serialize_match_snapshot(paid)})
    assert not paid.cards[ally.id].tapped and effective_power(paid, ally.id) == 2
