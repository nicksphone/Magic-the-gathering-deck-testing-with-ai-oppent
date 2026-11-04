"""Canonical native play plus separately labelled layer/lifecycle component controls."""
from copy import copy
import json
from pathlib import Path

import pytest

import test_saga_land_entry as entry
from api_contracts import AbilityAction, ManaAbilityAction
from game_state.copying import copy_match_state
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.oracle_effects import extract_activated_abilities, extract_saga_chapters, search_card_matches


FACTS = json.loads((Path(__file__).parent/'fixtures/saga_remaining.json').read_text())
entry.FACTS.update(FACTS)


def component_grant(state, cid, chapter=1):
    """Call the genuine resolver with a complete canonical chapter and source ref."""
    from rules_engine import activated_grants as grants
    card = state.cards[cid]
    clause = next(x['text'] for x in extract_saga_chapters(card.oracle_text) if x['number'] == chapter)
    instruction = grants.compile_instruction(clause, card.name)
    payload = {**instruction, 'target_card_id': cid, 'reference': grants.reference(card)}
    grants.resolve_grant(state, card.controller, payload)
    return payload


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_chapter_I_only_grants_then_native_tap_mana(seat):
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.HAND)
    state = entry.act(state, seat, dict(type='play_land', card_id=cid))
    assert not mana_ability_specs(state.cards[cid], state), 'Quoted mana is not a printed ability'
    before = dict(state.players[seat].mana_pool)
    state = entry.settle(state)
    assert state.players[seat].mana_pool == before, 'Grant resolution must not add mana'
    state = entry.restored(state)
    moves = [a for a in RulesEngine().legal_moves(state, seat)
             if a.get('card_id') == cid and a['type'] == 'activate_mana_ability']
    assert len(moves) == 1
    assert moves[0]['color'] == 'C' and moves[0]['output_bundle'] == {'C': 1}
    action = {k: v for k, v in moves[0].items() if k in ManaAbilityAction.model_fields}
    action['color'] = next(iter(moves[0]['outputs']))
    ManaAbilityAction.model_validate(action)
    state = entry.act(state, seat, action)
    assert state.cards[cid].tapped and state.players[seat].mana_pool.get('C') == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('loss_first', [True, False])
def test_component_actual_layer_six_order_not_blanket_printed_loss(seat, loss_first):
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    if loss_first:
        add_keyword_effect(state, cid, ['all abilities'], operation='remove')
    component_grant(state, cid)
    if not loss_first:
        add_keyword_effect(state, cid, ['all abilities'], operation='remove')
    specs = mana_ability_specs(state.cards[cid], state)
    assert bool(specs) is loss_first
    moves = [a for a in RulesEngine().legal_moves(state, seat)
             if a.get('card_id') == cid and a['type'] == 'activate_mana_ability']
    assert bool(moves) is loss_first


@pytest.mark.parametrize('seat', [1, 2])
def test_component_grants_snapshot_copy_identity_and_stable_indices(seat):
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    component_grant(state, cid)
    first = mana_ability_specs(state.cards[cid], state)[0][0]
    component_grant(state, cid, 2)
    assert mana_ability_specs(state.cards[cid], state)[0][0] == first
    ordinary = extract_activated_abilities(state.cards[cid], state=state)
    assert len(ordinary) == 1 and ordinary[0]['index'] != first
    assert 0 <= first <= 100 and 0 <= ordinary[0]['index'] <= 100
    AbilityAction.model_validate(dict(type='activate_ability', card_id=cid, ability_index=ordinary[0]['index']))
    state = entry.restored(state)
    clone = copy_match_state(state)
    assert clone.cards[cid].activated_ability_effects == state.cards[cid].activated_ability_effects
    assert clone.cards[cid].activated_ability_effects is not state.cards[cid].activated_ability_effects
    from rules_engine.copiable_values import values
    assert 'activated_ability_effects' not in values(state.cards[cid])
    assert state.cards[cid].oracle_text == FACTS["Urza's Saga"]['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
def test_component_old_source_reference_cannot_grant_to_reentry(seat):
    from rules_engine import activated_grants as grants
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    old = component_grant(state, cid)
    state.players[seat].battlefield.remove(cid)
    state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(cid)
    grants.resolve_grant(state, seat, old)
    assert not state.cards[cid].activated_ability_effects
    assert not mana_ability_specs(state.cards[cid], state)


@pytest.mark.parametrize('suffix', [' Then draw a card.', ' unless an opponent pays {1}.', ' until end of turn.'])
def test_complete_grant_never_discards_unknown_suffix(suffix):
    from rules_engine import activated_grants as grants
    clause = extract_saga_chapters(FACTS["Urza's Saga"]['oracle_text'])[0]['text']
    with pytest.raises(ActionRejected):
        grants.compile_instruction(clause + suffix, "Urza's Saga")


@pytest.mark.parametrize('body', ['This creature gains flying until end of turn.',
                                 'This permanent gains haste until end of turn.'])
def test_unrelated_existing_keyword_family_does_not_enter_activated_grant(body):
    from rules_engine import activated_grants as grants
    assert grants.compile_instruction(body) is None


@pytest.mark.parametrize('name,allowed', [('Ornithopter', True), ('Shuko', True), ('Soulless Jailer', False)])
def test_exact_printed_cost_is_not_unrestricted_artifact(name, allowed):
    state = entry.position(1)
    cid = entry.add(state, name, 1, Zone.LIBRARY)
    assert search_card_matches(state.cards[cid], 'artifact', printed_mana_costs=['{0}', '{1}']) is allowed


def test_component_snapshot_rejects_non_integer_grant_identity():
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    component_grant(state, cid)
    raw = serialize_match_snapshot(state)
    raw['cards'][cid]['activated_ability_effects'][0]['ability_index'] = True
    with pytest.raises((ValueError, ActionRejected)):
        deserialize_match_snapshot(raw)


def test_component_index_exhaustion_is_atomic_not_silent_truncation():
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    count = 0
    for _ in range(102):
        before = serialize_match_snapshot(state)
        try:
            component_grant(state, cid)
        except ActionRejected:
            assert serialize_match_snapshot(state) == before
            break
        count += 1
    else:
        raise AssertionError('Public index space must be bounded')
    records = state.cards[cid].activated_ability_effects
    assert len(records) == count and len({r['ability_index'] for r in records}) == count
    assert all(0 <= r['ability_index'] <= 100 for r in records)


def test_component_bool_reference_is_not_integer_identity():
    from rules_engine import activated_grants as grants
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    payload = component_grant(state, cid)
    payload['reference']['incarnation'] = True
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        grants.resolve_grant(state, 1, payload)
    assert serialize_match_snapshot(state) == before
