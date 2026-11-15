"""Independent canonical positions; all Q scores are explicitly synthetic.

No saved EVAL roots, fitted checkpoints, TRAIN rows, games or strength claims.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random

import pytest

from ai import learned_policy, mana_resource_policy as resources, pending_effects
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from tests.ai_decisions_canonical_cdba import raw_card

RULES = RulesEngine()
FORETELL = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/foretell.json').read_bytes())}
BURN_BYTES = (Path(__file__).parent / 'fixtures/ai_burn_foretell/CANONICAL-RAW.json').read_bytes()
assert sha256(BURN_BYTES).hexdigest() == '3072700528cfd0a7ec6878dc2a7f94cece02f3c2901221ee1ddd490c0aee214d'
BURN = json.loads(BURN_BYTES)
MANA = {c['name']: c for c in json.loads((Path(__file__).parent / 'fixtures/mana_resources.json').read_bytes())}
KICKER_BYTES = (Path(__file__).parent / 'fixtures/kicker.json').read_bytes()
assert sha256(KICKER_BYTES).hexdigest() == 'da4344ddb131c996c3182ca69ddf2d64a614d8fa62e841568eae97b14721e843'
KICKER = {'Burst Lightning': next(row for row in json.loads(KICKER_BYTES) if row['name'] == 'Burst Lightning')}
BOUNDARY = {}
for filename, pin, names in (
    ('legendary_channels.json', '0d3d0aaacf52d2f9dd5e55ae55da22ca7c05f80290d7415d3130620b6fa11d5a',
     {'Boseiju, Who Endures', 'Hallowed Fountain', 'Mind Stone'}),
    ('activation_modifiers.json', 'ea21a082c95a6f14a20c166e639a389365d89577b33df6beb6cafe1aac6ee822',
     {'Azure Mage'}),
    ('modal_spell_faces.json', 'ffb6877741439134938257c07262d58dcfd56050eb221211e20d8c6e7de7b332',
     {'Bala Ged Recovery // Bala Ged Sanctuary'}),
    ('death_cycle_ordering/canonical.json', '82a096075b1577480e7c966f1efdb364edda3966c6a5ad9fdc073dcab836f7b5',
     {'Lonely Sandbar'}),
):
    data = (Path(__file__).parent / 'fixtures' / filename).read_bytes()
    assert sha256(data).hexdigest() == pin
    rows = json.loads(data)
    BOUNDARY.update({row['name']: row for row in (rows.values() if isinstance(rows, dict) else rows)
                     if row.get('name') in names})
    assert names <= BOUNDARY.keys()


def position(seat, hand, lands, enemy=()):
    counts = Counter([*hand, *lands, *enemy])
    counts['Forest'] += 60 - sum(counts.values())
    deck = [dict(FORETELL[name] if name in FORETELL else BURN[name] if name in BURN
                 else MANA[name] if name in MANA else KICKER[name] if name in KICKER
                 else BOUNDARY[name] if name in BOUNDARY else raw_card(name), quantity=n, card_name=name)
            for name, n in counts.items() if n]
    state = MatchFactory.from_decks(deck, deck, seed=83141, game_id='canonical-c11-land-coverage')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
        player.lands_played_this_turn = 0

    def move(name, owner, zone):
        player = state.players[owner]
        printed_name = BOUNDARY.get(name, {}).get('card_faces', [{}])[0].get('name', name)
        cid = next(cid for cid in player.library if state.cards[cid].name in {name, printed_name})
        player.library.remove(cid)
        state.cards[cid].move_to_zone(zone)
        if name in KICKER:
            for field in ('oracle_text', 'mana_cost', 'type_line', 'colors'):
                assert getattr(state.cards[cid], field) == KICKER[name][field]
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
            state.cards[cid].summoning_sick = False
        return cid

    for name in lands:
        move(name, seat, Zone.BATTLEFIELD)
    cards = {name: move(name, seat, Zone.HAND) for name in hand}
    for name in enemy:
        move(name, 3-seat, Zone.BATTLEFIELD)
    return state, cards


def lands(state, seat):
    return [complete_action(m) for m in RULES.legal_moves(state, seat) if m['type'] == 'play_land']


def select_land(actions, state, name):
    return next(a for a in actions if state.cards[a['card_id']].name == name)


def route(monkeypatch, state, seat, proposals, scores, forecast=None):
    """Synthetic adverse scores; genuine feature encoding, admission and forecasts."""
    class AdverseScores:
        def __init__(self):
            self.calls = 0

        def prepare(self, pack):
            return self

        def predict(self, pack):
            value = scores[self.calls]
            self.calls += 1
            return {'q': value, 'v': 0.0}

    scorer = AdverseScores()
    contract = learned_policy._current_contract()
    binding = learned_policy.LivePolicyBinding(scorer, 'synthetic-adverse-Q-only', tuple(sorted(contract.items())))
    monkeypatch.setattr(AIAgent, '_strategic_top_actions', lambda *args: deepcopy(proposals))
    if forecast is not None:
        monkeypatch.setattr(pending_effects, 'unanswered_action_classification', forecast)
    agent = AIAgent(difficulty='master', learned_binding=binding)
    before, rng = serialize_match_snapshot(state), random.getstate()
    legal = RULES.legal_moves(deepcopy(state), seat)
    view, offered = decision_view(state, seat, legal)
    chosen = learned_policy.choose_learned_action(binding, agent, view, offered, seat,
        admit=lambda action: checked_action(state, RULES, seat, action))
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    assert scorer.calls == len(proposals)
    return chosen


def guarded(state, seat, selected, alternatives):
    fn = getattr(resources, 'prefer_nonregressive_land', None)
    assert callable(fn), 'new land coverage guard is absent in baseline'
    before, rng = serialize_match_snapshot(state), random.getstate()
    result = fn(AIAgent(difficulty='master'), state, seat, selected, alternatives)
    assert serialize_match_snapshot(state) == before and random.getstate() == rng
    return result


def foretold_position(seat, board):
    state, cards = position(seat, ['Plains', 'Island', 'Doomskar'], board)
    state.players[seat].mana_pool = {'C': 2}
    state = checked_action(state, RULES, seat, {'type': 'foretell', 'card_id': cards['Doomskar']})
    assert not any(state.players[seat].mana_pool.values())
    assert state.cards[cards['Doomskar']].zone == Zone.EXILE
    state.turn += 1  # A separately declared later-turn unit position, not a game replay.
    options = collect_cost_options(state, seat, state.cards[cards['Doomskar']])
    assert [(o.id, o.mana_cost) for o in options] == [('foretell_0', '{1}{W}{W}')]
    return state, cards, options[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_adverse_q_first_white_pip_improves_known_paid_foretell_before_full_cast(monkeypatch, seat):
    state, cards, cost = foretold_position(seat, ['Island'])
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    chosen = route(monkeypatch, state, seat, [blue, white], [.8, .1])
    assert chosen == white
    projected = checked_action(state, RULES, seat, chosen)
    assert not check_cost_option_available(projected, seat, projected.cards[cards['Doomskar']], cost)
    assert resources._can_pay(projected, seat, '{W}', projected.cards[cards['Doomskar']])


@pytest.mark.parametrize('seat', [1, 2])
def test_second_white_pip_unlocks_genuine_native_paid_foretell_one_ww(monkeypatch, seat):
    state, cards, cost = foretold_position(seat, ['Plains', 'Island'])
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    assert not check_cost_option_available(state, seat, state.cards[cards['Doomskar']], cost)
    chosen = route(monkeypatch, state, seat, [blue, white], [.8, .1])
    assert chosen == white
    developed = checked_action(state, RULES, seat, chosen)
    assert check_cost_option_available(developed, seat, developed.cards[cards['Doomskar']], cost)
    cast = checked_action(developed, RULES, seat, {'type': 'cast_spell', 'card_id': cards['Doomskar'],
        'from_exile': True, 'cost_choice': {'id': 'foretell_0'}})
    assert cast.stack[-1].payload['__was_foretold']
    assert len([cid for cid in cast.players[seat].battlefield if cast.cards[cid].tapped]) == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_high_printed_cost_fixed_pips_are_not_discarded(seat):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island', 'Forest'])
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    assert guarded(state, seat, blue, options) == white


@pytest.mark.parametrize('seat', [1, 2])
def test_known_blue_white_capacity_tradeoff_retains_q(seat):
    state, _ = position(seat, ['Plains', 'Island', 'Counterspell', 'Swords to Plowshares'], ['Forest'])
    options = lands(state, seat)
    blue = select_land(options, state, 'Island')
    assert guarded(state, seat, blue, options) == blue


@pytest.mark.parametrize('seat', [1, 2])
def test_joint_two_burn_costs_are_not_lost_to_one_independently_payable_answer(seat):
    state, cards = position(seat,
        ['Mountain', 'Plains', 'Lightning Bolt', 'Lightning Bolt', 'Swords to Plowshares'],
        ['Mountain', 'Island'], enemy=['Grizzly Bears'])
    state.players[3-seat].life = 6
    options = lands(state, seat)
    red = select_land(options, state, 'Mountain')
    bolts = [cid for cid in state.players[seat].hand if state.cards[cid].name == 'Lightning Bolt']
    assert len(bolts) == 2
    def burn_once(game, cid):
        game = checked_action(game, RULES, seat, {'type': 'cast_spell', 'card_id': cid,
            'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}})
        for _ in range(4):
            if not game.stack:
                return game
            game = checked_action(game, RULES, game.priority_player, {'type': 'pass_priority'})
        raise AssertionError('Bounded native Bolt settlement')
    with_red = burn_once(checked_action(state, RULES, seat, red), bolts[0])
    assert burn_once(with_red, bolts[1]).winner == seat
    with_white = burn_once(checked_action(state, RULES, seat, select_land(options, state, 'Plains')), bolts[0])
    with pytest.raises(ActionRejected):
        burn_once(with_white, bolts[1])
    assert guarded(state, seat, red, options) is red


@pytest.mark.parametrize('seat', [1, 2])
def test_equal_resource_coverage_retains_exact_q_action(seat):
    state, _ = position(seat, ['Plains', 'Island', 'Counterspell'], ['Island', 'Island'])
    options = lands(state, seat)
    blue = select_land(options, state, 'Island')
    assert guarded(state, seat, blue, options) is blue


@pytest.mark.parametrize('seat', [1, 2])
def test_nonadmitted_improving_land_is_never_invented(seat):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    blue = select_land(lands(state, seat), state, 'Island')
    assert guarded(state, seat, blue, [blue]) is blue


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('flag', ['pending_mechanic_choice', 'pending_replacement_choice', 'pending_trigger_order'])
def test_pending_state_retains_q_without_projection(seat, flag, monkeypatch):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    options = lands(state, seat);blue = select_land(options, state, 'Island')
    setattr(state, flag, {'unresolved': True})
    monkeypatch.setattr(resources, 'checked_action', lambda *args: pytest.fail('pending projection must not run'))
    assert guarded(state, seat, blue, options) is blue


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['RNG', 'library', 'opponent_hand', 'pending'])
def test_unknown_or_private_changing_land_projection_retains_q(monkeypatch, seat, change):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    options = lands(state, seat);blue = select_land(options, state, 'Island')
    original = resources.checked_action
    def changed(*args, **kwargs):
        projected = original(*args, **kwargs)
        if change == 'RNG':
            random.random()
        elif change == 'library':
            projected.players[seat].library.reverse()
        elif change == 'opponent_hand':
            projected.players[3-seat].hand.append('unobserved-private-card')
        else:
            projected.pending_mechanic_choice = {'unknown': True}
        return projected
    monkeypatch.setattr(resources, 'checked_action', changed)
    assert guarded(state, seat, blue, options) is blue


@pytest.mark.parametrize('seat', [1, 2])
def test_library_order_and_opposing_hidden_cards_do_not_change_choice(seat):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    options = lands(state, seat);blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    assert guarded(state, seat, blue, options) == white
    for player in state.players.values():
        player.library.reverse()
    opponent = state.players[3-seat]
    cid = opponent.library.pop()
    state.cards[cid].move_to_zone(Zone.HAND)
    opponent.hand.append(cid)
    assert guarded(state, seat, blue, options) == white


@pytest.mark.parametrize('seat', [1, 2])
def test_worse_original_terminal_prefix_does_not_override_q(monkeypatch, seat):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    options = lands(state, seat);blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    chosen = route(monkeypatch, state, seat, [blue, white], [.8, .1],
                   lambda view, pid, action, **kw: (False, action['card_id'] == white['card_id']))
    assert chosen == blue


@pytest.mark.parametrize('seat', [1, 2])
def test_original_known_winning_land_prefix_never_calls_resource_guard(monkeypatch, seat):
    state, _ = position(seat, ['Plains', 'Island', 'Doomskar'], ['Island'])
    options = lands(state, seat);blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    monkeypatch.setattr(resources, 'prefer_nonregressive_land', lambda *args: pytest.fail('Known win must be retained'))
    assert route(monkeypatch, state, seat, [blue, white], [.8, .1],
                 lambda view, pid, action, **kw: (action['card_id'] == blue['card_id'], False)) == blue


@pytest.mark.parametrize('seat', [1, 2])
def test_alternative_native_kicker_prices_do_not_double_count_one_card(seat):
    state, _ = position(seat, ['Plains', 'Mountain', 'Burst Lightning'], ['Island'])
    costs, demand = resources._known_land_costs(state, seat)
    assert len(costs) == 1 and len(costs[0][1]) == 2
    assert demand['R'] == 1 and demand['generic'] == 5


@pytest.mark.parametrize('seat', [1, 2])
def test_flexible_nonland_mana_is_a_shared_joint_payment_source(seat):
    state, _ = position(seat,
        ['Mountain', 'Plains', 'Lightning Bolt', 'Lightning Bolt', 'Swords to Plowshares'],
        ['Forest', 'Birds of Paradise'])
    options = lands(state, seat);red = select_land(options, state, 'Mountain')
    assert guarded(state, seat, red, options) is red


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_to_announced_lethal_is_not_replaced_by_land_guard(monkeypatch, seat):
    # A native opponent spell announcement is the only added stack state.
    opp = 3-seat
    state, cards = position(seat, ['Counterspell', 'Lightning Bolt'], ['Island', 'Island'])
    bolt = next(cid for cid in state.players[opp].library if state.cards[cid].name == 'Lightning Bolt')
    state.players[opp].library.remove(bolt)
    state.cards[bolt].move_to_zone(Zone.HAND);state.players[opp].hand.append(bolt)
    state.players[opp].mana_pool = {'R': 1};state.active_player = state.priority_player = opp
    state.players[seat].life = 3
    state = checked_action(state, RULES, opp, {'type': 'cast_spell', 'card_id': bolt, 'targets': {'target_player': seat}})
    state.priority_player = seat
    action = {'type': 'cast_spell', 'card_id': cards['Counterspell'], 'cost_choice': {'id': 'base'},
              'targets': {'target_stack_id': state.stack[-1].id}}
    chosen = route(monkeypatch, state, seat, [complete_action(action)], [.8])
    assert chosen == complete_action(action)
    checked_action(state, RULES, seat, chosen)


@pytest.mark.parametrize('seat', [1, 2])
def test_ordinary_native_exile_permission_preserves_red_white_tradeoff(seat):
    from rules_engine.card_faces import ordinary_exile_permission
    state, cards = position(seat,
        ['Mountain', 'Plains', 'Swords to Plowshares', 'Lightning Bolt'], ['Island'], enemy=['Grizzly Bears'])
    bolt = cards['Lightning Bolt']
    state.players[seat].hand.remove(bolt)
    state.cards[bolt].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(bolt)
    # Trusted native temporary-permission unit setup, not a causal impulse episode.
    state.players[seat].exile_play_until[bolt] = state.turn
    assert ordinary_exile_permission(state, seat, bolt)
    options = lands(state, seat)
    red, white = (select_land(options, state, name) for name in ('Mountain', 'Plains'))
    action = {'type': 'cast_spell', 'card_id': bolt, 'from_exile': True,
              'cost_choice': {'id': 'base'}, 'targets': {'target_player': 3-seat}}
    paid = checked_action(checked_action(state, RULES, seat, red), RULES, seat, action)
    assert paid.cards[bolt].zone == Zone.STACK
    with pytest.raises(ActionRejected):
        checked_action(checked_action(state, RULES, seat, white), RULES, seat, action)
    assert guarded(state, seat, red, [red, white]) is red


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_shock_land_does_not_dominate_free_land_by_ignoring_life(seat):
    state, _ = position(seat, ['Island', 'Hallowed Fountain', 'Swords to Plowshares'], ['Island'])
    options = lands(state, seat)
    blue = select_land(options, state, 'Island')
    shock = next(a for a in options if state.cards[a['card_id']].name == 'Hallowed Fountain'
                 and a.get('entry_choice') == 'pay_two_life')
    paid = checked_action(state, RULES, seat, shock)
    assert paid.players[seat].life == state.players[seat].life - 2
    assert resources._can_pay(paid, seat, '{W}')
    assert guarded(state, seat, blue, [blue, shock]) is blue


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('capability', ['channel', 'cycling', 'battlefield_activation'])
def test_known_unmodeled_capability_abstains_instead_of_claiming_dominance(seat, capability):
    from rules_engine.oracle_effects import extract_activated_abilities
    from rules_engine.cycling import cycling_cost
    hand = ['Island', 'Plains', 'Swords to Plowshares']
    board = ['Island']
    if capability == 'channel':
        hand.append('Boseiju, Who Endures')
    elif capability == 'cycling':
        hand.append('Lonely Sandbar')
    else:
        board.append('Merfolk Looter')
    state, cards = position(seat, hand, board, enemy=['Grizzly Bears'])
    if capability == 'channel':
        abilities = extract_activated_abilities(state.cards[cards['Boseiju, Who Endures']])
        assert any(a['activation_zone'] == 'hand' and '{G}' in a['mana_cost'] for a in abilities)
    elif capability == 'cycling':
        assert cycling_cost(state.cards[cards['Lonely Sandbar']].oracle_text) == '{U}'
    else:
        cid = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Merfolk Looter')
        assert extract_activated_abilities(state.cards[cid])
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    assert guarded(state, seat, blue, [blue, white]) is blue


@pytest.mark.parametrize('seat', [1, 2])
def test_consumed_modal_spell_land_is_not_a_retained_spell_cost_source(seat):
    name = 'Bala Ged Recovery // Bala Ged Sanctuary'
    state, cards = position(seat, ['Island', name, 'Swords to Plowshares'], ['Forest', 'Forest'])
    universe = resources._known_land_costs(state, seat)
    assert universe is not None and cards[name] in {cid for cid, _ in universe[0]}
    action = next(a for a in lands(state, seat) if a['card_id'] == cards[name] and a['selected_face_index'] == 1)
    projected = checked_action(state, RULES, seat, action)
    assert projected.cards[cards[name]].zone == Zone.BATTLEFIELD
    assert 'Land' in projected.cards[cards[name]].types
    assert resources._land_coverage(projected, seat, *universe) is None


def test_oversized_profile_abstains_before_any_native_payment_or_land_projection(monkeypatch):
    from rules_engine import costs as native_costs
    state, _ = position(1, ['Island', 'Plains'] + ['Doomskar'] * 12, ['Island'])
    options = lands(state, 1)
    blue = select_land(options, state, 'Island')
    monkeypatch.setattr(resources, '_can_pay', lambda *a, **kw: pytest.fail('preflight must precede payment'))
    monkeypatch.setattr(native_costs, 'check_cost_option_available', lambda *a, **kw: pytest.fail('preflight must precede cost payment'))
    monkeypatch.setattr(resources, 'checked_action', lambda *a, **kw: pytest.fail('preflight must precede land projection'))
    assert guarded(state, 1, blue, options) is blue


def test_four_land_four_cost_frame_remains_inside_explicit_probe_bound(monkeypatch):
    from rules_engine import costs as native_costs
    state, _ = position(1, ['Island', 'Plains', 'Mountain', 'Forest', 'Doomskar', 'Swords to Plowshares',
                           'Grizzly Bears', 'Lightning Bolt'], ['Island', 'Forest'])
    options = lands(state, 1)
    blue = select_land(options, state, 'Island')
    calls = []
    original, original_option = resources._can_pay, native_costs.check_cost_option_available
    def pay(*args, **kwargs):
        calls.append('capacity')
        return original(*args, **kwargs)
    def option(*args, **kwargs):
        calls.append('cost')
        return original_option(*args, **kwargs)
    monkeypatch.setattr(resources, '_can_pay', pay)
    monkeypatch.setattr(native_costs, 'check_cost_option_available', option)
    assert guarded(state, 1, blue, options) != blue
    assert 350 <= len(calls) <= resources._LAND_PROFILE_MAX_PROBES == 1024


@pytest.mark.parametrize('seat', [1, 2])
def test_native_paid_channel_access_is_not_traded_for_white_spell_access(seat):
    from rules_engine.oracle_effects import extract_activated_abilities
    state, cards = position(seat, ['Forest', 'Plains', 'Boseiju, Who Endures', 'Swords to Plowshares'],
                            ['Island'], enemy=['Mind Stone'])
    source = cards['Boseiju, Who Endures']
    ability = next(a for a in extract_activated_abilities(state.cards[source]) if a['activation_zone'] == 'hand')
    target = next(cid for cid in state.players[3-seat].battlefield if state.cards[cid].name == 'Mind Stone')
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': ability['index'],
              'targets': {'target_card_id': target}}
    options = lands(state, seat)
    green, white = (select_land(options, state, name) for name in ('Forest', 'Plains'))
    paid = checked_action(checked_action(state, RULES, seat, green), RULES, seat, action)
    assert paid.cards[source].zone == Zone.GRAVEYARD and paid.stack[-1].controller == seat
    with pytest.raises(ActionRejected):
        checked_action(checked_action(state, RULES, seat, white), RULES, seat, action)
    assert guarded(state, seat, green, [green, white]) is green


@pytest.mark.parametrize('seat', [1, 2])
def test_native_paid_board_activation_access_is_not_traded_for_white_spell_access(seat):
    from rules_engine.oracle_effects import extract_activated_abilities
    state, _ = position(seat, ['Island', 'Plains', 'Swords to Plowshares'],
                        ['Forest', 'Forest', 'Forest', 'Azure Mage'])
    source = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Azure Mage')
    ability = extract_activated_abilities(state.cards[source])[0]
    action = {'type': 'activate_ability', 'card_id': source, 'ability_index': ability['index'], 'targets': {}}
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    paid = checked_action(checked_action(state, RULES, seat, blue), RULES, seat, action)
    assert paid.stack[-1].controller == seat
    assert sum(paid.cards[cid].tapped for cid in paid.players[seat].battlefield) == 4
    with pytest.raises(ActionRejected):
        checked_action(checked_action(state, RULES, seat, white), RULES, seat, action)
    assert guarded(state, seat, blue, [blue, white]) is blue


@pytest.mark.parametrize('seat', [1, 2])
def test_consumable_mana_ability_is_an_unmodeled_resource_not_free_capacity(seat):
    from rules_engine.mana_abilities import mana_ability_specs
    state, _ = position(seat, ['Island', 'Plains', 'Swords to Plowshares'], ['Island', 'Skirk Prospector'])
    cid = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Skirk Prospector')
    assert any('sacrifice' in cost.lower() for _, cost, _ in mana_ability_specs(state.cards[cid], state))
    options = lands(state, seat)
    blue, white = (select_land(options, state, name) for name in ('Island', 'Plains'))
    assert guarded(state, seat, blue, [blue, white]) is blue
