"""Full printed Coating, real paid responses, and explicit grammar protocols."""
from copy import copy
import hashlib
import json
from pathlib import Path

import pytest

from effects.handlers import grant_keyword
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.type_effects import copiable_types, effective_types
from tests.rules_printed_facts_e4 import raw_card as printed_raw
from tests.rings_activation_native_support_5763 import raw_card as rings_raw


HERE = Path(__file__).parent / 'fixtures'
PINS = {
    'Liquimetal Coating': ('graveyard_batch_boundary_bf62/liquimetal-coating.json',
        '46a05afaabda76ca082479ff42fe92d2d7954c5ff53b672b0c888dd5b613529d'),
    'Cloudshift': ('favor_target_lifecycle/cloudshift.json',
        'a6477d60b641d708f9447b8f53637a6701b02531fce76c6b04f9cb0fc6ded47b'),
    'Breeding Pool': ('targeted_search_resolver/breeding-pool.json',
        'e825eff4daebb7a9c09da81573b93a78285fb37eda2b199255f8dacec688ef70'),
}


def raw(name):
    if name in PINS:
        filename, digest = PINS[name]
        data = (HERE / filename).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        value = json.loads(data)
    elif name in {'Sol Ring', 'Grizzly Bears'}:
        value = rings_raw(name)
    else:
        value = printed_raw(name)
    assert value['object'] == 'card' and value['name'] == name
    return value


def board(seat):
    names = ['Liquimetal Coating', 'Forest', 'Grizzly Bears', 'Sol Ring',
             'Breeding Pool', 'Cloudshift', 'Disenchant']
    deck = [{**raw(name), 'card_name': name, 'quantity': 1} for name in names]
    deck.append({**raw('Island'), 'card_name': 'Island', 'quantity': 53})
    state = MatchFactory.from_decks(deck, deck, seed=937)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    return state


def place(state, name, owner, zone=Zone.BATTLEFIELD):
    card = next(card for card in state.cards.values()
                if card.owner == owner and card.name == name)
    for player in state.players.values():
        for field in ('hand', 'library', 'graveyard', 'exile', 'battlefield'):
            if card.id in getattr(player, field):
                getattr(player, field).remove(card.id)
    card.move_to_zone(zone)
    card.controller = owner
    card.summoning_sick = False
    getattr(state.players[owner], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def act(state, seat, kind, **fields):
    return checked_action(state, RulesEngine(), seat, {'type': kind, **fields})


def activate(state, seat, source, target):
    return act(state, seat, 'activate_ability', card_id=source, ability_index=0,
               targets={'target_card_id': target})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('name', ['Forest', 'Grizzly Bears', 'Sol Ring', 'Breeding Pool'])
def test_actual_tap_addition_snapshot_copiable_values_and_cleanup(seat, foreign, name):
    state = board(seat)
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, name, 3 - seat if foreign else seat)
    before = list(effective_types(state, target))
    state = activate(state, seat, source, target)
    assert state.cards[source].tapped
    assert effective_types(state, target) == before
    assert len(state.stack) == 1
    assert resolve_top_of_stack(state)
    assert effective_types(state, target) == list(dict.fromkeys([*before, 'Artifact']))
    assert copiable_types(state.cards[target]) == before
    assert len(state.cards[target].type_effects) == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert 'Artifact' in effective_types(state, target)
    assert copiable_types(state.cards[target]) == before
    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    assert state.step == Step.CLEANUP
    assert effective_types(state, target) == before
    assert state.cards[target].type_effects == []


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_cloudshift_response_does_not_artifactize_a_reentered_object(seat):
    state = board(seat)
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, 'Grizzly Bears', 3 - seat)
    spell = place(state, 'Cloudshift', 3 - seat, Zone.HAND)
    sequence = state.cards[target].zone_change_sequence
    state = activate(state, seat, source, target)
    state = act(state, seat, 'pass_priority')
    state.players[3 - seat].mana_pool = {'W': 1}
    state = act(state, 3 - seat, 'cast_spell', card_id=spell,
                targets={'target_card_id': target})
    assert state.players[3 - seat].mana_pool.get('W', 0) == 0
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].zone_change_sequence == sequence + 2
    assert resolve_top_of_stack(state)
    assert 'Artifact' not in effective_types(state, target)
    assert state.cards[target].type_effects == []


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_disenchant_source_departure_does_not_cancel_its_ability(seat):
    state = board(seat)
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, 'Forest', seat)
    spell = place(state, 'Disenchant', 3 - seat, Zone.HAND)
    state = activate(state, seat, source, target)
    state = act(state, seat, 'pass_priority')
    state.players[3 - seat].mana_pool = {'C': 1, 'W': 1}
    state = act(state, 3 - seat, 'cast_spell', card_id=spell,
                targets={'target_card_id': source})
    assert sum(state.players[3 - seat].mana_pool.values()) == 0
    assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert resolve_top_of_stack(state)
    assert set(effective_types(state, target)) == {'Land', 'Artifact'}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keyword', ['hexproof', 'protection from artifacts'])
def test_native_resolved_protection_protocol_rejects_atomically(seat, keyword):
    state = board(seat)
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, 'Grizzly Bears', 3 - seat)
    # Effective-ability primitive, not an invented named-card Oracle body.
    grant_keyword(state, 3 - seat, {'target_card_id': target, 'keyword': keyword})
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        activate(state, seat, source, target)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_kind', ['unknown', 'missing', 'hand'])
def test_invalid_target_is_root_pure_without_paying_tap(seat, target_kind):
    state = board(seat)
    source = place(state, 'Liquimetal Coating', seat)
    target = place(state, 'Forest', seat, Zone.HAND) if target_kind == 'hand' else (
        None if target_kind == 'missing' else 'not-an-object')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        activate(state, seat, source, target)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('suffix', [
    ' Draw a card.', ' (Draw a card.)', ' If you do, draw a card.',
    '\nThen destroy it.', ' unless you pay {1}.',
])
def test_noncanonical_complete_body_suffix_protocol_never_grants_partial_type(suffix):
    state = board(1)
    source = place(state, 'Liquimetal Coating', 1)
    target = place(state, 'Forest', 1)
    proxy = copy(state.cards[source])
    proxy.types = []
    proxy.oracle_text = raw('Liquimetal Coating')['oracle_text'].split(': ', 1)[1] + suffix
    key, payload = infer_effect_from_oracle(state, proxy, 1, {'target_card_id': target})
    assert key == 'noop'
    assert '__unsupported_instruction' in payload
