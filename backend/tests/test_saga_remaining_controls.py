"""Additional canonical native search/token controls and labelled layer components."""
from copy import copy
import json
from pathlib import Path

import pytest

import test_saga_land_entry as entry
from test_resolved_activated_grants import component_grant
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.mana_abilities import mana_ability_specs
from rules_engine.oracle_effects import extract_saga_chapters, infer_effect_from_oracle, search_card_matches


entry.FACTS.update(json.loads((Path(__file__).parent/'fixtures/saga_remaining_controls.json').read_text()))


@pytest.fixture(autouse=True)
def owned_media_cache(monkeypatch, tmp_path):
    from card_data import placeholders, token_images, sync
    owned = tmp_path/'image-cache'
    for module in (placeholders, token_images, sync):
        monkeypatch.setattr(module, 'CACHE_DIR', owned)
    monkeypatch.setattr(token_images, '_INDEX_FILE', owned/'token-index.json')
    monkeypatch.setattr(token_images, '_TOKEN_IMAGE_CACHE', {})


@pytest.mark.parametrize('name,kind', [('Walking Ballista', 'artifact'), ('Darksteel Citadel', 'artifact'),
                                     ('Llanowar Elves', 'creature')])
def test_real_printed_X_absent_and_colored_cost_not_literal_zero_one(name, kind):
    assert name in entry.FACTS, 'A real full canonical fixture is required'
    state = entry.position(1)
    cid = entry.add(state, name, 1, Zone.LIBRARY)
    assert not search_card_matches(state.cards[cid], kind, printed_mana_costs=['{0}', '{1}'])


@pytest.mark.parametrize('seat', [1, 2])
def test_component_land_type_loss_does_not_remove_later_granted_mana(seat):
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    entry.add(state, 'Blood Moon', 3-seat, Zone.BATTLEFIELD)
    printed = mana_ability_specs(state.cards[cid], state)
    component_grant(state, cid)
    combined = mana_ability_specs(state.cards[cid], state)
    assert combined[:len(printed)] == printed
    outputs = [row[2] for row in combined]
    assert 'Add {R}.' in outputs and 'Add {C}.' in outputs


@pytest.mark.parametrize('seat', [1, 2])
def test_component_actual_controller_owns_granted_cost_and_token_PT(seat):
    from rules_engine.control_effects import record_control_effect
    state = entry.position(seat)
    cid = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    component_grant(state, cid)
    component_grant(state, cid, 2)
    record_control_effect(state, state.cards[cid], 3-seat)
    assert state.cards[cid].controller == 3-seat
    assert state.cards[cid].activated_ability_effects
    entry.restored(state)
    from rules_engine.oracle_effects import extract_activated_abilities, activation_source_eligible
    ability = extract_activated_abilities(state.cards[cid], state=state)[0]
    assert activation_source_eligible(state, 3-seat, cid, ability)
    assert not activation_source_eligible(state, seat, cid, ability)


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_canonical_token_body_is_dynamic_and_inherent(seat):
    from effects.registry import resolve_effect
    from rules_engine.state_based_actions import apply_state_based_actions
    from rules_engine.zone_actions import put_into_graveyard
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    artifact = entry.add(state, 'Shuko', seat, Zone.BATTLEFIELD)
    body = extract_saga_chapters(state.cards[saga].oracle_text)[1]['text'].split(': ', 1)[1][:-1]
    proxy = copy(state.cards[saga]);proxy.oracle_text = body
    key, payload = infer_effect_from_oracle(state, proxy, seat)
    assert key == 'create_token'
    assert payload['oracle_text'] == 'This token gets +1/+1 for each artifact you control.'
    before = set(state.cards)
    resolve_effect(state, seat, key, payload)
    apply_state_based_actions(state)
    ids = set(state.cards)-before
    assert len(ids) == 1
    token = state.cards[next(iter(ids))]
    assert token.is_token and {'Artifact', 'Creature'} <= set(token.types)
    assert token.zone == Zone.BATTLEFIELD
    assert (token.power, token.toughness) == (0, 0)
    assert effective_power(state, token.id) == effective_toughness(state, token.id) == 2
    put_into_graveyard(state, artifact)
    assert effective_power(state, token.id) == effective_toughness(state, token.id) == 1
    entry.restored(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_actual_search_handler_applies_exact_cost_to_auto_and_explicit(seat, explicit):
    from effects.registry import resolve_effect
    state = entry.position(seat)
    bad = entry.add(state, 'Soulless Jailer', seat, Zone.LIBRARY)
    good = entry.add(state, 'Shuko', seat, Zone.LIBRARY)
    state.players[seat].library.remove(bad);state.players[seat].library.insert(0, bad)
    state.mechanic_choice_players.clear();state.replacement_choice_players.clear()
    payload = dict(contains='artifact', destination='hand', count=1, printed_mana_costs=['{0}', '{1}'])
    if explicit:
        payload['selected_card_ids'] = [bad]
        with pytest.raises(ValueError):
            resolve_effect(state, seat, 'search_library', payload)
        assert state.cards[bad].zone == Zone.LIBRARY
        payload['selected_card_ids'] = [good]
    resolve_effect(state, seat, 'search_library', payload)
    assert state.cards[good].zone == Zone.HAND and state.cards[bad].zone == Zone.LIBRARY


@pytest.mark.parametrize('tail', [' Then draw a card.', ' If you control a creature.'])
def test_component_unknown_token_residual_is_not_a_vanilla_token(tail):
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    body = extract_saga_chapters(state.cards[cid].oracle_text)[1]['text'].split(': ', 1)[1][:-1]
    proxy = copy(state.cards[cid]);proxy.oracle_text = body + tail
    key, payload = infer_effect_from_oracle(state, proxy, 1)
    assert key == 'noop' and '__unsupported_instruction' in payload


@pytest.mark.parametrize('seat', [1, 2])
def test_component_nontoken_copy_keeps_inherent_token_self_reference(seat):
    from effects.registry import resolve_effect
    from rules_engine.copiable_values import apply, values
    from rules_engine.state_based_actions import apply_state_based_actions
    state = entry.position(seat)
    saga = entry.add(state, "Urza's Saga", seat, Zone.BATTLEFIELD)
    recipient = entry.add(state, 'Ornithopter', seat, Zone.BATTLEFIELD)
    body = extract_saga_chapters(state.cards[saga].oracle_text)[1]['text'].split(': ', 1)[1][:-1]
    proxy = copy(state.cards[saga]);proxy.oracle_text = body
    key, payload = infer_effect_from_oracle(state, proxy, seat)
    before = set(state.cards)
    resolve_effect(state, seat, key, payload)
    token = state.cards[next(iter(set(state.cards)-before))]
    assert token.is_token and not state.cards[recipient].is_token
    apply(state.cards[recipient], values(token))
    assert not state.cards[recipient].is_token, 'Copying characteristics does not make a token'
    assert effective_power(state, recipient) == effective_toughness(state, recipient) == 2
    apply_state_based_actions(state)
    assert state.cards[recipient].zone == Zone.BATTLEFIELD
