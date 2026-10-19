"""Trusted unit resources; paid checked episodes, NOT natural BO3/strength proof."""
from collections import Counter
from copy import deepcopy
from random import Random

from ai.agent import AIAgent
from ai.sideboard_facts import record_accepted_action
from card_data.hydration import hydrate_deck_cards, ready_for_match
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, draw_card
from main import MatchController, _post_step_finalize, _controller_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


def ready_deck(entries):
    """Declared known offline route, not fabricated persisted advice/coverage."""
    rows = hydrate_deck_cards(None, entries)
    for row in rows:
        row['match_ready'] = ready_for_match(row)
        assert row['match_ready'] and row['card_data_sources'] == ['offline_seed']
    return rows


def assert_play_draw_rejections(client, match):
    """Real missing/wrong human-seat requests cannot mutate the full root."""
    for operand in (None, {'player_id': 1, 'play_first': True}):
        before = deepcopy((serialize_match_snapshot(match.state), _controller_snapshot(match)))
        response = client.post(f'/matches/{match.state.id}/next-game',
                               **({'json': operand} if operand is not None else {}))
        assert response.status_code == 422
        assert response.json()['detail']['code'] == 'play_draw_choice_required'
        assert (serialize_match_snapshot(match.state), _controller_snapshot(match)) == before


def checked(match, pid, action):
    before = serialize_match_snapshot(match.state)
    result = checked_action(match.state, match.rules, pid, action)
    assert serialize_match_snapshot(match.state) == before
    record_accepted_action(match.state, result, pid, action)
    match.state = result


def settle(match):
    for _ in range(40):
        if not match.state.stack or match.state.winner is not None:
            return
        checked(match, match.state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Checked stack did not settle')


def draw_named(state, pid, wanted):
    """Ordinary original-order draws only; no source rename or hand injection."""
    for _ in range(60):
        names = [state.cards[cid].name for cid in state.players[pid].hand]
        if all(names.count(name) >= qty for name, qty in wanted.items()):
            return
        assert state.players[pid].library, 'Declared stock did not provide fixture hand'
        draw_card(state, pid)
    raise AssertionError('Ordinary draws did not provide declared stock')


def birth_order(rows, opening, permutation):
    """Declared unit stock order BEFORE Factory: fields/quantities unchanged."""
    stock = [dict(row, quantity=1) for row in rows for _ in range(row['quantity'])]
    ordered = [None] * len(stock)
    slots = iter(permutation[-7:])
    for name, count in opening.items():
        for _ in range(count):
            index = next(i for i, row in enumerate(stock) if row['card_name'] == name)
            ordered[next(slots)] = stock.pop(index)
    rest = iter(stock)
    ordered = [row if row is not None else next(rest) for row in ordered]
    assert Counter(row['card_name'] for row in ordered) == Counter({row['card_name']: row['quantity'] for row in rows})
    return ordered


def cast(match, pid, name, targets=None):
    cid = next(cid for cid in match.state.players[pid].hand if match.state.cards[cid].name == name)
    checked(match, pid, {'type': 'cast_spell', 'card_id': cid, **({'targets': targets} if targets else {})})
    assert match.state.stack[-1].source_card_id == cid
    return cid


def own_main(match):
    for _ in range(64):
        state = match.state
        if state.active_player == 1 and state.step == Step.PRECOMBAT_MAIN and not state.stack:
            return
        assert state.winner is None
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['kind'] == 'cleanup_discard'
            # Keep actual named spell stock; discard genuine lands first.
            options = sorted(pending['options'], key=lambda cid: ('Land' not in state.cards[cid].types, cid))
            checked(match, pending['player_id'], {'type': 'choose_mechanic', 'card_ids': options[:pending['count']]})
        else:
            checked(match, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Checked empty turn did not reach own main phase')


def fixture(main, side, *, seed, mode='player_vs_ai', artifact=False,
            public_counter=False, remember=False, finish=True, finalize=True, agents=None):
    entries = [{'card_name': row['card_name'], 'quantity': row['quantity']} for row in main]
    additions = [{'card_name': 'Lightning Bolt', 'quantity': 2 if public_counter else 1}]
    if remember:
        additions.append({'card_name': 'Teferi, Time Raveler', 'quantity': 1})
    entries[0]['quantity'] -= sum(row['quantity'] for row in additions)
    main = ready_deck(entries + additions)
    side = ready_deck(side)
    other = ready_deck([{'card_name': 'Island', 'quantity': 58},
                       {'card_name': 'Shuko', 'quantity': 1},
                       {'card_name': 'Counterspell', 'quantity': 1}])
    assert sum(row['quantity'] for row in main) == sum(row['quantity'] for row in other) == 60
    own_opening = {'Fatal Push': 3, 'Lightning Bolt': 2 if public_counter else 1,
                   **({'Teferi, Time Raveler': 1} if remember else {})}
    other_opening = {'Shuko': 1, 'Counterspell': 1}
    # Mirror only the two standard Factory shuffle permutations using a LOCAL
    # RNG. This predeclares controlled unit inputs, not a natural hand/seed claim.
    order_rng = Random(seed)
    own_order, other_order = list(range(60)), list(range(60))
    order_rng.shuffle(own_order)
    order_rng.shuffle(other_order)
    state = MatchFactory.from_decks(birth_order(main, own_opening, own_order),
                                    birth_order(other, other_opening, other_order), seed=seed)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 2 if artifact else 1
    state.players[2].life = 3  # Explicit trusted unit pose, no completed-winner injection.
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {'U': 6, 'R': 3, 'W': 3, 'B': 3, 'G': 3, 'C': 5}
    draw_named(state, 1, own_opening)
    draw_named(state, 2, other_opening)
    match = MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'ai', 2: 'ai' if mode == 'ai_vs_ai' else 'human'},
        ai=agents if agents is not None else {
            1: AIAgent(archetype='Control', opponent_archetype='Control'),
            2: AIAgent(archetype='Control', opponent_archetype='Control')},
        mode=mode, deck_ids=(None, None), mainboards={1: main, 2: other},
        sideboards={1: side, 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3, root_seed=seed)
    if artifact:
        cast(match, 2, 'Shuko')
        assert match.state.stack[-1].payload['mana_spent'] == 1
        settle(match)
    if finish:
        complete(match, public_counter=public_counter, finalize=finalize)
    return match


def return_artifact(match):
    own_main(match)
    match.state.players[1].mana_pool = {'W': 1, 'U': 2, 'R': 1}
    pw = cast(match, 1, 'Teferi, Time Raveler')
    assert match.state.stack[-1].payload['mana_spent'] == 3
    settle(match)
    artifact = next(cid for cid in match.state.players[2].battlefield if match.state.cards[cid].name == 'Shuko')
    move = next(move for move in match.rules.legal_moves(match.state, 1)
                if move['type'] == 'activate_loyalty' and move['card_id'] == pw and move['ability_index'] == 1)
    checked(match, 1, {**move, 'targets': {'target_card_id': artifact}})
    settle(match)
    assert match.state.cards[artifact].zone == Zone.HAND
    return artifact


def complete(match, *, public_counter=False, finalize=True):
    if match.state.priority_player != 1:
        checked(match, match.state.priority_player, {'type': 'pass_priority'})
    match.state.players[1].mana_pool['R'] = 2 if public_counter else 1
    cast(match, 1, 'Lightning Bolt', {'target_player': 2})
    assert match.state.stack[-1].payload['mana_spent'] == 1
    if public_counter:
        checked(match, 1, {'type': 'pass_priority'})
        target = match.state.stack[-1].id
        cast(match, 2, 'Counterspell', {'target_stack_id': target})
        assert match.state.stack[-1].payload['mana_spent'] == 2
        settle(match)
        cast(match, 1, 'Lightning Bolt', {'target_player': 2})
        assert match.state.stack[-1].payload['mana_spent'] == 1
    settle(match)
    assert match.state.winner == 1 and match.state.players[2].life == 0
    if finalize:
        _post_step_finalize(match, None)
        assert match.state.sideboard_facts['complete'] is True
