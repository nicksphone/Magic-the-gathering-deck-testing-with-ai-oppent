"""NEW strict canonical library-choice boundary ledger, not policy certification."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_activated_top_selection import position as base_position, card
from tests.test_private_choice_intent_boundary import environment, owned_disposable_source_only


ROOT = Path(__file__).parent / 'fixtures'
CARDS = ('Opt', 'Preordain', 'Consider', 'Notion Rain', 'Impulse', 'Memory Deluge')
ORDER_CARDS = ('Preordain', 'Notion Rain', 'Impulse')
PHASES = [(name, False) for name in CARDS] + [(name, True) for name in ORDER_CARDS]
ENGINE = RulesEngine()


def raw(name):
    if name == 'Preordain':
        row = json.loads((ROOT / 'library_choice_audit/preordain.json').read_text())
    elif name in ('Consider', 'Notion Rain'):
        row = next(x for x in json.loads((ROOT / 'surveil_mill.json').read_text()) if x['name'] == name)
    else:
        row = json.loads((ROOT / ('activated_top_selection/' + name.lower().replace(' ', '-') + '.json')).read_text())
    assert row['name'] == name and row['oracle_id'] and row['uri'].startswith('https://api.scryfall.com/cards/')
    assert row['oracle_text'] and row['mana_cost'] and row['type_line']
    return row


def action(ids):
    return {'type': 'choose_mechanic', 'card_ids': list(ids)}


def explicit(state, strategy=0):
    pending = state.pending_mechanic_choice
    options = pending['options']
    if pending['kind'] in {'scry', 'surveil'}:
        ids = [] if strategy == 0 else options[:1] if strategy == 1 else list(reversed(options))
    elif pending['kind'] == 'look_top_select_hand':
        ids = list(reversed(options))[:pending['count']]
    else:
        ids = list(reversed(options))
    return action(ids)


def position(name, seat, order=False):
    state, _, outside, _ = base_position(seat)
    foreign = card(state, 'forest', 3-seat, Zone.HAND).id
    row = raw(name)
    sample = MatchFactory.from_decks([{**row, 'card_name': name, 'quantity': 1}], [], seed=17)
    spell = deepcopy(next(iter(sample.cards.values())))
    spell.id = state.allocate_object_id()
    spell.owner = spell.controller = seat
    spell.move_to_zone(Zone.HAND)
    state.cards[spell.id] = spell
    state.players[seat].hand.append(spell.id)
    assert spell.name == name and spell.oracle_text == row['oracle_text']
    assert spell.mana_cost == row['mana_cost'] and spell.type_line == row['type_line']
    state.players[seat].mana_pool = {'U': 4, 'B': 2, 'C': 6}
    hint = next(x for x in ENGINE.legal_moves(deepcopy(state), seat)
                if x['type'] == 'cast_spell' and x['card_id'] == spell.id)
    cast = {'type': 'cast_spell', 'card_id': spell.id, 'targets': {},
            'cost_choice': {'id': hint['cost_options'][0]['id']}}
    state = checked_action(state, ENGINE, seat, cast)
    for _ in range(4):
        if state.pending_mechanic_choice:
            break
        state = checked_action(state, ENGINE, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice and state.cards[spell.id].zone == Zone.STACK
    if order:
        state = checked_action(state, ENGINE, seat, explicit(state))
        assert state.pending_mechanic_choice['kind'] in {'scry_top_order', 'surveil_top_order', 'topdeck_bottom_order'}
    return state, spell.id, outside, foreign


def expected_transition(state, chosen):
    """Exact partition/order and canonical downstream instructions, not fallback."""
    pending = deepcopy(state.pending_mechanic_choice)
    seat = pending['player_id']
    library = list(state.players[seat].library)
    hand = list(state.players[seat].hand)
    grave = list(state.players[seat].graveyard)
    life = state.players[seat].life
    source = next(c for c in state.cards.values() if c.zone == Zone.STACK and c.controller == seat)
    ids = chosen['card_ids']
    result = checked_action(state, ENGINE, seat, chosen)
    if result.pending_mechanic_choice:
        if pending['kind'] in {'scry', 'surveil'}:
            assert result.players[seat].library == library
            assert result.players[seat].hand == hand and result.players[seat].graveyard == grave
            assert result.cards[source.id].zone == Zone.STACK
        else:
            assert pending['kind'] == 'look_top_select_hand'
            assert result.pending_mechanic_choice['kind'] == 'topdeck_bottom_order'
            assert result.players[seat].hand == hand + ids
            rest = [cid for cid in pending['top_ids'] if cid not in ids]
            assert result.players[seat].library == rest + library[:-len(pending['top_ids'])]
            assert result.players[seat].graveyard == grave and result.cards[source.id].zone == Zone.STACK
        return result
    if pending['kind'] in {'scry', 'surveil', 'scry_top_order', 'surveil_top_order'}:
        top = pending['top_ids']
        bottom = pending.get('bottom_ids', ids)
        ordered = ids if pending['kind'].endswith('_top_order') else [cid for cid in reversed(top) if cid not in ids]
        remaining = library[:-len(top)] + list(reversed(ordered))
        if pending['kind'].startswith('scry'):
            remaining = list(bottom) + remaining
        else:
            assert result.players[seat].graveyard == grave + list(bottom) + [source.id]
        draws = 2 if source.name == 'Notion Rain' else 1
        assert result.players[seat].hand == hand + list(reversed(remaining[-draws:]))
        assert result.players[seat].library == remaining[:-draws]
        assert result.players[seat].life == life - (2 if source.name == 'Notion Rain' else 0)
        assert result.draws_this_turn[seat] == draws
    elif pending['kind'] == 'look_top_select_hand':
        assert result.players[seat].hand == hand + ids
        assert result.draws_this_turn[seat] == 0
        assert set(result.players[seat].library[:len(pending['top_ids'])-len(ids)]) == set(pending['top_ids']) - set(ids)
        assert result.players[seat].library[len(pending['top_ids'])-len(ids):] == library[:-len(pending['top_ids'])]
    else:
        assert pending['kind'] == 'topdeck_bottom_order'
        assert result.players[seat].library[:len(ids)] == ids
        assert result.players[seat].library[len(ids):] == library[len(ids):]
    assert result.cards[source.id].zone == Zone.GRAVEYARD
    assert not result.pending_mechanic_choice and not result.stack
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', CARDS)
@pytest.mark.parametrize('strategy', [0, 1, 2])
def test_actual_cast_minimal_choices_exact_continuation_and_replay(name, seat, strategy):
    state, _, _, _ = position(name, seat)
    env = environment(state)
    replay = environment(deserialize_match_snapshot(serialize_match_snapshot(state)))
    for _ in range(3):
        chosen = explicit(env._state, strategy)
        before = env.snapshot()
        assert env.lookup_intent(chosen, seat)['action'] == chosen
        assert env.lookup_intent({**chosen, 'choice_id': None, 'damage_assignment': None}, seat)['action'] == chosen
        assert env.snapshot() == before
        expected = expected_transition(env._state, chosen)
        assert env.step(chosen, seat) == replay.step(chosen, seat)
        assert serialize_match_snapshot(env._state) == serialize_match_snapshot(expected)
        assert env.snapshot() == replay.snapshot()
        if not env._state.pending_mechanic_choice:
            break
    assert not env._state.pending_mechanic_choice
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(chosen, seat)
    assert env.snapshot() == after


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
@pytest.mark.parametrize('surface', ['raw', 'policy'])
def test_whole_actual_views_preserve_only_explicit_choice(name, order, seat, surface):
    state, _, _, _ = position(name, seat, order)
    env = environment(state)
    view = (ENGINE.legal_moves(deepcopy(state), seat)[0] if surface == 'raw'
            else env.prompts(seat)[0]['hint'])
    chosen = explicit(state)
    original = deepcopy(view)
    before = env.snapshot()
    assert env.lookup_intent({**view, **chosen}, seat) == env.lookup(chosen, seat)
    assert view == original and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_private_owned_display_and_wrong_actor_before_helper(name, order, seat, monkeypatch):
    state, _, outside, foreign = position(name, seat, order)
    env = environment(state)
    before = env.snapshot()
    actor, other = env.observe(seat), env.observe(3-seat)
    options = state.pending_mechanic_choice['options']
    assert all(cid in actor['known_cards'] and cid not in other['known_cards'] for cid in options)
    assert all(cid not in actor['known_cards'] for cid in outside) and foreign not in json.dumps(actor)
    assert not other['pending_choice'].get('prompts', [])
    assert not ENGINE.legal_moves(deepcopy(state), 3-seat)
    for key in ('effect_payload', 'top_ids', 'resolving_item', 'controller', 'bottom_ids'):
        assert key not in json.dumps(actor['pending_choice'])
    assert env.snapshot() == before

    def forbidden(_):
        pytest.fail('Wrong actor reached complete_action')

    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(explicit(state), 3-seat)
    assert env.snapshot() == before


BAD = ({'unknown': None}, {'selected_card_ids': None}, {'selected_card_ids': {'card_ids': []}},
       {'targets': {'card_ids': []}}, {'card_ids': None}, {'card_ids': {'choice_id': None}},
       {'player_id': None}, {'resolving_item': {'unsupported_nested_alias': None}})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
@pytest.mark.parametrize('extra', BAD)
def test_unknown_null_aliases_reject_before_helper_and_preserve_roots(name, order, seat, extra, monkeypatch):
    state, _, _, _ = position(name, seat, order)
    env = environment(state)
    before = env.snapshot()
    request = {**explicit(state), **deepcopy(extra)}
    original = deepcopy(request)

    def forbidden(_):
        pytest.fail('Malformed alias reached complete_action')

    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_typed_unavailable_duplicates_and_stale_policy_hint_are_atomic(name, order, seat):
    state, _, _, foreign = position(name, seat, order)
    env = environment(state)
    before = env.snapshot()
    hint = env.prompts(seat)[0]['hint']
    option = state.pending_mechanic_choice['options'][0]
    for chosen in (action([foreign]), action([option, option])):
        with pytest.raises(ActionRejected):
            env.lookup_intent(chosen, seat)
        assert env.snapshot() == before
    chosen = explicit(state)
    env.step(chosen, seat)
    after = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, **chosen}, seat)
    assert env.snapshot() == after
