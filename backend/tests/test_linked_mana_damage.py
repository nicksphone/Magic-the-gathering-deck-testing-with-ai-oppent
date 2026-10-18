"""Native complete-Oracle mana/damage; malformed text is protocol-only input."""
import pytest

from effects import handlers
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.mana_abilities import mana_ability_views
from tests.mana_canonical_76 import entry


def position(seat, *, foreign_owner=False, protocol=None):
    if protocol is None:
        row = entry('Battlefield Forge', 8)
    else:
        # Anonymous grammar controls are not official card facts.
        name, oracle = protocol
        row = {'quantity': 8, 'card_name': name, 'type_line': 'Land',
               'oracle_text': oracle, 'colors': [], 'layout': 'normal'}
    state = MatchFactory.from_decks([row], [row], seed=618)
    owner = 3 - seat if foreign_owner else seat
    source = state.cards[state.players[owner].library[-1]]
    state.players[owner].library.remove(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[owner].battlefield.append(source.id)
    if foreign_owner:
        handlers.change_control(state, seat, {'target_card_id': source.id})
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    return state, source


@pytest.fixture
def damage_calls(monkeypatch):
    calls = []
    original = handlers.emit_event

    def observe(state, event, payload):
        if event == 'damage_dealt':
            calls.append((state, dict(payload)))
        return original(state, event, payload)

    monkeypatch.setattr(handlers, 'emit_event', observe)
    return calls


def committed_damage(calls, state):
    # Affordability trials must not masquerade as committed damage events.
    return [payload for current, payload in calls if current is state]


def request(source, color, route='native'):
    if route == 'native':
        return {'type': 'activate_mana_ability', 'card_id': source.id,
                'ability_index': 0 if color == 'C' else 1, 'color': color}
    if route == 'bulk':
        return {'type': 'tap_lands_bulk', 'land_name': source.name, 'count': 1, 'color': color}
    return {'type': 'tap_land_for_mana', 'card_id': source.id, 'color': color}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('color', ['R', 'W'])
def test_full_forge_native_view_and_checked_execution(seat, color, damage_calls):
    state, source = position(seat)
    before = serialize_match_snapshot(state)
    moves = [m for m in RulesEngine().legal_moves(state, seat)
             if m['type'] == 'activate_mana_ability' and m['card_id'] == source.id]
    colored = [m for m in moves if m['ability_index'] == 1]
    assert len(colored) == 1
    assert colored[0]['outputs'] == {'R': 1, 'W': 1}
    result = checked_action(state, RulesEngine(), seat, request(source, color))
    assert result.players[seat].mana_pool[color] == 1
    assert result.players[seat].life == 19
    assert result.players[3 - seat].life == 20
    assert result.cards[source.id].tapped
    assert committed_damage(damage_calls, result) == [
        {'source_card_id': source.id, 'target_player': seat, 'amount': 1}]
    assert serialize_match_snapshot(state) == before
    assert not result.stack and not result.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('color', ['R', 'W'])
@pytest.mark.parametrize('route', ['legacy', 'bulk'])
def test_legacy_and_bulk_use_the_same_complete_instruction(seat, color, route, damage_calls):
    state, source = position(seat)
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, request(source, color, route))
    assert result.players[seat].mana_pool[color] == 1
    assert result.players[seat].life == 19
    assert result.cards[source.id].tapped
    assert committed_damage(damage_calls, result) == [
        {'source_card_id': source.id, 'target_player': seat, 'amount': 1}]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_source_owner_is_not_the_damage_recipient(seat, damage_calls):
    state, source = position(seat, foreign_owner=True)
    assert source.owner == 3 - seat and source.controller == seat
    result = checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert result.players[seat].life == 19
    assert result.players[source.owner].life == 20
    assert committed_damage(damage_calls, result) == [
        {'source_card_id': source.id, 'target_player': seat, 'amount': 1}]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['native', 'legacy', 'bulk'])
def test_colorless_ability_never_executes_colored_self_damage(seat, route, damage_calls):
    state, source = position(seat)
    result = checked_action(state, RulesEngine(), seat, request(source, 'C', route))
    assert result.players[seat].mana_pool['C'] == 1
    assert result.players[seat].life == 20
    assert result.cards[source.id].tapped
    assert committed_damage(damage_calls, result) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cost', ['{W}', '{R}', '{1}'])
def test_preflight_is_pure_and_payment_commits_selected_damage_once(seat, cost, damage_calls):
    state, source = position(seat)
    before = serialize_match_snapshot(state)
    rng_before = state.rng.getstate()
    assert can_pay_with_pool_and_lands(state, seat, cost)
    assert serialize_match_snapshot(state) == before
    assert state.rng.getstate() == rng_before
    assert auto_pay_cost(state, seat, cost)
    expected = [] if cost == '{1}' else [
        {'source_card_id': source.id, 'target_player': seat, 'amount': 1}]
    assert committed_damage(damage_calls, state) == expected
    assert state.players[seat].life == (20 if cost == '{1}' else 19)
    assert not any(state.players[seat].mana_pool.values())
    assert state.cards[source.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_real_existing_prevention_is_not_replaced_by_a_pay_life_cost(seat, damage_calls):
    from rules_engine.prevention import add_player_prevention_shield
    state, source = position(seat)
    # Existing explicit legacy shield resource, not an invented spell/receipt.
    add_player_prevention_shield(state, seat, 1)
    result = checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert result.players[seat].mana_pool['W'] == 1
    assert result.players[seat].life == 20
    assert result.players[seat].prevent_damage_shield == 0
    assert state.players[seat].prevent_damage_shield == 1
    assert committed_damage(damage_calls, result) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life,held,shield,allowed,after_life', [
    (3, 3, 0, False, 3), (3, 2, 0, True, 2),
    (3, 3, 1, True, 3), (1, 0, 0, True, 0),
])
def test_planner_reserves_actual_post_damage_life_not_a_fake_fixed_price(
        seat, life, held, shield, allowed, after_life):
    from rules_engine.prevention import add_player_prevention_shield
    state, source = position(seat)
    state.players[seat].life = life
    add_player_prevention_shield(state, seat, shield)
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{W}', protected_life=held) is allowed
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{W}', protected_life=held) is allowed
    assert state.players[seat].life == after_life
    if not allowed:
        assert serialize_match_snapshot(state) == before
    else:
        assert state.cards[source.id].tapped
        assert not any(state.players[seat].mana_pool.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['wrong_color', 'wrong_seat', 'wrong_index', 'tapped', 'suppressed'])
def test_rejected_native_requests_keep_the_entire_input_snapshot(seat, invalid):
    state, source = position(seat)
    action = request(source, 'W')
    actor = seat
    if invalid == 'wrong_color':
        action['color'] = 'U'
    elif invalid == 'wrong_seat':
        actor = 3 - seat
    elif invalid == 'wrong_index':
        action['ability_index'] = 99
    elif invalid == 'tapped':
        source.tapped = True
    else:
        from rules_engine.keyword_effects import add_keyword_effect
        add_keyword_effect(state, source.id, ['all abilities'], operation='remove')
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [
    ' You win the game.', ' (You lose the game.)',
    ' Then draw a card.', ' (Unknown instruction: add {W}.)',
])
def test_complete_raw_unknown_tails_cannot_reward_a_normalized_prefix(seat, suffix):
    state, source = position(seat)
    # Deliberate noncanonical malformed instruction, never asserted as RAW.
    source.oracle_text += suffix
    before = serialize_match_snapshot(state)
    views = mana_ability_views(state, source)
    assert [v['ability_index'] for v in views] == [0]
    assert not can_pay_with_pool_and_lands(state, seat, '{W}')
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('matching', [True, False])
def test_escaped_source_name_is_a_binding_not_a_regex_or_card_name_handler(seat, matching):
    name = 'Protocol[0].+'
    reference = name if matching else 'Protocol000x'
    state, source = position(seat, protocol=(name,
        '{T}: Add {C}.\n{T}: Add {W}. ' + reference + ' deals 1 damage to you.'))
    before = serialize_match_snapshot(state)
    views = [v for v in mana_ability_views(state, source) if 'W' in v['outputs']]
    assert bool(views) is matching
    if matching:
        result = checked_action(state, RulesEngine(), seat, request(source, 'W'))
        assert result.players[seat].life == 19
    else:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('prefix', ['If you have ten poison counters, ', 'Unknown qualification: '])
def test_unknown_raw_prefix_cannot_be_lost_before_the_native_cost(seat, prefix):
    state, source = position(seat)
    source.oracle_text = source.oracle_text.replace(
        '{T}: Add {R}', prefix + '{T}: Add {R}')
    before = serialize_match_snapshot(state)
    assert [v['ability_index'] for v in mana_ability_views(state, source)] == [0]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unrepresentable_protocol_damage_constant_fails_closed_without_a_view_exception(seat):
    state, source = position(seat)
    source.oracle_text = source.oracle_text.replace('deals 1 damage', 'deals ' + '9' * 5000 + ' damage')
    before = serialize_match_snapshot(state)
    assert [v['ability_index'] for v in mana_ability_views(state, source)] == [0]
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, request(source, 'W'))
    assert serialize_match_snapshot(state) == before
