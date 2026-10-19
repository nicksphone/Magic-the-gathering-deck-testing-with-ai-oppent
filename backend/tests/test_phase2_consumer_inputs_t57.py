"""Real canonical consumers; transport negatives are not card or outcome facts."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge import service as advice
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.mana import can_pay_with_pool_and_lands, repeatable_nonland_mana_outputs
from tests.library_canonical_fixtures import raw_card


DATA = (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RAW = {row['name']: row for row in map(json.loads, DATA.splitlines())}


def _raw(name):
    return deepcopy(RAW[name]) if name in RAW else raw_card(name)


def _entry(name, quantity, profiled):
    raw = _raw(name)
    image = ScryfallSyncService._extract_remote_image_uri(raw)
    assert image, 'Full canonical fixture must already have a remote image operand'
    normalized = ScryfallSyncService._normalize_payload(raw, image)
    entry = {**raw, **normalized, 'card_name': name, 'quantity': quantity,
             'colors': deepcopy(raw['colors']),
             'card_faces': json.loads(normalized['card_faces_json'])}
    if profiled:
        row = SimpleNamespace(name=name, scryfall_id=raw['id'], oracle_source='scryfall',
                              profiles_json=json.dumps(merge_profile_payload(
                                  {'card_data': raw, 'rulings_verified': False}, derive_profile(raw))))
        entry['knowledge_snapshot'] = advice.snapshot_for(row, name, entry)
        assert entry['knowledge_snapshot']
    return entry


def _pose(state, card, zone):
    player = state.players[card.owner]
    getattr(player, card.zone.value).remove(card.id)
    getattr(player, zone.value).append(card.id)
    card.move_to_zone(zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False


def _born(seat, own_names, opposing_names=(), *, profiled=True):
    own = [_entry(name, 4, profiled) for name in own_names] + [_entry('Forest', 24, profiled)]
    other = [_entry(name, 4, profiled) for name in opposing_names] + [_entry('Forest', 24, profiled)]
    state = MatchFactory.from_decks(own if seat == 1 else other,
                                   other if seat == 1 else own, seed=731,
                                   game_id='phase2-consumer-inputs')
    birth_facts = deepcopy(state.sideboard_facts)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 7
    for player in state.players.values():
        for cid in list(player.hand):
            _pose(state, state.cards[cid], Zone.LIBRARY)
    assert state.sideboard_facts == birth_facts
    assert all(card.characteristic_record for card in state.cards.values())
    return state


def _card(state, name, owner):
    return next(card for card in state.cards.values() if card.name == name and card.owner == owner)


def _act(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def _settle(state):
    for _ in range(12):
        if not state.stack:
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order), 'Unexpected native continuation stays explicit'
        state = _act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Real stack did not settle within twelve checked passes')


def _tag_observations(actor, monkeypatch):
    original = actor._spell_tags
    hits = []

    def observe(card):
        tags = original(card)
        hits.append((sys._getframe(1).f_code.co_name, getattr(card, 'id', None), frozenset(tags)))
        return tags

    monkeypatch.setattr(actor, '_spell_tags', observe)
    return hits


def _blocking(seat, name):
    root = _born(seat, (name,), ('Grizzly Bears',))
    defender, attacker = _card(root, name, seat), _card(root, 'Grizzly Bears', 3 - seat)
    _pose(root, defender, Zone.BATTLEFIELD)
    _pose(root, attacker, Zone.BATTLEFIELD)
    root.active_player = root.priority_player = 3 - seat
    root.step = Step.DECLARE_ATTACKERS
    root = _act(root, 3 - seat, {'type': 'attack', 'attackers': [attacker.id],
                               'attack_targets': {attacker.id: 'player:' + str(seat)}})
    for _ in range(12):
        if root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat:
            break
        root = _act(root, root.priority_player, {'type': 'pass_priority'})
    assert root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat
    move = next(move for move in RulesEngine().legal_moves(root, seat) if move['type'] == 'block')
    move = {**move, 'blocks': {attacker.id: [defender.id]}}
    result = _act(root, seat, {'type': 'block', 'blocks': move['blocks']})
    assert defender.id in result.blocks.get(attacker.id, [])
    return root, defender.id, move


def _tokens(seat, *, profiled=True):
    state = _born(seat, ('Secure the Wastes',), profiled=profiled)
    source = _card(state, 'Secure the Wastes', seat)
    _pose(state, source, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'C': 3}
    return state, source.id


def _removal(seat):
    state = _born(seat, ('Go for the Throat',), ('Grizzly Bears',))
    source, target = _card(state, 'Go for the Throat', seat), _card(state, 'Grizzly Bears', 3 - seat)
    _pose(state, source, Zone.HAND)
    _pose(state, target, Zone.BATTLEFIELD)
    alternative = next(card for card in state.cards.values()
                       if card.name == target.name and card.owner == target.owner and card.id != target.id)
    _pose(state, alternative, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == source.id)
    assert target.id in {item['id'] for item in move['target_hints']['creature_targets']}
    return state, source.id, target.id, {**move, 'targets': {'target_card_id': target.id}}


class _RouteReads(tuple):
    def __new__(cls, routes, reads):
        result = super().__new__(cls, routes)
        result.reads = reads
        return result

    def __iter__(self):
        self.reads.append('iterate')
        return super().__iter__()

    def __getitem__(self, key):
        self.reads.append('select')
        return super().__getitem__(key)


@pytest.mark.parametrize('seat', [1, 2])
def test_block_bias_consumes_selected_canonical_ramp_role(seat, monkeypatch):
    root, cid, move = _blocking(seat, 'Llanowar Elves')
    before = serialize_match_snapshot(root)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    hits = _tag_observations(actor, monkeypatch)
    assert repeatable_nonland_mana_outputs(root.cards[cid], state=root) == {'G': 1}
    assert actor._block_bias(root, move, seat) == pytest.approx(-2.3)
    assert any(caller == '_block_bias' and source == cid and 'ramp' in tags
               for caller, source, tags in hits), 'Selected native mana classification bypassed knowledge roles'
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_ramp_role_does_not_invent_repeatable_mana_for_grazer(seat, monkeypatch):
    root, cid, move = _blocking(seat, 'Arboreal Grazer')
    before = serialize_match_snapshot(root)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    hits = _tag_observations(actor, monkeypatch)
    assert repeatable_nonland_mana_outputs(root.cards[cid], state=root) == {}
    assert actor._block_bias(root, move, seat) == pytest.approx(2.0)
    assert any(caller == '_block_bias' and source == cid and 'ramp' in tags
               for caller, source, tags in hits), 'Non-mana ramp control never reached the role consumer'
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_x_consumer_keeps_native_affordability_and_real_token_result(seat, monkeypatch):
    root, cid = _tokens(seat)
    before = serialize_match_snapshot(root)
    actor = AIAgent(difficulty='strong', archetype='Control')
    hits = _tag_observations(actor, monkeypatch)
    x = actor._choose_x_value(root, seat, root.cards[cid].mana_cost, card=root.cards[cid])
    assert x == 2
    assert can_pay_with_pool_and_lands(root, seat, root.cards[cid].mana_cost, x_value=x)
    assert not can_pay_with_pool_and_lands(root, seat, root.cards[cid].mana_cost, x_value=4)
    result = _act(root, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': {'x_value': x}})
    assert result.stack[-1].payload['mana_spent'] == 3
    result = _settle(result)
    assert result.cards[cid].zone == Zone.GRAVEYARD
    assert len([card for card in result.cards.values()
                if card.controller == seat and card.zone == Zone.BATTLEFIELD and card.is_token]) == 2
    assert {'_choose_x_value', '_score_x_value', '_minimum_useful_x_value'} <= {
        caller for caller, source, tags in hits if source == cid and 'token' in tags}
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_x_score_uses_roles_and_label_only_negative_is_not_a_birth(seat, monkeypatch):
    root, cid = _tokens(seat)
    before = serialize_match_snapshot(root)
    actor = AIAgent(difficulty='strong', archetype='Control')
    hits = _tag_observations(actor, monkeypatch)
    # Metadata-label perturbation only; the real Factory card/stock is untouched.
    alias = SimpleNamespace(**deepcopy(vars(root.cards[cid])))
    alias.name = 'Bolt display label, not a physical printing'
    assert actor._score_x_value(root, seat, alias, alias.mana_cost, 2, 3, 1) == pytest.approx(2.0)
    assert any(caller == '_score_x_value' and source == cid and 'token' in tags
               for caller, source, tags in hits), 'Direct X-score caller bypassed persisted roles'
    alias.oracle_text = ''  # Explicit negative surface mismatch, not canonical Oracle.
    assert 'burn' not in actor._spell_tags(alias)
    assert root.cards[cid].name == 'Secure the Wastes'
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_profile_at_birth_keeps_actual_decision_and_private_fallback(seat):
    known, cid = _tokens(seat)
    missing, other = _tokens(seat, profiled=False)
    assert cid == other
    before = [serialize_match_snapshot(state) for state in (known, missing)]
    decisions = [AIAgent(difficulty='strong', archetype='Control').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat) for state in (known, missing)]
    assert decisions[0].action == decisions[1].action
    assert decisions[0].knowledge_usage['persisted'] > 0
    assert decisions[1].knowledge_usage['fallback'] > 0
    assert decisions[1].knowledge_usage['fallback_reasons']['missing'] > 0
    for state, decision, original in zip((known, missing), decisions, before):
        encoded = json.dumps(decision.knowledge_usage)
        assert not any(key in encoded for key in ('source_sha256', 'oracle_id', 'Secure', 'token'))
        assert 'knowledge_snapshot' not in json.dumps(serialize_match(state))
        _act(state, seat, decision.action)
        assert serialize_match_snapshot(state) == original


@pytest.mark.parametrize('seat', [1, 2])
def test_removal_reads_compiled_route_before_real_checked_paid_destroy(seat, monkeypatch):
    root, cid, target, move = _removal(seat)
    before = serialize_match_snapshot(root)
    original, reads = advice.estimate_for, []
    actual = original(root.cards[target])
    assert any(route.effect_key == 'destroy_permanent' for route in actual.routes)

    def observed(card):
        value = original(card)
        return (replace(value, routes=_RouteReads(value.routes, reads))
                if value is not None and getattr(card, 'id', None) == target else value)

    monkeypatch.setattr(advice, 'estimate_for', observed)
    assert AIAgent(difficulty='strong', archetype='Midrange')._premium_removal_priority(root, move, seat) is False
    assert reads, 'Tier-only advice bypassed the actual compiled answer routes'
    result = _act(root, seat, {'type': 'cast_spell', 'card_id': cid,
                               'targets': {'target_card_id': target}})
    assert result.stack[-1].payload['mana_spent'] == 2
    result = _settle(result)
    assert result.cards[target].zone == result.cards[cid].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_route_transport_is_unavailable_not_a_native_target_veto(seat, monkeypatch):
    root, cid, target, move = _removal(seat)
    before = serialize_match_snapshot(root)
    original = advice.estimate_for
    actual = original(root.cards[target])
    route = next(route for route in actual.routes if route.effect_key == 'destroy_permanent')
    # Advice-transport protocol negatives, never changed canonical card facts.
    for routes in ((), (replace(route, target_zone='stack'),),
                   (replace(route, targeted=False),),
                   (replace(route, conditions=route.conditions + ('unreviewed-condition',)),)):
        def unavailable(card):
            value = original(card)
            return (replace(value, routes=routes)
                    if value is not None and getattr(card, 'id', None) == target else value)

        monkeypatch.setattr(advice, 'estimate_for', unavailable)
        actor = AIAgent(difficulty='strong', archetype='Midrange')
        assert actor._premium_removal_priority(root, move, seat) is None
        native = _act(root, seat, {'type': 'cast_spell', 'card_id': cid,
                                   'targets': {'target_card_id': target}})
        assert native.stack[-1].source_card_id == cid
        assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_live_hexproof_stays_authoritative_before_advice_and_rejects_atomically(seat):
    root, cid, target, _ = _removal(seat)
    add_keyword_effect(root, target, ['hexproof'])
    before = serialize_match_snapshot(root)
    move = next(move for move in RulesEngine().legal_moves(root, seat)
                if move['type'] == 'cast_spell' and move.get('card_id') == cid)
    assert target not in {item['id'] for item in move['target_hints']['creature_targets']}
    request = {'type': 'cast_spell', 'card_id': cid, 'targets': {'target_card_id': target}}
    assert AIAgent(difficulty='strong', archetype='Midrange')._premium_removal_priority(
        root, {**move, 'targets': request['targets']}, seat) is None
    with pytest.raises(ActionRejected):
        checked_action(root, RulesEngine(), seat, request)
    assert serialize_match_snapshot(root) == before
