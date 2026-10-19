"""New paid core witnesses, not complete-card certification or warning waivers."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest
import domain_paid_support as g
import test_suncleanser_desired as sun
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.continuous import has_keyword, effective_power
from rules_engine.card_types import is_token_card

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1]
OUT = Path(os.environ['GAP6_EVIDENCE'])
CANON = json.loads((ROOT/'gap6/canonical-six.json').read_bytes())['cards']
RULES = RulesEngine()
ACTIONS = []

@pytest.fixture
def facts():
    ACTIONS.clear()
    rows = {}
    for relative in ('audit/gate2-springheart/fixtures/canonical.json',
                     'audit/gate2-stormdrake/canonical.json'):
        rows.update(json.loads((SOURCE/relative).read_bytes()))
    for directory in ('backend/tests/fixtures/archangel_pair', 'audit/gate2-suncleanser'):
        for path in (SOURCE/directory).glob('*.json'):
            raw = json.loads(path.read_bytes())
            if raw.get('object') == 'card':
                rows[raw['name']] = raw
    rows.update({name: value['canonical'] for name, value in CANON.items()})
    counter = json.loads((SOURCE/'audit/brainstorm/fixtures/counterspell.json').read_bytes())
    assert counter['object']=='card' and counter['name']=='Counterspell'
    assert counter['mana_cost']=='{U}{U}' and counter['oracle_text']=='Counter target spell.'
    rows[counter['name']] = counter
    original = deepcopy(rows)
    yield rows
    assert rows == original, 'Canonical input fixtures mutated'

def snapshot(state):
    return serialize_match_snapshot(state)

def act(state, seat, action):
    before = snapshot(state)
    result = checked_action(state, RULES, seat, deepcopy(action))
    assert snapshot(state) == before, 'Public action mutated its input'
    ACTIONS.append({'seat':seat,'action':deepcopy(action),
        'input_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
        'output_sha256':hashlib.sha256(json.dumps(snapshot(result),sort_keys=True).encode()).hexdigest(),
        'mana_before':{p:dict(v.mana_pool) for p,v in state.players.items()},
        'mana_after':{p:dict(v.mana_pool) for p,v in result.players.items()},
        'stack_after':[{'id':i.id,'source':i.source_card_id,'controller':i.controller,
                        'effect':i.effect_key,'payload':deepcopy(i.payload)} for i in result.stack]})
    return result

def offers(state, seat):
    before = snapshot(state)
    moves = RULES.legal_moves(state, seat)
    assert snapshot(state) == before
    # Only opponent-private operands are excluded; actor-owned choices are public to actor.
    encoded = json.dumps(moves)
    for cid in state.players[3-seat].hand + state.players[3-seat].library:
        assert cid not in encoded
    return moves

def private(state, seat):
    ids = state.players[seat].hand + state.players[seat].library
    return {'hand': list(state.players[seat].hand), 'library': list(state.players[seat].library),
            'cards': {cid: snapshot(state)['cards'][cid] for cid in ids}}

def cold(state):
    before = snapshot(state)
    result = g.restore(state)
    assert snapshot(result) == before
    return result

def priority(state, seat):
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    return state

def advance(state, predicate):
    for _ in range(96):
        if predicate(state):
            return state
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('96 public-pass bound')

def paid(state, seat, source, pool, targets=None, choice='base'):
    state = priority(state, seat)
    state.players[seat].mana_pool = dict(pool)
    assert state.cards[source].oracle_text == CANON[state.cards[source].name]['canonical']['oracle_text'] \
        if state.cards[source].name in CANON else True
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                              'cost_choice': {'id': choice}, 'targets': targets or {}})
    item = next(i for i in state.stack if i.source_card_id == source)
    assert state.cards[source].zone == Zone.STACK and item.controller == seat
    assert item.payload['mana_spent'] == sum(pool.values())
    assert sum(state.players[seat].mana_pool.values()) == 0
    return cold(state), item.id

def choose_target(state, seat, target):
    for _ in range(8):
        if not state.pending_trigger_order:
            return state
        moves = offers(state, seat)
        selected = [m for m in moves if m['type'] == 'choose_trigger_target'
                    and all(m.get(k) == v for k, v in target.items())]
        if selected:
            state = act(state, seat, selected[0])
        else:
            orders = [m for m in moves if m['type'] == 'choose_trigger_order']
            assert orders, 'Actual public target or order absent'
            state = act(state, seat, orders[0])
    raise AssertionError('8 target/order bound')

def record(request, state, card, clauses, **observed):
    path = OUT/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'.json')
    path.write_text(json.dumps({'node': request.node.nodeid, 'card': card,
        'canonical_oracle': CANON[card]['canonical']['oracle_text'],
        'witnessed_clauses': clauses, 'observed': observed, 'snapshot': snapshot(state),
        'checked_action_transcript':ACTIONS}, indent=2)+'\n')

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice,count,extra', [('base',0,{}), ('kicker_1',1,{'B':1}),
    ('kicker_2',1,{'R':1}), ('kicker_1_2',2,{'B':1,'R':1})])
def test_archangel_paid_core(facts, seat, choice, count, extra, request):
    original = deepcopy(facts)
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Archangel of Wrath', seat, Zone.HAND)
    hidden = private(state, 3-seat)
    state, frame = paid(state, seat, source, {'C':2,'W':2,**extra}, choice=choice)
    assert state.cards[source].kicker_count == count
    state = advance(state, lambda s: all(i.id != frame for i in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert has_keyword(state, source, 'flying') and has_keyword(state, source, 'lifelink')
    state = choose_target(cold(state), seat, {'target_player':3-seat})
    assert len(state.stack) == count
    state = advance(cold(state), lambda s: not s.stack)
    assert state.players[seat].life == 20+2*count
    assert state.players[3-seat].life == 20-2*count
    assert private(state, 3-seat) == hidden and facts == original
    record(request, state, 'Archangel of Wrath', ['paired public cost', 'flying/lifelink',
        'independent kicked entry damage'], count=count, choice=choice)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['plain', 'bestow-pay', 'bestow-decline'])
def test_springheart_paid_landfall_core(facts, seat, route, request):
    state = g.position(facts, seat)
    host = g.add(state, facts, 'Raging Goblin', seat)
    source = g.add(state, facts, 'Springheart Nantuko', seat, Zone.HAND)
    land = g.add(state, facts, 'Forest', seat, Zone.HAND)
    hidden = private(state, 3-seat)
    power = effective_power(state, host)
    state, frame = paid(state, seat, source, {'C':1,'G':1},
        {'target_card_id':host} if route != 'plain' else {},
        'bestow' if route != 'plain' else 'base')
    state = advance(state, lambda s: all(i.id != frame for i in s.stack))
    assert state.cards[source].attached_to == (host if route != 'plain' else None)
    assert effective_power(state, host) == power+(route != 'plain')
    assert not any(is_token_card(state.cards[c]) for c in state.players[seat].battlefield)
    state = priority(cold(state), seat)
    state.players[seat].mana_pool = {'C':1,'G':1}
    state = act(state, seat, {'type':'play_land', 'card_id':land})
    assert state.cards[land].zone == Zone.BATTLEFIELD
    state = advance(state, lambda s: s.pending_mechanic_choice or s.pending_trigger_order or not s.stack)
    if route != 'plain' or state.pending_trigger_order:
        moves = offers(state, seat)
        selected = [m for m in moves if m['type'] in {'choose_mechanic','choose_optional_effect'}
                    and m.get('accept') is (route != 'bestow-decline')]
        assert len(selected) == 1, 'Real advertised optional action absent/ambiguous'
        state = act(cold(state), seat, selected[0])
    state = advance(cold(state), lambda s: not s.stack and not s.pending_mechanic_choice)
    tokens = [state.cards[c] for c in state.players[seat].battlefield if is_token_card(state.cards[c])]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.power == token.toughness == 1
    if route == 'bestow-pay':
        assert token.name == facts['Raging Goblin']['name']
        assert token.oracle_text == facts['Raging Goblin']['oracle_text']
        assert sum(state.players[seat].mana_pool.values()) == 0
    else:
        assert 'Insect' in token.type_line and token.colors == ['G']
        assert sum(state.players[seat].mana_pool.values()) == 2
    assert private(state, 3-seat) == hidden
    record(request, cold(state), 'Springheart Nantuko', ['paid plain/bestow',
        'attached buff', 'actual land entry', 'copy payment or fallback'], route=route)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['creature', 'player'])
def test_suncleanser_paid_modal_core(facts, seat, mode, request):
    state, target = sun.prepare(facts, seat, mode)
    assert sun.count(state, mode, target) == 1, 'Independent actual counter cause required'
    source = g.add(state, facts, 'Suncleanser', seat, Zone.HAND)
    state, frame = paid(state, seat, source, {'C':1,'W':1})
    state = advance(state, lambda s: all(i.id != frame for i in s.stack))
    assert state.pending_mechanic_choice['kind'] == 'entry_mode'
    moves = offers(cold(state), seat)
    options = sun.public_mode_options(moves, seat, mode)
    assert len(options) == 1
    state = act(state, seat, {'type':'choose_mechanic','choice_id':options[0]})
    state = choose_target(cold(state), seat,
        {'target_card_id':target} if mode == 'creature' else {'target_player':target})
    state = advance(state, lambda s: not s.stack)
    assert sun.count(state, mode, target) == 0
    assert len(state.retained_counter_prohibitions) == 1
    state = sun.placement(cold(state), facts, seat, mode, target)
    assert sun.count(state, mode, target) == 0, 'Actual second counter cause must be prevented'
    record(request, cold(state), 'Suncleanser', ['paid entry', 'public modal target',
        'all-counter removal', 'actual counter prevention'], mode=mode)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ability', [0, 1, 2])
def test_emperor_paid_flash_loyalty_core(facts, seat, ability, request):
    state = g.position(facts, seat)
    state.active_player = 3-seat
    state.step = Step.END_STEP
    source = g.add(state, facts, 'The Wandering Emperor', seat, Zone.HAND)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    state.cards[target].tapped = True
    hidden = private(state, 3-seat)
    state, frame = paid(state, seat, source, {'C':2,'W':2})
    state = advance(state, lambda s: all(i.id != frame for i in s.stack))
    state = priority(cold(state), seat)
    action = {'type':'activate_loyalty','card_id':source,'ability_index':ability,
              'targets':{'target_card_id':target} if ability != 1 else {}}
    assert any(m['type']=='activate_loyalty' and m.get('ability_index')==ability
               for m in offers(state, seat))
    old_board = set(state.players[seat].battlefield)
    state = act(state, seat, action)
    assert state.cards[source].loyalty == [4,2,1][ability]
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, seat, action)
    assert snapshot(state) == before
    state = advance(cold(state), lambda s: not s.stack)
    if ability == 0:
        assert state.cards[target].counters['+1/+1'] == 1 and has_keyword(state, target, 'first strike')
    elif ability == 1:
        tokens = [state.cards[c] for c in set(state.players[seat].battlefield)-old_board]
        assert len(tokens)==1 and tokens[0].power==tokens[0].toughness==2
        assert has_keyword(state, tokens[0].id, 'vigilance')
    else:
        assert state.cards[target].zone==Zone.EXILE and state.players[seat].life==22
    assert private(state, 3-seat)==hidden
    record(request, cold(state), 'The Wandering Emperor', ['paid opponent-turn flash',
        'entry-turn instant loyalty permission', 'loyalty debit/effect', 'repeated use rejection'], ability=ability)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['no-blue', 'blue-bounce', 'counter'])
def test_veil_paid_response_core(facts, seat, case, request):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Veil of Summer', seat, Zone.HAND)
    target = g.add(state, facts, 'Raging Goblin', seat)
    response = protected = None
    if case == 'counter':
        bolt = g.add(state, facts, 'Lightning Bolt', seat, Zone.HAND)
        state, protected = paid(state, seat, bolt, {'R':1}, {'target_player':3-seat})
        counter = g.add(state, facts, 'Counterspell', 3-seat, Zone.HAND)
        state, response = paid(state, 3-seat, counter, {'U':2}, {'target_stack_id':protected})
    elif case == 'blue-bounce':
        bounce = g.add(state, facts, 'Unsummon', 3-seat, Zone.HAND)
        state, response = paid(state, 3-seat, bounce, {'U':1}, {'target_card_id':target})
    hidden = private(state, 3-seat)
    library = list(state.players[seat].library)
    state, frame = paid(state, seat, source, {'G':1})
    state = advance(state, lambda s: all(i.id!=frame for i in s.stack))
    assert state.players[seat].library == (library if case=='no-blue' else library[:-1])
    if case != 'no-blue':
        assert library[-1] in state.players[seat].hand
        state = advance(cold(state), lambda s: all(i.id!=response for i in s.stack))
        if case == 'counter':
            assert any(i.id==protected for i in state.stack)
        else:
            assert state.cards[target].zone==Zone.BATTLEFIELD
    assert private(state, 3-seat)==hidden
    record(request, cold(state), 'Veil of Summer', ['paid response', 'actual cast-color draw condition',
        'uncounterable spell or blue permanent shield'], case=case)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pay', [False, True])
def test_stormdrake_paid_exchange_core(facts, seat, pay, request):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Volatile Stormdrake', seat, Zone.HAND)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    own = g.add(state, facts, 'Raging Goblin', seat)
    land = g.add(state, facts, 'Forest', 3-seat)
    hidden = private(state, 3-seat)
    state, frame = paid(state, seat, source, {'C':1,'U':1})
    state = advance(state, lambda s: all(i.id!=frame for i in s.stack))
    moves = offers(cold(state), seat)
    selected = [m for m in moves if m['type']=='choose_trigger_target' and m.get('target_card_id')==target]
    assert len(selected)==1
    for invalid in (own, land):
        before = snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RULES, seat, {**selected[0],'target_card_id':invalid})
        assert snapshot(state)==before
    state = act(state, seat, selected[0])
    state = advance(state, lambda s: s.pending_mechanic_choice or not s.stack)
    assert state.cards[source].controller==3-seat and state.cards[target].controller==seat
    assert state.players[seat].counters['energy']==4
    assert state.pending_mechanic_choice['kind']=='exchange_energy_payment'
    moves = offers(cold(state), seat)
    option = 'pay' if pay else 'decline'
    assert any(option in m.get('options',[]) for m in moves)
    state = act(state, seat, {'type':'choose_mechanic','choice_id':option})
    state = advance(cold(state), lambda s: not s.stack and not s.pending_mechanic_choice)
    assert state.players[seat].counters['energy']==(3 if pay else 4)
    assert state.cards[target].owner==3-seat and state.cards[source].owner==seat
    assert state.cards[target].zone==(Zone.BATTLEFIELD if pay else Zone.GRAVEYARD)
    if not pay:
        assert target in state.players[3-seat].graveyard
    assert private(state, 3-seat)==hidden
    record(request, cold(state), 'Volatile Stormdrake', ['paid entry', 'opponent creature target',
        'exchange ownership', 'four energy', 'public payment or foreign-owner sacrifice'], pay=pay)
