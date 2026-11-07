"""Canonical cost/tax query boundaries; no game rollout or learned binding."""
from copy import deepcopy
import json
from pathlib import Path
import pickle
import pytest

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine import hooks, basic_land_layer, query_context
from rules_engine.continuous import printed_abilities_suppressed
from tests.ai_information76_canonical import deck_entry

FIXTURES=Path(__file__).resolve().parent/'fixtures'
METRICS=[]


def position(seat):
    deck=[deck_entry('Island',8)]
    state=MatchFactory.from_decks(deck,deck,seed=703)
    state.pregame_pending=False; state.kept_hands={1,2}
    state.active_player=state.priority_player=seat; state.step=Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for _ in range(3):
            cid=player.hand.pop(); card=state.cards[cid]
            card.move_to_zone(Zone.BATTLEFIELD); player.battlefield.append(cid)
            assign_static_order_on_battlefield_entry(state,cid)
    def add(raw,owner,zone):
        assert raw['object']=='card'
        sample=MatchFactory.from_decks([{**raw,'card_name':raw['name'],'quantity':1}],[],seed=0)
        card=next(iter(sample.cards.values())); card.id=state.allocate_object_id()
        card.owner=card.controller=owner; card.move_to_zone(zone)
        state.cards[card.id]=card; getattr(state.players[owner],zone.value).append(card.id)
        if zone==Zone.BATTLEFIELD: assign_static_order_on_battlefield_entry(state,card.id)
        return card
    fixtures=FIXTURES
    tax=add(json.loads((fixtures/'chandra_complete/thalia.raw.json').read_bytes()),3-seat,Zone.BATTLEFIELD)
    raw=next(row for row in json.loads((fixtures/'graveyard_permissions/canonical.json').read_bytes())['data']
             if row['name']=='Humility')
    humility=add(raw,seat,Zone.EXILE)
    return state,tax,humility


def move(state,card,zone):
    getattr(state.players[card.owner],card.zone.value).remove(card.id)
    card.move_to_zone(zone); getattr(state.players[card.owner],zone.value).append(card.id)
    if zone==Zone.BATTLEFIELD: assign_static_order_on_battlefield_entry(state,card.id)


def context(state,seat):
    return hooks.CostContext(player_id=seat,card_name='Lightning Bolt',mana_cost='{R}',
                             state=state,spell_types={'Instant'},spell_colors={'R'})


@pytest.mark.parametrize('seat',[1,2])
def test_one_readonly_tax_batch_builds_one_layer_view(seat,monkeypatch):
    state,tax,humility=position(seat); before=pickle.dumps(state,protocol=5)
    original=basic_land_layer._printed_layer_four_effect; scanned=[]
    def observed(text):
        scanned.append(text); return original(text)
    monkeypatch.setattr(basic_land_layer,'_printed_layer_four_effect',observed)
    count=sum(len(player.battlefield) for player in state.players.values())
    value=context(state,seat); result=hooks._apply_static_spell_taxes(value)
    assert result is value and value.generic_increase==1 and value.generic_reduction==0
    assert pickle.dumps(state,protocol=5)==before
    assert query_context._query.get() is None
    METRICS.append({'seat':seat,'battlefield_cards':count,'layer_scan_card_visits':len(scanned)})
    assert len(scanned)<=count, (len(scanned),count)


@pytest.mark.parametrize('seat',[1,2])
def test_humility_and_tax_changes_are_fresh_between_calls(seat):
    state,tax,humility=position(seat)
    def cost(expected):
        before=pickle.dumps(state,protocol=5)
        value=hooks._apply_static_spell_taxes(context(state,seat))
        assert value.generic_increase==expected
        assert pickle.dumps(state,protocol=5)==before
        assert query_context._query.get() is None
    cost(1); move(state,humility,Zone.BATTLEFIELD); cost(0)
    move(state,humility,Zone.EXILE); cost(1)
    move(state,tax,Zone.GRAVEYARD); cost(0)
    move(state,tax,Zone.BATTLEFIELD); cost(1)


@pytest.mark.parametrize('seat',[1,2])
def test_registered_modifier_mutates_before_after_nested_helper_without_stale_queries(seat):
    state,tax,humility=position(seat); registered=list(hooks._COST_MODIFIERS); calls=[]
    def modifier(value):
        assert query_context._query.get() is None, 'Cost callback must not inherit a new batch scope'
        calls.append('entered')
        move(state,humility,Zone.BATTLEFIELD)
        nested=hooks._apply_static_spell_taxes(context(state,seat))
        assert nested.generic_increase==0
        assert query_context._query.get() is None
        assert printed_abilities_suppressed(state,tax.id)
        move(state,humility,Zone.EXILE)
        assert not printed_abilities_suppressed(state,tax.id), 'Query after callback mutation must be fresh'
        assert hooks._apply_static_spell_taxes(context(state,seat)).generic_increase==1
        calls.append('returned'); return value
    try:
        hooks.register_cost_modifier(modifier)
        for _ in range(2):
            value=context(state,seat)
            assert hooks.apply_cost_modifiers(value) is value
            assert value.generic_increase==1
        assert calls==['entered','returned','entered','returned']
        assert query_context._query.get() is None
    finally: hooks._COST_MODIFIERS[:]=registered


def test_scope_restores_on_helper_and_registered_callback_exceptions(monkeypatch):
    state,tax,humility=position(1); outer,_,_=position(2)
    error=TimeoutError('native helper interruption'); original=hooks.spell_cost_modifier
    def fail(text): raise error
    with query_context.rule_query_scope(outer):
        parent=query_context._query.get()
        monkeypatch.setattr(hooks,'spell_cost_modifier',fail)
        with pytest.raises(TimeoutError) as caught: hooks._apply_static_spell_taxes(context(state,1))
        assert caught.value is error and query_context._query.get() is parent
        monkeypatch.setattr(hooks,'spell_cost_modifier',original)
    assert query_context._query.get() is None
    registered=list(hooks._COST_MODIFIERS); calls=[]
    def modifier(value):
        calls.append(1); assert query_context._query.get() is None; raise error
    try:
        hooks.register_cost_modifier(modifier)
        with pytest.raises(TimeoutError) as caught: hooks.apply_cost_modifiers(context(state,1))
        assert caught.value is error and calls==[1] and query_context._query.get() is None
    finally: hooks._COST_MODIFIERS[:]=registered


def test_early_returns_and_existing_parent_scope_are_unchanged():
    for value in (hooks.CostContext(1,'none',''),hooks.CostContext(1,'ability','',is_spell=False)):
        before=deepcopy(vars(value))
        assert hooks._apply_static_spell_taxes(value) is value and vars(value)==before
        assert query_context._query.get() is None
    state,tax,humility=position(1)
    with query_context.rule_query_scope(state):
        parent=query_context._query.get()
        value=hooks._apply_static_spell_taxes(context(state,1))
        assert value.generic_increase==1 and query_context._query.get() is parent
    assert query_context._query.get() is None
