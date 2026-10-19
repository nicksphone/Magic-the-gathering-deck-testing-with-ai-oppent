"""Genuine public actions and full printed rules, never fabricated event ABIs."""
from dataclasses import replace
import hashlib
import json

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.ability_model import build_spell_spec
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.targeting import stack_object_kind
from tests.oracle_effects_positive_fixtures_8d import remaining_card
from tests.oracle_effects_semantic_support_8d import HERE, PURIFY_SHA256, full_raw, purify_card
from tests.rules_printed_facts_e4 import canonical_deck_entry


def position():
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=937)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    return state


def add(state, name, cid, seat=1, zone=Zone.BATTLEFIELD):
    if name == 'Ossification':
        raw = full_raw(name)
        sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 8}], [], seed=100)
        card = replace(next(c for c in sample.cards.values() if c.zone == Zone.LIBRARY),
                       id=cid, owner=seat, controller=seat, zone=zone, instance_order=0)
    else:
        card = remaining_card(name, id=cid, owner=seat, controller=seat, zone=zone)
    card.summoning_sick = False
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    return card


def activate_pyromancer(state, seat=1):
    return checked_action(state, RulesEngine(), seat, {
        'type': 'activate_ability', 'card_id': 'pyromancer', 'ability_index': 0,
        'targets': {'target_player': 3-seat}})


def test_rings_real_own_nonmana_activation_publishes_its_trigger():
    state = position()
    rings = add(state, 'Rings of Brighthearth', 'rings')
    add(state, 'Prodigal Pyromancer', 'pyromancer')
    state.players[1].mana_pool['C'] = 2
    state = activate_pyromancer(state)
    original = next(item for item in state.stack if item.source_card_id == 'pyromancer')
    assert stack_object_kind(state, original) == 'activated'
    assert state.cards['pyromancer'].tapped and state.players[1].mana_pool['C'] == 2
    # No invented payment payload: stop at the genuine missing event boundary.
    triggers = [item for item in state.stack if item.source_card_id == rings.id]
    assert len(triggers) == 1
    assert stack_object_kind(state, triggers[0]) == 'triggered'
    assert state.stack.index(triggers[0]) > state.stack.index(original)


def test_rings_does_not_copy_opponents_nonmana_activation():
    state = position()
    add(state, 'Rings of Brighthearth', 'rings')
    add(state, 'Prodigal Pyromancer', 'pyromancer', seat=2)
    state.active_player = state.priority_player = 2
    state = activate_pyromancer(state, 2)
    assert len(state.stack) == 1 and state.stack[0].source_card_id == 'pyromancer'
    assert stack_object_kind(state, state.stack[0]) == 'activated'


def test_rings_does_not_copy_a_real_mana_ability():
    state = position()
    add(state, 'Rings of Brighthearth', 'rings')
    add(state, 'Island', 'mana-land')
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'tap_land_for_mana', 'card_id': 'mana-land', 'color': 'U'})
    assert state.cards['mana-land'].tapped and state.players[1].mana_pool['U'] == 1
    assert state.stack == []


@pytest.mark.parametrize('index,source_name,kind,cost', [
    (0, 'Prodigal Pyromancer', 'activated or triggered ability', 2),
    (1, 'Lightning Bolt', 'instant or sorcery spell', 3),
    (2, 'Grizzly Bears', 'permanent spell', 4),
])
def test_lithoform_native_indices_publish_the_selected_real_ability(index, source_name, kind, cost):
    state = position()
    copier = add(state, 'Lithoform Engine', 'lithoform')
    state.players[1].mana_pool.update(C=10, R=1, G=1)
    if index == 0:
        add(state, source_name, 'pyromancer')
        state = activate_pyromancer(state)
    else:
        add(state, source_name, 'source', zone=Zone.HAND)
        action = {'type': 'cast_spell', 'card_id': 'source'}
        if index == 1:
            action['targets'] = {'target_player': 2}
        state = checked_action(state, RulesEngine(), 1, action)
    source = state.stack[-1]
    move = next(m for m in RulesEngine().legal_moves(state, 1)
                if m['type'] == 'activate_ability' and m['card_id'] == copier.id
                and m['ability_index'] == index)
    assert source.id in {item['id'] for item in move['target_hints']['stack_targets']}
    before = state.players[1].mana_pool['C']
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'activate_ability', 'card_id': copier.id, 'ability_index': index,
        'targets': {'target_stack_id': source.id}})
    copy = state.stack[-1]
    assert copy.source_card_id == copier.id and stack_object_kind(state, copy) == 'activated'
    assert copy.effect_key == ('copy_ability' if index == 0 else 'copy_spell')
    assert copy.payload['target_stack_id'] == source.id and copy.payload['copy_kind'] == kind
    assert state.cards[copier.id].tapped and state.players[1].mana_pool['C'] == before-cost


def test_lithoform_rejected_wrong_kind_target_changes_no_authoritative_state():
    state = position()
    add(state, 'Lithoform Engine', 'lithoform')
    add(state, 'Lightning Bolt', 'bolt', zone=Zone.HAND)
    state.players[1].mana_pool.update(C=2, R=1)
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'cast_spell', 'card_id': 'bolt', 'targets': {'target_player': 2}})
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            'type': 'activate_ability', 'card_id': 'lithoform', 'ability_index': 0,
            'targets': {'target_stack_id': state.stack[-1].id}})
    assert serialize_match_snapshot(state) == before


def test_vindicate_genuine_land_target_is_destroyed_without_touching_artifact():
    state = position()
    land = add(state, 'Island', 'land', seat=2)
    artifact = add(state, 'Sol Ring', 'artifact', seat=2)
    source = add(state, 'Vindicate', 'vindicate', zone=Zone.HAND)
    key, payload = infer_effect_from_oracle(state, source, 1, {'target_card_id': land.id})
    assert key == 'destroy_permanent' and payload['target_card_id'] == land.id
    resolve_effect(state, 1, key, payload)
    assert land.id in state.players[2].graveyard and land.zone == Zone.GRAVEYARD
    assert artifact.id in state.players[2].battlefield and artifact.zone == Zone.BATTLEFIELD


def test_collected_company_preserves_rng_and_the_below_six_order():
    state = position()
    source = add(state, 'Collected Company', 'company', zone=Zone.HAND)
    creature = add(state, 'Elvish Mystic', 'creature-library', zone=Zone.LIBRARY)
    before = list(state.players[1].library)
    rng = state.rng.getstate()
    key, payload = infer_effect_from_oracle(state, source, 1)
    assert key == 'topdeck_put_creatures_battlefield'
    assert (payload['top_n'], payload['max_creatures'], payload['mv_max']) == (6, 2, 3)
    assert payload['bottom_any_order'] is True and payload['bottom_random'] is False
    resolve_effect(state, 1, key, payload)
    rest = [cid for cid in before[-6:] if cid != creature.id]
    assert state.players[1].library == list(reversed(rest)) + before[:-6]
    assert state.rng.getstate() == rng
    assert creature.id in state.players[1].battlefield


def test_collected_company_cannot_search_for_an_eligible_card_below_six():
    state = position()
    source = add(state, 'Collected Company', 'company', zone=Zone.HAND)
    creature = add(state, 'Elvish Mystic', 'below-six', zone=Zone.LIBRARY)
    state.players[1].library.remove(creature.id)
    state.players[1].library.insert(0, creature.id)
    rng = state.rng.getstate()
    key, payload = infer_effect_from_oracle(state, source, 1)
    resolve_effect(state, 1, key, payload)
    assert creature.id in state.players[1].library and creature.id not in state.players[1].battlefield
    assert creature.zone == Zone.LIBRARY and state.rng.getstate() == rng


def test_bane_permanent_spell_has_no_cast_time_etb_reward():
    state = position()
    source = add(state, 'Bane of Progress', 'bane', zone=Zone.HAND)
    artifact = add(state, 'Sol Ring', 'artifact')
    state.players[1].mana_pool.update(C=4, G=2)
    spec = build_spell_spec(state, source, 1)
    assert spec.effect.key == 'noop'
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id})
    assert state.stack[-1].source_card_id == source.id and state.stack[-1].effect_key == 'noop'
    assert artifact.id in state.players[1].battlefield and state.cards[artifact.id].zone == Zone.BATTLEFIELD
    assert state.cards[source.id].counters == {}  # Do not resolve/certify Bane's ETB here.


def test_vaults_native_targetless_spell_returns_both_owners_without_theft():
    state = position()
    own = add(state, 'Sol Ring', 'own-artifact', zone=Zone.GRAVEYARD)
    enemy = add(state, 'Oath of Nissa', 'enemy-enchantment', seat=2, zone=Zone.GRAVEYARD)
    source = add(state, 'Open the Vaults', 'vaults', zone=Zone.HAND)
    state.players[1].mana_pool.update(C=4, W=2)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id})
    from rules_engine.stack_engine import resolve_top_of_stack
    assert resolve_top_of_stack(state)
    assert own.id in state.players[1].battlefield and enemy.id in state.players[2].battlefield
    assert state.cards[own.id].controller == 1 and state.cards[enemy.id].controller == 2
    assert own.id not in state.players[1].graveyard and enemy.id not in state.players[2].graveyard


def test_vaults_native_resolution_leaves_nontypes_and_unattachable_aura_in_graveyard():
    state = position()
    artifact = add(state, 'Sol Ring', 'artifact', zone=Zone.GRAVEYARD)
    creature = add(state, 'Grizzly Bears', 'creature', zone=Zone.GRAVEYARD)
    land = add(state, 'Forest', 'land', zone=Zone.GRAVEYARD)
    aura = add(state, 'Ossification', 'unattachable-aura', zone=Zone.GRAVEYARD)
    source = add(state, 'Open the Vaults', 'vaults', zone=Zone.HAND)
    state.players[1].mana_pool.update(C=4, W=2)
    state = checked_action(state, RulesEngine(), 1, {'type': 'cast_spell', 'card_id': source.id})
    from rules_engine.stack_engine import resolve_top_of_stack
    assert resolve_top_of_stack(state)
    assert artifact.id in state.players[1].battlefield
    for card in (creature, land, aura):
        assert card.id in state.players[1].graveyard and state.cards[card.id].zone == Zone.GRAVEYARD


def test_verified_purify_raw_provenance_and_materialized_objects_are_complete_and_fresh():
    data = (HERE / 'purify.json').read_bytes()
    proof = json.loads((HERE / 'PROVENANCE.json').read_bytes())
    assert hashlib.sha256(data).hexdigest() == proof['body_sha256'] == PURIFY_SHA256
    assert proof['http_status'] == 200 and proof['retries'] == 0 and not proof['redirects_allowed']
    raw = full_raw('Purify')
    first = purify_card(id='wipe', owner=1, controller=1, zone=Zone.HAND)
    second = purify_card(id='wipe', owner=1, controller=1, zone=Zone.HAND)
    assert (first.name, first.oracle_text, first.mana_cost, first.type_line, first.colors, first.layout) == tuple(
        raw[key] for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout'))
    assert first.card_faces == raw.get('card_faces', []) and first is not second
    first.colors.append('noncanonical freshness sentinel')
    assert second.colors == raw['colors'] and full_raw('Purify') == raw
