"""Complete payment trials reuse selective copying without discarding history."""
from copy import deepcopy
import copy
import importlib
import importlib.util
import pickle

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from tests.test_mana_abilities import paid_position


def copier():
    assert importlib.util.find_spec('game_state.copying') is not None, 'Shared state copier missing'
    return importlib.import_module('game_state.copying').copy_match_state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('history', [0, 1024])
def test_default_copy_retains_full_history_rng_and_state_without_mutation(seat, history):
    state = paid_position(seat)
    state.log.extend(f'Historical diagnostic {i}' for i in range(history))
    before = serialize_match_snapshot(state)
    rng = state.rng.getstate()
    cloned = copier()(state)
    assert serialize_match_snapshot(cloned) == before
    assert cloned.rng.getstate() == rng and cloned.rng is not state.rng
    assert cloned.log == state.log and cloned.log is not state.log
    cloned.log.append('Speculative payment')
    cloned.players[seat].mana_pool['G'] = 123
    cloned.rng.random()
    assert serialize_match_snapshot(state) == before and state.rng.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_shared_metadata_attribute_aliases_cycles_and_siblings_are_isolated(seat):
    state = paid_position(seat)
    left, right = [state.cards[cid] for cid in state.players[seat].battlefield[:2]]
    metadata = [{'nested': [1]}]
    left.card_faces = right.card_faces = metadata
    left.copy_peer, right.copy_peer = right, left
    left.copy_attributes = right.__dict__
    state.history_alias = state.log
    before = pickle.dumps(state, protocol=5)
    clone, sibling = copier()(state), copier()(state)
    a, b = clone.cards[left.id], clone.cards[right.id]
    assert a.card_faces is b.card_faces and a.card_faces is not metadata
    assert a.copy_peer is b and b.copy_peer is a
    assert a.copy_attributes is b.__dict__
    assert clone.history_alias is clone.log and clone.log is not state.log
    a.card_faces[0]['nested'].append(2)
    clone.log.append('Trial-only history')
    assert sibling.cards[left.id].card_faces == metadata
    assert sibling.log == state.log and sibling.log is not state.log
    assert pickle.dumps(state, protocol=5) == before


def test_caller_memo_overrides_are_retained_without_mutating_the_memo():
    state = paid_position(1)
    explicit = ['Explicit caller view']
    memo = {id(state.log): explicit}
    original = dict(memo)
    cloned = copier()(state, memo=memo)
    assert memo == original and cloned.log is explicit
    from ai.pending_effects import planning_copy
    assert planning_copy(state, memo=memo).log is explicit


def test_ai_history_policy_stays_explicit_and_default_history_is_not_dropped():
    state = paid_position(1)
    state.log.append('Real retained history')
    from ai.pending_effects import planning_copy
    assert planning_copy(state).log == []
    assert copier()(state).log == state.log
    assert copier()(state, include_history=False).log == []


def test_ai_field_copy_ablation_hook_still_observes_actual_card_fields(monkeypatch):
    from ai import pending_effects
    state = paid_position(1)
    visited = []
    def reference(value, memo):
        visited.append(type(value))
        return deepcopy(value, memo)
    monkeypatch.setattr(pending_effects, '_copy_card_field', reference)
    clone = pending_effects.planning_copy(state)
    assert visited, 'Existing card-fields/hotpaths benchmark hook became inert'
    expected = serialize_match_snapshot(state)
    expected['log'] = []
    assert serialize_match_snapshot(clone) == expected


@pytest.mark.parametrize('ai_copy', [False, True])
def test_caller_attribute_dictionary_override_is_not_overwritten(ai_copy):
    state = paid_position(1)
    card = next(iter(state.cards.values()))
    replacement = {**card.__dict__, 'counters': {'charge': 99}}
    memo = {id(card.__dict__): replacement}
    before = dict(memo)
    if ai_copy:
        from ai.pending_effects import planning_copy
        copy_state = planning_copy
    else:
        copy_state = copier()
    clone = copy_state(state, memo=memo)
    assert clone.cards[card.id].counters == {'charge': 99}
    assert card.counters != {'charge': 99} and memo == before


def test_history_subclass_keeps_its_custom_deepcopy_contract():
    class History(list):
        def __deepcopy__(self, memo):
            result = History(['Custom history copy'])
            memo[id(self)] = result
            return result
    state = paid_position(1)
    state.log = History(['Original'])
    state.history_alias = state.log
    clone = copier()(state)
    assert type(clone.log) is History and clone.log == ['Custom history copy']
    assert clone.history_alias is clone.log and state.log == ['Original']


def test_mutable_history_string_subclass_is_not_shared_as_an_exact_string():
    class Entry(str):
        pass
    state = paid_position(1)
    entry = Entry('Annotated history')
    entry.notes = [1]
    state.log = [entry]
    clone = copier()(state)
    clone.log[0].notes.append(2)
    assert type(clone.log[0]) is Entry and entry.notes == [1]


def test_attribute_dictionary_subclass_keeps_its_custom_deepcopy_contract():
    class Attributes(dict):
        def __deepcopy__(self, memo):
            result = deepcopy(dict(self), memo)
            result['custom_attributes_used'] = True
            memo[id(self)] = result
            return result
    state = paid_position(1)
    card = next(iter(state.cards.values()))
    card.__dict__ = Attributes(card.__dict__)
    clone = copier()(state)
    assert clone.cards[card.id].custom_attributes_used is True
    assert not hasattr(card, 'custom_attributes_used')


def test_card_subclass_keeps_its_custom_deepcopy_contract():
    class CustomCard(CardInstance):
        def __deepcopy__(self, memo):
            result = object.__new__(type(self))
            memo[id(self)] = result
            result.__dict__ = deepcopy(self.__dict__, memo)
            result.custom_copy_used = True
            return result
    state = paid_position(1)
    card = CustomCard('custom', 'Copy-contract fixture', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    clone = copier()(state)
    assert type(clone.cards[card.id]) is CustomCard
    assert clone.cards[card.id].custom_copy_used is True
    assert not hasattr(card, 'custom_copy_used')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_planner_does_not_generically_reconstruct_exact_card_dictionaries(seat, monkeypatch):
    from rules_engine.mana import can_pay_with_pool_and_lands
    state = paid_position(seat)
    card_dicts = {id(card.__dict__) for card in state.cards.values()}
    original = copy._deepcopy_dispatch[dict]
    visits = []
    def counted(value, memo):
        if id(value) in card_dicts:
            visits.append(id(value))
        return original(value, memo)
    monkeypatch.setitem(copy._deepcopy_dispatch, dict, counted)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}')
    assert serialize_match_snapshot(state) == before
    assert visits == [], 'Payment trials still traverse every immutable card field through deepcopy'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cost', ['{G}', '{G}{G}{G}'])
def test_real_payment_plan_search_and_complete_commit_match_stdlib_reference(seat, cost, monkeypatch):
    from rules_engine import mana
    fast_copy = copier()
    state = paid_position(seat)
    state.log.extend(['Real prior history', 'Second retained entry'])
    before = serialize_match_snapshot(state)
    original_plan = mana._plan_payment
    traces = []
    def traced(current, actor, requirements, **context):
        traces[-1].append((tuple(sorted(requirements.items())),
                          tuple(sorted(context.get('excluded_sources') or ())),
                          tuple(sorted(context.get('reserved_card_ids') or ())),
                          context.get('protected_life', 0), context.get('optimize_paid', False)))
        return original_plan(current, actor, requirements, **context)
    results = []
    for implementation in (deepcopy, fast_copy):
        traces.append([])
        with monkeypatch.context() as patch:
            patch.setattr(mana, 'copy_match_state', implementation)
            patch.setattr(mana, '_plan_payment', traced)
            plan = mana._spell_payment_plan(state, seat, mana.parse_mana_cost(cost),
                payment_context=('spell', {'Creature'}), optimize_paid=True)
            committed = deepcopy(state)
            assert mana.auto_pay_cost(committed, seat, cost, spell_types={'Creature'})
            results.append((plan, serialize_match_snapshot(committed), committed.rng.getstate()))
    assert results[0] == results[1] and traces[0] == traces[1]
    assert traces[0] and serialize_match_snapshot(state) == before
