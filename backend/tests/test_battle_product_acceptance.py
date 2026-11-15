"""Paid Invasion of Zendikar play in each seat from a declared legal position."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_card_view, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.card_faces import card_mana_value
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.type_effects import effective_types
from tests.test_battle_characteristics import mark
from tests.test_battle_combat import act, assert_life, cold, reach
from tests.test_battle_entry import announce, place, position


def resolve_until(state, predicate):
    for _ in range(12):
        if predicate(state):
            return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native resolution missed its declared boundary')


def decision(state, player):
    moves = RulesEngine().legal_moves(state, player)
    before = serialize_match_snapshot(state)
    choice = AIAgent(difficulty='strong').choose_action(state, moves, player)
    assert serialize_match_snapshot(state) == before
    return choice.action


def battle_position(seat, *, extra=()):
    state, battle = position(seat, extra=('Grizzly Bears',) * 3 + extra)
    attackers = [place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD) for _ in range(3)]
    return state, battle, attackers


def add_bear_blocker(state, seat):
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    from rules_engine.counter_placement import put_counters
    put_counters(state, '+1/+1', 1, target_card_id=blocker)


def paid_front(state, seat, battle):
    state.mechanic_choice_players = {seat}
    state = announce(state, seat, battle)
    state = resolve_until(state, lambda s: s.pending_mechanic_choice is not None)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and pending['player_id'] == seat
    assert pending['count'] == 2 and pending['min_count'] == 0
    assert pending['resolving_item']['source_card_id'] == battle
    chosen = pending['options'][:2]
    assert len(chosen) == 2 and all(state.cards[cid].type_line.startswith('Basic Land') for cid in chosen)
    library = set(state.players[seat].library)
    rng = state.rng.getstate()
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert not state.pending_mechanic_choice
    assert set(state.players[seat].library) == library - set(chosen)
    assert state.rng.getstate() != rng
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].tapped for cid in chosen)
    assert state.cards[battle].zone == Zone.BATTLEFIELD
    assert state.cards[battle].counters['defense'] == 3 and state.cards[battle].battle_protector == 3-seat
    return state


def cast_paid_back(state, seat, battle, attackers):
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
                            'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    assert state.priority_player == 3-seat
    mark('Task6-paid-Battle-AI-block-response-reached')
    response = decision(state, 3-seat)
    assert response['type'] in {'block', 'pass_priority'}
    state = act(state, 3-seat, response)
    state = reach(state, Step.COMBAT_DAMAGE)
    mark('Task6-paid-Battle-combat-result-assertion-reached')
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert_life(state)
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    state = resolve_until(state, lambda s: s.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    mark('Task6-paid-Battle-back-preview-assertion-reached')
    state = cold(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == battle)
    assert move['card_view']['name'] == 'Awakened Skyclave'
    assert move['selected_face_index'] == 1 and move['card_view']['selected_face_index'] == 1
    assert set(move['card_view']['types']) == {'Creature'}
    mark('Task6-paid-Battle-transformed-AI-decision-reached')
    choice = decision(state, seat)
    assert choice['type'] == 'cast_spell' and choice['card_id'] == battle and choice['selected_face_index'] == 1
    before = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = act(state, seat, choice)
    mark('Task6-paid-Battle-back-stack-assertion-reached')
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) == before
    assert state.cards[battle].zone == Zone.STACK and set(effective_types(state, battle)) == {'Creature'}
    assert card_mana_value(state.cards[battle]) == 4
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_siege_search_combat_defeat_transformed_ai_cast_and_land_mana(seat):
    state, battle, attackers = battle_position(seat)
    add_bear_blocker(state, seat)
    state = paid_front(state, seat, battle)
    front = serialize_card_view(state, battle)
    assert front['name'] == 'Invasion of Zendikar'
    mark('Task6-paid-Battle-view-assertion-reached')
    assert front['printed_defense'] == '3' and front['defense'] == 3 and front['battle_protector'] == 3-seat
    mark('Task6-paid-Battle-front-view-verified')
    state = cast_paid_back(state, seat, battle, attackers)
    state = resolve_until(state, lambda s: s.cards[battle].zone == Zone.BATTLEFIELD)
    mark('Task6-paid-Battle-back-effective-types-assertion-reached')
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4
    assert has_keyword(state, battle, 'vigilance') and has_keyword(state, battle, 'haste')
    assert state.cards[battle].name == 'Awakened Skyclave' and not state.cards[battle].tapped
    back = serialize_card_view(state, battle)
    mark('Task6-paid-Battle-back-mana-output-assertion-reached')
    assert set(back['mana_source_colors']) == set('WUBRG')
    assert back.get('defense') is None and back.get('battle_protector') is None
    for color in 'WUBRG':
        branch = act(cold(state), seat, {'type': 'tap_land_for_mana', 'card_id': battle, 'color': color})
        assert branch.cards[battle].tapped and branch.players[seat].mana_pool.get(color) == 1
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_planning_and_information_copies_keep_visible_battle_and_hide_unseen_battle(seat):
    from ai.information import decision_view
    from ai.pending_effects import planning_copy
    from game_state.state import object_incarnation
    from rules_engine.graveyard_inventory import public_graveyard_inventory
    from tests.test_battle_entry import BATTLE

    state, battle, _ = battle_position(seat)
    add_bear_blocker(state, seat)
    state = paid_front(state, seat, battle)
    hidden = next(cid for cid in state.players[3-seat].library
                  if state.cards[cid].name == BATTLE.split(' // ')[0])
    original = serialize_match_snapshot(state)
    restored = cold(state)
    planned = planning_copy(restored)
    projected, _ = decision_view(restored, seat, [])
    for current in (restored, planned, projected):
        card = current.cards[battle]
        assert card.printed_defense == '3' and card.counters['defense'] == 3
        assert card.battle_protector == 3-seat
        assert object_incarnation(card) == object_incarnation(state.cards[battle])
        assert public_graveyard_inventory(current, seat)['status'] == 'unknown'
    assert planned.cards[battle] is not state.cards[battle]
    assert projected.cards[hidden].name == '' and projected.cards[hidden].printed_defense is None
    assert serialize_match_snapshot(state) == original


@pytest.mark.parametrize('seat', [1, 2])
def test_departed_copied_battle_lki_keeps_defense_and_protector_after_reload(seat):
    from effects.registry import resolve_effect
    from game_state.state import object_incarnation
    from rules_engine.events import _departed_card_view
    from tests.test_battle_transformed_cast import position as copied_position

    # The initial copy is a declared policy position. Exile and LKI are native.
    state, battle = copied_position(seat, source='Shifting Woodland')
    before = object_incarnation(state.cards[battle])
    resolve_effect(state, seat, 'exile', {'target_card_id': battle})
    state = cold(state)
    current = state.cards[battle]
    assert current.zone == Zone.EXILE and current.name == 'Shifting Woodland'
    assert current.printed_defense is None and current.battle_protector is None
    former = _departed_card_view(state, battle)
    mark('Task6-departed-copied-Battle-LKI-assertion-reached')
    assert 'Battle' in former.types and former.printed_defense == '3'
    assert former.counters['defense'] == 3 and former.battle_protector == 3-seat
    assert current.last_known_battlefield['battlefield_incarnation'] == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_permanent_spell_copy_enters_as_double_faced_battle_token(seat):
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_entry_unadapted_two_families_641 import raw

    state, battle = position(seat)
    for _ in range(6):
        place(state, seat, 'Forest', Zone.BATTLEFIELD)
    engine_id = place_full_printing(state, seat, raw('Lithoform Engine'), Zone.HAND)
    state = announce(state, seat, engine_id)
    assert resolve_top_of_stack(state) and state.cards[engine_id].zone == Zone.BATTLEFIELD
    state = announce(state, seat, battle)
    original = state.stack[-1].id
    before = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield if cid != engine_id)
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine_id, 'ability_index': 2,
                             'targets': {'target_stack_id': original}})
    assert state.cards[engine_id].tapped
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield if cid != engine_id) == before + 4
    assert resolve_top_of_stack(state)
    assert state.stack[-1].payload['__stack_copy_kind'] == 'spell'
    assert state.stack[-1].payload['__copied_from_stack_id'] == original
    assert state.cards[battle].zone == Zone.STACK
    state = cold(state)
    mark('Task6-paid-Battle-spell-copy-entry-assertion-reached')
    assert resolve_top_of_stack(state)
    token = next(state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    assert token.name == 'Invasion of Zendikar' and token.printed_defense == '3'
    assert token.counters['defense'] == 3 and token.battle_protector == 3-seat
    assert token.layout == 'double_faced_token' and len(token.card_faces) == 2
    assert token.card_faces[1]['name'] == 'Awakened Skyclave'
    assert state.cards[battle].zone == Zone.STACK and any(item.id == original for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_defense_battle_departure_has_its_own_reason_in_game_log(seat):
    from rules_engine.counter_removal import remove_counters
    from rules_engine.state_based_actions import apply_state_based_actions
    from tests.test_battle_combat import position as combat_position

    state, battle, _ = combat_position(seat)
    # Declared subtypeless policy position exercises the zero-defense SBA.
    state.cards[battle].type_line = 'Battle'
    state.cards[battle].battle_protector = seat
    assert remove_counters(state, battle, 'defense', 3) == 3
    apply_state_based_actions(state)
    assert state.cards[battle].zone == Zone.GRAVEYARD
    assert any('Invasion of Zendikar' in line and 'zero defense' in line.lower() for line in state.log)


def place_full_printing(state, seat, printing, zone):
    assert printing['object'] == 'card' and len(printing) >= 50
    assert all(printing.get(key) for key in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout'))
    stock = MatchFactory.from_decks([{**printing, 'card_name': printing['name'], 'quantity': 8}], [], seed=1207)
    card = next(card for card in stock.cards.values() if card.zone == Zone.LIBRARY)
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


@pytest.mark.parametrize('seat', [1, 2])
def test_eidolon_uses_the_physical_mana_value_of_a_transformed_cast(seat):
    from rules_engine.counter_placement import put_counters
    from tests.test_any_player_cast_damage import RAW

    state, battle, attackers = battle_position(seat)
    eidolon = place_full_printing(state, 3-seat, RAW['Eidolon of the Great Revel'], Zone.BATTLEFIELD)
    put_counters(state, '+1/+1', 1, target_card_id=eidolon)
    state = paid_front(state, seat, battle)
    state = cast_paid_back(state, seat, battle, attackers)
    assert state.cards[eidolon].zone == Zone.BATTLEFIELD
    mark('Task6-transformed-spell-Eidolon-threshold-assertion-reached')
    assert all(item.source_card_id != eidolon for item in state.stack)
    state = resolve_until(state, lambda s: s.cards[battle].zone == Zone.BATTLEFIELD)
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_fatal_push_without_revolt_leaves_the_physical_transformed_creature(seat):
    from tests.test_veil_turn_protection_goldens import RAW

    opponent = 3-seat
    state, battle, attackers = battle_position(seat, extra=('Swamp',))
    add_bear_blocker(state, seat)
    swamp = place(state, opponent, 'Swamp', Zone.BATTLEFIELD)
    push = place_full_printing(state, opponent, RAW['Fatal Push'], Zone.HAND)
    state = paid_front(state, seat, battle)
    state = cast_paid_back(state, seat, battle, attackers)
    state = resolve_until(state, lambda s: s.cards[battle].zone == Zone.BATTLEFIELD)
    assert opponent not in state.players_with_permanent_departure
    if state.priority_player != opponent:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, opponent, {'type': 'cast_spell', 'card_id': push,
                                 'targets': {'target_card_id': battle}})
    assert state.cards[swamp].tapped and state.cards[push].zone == Zone.STACK
    state = resolve_until(cold(state), lambda s: s.cards[push].zone == Zone.GRAVEYARD)
    mark('Task6-transformed-permanent-Fatal-Push-threshold-assertion-reached')
    assert state.cards[battle].zone == Zone.BATTLEFIELD
    assert card_mana_value(state.cards[battle]) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_seedshark_incubates_for_wedding_festivity_cast_transformed(seat):
    from tests.canonical_positive_fixtures import raw_card

    state, wedding, shark = announce_copied_battle_back(
        seat, raw_card('Wedding Announcement // Wedding Festivity'))
    assert state.cards[wedding].name == 'Wedding Festivity'
    state = resolve_seedshark_trigger(state, seat, wedding, shark, expected=3)
    assert state.cards[wedding].zone == Zone.BATTLEFIELD
    assert (effective_power(state, shark), effective_toughness(state, shark)) == (3, 5)


def announce_copied_battle_back(seat, printing):
    from rules_engine.copiable_values import apply, values
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_battle_defeat import remove
    from tests.test_battle_transformed_cast import cast_action, position as copied_position

    state, battle = copied_position(seat)
    source = place_full_printing(state, seat, printing, Zone.BATTLEFIELD)
    shark = place_full_printing(state, seat, raw_card('Chrome Host Seedshark'), Zone.BATTLEFIELD)
    # Start from a declared copy position and play the actual defeat and cast.
    apply(state.cards[source], values(state.cards[battle]))
    state.cards[source].counters['defense'] = 3
    state.cards[source].battle_protector = 3-seat
    state.mechanic_choice_players = {seat}
    assert remove(state, source, 3) == 3
    assert state.stack[-1].effect_key == 'battle_defeat'
    resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.EXILE
    assert state.pending_mechanic_choice['effect_payload']['target_card_id'] == source
    before_taps = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = act(cold(state), seat, cast_action(source))
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) == before_taps
    return state, source, shark


def resolve_seedshark_trigger(state, seat, source, shark, *, expected):
    from rules_engine.stack_engine import resolve_top_of_stack

    assert state.cards[source].zone == Zone.STACK and card_mana_value(state.cards[source]) == expected
    triggers = [item for item in state.stack if item.source_card_id == shark and item.effect_key == 'incubate']
    assert len(triggers) == 1 and triggers[0] is state.stack[-1]
    mark('Task6-transformed-spell-Incubate-value-assertion-reached')
    assert triggers[0].payload['counters'] == expected
    assert resolve_top_of_stack(state)
    incubators = [state.cards[cid] for cid in state.players[seat].battlefield
                  if state.cards[cid].name == 'Incubator']
    assert len(incubators) == 1 and incubators[0].counters.get('+1/+1') == expected
    assert state.cards[source].zone == Zone.STACK
    assert resolve_top_of_stack(state)
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_seedshark_incubates_the_mana_value_of_the_physical_back_spell(seat):
    from tests.test_transformed_jace_birth_fidelity import official_parent

    state, jace, shark = announce_copied_battle_back(seat, official_parent())
    assert state.cards[jace].name == 'Jace, Telepath Unbound'
    state = resolve_seedshark_trigger(state, seat, jace, shark, expected=2)
    assert state.cards[jace].zone == Zone.BATTLEFIELD and state.cards[jace].loyalty == 5
    exercise_jace_loyalty(state, seat, jace)


def exercise_jace_loyalty(state, seat, jace):
    from rules_engine.counter_placement import put_counters
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_battle_combat import row
    from tests.test_battle_entry import move
    from tests.test_battle_transformed_cast import reject

    opponent = 3 - seat
    creature = place_full_printing(state, opponent, row('Grizzly Bears', 1), Zone.BATTLEFIELD)
    bolt = place_full_printing(state, seat, row('Lightning Bolt', 1), Zone.GRAVEYARD)
    mountain = place_full_printing(state, seat, row('Mountain', 1), Zone.BATTLEFIELD)

    def activate(current, index, target=None):
        action = {'type': 'activate_loyalty', 'card_id': jace, 'ability_index': index}
        if target is not None:
            action['targets'] = {'target_card_id': target}
        return act(current, seat, action)

    optional = activate(cold(state), 0)
    assert resolve_top_of_stack(optional)
    assert optional.cards[jace].loyalty == 6 and effective_power(optional, creature) == 2

    weakened = activate(cold(state), 0, creature)
    assert resolve_top_of_stack(weakened)
    weakened = cold(weakened)
    mark('Task6-Jace-next-turn-stat-assertion-reached')
    assert weakened.cards[jace].loyalty == 6
    assert (effective_power(weakened, creature), effective_toughness(weakened, creature)) == (0, 2)
    for player, power in [(opponent, 0), (seat, 2)]:
        weakened.step = Step.CLEANUP
        RulesEngine().next_step(weakened)
        assert weakened.active_player == player and effective_power(weakened, creature) == power
    stale_creature = activate(cold(state), 0, creature)
    move(stale_creature, creature, Zone.EXILE)
    move(stale_creature, creature, Zone.BATTLEFIELD)
    assert resolve_top_of_stack(stale_creature)
    assert effective_power(stale_creature, creature) == 2

    granted = activate(cold(state), 1, bolt)
    assert resolve_top_of_stack(granted)
    granted = cold(granted)
    expired = cold(granted)
    expired.step = Step.END_STEP
    RulesEngine().next_step(expired)
    assert expired.step == Step.CLEANUP
    from rules_engine.loyalty_instructions import graveyard_cast_granted
    mark('Task6-Jace-cleanup-grant-assertion-reached')
    assert not graveyard_cast_granted(expired, seat, bolt)
    cast_bolt = {'type': 'cast_spell', 'card_id': bolt, 'from_graveyard': True,
                 'targets': {'target_player': opponent}}
    stale_grant = cold(granted)
    move(stale_grant, bolt, Zone.EXILE)
    move(stale_grant, bolt, Zone.GRAVEYARD)
    reject(stale_grant, seat, cast_bolt)
    mark('Task6-Jace-paid-graveyard-cast-reached')
    announced = act(granted, seat, cast_bolt)
    assert announced.cards[jace].loyalty == 2 and announced.cards[mountain].tapped
    resolved = resolve_until(announced, lambda current: current.cards[bolt].zone != Zone.STACK)
    assert resolved.cards[bolt].zone == Zone.EXILE and resolved.players[opponent].life == 17

    countered = cold(announced)
    counter = place_full_printing(countered, opponent, row('Counterspell', 1), Zone.HAND)
    islands = [place_full_printing(countered, opponent, row('Island', 1), Zone.BATTLEFIELD)
               for _ in range(2)]
    spell = next(item for item in countered.stack if item.source_card_id == bolt)
    countered = act(countered, seat, {'type': 'pass_priority'})
    countered = act(countered, opponent, {'type': 'cast_spell', 'card_id': counter,
                                        'targets': {'target_stack_id': spell.id}})
    assert all(countered.cards[cid].tapped for cid in islands)
    countered = resolve_until(countered, lambda current: current.cards[bolt].zone != Zone.STACK)
    assert countered.cards[bolt].zone == Zone.EXILE and countered.players[opponent].life == 20

    emblem_state = cold(state)
    put_counters(emblem_state, 'loyalty', 4, target_card_id=jace)
    emblem_state = activate(emblem_state, 2)
    assert resolve_top_of_stack(emblem_state)
    assert emblem_state.cards[jace].zone == Zone.GRAVEYARD
    assert len(emblem_state.emblems) == 1
    emblem = emblem_state.emblems[0]
    assert emblem_state.cards[emblem].zone == Zone.COMMAND
    spell = place_full_printing(emblem_state, seat, row('Grizzly Bears', 1), Zone.HAND)
    emblem_state.trigger_order_choice_required = True
    emblem_state.trigger_order_choice_players = {seat}
    before = len(emblem_state.players[opponent].library)
    mark('Task6-Jace-emblem-cast-reached')
    emblem_state = act(cold(emblem_state), seat, {'type': 'cast_spell', 'card_id': spell})
    trigger = next(item for item in emblem_state.stack if item.source_card_id == emblem)
    assert emblem_state.pending_trigger_order['phase'] == 'targets'
    choose = {'type': 'choose_trigger_target', 'stack_id': trigger.id}
    reject(emblem_state, seat, {**choose, 'target_player': seat})
    emblem_state = act(cold(emblem_state), seat, {**choose, 'target_player': opponent})
    current = next(item for item in emblem_state.stack if item.id == trigger.id)
    assert current.effect_key == 'mill_cards' and current.payload['target_player'] == opponent
    emblem_state = resolve_until(emblem_state, lambda current: all(item.id != trigger.id for item in current.stack))
    assert len(emblem_state.players[opponent].library) == before - 5
    assert emblem_state.cards[spell].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_transformed_payment_trial_retains_exact_permission(seat, monkeypatch):
    from contextvars import copy_context
    from rules_engine.card_faces import select_cast_face
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_battle_defeat import ref, remove
    from tests.test_battle_transformed_cast import VALKI, position as copied_battle_position

    state, battle = copied_battle_position(seat, VALKI, ('Sphere of Resistance',))
    place(state, 3-seat, 'Sphere of Resistance', Zone.BATTLEFIELD)
    state.mechanic_choice_players = set()
    materialize = AIAgent._materialize_action
    scopes = []

    def probe(agent, current, move, player, **kwargs):
        from ai.casting_resources import _requirements

        assert current is state and player == seat and move['card_id'] == battle
        assert move['from_exile'] is True and move['selected_face_index'] == 1
        before = serialize_match_snapshot(current)
        action = materialize(agent, current, move, player, **kwargs)
        face = select_cast_face(current.cards[battle], 1)
        assert face.name == 'Tibalt, Cosmic Impostor' and face.mana_cost == '{5}{B}{R}'
        requirements, = _requirements(current, face, action, player)
        mark('Task4-automatic-transformed-waiver-requirements-reached')
        assert requirements['generic'] == 1 and sum(requirements.values()) == 1

        from ai.casting_resources import _automatic_effect_permission
        from rules_engine.effect_casts import project_cast

        permission = _automatic_effect_permission(current, player, battle)
        assert permission == {
            'permission_kind': 'battle_transformed', 'target_card_id': battle,
            'reference': ref(current.cards[battle]), 'face_index': 1}
        scopes.append((copy_context(), _automatic_effect_permission))
        projected = project_cast(current, player, action, permission)
        assert projected.cards[battle].zone == Zone.STACK
        assert projected.stack[-1].payload['mana_spent'] == 1
        assert serialize_match_snapshot(current) == before
        return action

    monkeypatch.setattr(AIAgent, '_materialize_action', probe)
    assert remove(state, battle, 3) == 3
    resolve_top_of_stack(state)
    assert state.cards[battle].zone == Zone.STACK
    assert state.stack[-1].payload['mana_spent'] == 1
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) == 1
    (context, permission_for), = scopes
    assert context.run(permission_for, state, seat, battle) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_experience_threshold_uses_the_paid_stack_mana_value(seat):
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_low_mana_value_cast_trigger_boundaries import add_raw
    from tests.test_player_counters import source

    for x, experience in ((2, 0), (3, 1)):
        state, _ = position(seat)
        kalemne = source(state, 'Kalemne, Disciple of Iroas', seat)
        ballista = add_raw(state, 'Walking Ballista', seat)
        state.players[seat].mana_pool = {'C': 2*x}
        state = act(state, seat, {'type': 'cast_spell', 'card_id': ballista,
                                  'cost_choice': {'id': 'base'}, 'targets': {'x_value': x}})
        spell = next(item for item in state.stack if item.source_card_id == ballista)
        assert spell.payload['x_value'] == x and spell.payload['mana_spent'] == 2*x
        assert card_mana_value(state.cards[ballista], x_value=spell.payload['x_value']) == 2*x
        triggers = [item for item in state.stack if item.source_card_id == kalemne.id]
        mark('Task6-player-counter-paid-stack-X-threshold-reached')
        assert len(triggers) == experience
        assert not state.players[seat].counters
        state = cold(state)
        if experience:
            assert state.stack[-1].effect_key == 'add_player_counters'
            assert resolve_top_of_stack(state)
            assert state.cards[ballista].zone == Zone.STACK
        assert state.players[seat].counters.get('experience', 0) == experience
        assert resolve_top_of_stack(state)
        assert state.cards[ballista].zone == Zone.BATTLEFIELD
        assert state.cards[ballista].counters.get('+1/+1') == x


@pytest.mark.parametrize('seat', [1, 2])
def test_physical_aura_back_requires_a_target_and_resolves_attached(seat):
    import hashlib
    import json
    from pathlib import Path
    from rules_engine.copiable_values import apply, values
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_battle_defeat import remove
    from tests.test_battle_transformed_cast import cast_action, casts, position as copied_position, reject

    # Exact Scryfall Oracle Cards record preserved in Clusterforgers/magic
    # at fdd46f9dfcf07c96b3ffab7ab88d6a7544571f8e.
    path = Path(__file__).parent / 'fixtures/battle_cast_full_printing/drogskol-infantry-vow-10.json'
    encoded = path.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == 'fc127ea9210a9076fb05cde2161b116b8007ffefb5231630aafc0a032d998539'
    printing = json.loads(encoded)
    assert printing['name'] == 'Drogskol Infantry // Drogskol Armaments'
    assert printing['layout'] == 'transform' and printing['set'] == 'vow'
    state, battle = copied_position(seat, extra=('Grizzly Bears',))
    bear = place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    forest = next(cid for cid in state.players[seat].battlefield if cid != bear)
    aura = place_full_printing(state, seat, printing, Zone.BATTLEFIELD)
    apply(state.cards[aura], values(state.cards[battle]))
    state.cards[aura].counters['defense'] = 3
    state.cards[aura].battle_protector = 3-seat
    state.mechanic_choice_players = {seat}
    assert remove(state, aura, 3) == 3
    assert state.stack[-1].effect_key == 'battle_defeat'
    assert not resolve_top_of_stack(state)
    assert state.cards[aura].zone == Zone.EXILE
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    state = cold(state)
    offered, = casts(state, seat)
    assert offered['card_view']['name'] == 'Drogskol Armaments'
    assert [target['id'] for target in offered['target_hints']['aura_targets']] == [bear]
    mark('Task4-physical-Aura-back-required-target-rejection-reached')
    reject(state, seat, cast_action(aura))
    reject(state, seat, cast_action(aura, targets={'target_card_id': forest}))
    human = act(cold(state), seat, cast_action(aura, targets={'target_card_id': bear}))
    assert human.cards[aura].zone == Zone.STACK
    mark('Task4-physical-Aura-back-AI-attachment-trial-reached')
    choice = decision(state, seat)
    assert choice['type'] == 'cast_spell'
    assert choice['card_id'] == aura and choice['targets']['target_card_id'] == bear
    state = act(state, seat, choice)
    assert state.cards[aura].zone == Zone.STACK
    assert state.stack[-1].payload['mana_spent'] == 0
    assert card_mana_value(state.cards[aura]) == 2
    state = cold(state)
    assert resolve_top_of_stack(state)
    mark('Task4-physical-Aura-back-attachment-reached')
    assert state.cards[aura].zone == Zone.BATTLEFIELD and state.cards[aura].attached_to == bear
    assert state.cards[aura].name == 'Drogskol Armaments'
    assert (effective_power(state, bear), effective_toughness(state, bear)) == (4, 4)


@pytest.mark.parametrize('seat', [1, 2])
def test_ugin_mass_exile_uses_physical_back_value_and_native_departure(seat):
    from game_state.state import object_incarnation
    from tests.test_knowledge_ingest import _official_card

    state, battle, attackers = battle_position(seat)
    state = paid_front(state, seat, battle)
    state = cast_paid_back(state, seat, battle, attackers)
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    state = reach(state, Step.POSTCOMBAT_MAIN)
    ugin = place_full_printing(state, seat, _official_card('Ugin, the Spirit Dragon'), Zone.BATTLEFIELD)
    assert state.cards[ugin].loyalty == 7
    reference = (object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence)
    assert state.cards[battle].name == 'Awakened Skyclave' and card_mana_value(state.cards[battle]) == 4
    for amount in (3, 4):
        branch = act(cold(state), seat, {'type': 'activate_loyalty', 'card_id': ugin,
                                        'ability_index': 1, 'targets': {'x_value': amount}})
        assert branch.cards[ugin].loyalty == 7-amount
        assert branch.stack[-1].effect_key == 'exile_colored_permanents_mana_value_at_most'
        branch = resolve_until(cold(branch), lambda current: not current.stack)
        mark('Task6-Ugin-physical-back-mana-value-threshold-reached')
        if amount == 3:
            assert branch.cards[battle].zone == Zone.BATTLEFIELD
            assert branch.cards[battle].name == 'Awakened Skyclave'
            assert (object_incarnation(branch.cards[battle]), branch.cards[battle].zone_change_sequence) == reference
        else:
            assert branch.cards[battle].zone == Zone.EXILE and battle in branch.players[seat].exile
            mark('Task6-Ugin-physical-back-native-zone-reset-reached')
            assert branch.cards[battle].name == 'Invasion of Zendikar'
            assert branch.cards[battle].selected_face_index in (None, 0)
            assert object_incarnation(branch.cards[battle]) == reference[0]
            assert branch.cards[battle].zone_change_sequence == reference[1]+1
            assert branch.cards[battle].last_known_battlefield['name'] == 'Awakened Skyclave'


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_stormdrake_exchange_charges_physical_back_mana_value(seat):
    from tests.test_knowledge_ingest import _official_card
    from tests.test_printed_body_admission import facts

    target_seat = 3-seat
    state, battle, attackers = battle_position(target_seat)
    state = paid_front(state, target_seat, battle)
    state = cast_paid_back(state, target_seat, battle, attackers)
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    for _ in range(32):
        if state.active_player == seat and state.step == Step.PRECOMBAT_MAIN:
            break
        assert not state.stack and not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Native priority did not reach the next player main phase')
    place_full_printing(state, seat, _official_card('Island'), Zone.BATTLEFIELD)
    place(state, seat, 'Forest', Zone.BATTLEFIELD)
    printing = facts.__wrapped__()['Volatile Stormdrake']
    mark('Task6-Stormdrake-original-full-printing-intake-reached')
    drake = place_full_printing(state, seat, printing, Zone.HAND)
    mark('Task6-Stormdrake-full-printing-native-birth-reached')
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': drake})
    mark('Task6-Stormdrake-paid-cast-assertion-reached')
    spell = next(item for item in state.stack if item.source_card_id == drake)
    assert spell.payload['mana_spent'] == 2
    state = resolve_until(state, lambda current: current.pending_trigger_order is not None)
    assert state.pending_trigger_order['phase'] == 'targets'
    target_choice = next(move for move in RulesEngine().legal_moves(state, seat)
                         if move['type'] == 'choose_trigger_target' and move['target_card_id'] == battle)
    state = act(cold(state), seat, {'type': 'choose_trigger_target',
                                   'stack_id': target_choice['stack_id'], 'target_card_id': battle})
    state = resolve_until(state, lambda current: bool(current.pending_mechanic_choice))
    mark('Task6-Stormdrake-native-payment-choice-assertion-reached')
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'exchange_energy_payment' and pending['player_id'] == seat
    assert state.cards[drake].controller == target_seat and state.cards[battle].controller == seat
    assert state.players[seat].counters['energy'] == 4
    assert set(pending['options']) == {'pay', 'decline'}
    mark('Task6-Stormdrake-physical-back-energy-cost-reached')
    assert pending['effect_payload']['energy_cost'] == 4
    paid = act(cold(state), seat, {'type': 'choose_mechanic', 'choice_id': 'pay'})
    assert not paid.pending_mechanic_choice
    assert paid.players[seat].counters['energy'] == 0
    assert paid.cards[battle].zone == Zone.BATTLEFIELD and paid.cards[battle].controller == seat
    declined = act(cold(state), seat, {'type': 'choose_mechanic', 'choice_id': 'decline'})
    assert not declined.pending_mechanic_choice
    assert declined.players[seat].counters['energy'] == 4
    assert declined.cards[battle].zone == Zone.GRAVEYARD and battle in declined.players[target_seat].graveyard
    assert declined.cards[battle].name == 'Invasion of Zendikar'


@pytest.mark.parametrize('seat', [1, 2])
def test_native_ai_chooses_ugin_threshold_for_a_physical_transformed_threat(seat):
    from tests.test_knowledge_ingest import _official_card

    target_seat = 3-seat
    state, battle, attackers = battle_position(target_seat)
    state = paid_front(state, target_seat, battle)
    state = cast_paid_back(state, target_seat, battle, attackers)
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    for _ in range(32):
        if state.active_player == seat and state.step == Step.PRECOMBAT_MAIN:
            break
        assert not state.stack and not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Native priority did not reach the Ugin controller main phase')
    ugin = place_full_printing(state, seat, _official_card('Ugin, the Spirit Dragon'), Zone.BATTLEFIELD)
    assert state.cards[ugin].loyalty == 7 and card_mana_value(state.cards[battle]) == 4
    mark('Task6-native-AI-Ugin-physical-threat-threshold-reached')
    choice = decision(state, seat)
    if choice['type'] == 'play_land':
        state = act(state, seat, choice)
        choice = decision(state, seat)
    assert choice['type'] == 'activate_loyalty' and choice['card_id'] == ugin
    mark('Task6-native-AI-Ugin-physical-mana-value-X-reached')
    assert choice['ability_index'] == 1 and choice['targets']['x_value'] == 4
    state = act(state, seat, choice)
    state = resolve_until(cold(state), lambda current: not current.stack)
    assert state.cards[ugin].zone == Zone.BATTLEFIELD and state.cards[ugin].loyalty == 3
    assert state.cards[battle].zone == Zone.EXILE and battle in state.players[target_seat].exile
    assert state.cards[battle].name == 'Invasion of Zendikar'


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_lockdown_preserves_physical_nonland_back_and_returns_linked_card(seat):
    from tests.ai_decisions_canonical_cdba import raw_card as ai_printing
    from tests.canonical_positive_fixtures import raw_card
    from tests.test_knowledge_ingest import _official_card

    state, wedding, shark = announce_copied_battle_back(
        seat, raw_card('Wedding Announcement // Wedding Festivity'))
    state = resolve_seedshark_trigger(state, seat, wedding, shark, expected=3)
    bear = place_full_printing(state, seat, _official_card('Grizzly Bears'), Zone.BATTLEFIELD)
    for _ in range(4):
        place_full_printing(state, seat, _official_card('Plains'), Zone.BATTLEFIELD)
    lockdown = place_full_printing(state, seat, _official_card('Temporary Lockdown'), Zone.HAND)
    disenchant = place_full_printing(state, seat, ai_printing('Disenchant'), Zone.HAND)
    sequence = state.cards[wedding].zone_change_sequence
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': lockdown})
    spell = next(item for item in state.stack if item.source_card_id == lockdown)
    assert spell.payload['mana_spent'] == 3
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task6-linked-mass-exile-physical-back-threshold-reached')
    assert state.cards[wedding].zone == Zone.BATTLEFIELD and state.cards[wedding].name == 'Wedding Festivity'
    assert card_mana_value(state.cards[wedding]) == 3
    assert state.cards[wedding].zone_change_sequence == sequence
    assert state.cards[shark].zone == Zone.BATTLEFIELD
    assert state.cards[bear].zone == Zone.EXILE and bear in state.players[seat].exile
    link, = state.linked_exiles
    assert link['source_id'] == lockdown and link['card_ids'] == [bear]
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': disenchant,
                                   'targets': {'target_card_id': lockdown}})
    spell = next(item for item in state.stack if item.source_card_id == disenchant)
    assert spell.payload['mana_spent'] == 2
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task6-linked-mass-exile-native-return-reached')
    assert state.cards[lockdown].zone == Zone.GRAVEYARD
    assert state.cards[bear].zone == Zone.BATTLEFIELD and state.cards[bear].controller == seat
    assert state.cards[wedding].zone == Zone.BATTLEFIELD and state.cards[wedding].zone_change_sequence == sequence
    assert not state.linked_exiles
    assert (effective_power(state, bear), effective_toughness(state, bear)) == (3, 3)


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_mass_exile_uses_current_land_type_and_predeparture_cohort(seat, monkeypatch):
    from rules_engine import events
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_battle_defeat import remove
    from tests.test_battle_transformed_cast import cast_action, position as copied_position
    from tests.test_entry_unadapted_two_families_641 import raw
    from tests.test_knowledge_ingest import _official_card

    state, battle = copied_position(seat)
    for _ in range(6):
        place(state, seat, 'Forest', Zone.BATTLEFIELD)
    engine = place_full_printing(state, seat, raw('Lithoform Engine'), Zone.HAND)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': engine})
    state = resolve_until(state, lambda current: not current.stack)
    state.mechanic_choice_players = {seat}
    assert remove(state, battle, 3) == 3
    assert not resolve_top_of_stack(state) and state.pending_mechanic_choice['kind'] == 'effect_cast'
    state = act(cold(state), seat, cast_action(battle))
    original = state.stack[-1].id
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine, 'ability_index': 2,
                             'targets': {'target_stack_id': original}})
    assert state.cards[engine].tapped
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task6-linked-exile-paid-copy-resolved')
    copy, = [cid for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    mark('Task6-linked-exile-copy-identity-reached')
    assert state.cards[copy].name == 'Awakened Skyclave'
    mark('Task6-linked-exile-copy-mana-value-reached')
    assert card_mana_value(state.cards[copy]) == 0
    mark('Task6-linked-exile-copy-current-types-reached')
    assert set(effective_types(state, copy)) == {'Land', 'Creature', 'Token'}
    mark('Task6-linked-exile-physical-value-reached')
    assert card_mana_value(state.cards[battle]) == 4
    for _ in range(2):
        place_full_printing(state, seat, _official_card('Plains'), Zone.BATTLEFIELD)
    bear = place_full_printing(state, seat, _official_card('Grizzly Bears'), Zone.BATTLEFIELD)
    lockdown = place_full_printing(state, seat, _official_card('Temporary Lockdown'), Zone.HAND)
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': lockdown})
    collect = events._collect_triggers
    departures = []

    def observe_departure(current, event, payload):
        if event == 'leaves_battlefield':
            mark('Task6-linked-exile-current-land-cohort-reached')
            assert payload['card_id'] != copy
            mark('Task6-linked-exile-before-native-departure-reached')
            assert current.cards[payload['card_id']].zone == Zone.BATTLEFIELD
            departures.append(payload['card_id'])
        return collect(current, event, payload)

    with monkeypatch.context() as patch:
        patch.setattr(events, '_collect_triggers', observe_departure)
        state = resolve_until(state, lambda current: not current.stack)
    assert departures == [bear]
    assert state.cards[copy].zone == state.cards[battle].zone == Zone.BATTLEFIELD
    assert set(effective_types(state, copy)) == {'Land', 'Creature', 'Token'}
    assert state.cards[bear].zone == Zone.EXILE
    link, = state.linked_exiles
    assert link['source_id'] == lockdown and link['card_ids'] == [bear]


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_sacrifice_trigger_can_damage_battle_after_source_departs(seat):
    from game_state.state import object_incarnation
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_knowledge_ingest import _official_card

    state, battle, _ = battle_position(seat)
    # The additional basic lands are declared resources; every spell is paid.
    for name in ('Mountain', 'Mountain', 'Mountain', 'Swamp'):
        place_full_printing(state, seat, _official_card(name), Zone.BATTLEFIELD)
    state = paid_front(state, seat, battle)
    devil = place_full_printing(state, seat, raw_card('Mayhem Devil'), Zone.HAND)
    state = announce(state, seat, devil, cost=3)
    state = resolve_until(state, lambda current: not current.stack)
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = announce(state, seat, firebrand, cost=1)
    state = resolve_until(state, lambda current: not current.stack)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    reference = {'incarnation': object_incarnation(state.cards[devil]),
                 'zone_change_sequence': state.cards[devil].zone_change_sequence}
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
                                   'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert state.cards[firebrand].zone == Zone.GRAVEYARD
    assert state.pending_trigger_order['phase'] == 'targets'
    trigger = next(item for item in state.stack if item.source_card_id == devil)
    assert trigger.payload['__trigger_source_reference'] == reference
    state = cold(state)
    choices = RulesEngine().legal_moves(state, seat)
    mark('Task6-paid-any-target-trigger-Battle-option-reached')
    assert any(move.get('target_card_id') == battle for move in choices)
    assert {move.get('target_player') for move in choices if 'target_player' in move} == {1, 2}
    assert all('Land' not in effective_types(state, move['target_card_id'])
               for move in choices if move.get('target_card_id') != battle and move.get('target_card_id'))
    state = act(state, seat, {'type': 'choose_trigger_target', 'stack_id': trigger.id,
                            'target_card_id': battle})
    bolt = place_full_printing(state, seat, _official_card('Lightning Bolt'), Zone.HAND)
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': bolt,
                                   'targets': {'target_card_id': devil}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: current.cards[devil].zone == Zone.GRAVEYARD)
    trigger = next(item for item in state.stack if item.source_card_id == devil)
    assert trigger.payload['__trigger_source_reference'] == reference
    assert trigger.payload['__source_lki']['name'] == 'Mayhem Devil'
    state = resolve_until(cold(state), lambda current: not current.stack)
    mark('Task6-paid-departed-source-Battle-trigger-damage-reached')
    assert state.cards[battle].zone == Zone.BATTLEFIELD and state.cards[battle].counters['defense'] == 2
    assert state.cards[battle].battle_protector == 3-seat
    assert state.cards[devil].zone == state.cards[firebrand].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 20 and state.players[3-seat].life == 19


@pytest.mark.parametrize('seat', [1, 2])
def test_old_damage_trigger_does_not_follow_blinked_back_to_new_siege(seat):
    from game_state.state import object_incarnation
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_copy_native_936 import raw
    from tests.test_knowledge_ingest import _official_card

    state, battle, attackers = battle_position(seat)
    for name in ('Mountain', 'Mountain', 'Swamp', 'Plains'):
        place_full_printing(state, seat, _official_card(name), Zone.BATTLEFIELD)
    state = paid_front(state, seat, battle)
    devil = place_full_printing(state, seat, raw_card('Mayhem Devil'), Zone.HAND)
    state = announce(state, seat, devil, cost=3)
    state = resolve_until(state, lambda current: not current.stack)
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = announce(state, seat, firebrand, cost=1)
    state = resolve_until(state, lambda current: not current.stack)
    state = cast_paid_back(state, seat, battle, attackers)
    state = resolve_until(state, lambda current: not current.stack)
    assert state.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    old_reference = [object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence]
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
                                   'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert state.pending_trigger_order['phase'] == 'targets'
    trigger = next(item for item in state.stack if item.source_card_id == devil)
    state = act(cold(state), seat, {'type': 'choose_trigger_target', 'stack_id': trigger.id,
                                   'target_card_id': battle})
    blink = place_full_printing(state, seat, raw('Cloudshift'), Zone.HAND)
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': blink,
                                   'targets': {'target_card_id': battle}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    assert state.cards[battle].name == 'Invasion of Zendikar'
    assert set(effective_types(state, battle)) == {'Battle'}
    assert state.cards[battle].counters['defense'] == 3
    assert [object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence] != old_reference
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': []})
    state = resolve_until(cold(state), lambda current: not current.stack)
    mark('Task6-returned-Siege-old-trigger-damage-reached')
    assert state.cards[battle].zone == Zone.BATTLEFIELD and state.cards[battle].counters['defense'] == 3
    assert state.cards[battle].battle_protector == 3-seat
    assert state.cards[blink].zone == state.cards[firebrand].zone == Zone.GRAVEYARD
    assert state.players[seat].life == 20 and state.players[3-seat].life == 19


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_trigger_copy_retargets_from_card_to_player_without_old_reference(seat):
    from game_state.state import object_incarnation
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_unadapted_two_families_641 import raw
    from tests.test_knowledge_ingest import _official_card

    state, battle, attackers = battle_position(seat)
    for _ in range(6):
        place(state, seat, 'Forest', Zone.BATTLEFIELD)
    for name in ('Mountain', 'Mountain', 'Swamp'):
        place_full_printing(state, seat, _official_card(name), Zone.BATTLEFIELD)
    engine = place_full_printing(state, seat, raw('Lithoform Engine'), Zone.HAND)
    state = announce(state, seat, engine, cost=4)
    state = resolve_until(state, lambda current: not current.stack)
    state = paid_front(state, seat, battle)
    devil = place_full_printing(state, seat, raw_card('Mayhem Devil'), Zone.HAND)
    state = announce(state, seat, devil, cost=3)
    state = resolve_until(state, lambda current: not current.stack)
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = announce(state, seat, firebrand, cost=1)
    state = resolve_until(state, lambda current: not current.stack)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
                                   'ability_index': 0, 'targets': {'target_player': 3-seat}})
    original = next(item for item in state.stack if item.source_card_id == devil)
    state = act(cold(state), seat, {'type': 'choose_trigger_target', 'stack_id': original.id,
                                   'target_card_id': battle})
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': engine,
                                   'ability_index': 0, 'targets': {'target_stack_id': original.id}})
    assert state.cards[engine].tapped
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'copy_target'
    copied_id = pending['stack_id']
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__stack_copy_kind'] == 'triggered'
    assert copied.payload['__trigger_target_reference'] == [
        object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence]
    assert f'target_player:{3-seat}' in pending['options']
    assert f'target_card_id:{attackers[0]}' in pending['options']
    player_branch = act(cold(state), seat, {'type': 'choose_mechanic',
                                           'card_ids': [f'target_player:{3-seat}']})
    player_branch = resolve_until(cold(player_branch), lambda current: not current.stack)
    mark('Task6-retargeted-trigger-copy-player-resolution-reached')
    assert player_branch.players[3-seat].life == 18 and player_branch.players[seat].life == 20
    assert player_branch.cards[battle].counters['defense'] == 2
    card_branch = act(cold(state), seat, {'type': 'choose_mechanic',
                                         'card_ids': [f'target_card_id:{attackers[0]}']})
    copied = next(item for item in card_branch.stack if item.id == copied_id)
    assert copied.payload['__trigger_target_reference'] == [
        object_incarnation(card_branch.cards[attackers[0]]), card_branch.cards[attackers[0]].zone_change_sequence]
    card_branch = resolve_until(cold(card_branch), lambda current: not current.stack)
    assert card_branch.players[3-seat].life == 19 and card_branch.players[seat].life == 20
    assert card_branch.cards[battle].counters['defense'] == 2
    assert card_branch.cards[attackers[0]].zone == Zone.BATTLEFIELD
    assert card_branch.cards[attackers[0]].counters['__damage_marked'] == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_copy_can_choose_returned_siege_as_new_object_or_keep_old_target(seat):
    from game_state.state import object_incarnation
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_copy_native_936 import raw
    from tests.test_entry_unadapted_two_families_641 import raw as engine_printing
    from tests.test_knowledge_ingest import _official_card

    state, battle, attackers = battle_position(seat)
    for _ in range(6):
        place(state, seat, 'Forest', Zone.BATTLEFIELD)
    for name in ('Mountain', 'Mountain', 'Swamp', 'Plains'):
        place_full_printing(state, seat, _official_card(name), Zone.BATTLEFIELD)
    mark('Task6-trigger-copy-new-object-full-engine-printing-reached')
    engine = place_full_printing(state, seat, engine_printing('Lithoform Engine'), Zone.HAND)
    state = announce(state, seat, engine, cost=4)
    state = resolve_until(state, lambda current: not current.stack)
    state = paid_front(state, seat, battle)
    devil = place_full_printing(state, seat, raw_card('Mayhem Devil'), Zone.HAND)
    state = announce(state, seat, devil, cost=3)
    state = resolve_until(state, lambda current: not current.stack)
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = announce(state, seat, firebrand, cost=1)
    state = resolve_until(state, lambda current: not current.stack)
    state = cast_paid_back(state, seat, battle, attackers)
    state = resolve_until(state, lambda current: not current.stack)
    old_reference = [object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence]
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
                                   'ability_index': 0, 'targets': {'target_player': 3-seat}})
    original = next(item for item in state.stack if item.source_card_id == devil)
    state = act(cold(state), seat, {'type': 'choose_trigger_target', 'stack_id': original.id,
                                   'target_card_id': battle})
    blink = place_full_printing(state, seat, raw('Cloudshift'), Zone.HAND)
    state = act(cold(state), seat, {'type': 'cast_spell', 'card_id': blink,
                                   'targets': {'target_card_id': battle}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': []})
    current_reference = [object_incarnation(state.cards[battle]), state.cards[battle].zone_change_sequence]
    assert current_reference != old_reference and state.cards[battle].name == 'Invasion of Zendikar'
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': engine,
                                   'ability_index': 0, 'targets': {'target_stack_id': original.id}})
    assert state.cards[engine].tapped
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'copy_target'
    copied_id = pending['stack_id']
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__trigger_target_reference'] == old_reference
    mark('Task6-trigger-copy-returned-object-choice-reached')
    assert f'target_card_id:{battle}' in pending['options'] and 'keep' in pending['options']
    kept = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    kept_copy = next(item for item in kept.stack if item.id == copied_id)
    assert kept_copy.payload['__trigger_target_reference'] == old_reference
    kept = resolve_until(cold(kept), lambda current: not current.stack)
    assert kept.cards[battle].zone == Zone.BATTLEFIELD and kept.cards[battle].counters['defense'] == 3
    assert kept.players[3-seat].life == 19 and kept.players[seat].life == 20
    changed = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{battle}']})
    changed_copy = next(item for item in changed.stack if item.id == copied_id)
    original_trigger = next(item for item in changed.stack if item.id == original.id)
    assert changed_copy.payload['__trigger_target_reference'] == current_reference
    assert original_trigger.payload['__trigger_target_reference'] == old_reference
    changed = resolve_until(cold(changed), lambda current: not current.stack)
    assert changed.cards[battle].zone == Zone.BATTLEFIELD and changed.cards[battle].counters['defense'] == 2
    assert changed.players[3-seat].life == 19 and changed.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_damage_trigger_finishes_beneficial_own_siege_without_hidden_hand_peeking(seat, monkeypatch):
    from ai import heuristics
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_battle_transformed_cast import row as back_printing
    from tests.test_knowledge_ingest import _official_card

    state, battle, _ = battle_position(seat)
    for name in ('Mountain', 'Mountain', 'Mountain', 'Mountain', 'Swamp'):
        place_full_printing(state, seat, _official_card(name), Zone.BATTLEFIELD)
    state = paid_front(state, seat, battle)
    devil = place_full_printing(state, seat, raw_card('Mayhem Devil'), Zone.HAND)
    state = announce(state, seat, devil, cost=3)
    state = resolve_until(state, lambda current: not current.stack)
    firebrands = []
    for _ in range(3):
        source = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
        state = announce(state, seat, source, cost=1)
        state = resolve_until(state, lambda current: not current.stack)
        firebrands.append(source)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    for source in firebrands[:2]:
        state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': source,
                                       'ability_index': 0, 'targets': {'target_player': 3-seat}})
        trigger = next(item for item in state.stack if item.source_card_id == devil)
        state = act(cold(state), seat, {'type': 'choose_trigger_target', 'stack_id': trigger.id,
                                       'target_card_id': battle})
        state = resolve_until(state, lambda current: not current.stack)
    assert state.cards[battle].counters['defense'] == 1
    assert state.players[3-seat].life == 18
    state.trigger_order_choice_required = False
    state.trigger_order_choice_players = set()
    policy = heuristics.choose_damage_trigger_target

    def automatic(current):
        calls = []
        def unchanged_policy(position, controller, amount, options, **context):
            before = serialize_match_snapshot(position)
            selected = policy(position, controller, amount, options, **context)
            assert serialize_match_snapshot(position) == before
            calls.append(controller)
            return selected
        with monkeypatch.context() as patch:
            patch.setattr(heuristics, 'choose_damage_trigger_target', unchanged_policy)
            current = act(current, seat, {'type': 'activate_ability', 'card_id': firebrands[2],
                                         'ability_index': 0, 'targets': {'target_player': 3-seat}})
        assert calls
        return current

    chosen = automatic(cold(state))
    trigger = next(item for item in chosen.stack if item.source_card_id == devil)
    mark('Task6-automatic-beneficial-own-Siege-target-reached')
    assert trigger.payload.get('target_card_id') == battle and trigger.payload.get('target_player') is None
    chosen = resolve_until(chosen, lambda current: current.pending_mechanic_choice is not None)
    assert chosen.cards[battle].zone == Zone.EXILE
    assert chosen.pending_mechanic_choice['kind'] == 'effect_cast'
    action = decision(chosen, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == battle
    chosen = act(cold(chosen), seat, action)
    chosen = resolve_until(chosen, lambda current: not current.stack)
    assert chosen.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(chosen, battle)) == {'Creature', 'Land'}
    assert effective_power(chosen, battle) == effective_toughness(chosen, battle) == 4
    assert chosen.players[seat].life == 20 and chosen.players[3-seat].life == 17
    # These are independent declared policy controls, not inferred play histories.
    lethal = cold(state)
    lethal.players[3-seat].life = 1
    lethal = automatic(lethal)
    trigger = next(item for item in lethal.stack if item.source_card_id == devil)
    assert trigger.payload.get('target_player') == 3-seat
    restricted = cold(state)
    place_full_printing(restricted, 3-seat, back_printing('Drannith Magistrate', 1), Zone.BATTLEFIELD)
    restricted = automatic(restricted)
    trigger = next(item for item in restricted.stack if item.source_card_id == devil)
    assert trigger.payload.get('target_player') == 3-seat
    for name in ('Lightning Bolt', 'Forest'):
        hidden = cold(state)
        place_full_printing(hidden, 3-seat, _official_card(name), Zone.HAND)
        hidden = automatic(hidden)
        trigger = next(item for item in hidden.stack if item.source_card_id == devil)
        assert trigger.payload.get('target_card_id') == battle


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_towashi_observes_modal_back_cast_through_copied_siege_defeat(seat):
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.day_night_apnap_canonical import raw_card
    from tests.test_battle_defeat import remove
    from tests.test_battle_transformed_cast import VALKI, cast_action, position as copied_position
    from tests.test_knowledge_ingest import _official_card

    # The initial copied Siege is a declared position; the observer, defeat,
    # exile, back spell, entry trigger and accepted draw are played natively.
    state, battle = copied_position(seat, source=VALKI)
    place_full_printing(state, seat, _official_card('Island'), Zone.BATTLEFIELD)
    observer = place_full_printing(state, seat, raw_card('Corruption of Towashi'), Zone.HAND)
    state = announce(state, seat, observer, cost=5)
    state = resolve_until(state, lambda current: not current.stack)
    incubator, = [cid for cid in state.players[seat].battlefield
                  if state.cards[cid].name == 'Incubator']
    assert state.cards[incubator].counters == {'+1/+1': 4}
    state.mechanic_choice_players = {seat}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    assert remove(state, battle, 3) == 3
    assert not resolve_top_of_stack(state)
    assert state.cards[battle].zone == Zone.EXILE
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    state = act(cold(state), seat, cast_action(battle))
    assert state.cards[battle].zone == Zone.STACK
    assert state.cards[battle].name == 'Tibalt, Cosmic Impostor'
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert state.cards[battle].layout == 'modal_dfc' and state.cards[battle].selected_face_index == 1
    assert state.cards[battle].loyalty == 5
    mark('Task6-Towashi-modal-transformed-entry-trigger-reached')
    trigger, = [item for item in state.stack if item.source_card_id == observer]
    assert trigger.effect_key == 'draw_cards' and trigger.controller == seat
    assert trigger.payload['target_player'] == seat and trigger.payload['__may_choose']
    before = len(state.players[seat].hand)
    assert not resolve_top_of_stack(state)
    assert state.pending_trigger_order['phase'] == 'optional'
    state = cold(state)
    accept = next(move for move in RulesEngine().legal_moves(state, seat)
                  if move['type'] == 'choose_optional_effect' and move['accept'])
    state = act(state, seat, accept)
    assert len(state.players[seat].hand) == before + 1
    assert not state.stack and state.pending_trigger_order is None
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': incubator,
                                   'ability_index': 0})
    state = resolve_until(state, lambda current: not current.stack)
    assert state.cards[incubator].selected_face_index == 1
    assert len(state.players[seat].hand) == before + 1


@pytest.mark.parametrize('seat', [1, 2])
def test_physical_avatar_back_keeps_optional_sacrifice_payment_and_tax(seat):
    import hashlib
    import json
    from pathlib import Path
    from rules_engine.card_faces import select_cast_face
    from rules_engine.copiable_values import apply, values
    from rules_engine.costs import collect_cost_options
    from rules_engine.stack_engine import resolve_top_of_stack
    from tests.test_battle_defeat import remove
    from tests.test_battle_transformed_cast import cast_action, position as copied_position, reject, row
    from tests.test_knowledge_ingest import _official_card

    data = (Path(__file__).parent / 'fixtures/battle_cast_full_printing/extus-stx-149.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == '76f49e104f586cc4f72a93a42f1076cbb0cac73ac54d187a2a065d0360caf826'
    printing = json.loads(data)
    assert len(printing) == 61 and len(printing['card_faces']) == 2
    from rules_engine.spell_cost_clauses import spell_additional_costs
    text = printing['card_faces'][1]['oracle_text']
    # Explicit negative grammar vectors are not substitute printing objects.
    for malformed in (text + ' Draw a card.', text.replace('haste and', 'flying and'),
                      text.replace('may sacrifice any number of creatures', 'may sacrifice any number of artifacts')):
        assert spell_additional_costs(malformed, printing['card_faces'][1]['name']) is None
    # Copy, tax and available creatures are declared positions. The native
    # defeat, back announcement, selected costs and resolution follow below.
    state, template = copied_position(seat)
    source = place_full_printing(state, seat, printing, Zone.BATTLEFIELD)
    apply(state.cards[source], values(state.cards[template]))
    state.cards[source].counters['defense'] = 3
    state.cards[source].battle_protector = 3-seat
    own = place_full_printing(state, seat, _official_card('Grizzly Bears'), Zone.BATTLEFIELD)
    other = place_full_printing(state, 3-seat, _official_card('Grizzly Bears'), Zone.BATTLEFIELD)
    place_full_printing(state, 3-seat, row('Sphere of Resistance', 1), Zone.BATTLEFIELD)
    state.mechanic_choice_players = {seat}
    assert remove(state, source, 3) == 3
    assert not resolve_top_of_stack(state) and state.cards[source].zone == Zone.EXILE
    state = cold(state)
    options = collect_cost_options(state, seat, select_cast_face(state.cards[source], 1), without_mana=True)
    mark('Task4-physical-Avatar-back-optional-sacrifice-cost-options-reached')
    assert {option.sacrifice_creatures for option in options} == {0, 1}
    paid = next(option for option in options if option.sacrifice_creatures == 1)
    free = next(option for option in options if option.sacrifice_creatures == 0)
    reject(cold(state), seat, cast_action(source, cost_choice={'id': paid.id, 'sacrifice_card_ids': []}))
    reject(cold(state), seat, cast_action(source, cost_choice={'id': paid.id, 'sacrifice_card_ids': [other]}))
    for option, chosen, mana in ((paid, [own], 0), (free, [], 1)):
        branch = cold(state)
        before = sum(branch.cards[cid].tapped for cid in branch.players[seat].battlefield)
        branch = act(branch, seat, cast_action(source, cost_choice={
            'id': option.id, 'sacrifice_card_ids': chosen}))
        mark('Task4-physical-Avatar-back-selected-cost-paid-reached')
        spell = next(item for item in branch.stack if item.source_card_id == source)
        assert spell.payload['mana_spent'] == mana
        assert sum(branch.cards[cid].tapped for cid in branch.players[seat].battlefield) == before + mana
        assert branch.cards[own].zone == (Zone.GRAVEYARD if chosen else Zone.BATTLEFIELD)
        assert branch.cards[other].zone == Zone.BATTLEFIELD
        assert branch.cards[source].name == 'Awaken the Blood Avatar' and card_mana_value(branch.cards[source]) == 8
        branch = resolve_until(cold(branch), lambda current: current.pending_mechanic_choice is not None)
        pending = branch.pending_mechanic_choice
        assert pending['kind'] == 'sacrifice' and pending['player_id'] == 3-seat
        assert pending['count'] == 1 and pending['options'] == [other]
        assert not any(branch.cards[cid].is_token for cid in branch.players[seat].battlefield)
        branch = act(cold(branch), 3-seat, {'type': 'choose_mechanic', 'card_ids': [other]})
        branch = resolve_until(branch, lambda current: not current.stack)
        mark('Task4-physical-Avatar-back-complete-resolution-reached')
        assert branch.cards[source].zone == Zone.GRAVEYARD
        assert branch.cards[other].zone == Zone.GRAVEYARD
        avatar, = [cid for cid in branch.players[seat].battlefield if branch.cards[cid].is_token]
        assert effective_power(branch, avatar) == 3 and effective_toughness(branch, avatar) == 6
        assert has_keyword(branch, avatar, 'haste')
        assert_life(branch)
        branch = reach(branch, Step.DECLARE_ATTACKERS)
        branch = act(branch, seat, {'type': 'attack', 'attackers': [avatar]})
        mark('Task4-physical-Avatar-back-token-attack-trigger-reached')
        assert any(item.source_card_id == avatar for item in branch.stack)
        branch = resolve_until(cold(branch), lambda current: not current.stack)
        assert branch.players[3-seat].life == 17 and branch.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_siege_snapshot_documents_and_restored_permissions_are_independent(seat):
    from copy import deepcopy
    from game_state.serializers import deserialize_match_snapshot
    from tests.test_battle_transformed_cast import cast_action, reject

    state, battle, attackers = battle_position(seat)
    state = paid_front(state, seat, battle)
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
                            'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.stack[-1].effect_key == 'battle_defeat'
    baseline = deepcopy(serialize_match_snapshot(state))
    outgoing = serialize_match_snapshot(state)
    # Deliberate transport-document corruption is a negative control, not a
    # substitute printing or a played change to this game's physical card.
    outgoing['stack'][-1]['payload']['__trigger_source_reference']['incarnation'] += 1
    mark('Task6-Battle-outgoing-stack-snapshot-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    outgoing = serialize_match_snapshot(state)
    outgoing['cards'][battle]['card_faces'][1]['name'] = 'Untrusted transport edit'
    assert serialize_match_snapshot(state) == baseline
    view = serialize_card_view(state, battle)
    view['card_faces'][1]['name'] = 'Untrusted card-view edit'
    mark('Task6-Battle-card-view-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    from game_state.serializers import serialize_match
    public = serialize_match(state)
    displayed = next(card for card in public['players'][seat]['battlefield'] if card['id'] == battle)
    displayed['card_faces'][1]['name'] = 'Untrusted match-view edit'
    assert serialize_match_snapshot(state) == baseline
    document = deepcopy(baseline)
    restored = deserialize_match_snapshot(document)
    sibling = deserialize_match_snapshot(document)
    sibling_before = deepcopy(serialize_match_snapshot(sibling))
    restored.stack[-1].payload['__trigger_source_reference']['incarnation'] += 1
    restored.cards[battle].card_faces[1]['name'] = 'Untrusted restored edit'
    mark('Task6-Battle-restored-stack-snapshot-isolation-reached')
    assert document == baseline

    assert serialize_match_snapshot(sibling) == sibling_before

    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    baseline = deepcopy(serialize_match_snapshot(state))
    outgoing = serialize_match_snapshot(state)
    outgoing['pending_mechanic_choice']['effect_payload']['face_index'] = 0
    outgoing['cards'][battle]['last_known_battlefield']['types'].clear()
    mark('Task6-Battle-outgoing-permission-snapshot-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    document = deepcopy(baseline)
    restored = deserialize_match_snapshot(document)
    sibling = deserialize_match_snapshot(document)
    sibling_before = deepcopy(serialize_match_snapshot(sibling))
    restored.pending_mechanic_choice['effect_payload']['face_index'] = 0
    restored.cards[battle].last_known_battlefield['types'].clear()
    mark('Task6-Battle-restored-permission-snapshot-isolation-reached')
    assert document == baseline
    mark('Task6-Battle-restored-permission-input-unchanged')
    assert serialize_match_snapshot(sibling) == sibling_before
    mark('Task6-Battle-restored-permission-sibling-unchanged')
    reject(restored, seat, cast_action(battle))
    mark('Task6-Battle-corrupted-permission-rejected')
    for current in (state, sibling):
        current = act(current, seat, cast_action(battle))
        mark('Task6-Battle-independent-snapshot-native-cast-reached')
        assert current.cards[battle].zone == Zone.STACK
        assert current.cards[battle].name == 'Awakened Skyclave'
        current = resolve_until(current, lambda position: position.cards[battle].zone == Zone.BATTLEFIELD)
        assert set(effective_types(current, battle)) == {'Creature', 'Land'}
        assert effective_power(current, battle) == effective_toughness(current, battle) == 4
    assert document == baseline


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_trample_to_siege_counts_native_marked_lethal_damage(seat):
    from rules_engine.combat import DMG_MARK_KEY
    from tests.pending_permanent_fullraw import raw_card as permanent_raw
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_copy_native_936 import raw
    from tests.test_knowledge_ingest import _official_card
    from tests.test_battle_transformed_cast import cast_action

    state, battle = position(seat)
    # These complete-printing permanents are declared ready resources, not a
    # claim that their earlier turns were played. All subsequent actions are native.
    elf = place_full_printing(state, seat, raw_card('Llanowar Elves'), Zone.BATTLEFIELD)
    state.cards[elf].summoning_sick = False
    state.cards[elf].entered_turn = state.turn - 1
    myr = place_full_printing(state, 3-seat, permanent_raw('Darksteel Myr'), Zone.BATTLEFIELD)
    mountain = place_full_printing(state, seat, _official_card('Mountain'), Zone.BATTLEFIELD)
    state.mechanic_choice_players = {seat}
    forests = [cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Forest']
    for cid in forests[:4]:
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': cid, 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': battle})
    assert state.stack[-1].payload['mana_spent'] == 4
    assert not state.cards[elf].tapped and not sum(state.players[seat].mana_pool.values())
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    chosen = state.pending_mechanic_choice['options'][:2]
    assert len(chosen) == 2
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.cards[battle].counters['defense'] == 3
    assert state.cards[battle].battle_protector == 3-seat

    rancor = place_full_printing(state, seat, raw('Rancor'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': forests[4], 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rancor,
                            'targets': {'target_card_id': elf}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    assert effective_power(state, elf) == 3 and has_keyword(state, elf, 'trample')
    assert not state.cards[elf].tapped
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': mountain, 'color': 'R'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': firebrand})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
        'ability_index': 0, 'targets': {'target_card_id': myr}})
    assert state.cards[firebrand].zone == Zone.GRAVEYARD
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task5-native-marked-lethal-indestructible-blocker-reached')
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert has_keyword(state, myr, 'indestructible') and effective_toughness(state, myr) == 1
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    state = reach(cold(state), Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': [elf],
                            'attack_targets': {elf: 'battle:' + battle}})
    mark('Task5-native-trample-Siege-attack-declared')
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'block', 'blocks': {elf: [myr]}})
    mark('Task5-native-indestructible-block-declared')
    # Exercise the automatic fallback, which must obey the same marked-lethal
    # rule as explicit player assignments. No damage counters are edited.
    state.mechanic_choice_players = set()
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    mark('Task5-automatic-trample-marked-lethal-Siege-damage-reached')
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert_life(state)
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    state.mechanic_choice_players = {seat}
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_deathtouch_trample_to_siege_counts_native_marked_lethal_damage(seat):
    from rules_engine.combat import DMG_MARK_KEY
    from tests.combat_canonical_022 import raw_card as combat_raw
    from tests.pending_permanent_fullraw import raw_card as permanent_raw
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_copy_native_936 import raw
    from tests.test_knowledge_ingest import _official_card
    from tests.test_battle_transformed_cast import cast_action

    state, battle = position(seat)
    # These complete-printing permanents are declared ready resources, not a
    # claim that their earlier turns were played. All subsequent actions are native.
    rats = place_full_printing(state, seat, combat_raw('Typhoid Rats'), Zone.BATTLEFIELD)
    state.cards[rats].summoning_sick = False
    state.cards[rats].entered_turn = state.turn - 1
    myr = place_full_printing(state, 3-seat, permanent_raw('Darksteel Myr'), Zone.BATTLEFIELD)
    mountain = place_full_printing(state, seat, _official_card('Mountain'), Zone.BATTLEFIELD)
    state.mechanic_choice_players = {seat}
    forests = [cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Forest']
    for cid in forests[:4]:
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': cid, 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': battle})
    assert state.stack[-1].payload['mana_spent'] == 4
    assert not state.cards[rats].tapped and not sum(state.players[seat].mana_pool.values())
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    chosen = state.pending_mechanic_choice['options'][:2]
    assert len(chosen) == 2
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.cards[battle].counters['defense'] == 3
    assert state.cards[battle].battle_protector == 3-seat

    rancor = place_full_printing(state, seat, raw('Rancor'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': forests[4], 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rancor,
                            'targets': {'target_card_id': rats}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    assert effective_power(state, rats) == 3 and has_keyword(state, rats, 'trample')
    assert not state.cards[rats].tapped
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': mountain, 'color': 'R'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': firebrand})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
        'ability_index': 0, 'targets': {'target_card_id': myr}})
    assert state.cards[firebrand].zone == Zone.GRAVEYARD
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task5-native-deathtouch-marked-lethal-blocker-reached')
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert has_keyword(state, myr, 'indestructible') and effective_toughness(state, myr) == 1
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    state = reach(cold(state), Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': [rats],
                            'attack_targets': {rats: 'battle:' + battle}})
    mark('Task5-native-deathtouch-trample-Siege-attack-declared')
    assert has_keyword(state, rats, 'deathtouch')
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'block', 'blocks': {rats: [myr]}})
    mark('Task5-native-deathtouch-indestructible-block-declared')
    # Exercise the automatic fallback, which must obey the same marked-lethal
    # rule as explicit player assignments. No damage counters are edited.
    state.mechanic_choice_players = set()
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    mark('Task5-automatic-deathtouch-trample-marked-lethal-Siege-damage-reached')
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert_life(state)
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    state.mechanic_choice_players = {seat}
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_frostfang_attacking_grant_tracks_native_siege_combat_and_reload(seat):
    from rules_engine.combat import DMG_MARK_KEY
    from tests.combat_canonical_022 import raw_card as combat_raw
    from tests.pending_permanent_fullraw import raw_card as permanent_raw
    from tests.rules_printed_facts_e4 import raw_card
    from tests.test_entry_copy_native_936 import raw
    from tests.test_knowledge_ingest import _official_card
    from tests.test_battle_transformed_cast import cast_action

    state, battle = position(seat)
    # These complete-printing permanents are declared ready resources, not a
    # claim that their earlier turns were played. All subsequent actions are native.
    elf = place_full_printing(state, seat, raw_card('Llanowar Elves'), Zone.BATTLEFIELD)
    state.cards[elf].summoning_sick = False
    state.cards[elf].entered_turn = state.turn - 1
    printing = combat_raw('Ohran Frostfang')
    assert 'Attacking creatures you control have deathtouch.' in printing['oracle_text']
    frostfang = place_full_printing(state, seat, printing, Zone.BATTLEFIELD)
    assert not has_keyword(state, elf, 'deathtouch')
    assert not has_keyword(state, frostfang, 'deathtouch')
    myr = place_full_printing(state, 3-seat, permanent_raw('Darksteel Myr'), Zone.BATTLEFIELD)
    mountain = place_full_printing(state, seat, _official_card('Mountain'), Zone.BATTLEFIELD)
    state.mechanic_choice_players = {seat}
    forests = [cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Forest']
    for cid in forests[:4]:
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': cid, 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': battle})
    assert state.stack[-1].payload['mana_spent'] == 4
    assert not state.cards[elf].tapped and not sum(state.players[seat].mana_pool.values())
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    chosen = state.pending_mechanic_choice['options'][:2]
    assert len(chosen) == 2
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.cards[battle].counters['defense'] == 3
    assert state.cards[battle].battle_protector == 3-seat

    rancor = place_full_printing(state, seat, raw('Rancor'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': forests[4], 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': rancor,
                            'targets': {'target_card_id': elf}})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    assert effective_power(state, elf) == 3 and has_keyword(state, elf, 'trample')
    assert not state.cards[elf].tapped
    firebrand = place_full_printing(state, seat, raw_card('Fanatical Firebrand'), Zone.HAND)
    state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': mountain, 'color': 'R'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': firebrand})
    assert state.stack[-1].payload['mana_spent'] == 1
    state = resolve_until(state, lambda current: not current.stack)
    state = act(cold(state), seat, {'type': 'activate_ability', 'card_id': firebrand,
        'ability_index': 0, 'targets': {'target_card_id': myr}})
    assert state.cards[firebrand].zone == Zone.GRAVEYARD
    state = resolve_until(state, lambda current: not current.stack)
    mark('Task6-Frostfang-native-marked-lethal-blocker-reached')
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert has_keyword(state, myr, 'indestructible') and effective_toughness(state, myr) == 1
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    state = reach(cold(state), Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': [elf],
                            'attack_targets': {elf: 'battle:' + battle}})
    mark('Task6-Frostfang-current-attacking-grant-reached')
    for current in (state, cold(state)):
        assert elf in current.attackers
        assert has_keyword(current, elf, 'deathtouch')
        assert not has_keyword(current, frostfang, 'deathtouch')
        assert not has_keyword(current, myr, 'deathtouch')
        assert not has_keyword(current, battle, 'deathtouch')
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'block', 'blocks': {elf: [myr]}})
    mark('Task6-Frostfang-native-indestructible-block-declared')
    # Exercise the automatic fallback, which must obey the same marked-lethal
    # rule as explicit player assignments. No damage counters are edited.
    state.mechanic_choice_players = set()
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    mark('Task6-Frostfang-automatic-trample-Siege-damage-reached')
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.cards[myr].counters[DMG_MARK_KEY] == 1
    assert state.cards[myr].zone == Zone.BATTLEFIELD
    assert_life(state)
    assert sum(item.effect_key == 'battle_defeat' for item in state.stack) == 1
    state.mechanic_choice_players = {seat}
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4
    assert has_keyword(state, elf, 'deathtouch')
    assert not has_keyword(state, battle, 'deathtouch')
    state = reach(cold(state), Step.END_COMBAT)
    mark('Task6-Frostfang-end-of-combat-membership-reached')
    assert has_keyword(state, elf, 'deathtouch')
    state = reach(cold(state), Step.POSTCOMBAT_MAIN)
    mark('Task6-Frostfang-postcombat-membership-cleared-reached')
    assert not state.attackers
    assert not has_keyword(state, elf, 'deathtouch')
    assert not has_keyword(state, frostfang, 'deathtouch')
    assert not has_keyword(state, battle, 'deathtouch')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_siege_legal_move_documents_are_independent_of_pending_native_state(seat):
    from copy import deepcopy
    from tests.test_battle_transformed_cast import cast_action

    state, battle, attackers = battle_position(seat)
    state.mechanic_choice_players = {seat}
    state = announce(state, seat, battle)
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    assert state.pending_mechanic_choice['resolving_item']['source_card_id'] == battle
    chosen = list(state.pending_mechanic_choice['options'][:2])
    assert len(chosen) == 2
    baseline = deepcopy(serialize_match_snapshot(state))
    outgoing = next(move for move in RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'choose_mechanic')
    # These edits corrupt only an untrusted returned move document. They are
    # negative ownership controls, not played changes to native card history.
    outgoing['resolving_item']['source_card_id'] = 'Untrusted move-document edit'
    mark('Task6-pending-Siege-legal-move-resolution-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    outgoing = next(move for move in RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'choose_mechanic')
    outgoing['options'].clear()
    mark('Task6-pending-Siege-legal-move-options-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    outgoing = next(move for move in RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'choose_mechanic')
    outgoing['resolving_item']['payload'].clear()
    mark('Task6-pending-Siege-legal-move-payload-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert not state.pending_mechanic_choice
    assert state.cards[battle].zone == Zone.BATTLEFIELD
    assert state.cards[battle].counters['defense'] == 3
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].tapped for cid in chosen)
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.stack[-1].effect_key == 'battle_defeat'
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    assert state.cards[battle].zone == Zone.EXILE
    baseline = deepcopy(serialize_match_snapshot(state))
    outgoing = next(move for move in RulesEngine().legal_moves(state, seat)
                    if move['type'] == 'cast_spell' and move['card_id'] == battle)
    outgoing['card_view']['card_faces'][1]['name'] = 'Untrusted move-face edit'
    mark('Task6-Siege-back-legal-move-physical-face-isolation-reached')
    assert serialize_match_snapshot(state) == baseline
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert state.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_accepted_loyalty_request_does_not_retain_caller_target_containers(seat):
    from copy import deepcopy
    from tests.test_compleated_loyalty_full import RAW
    from tests.test_knowledge_ingest import _official_card
    from tests.test_battle_transformed_cast import cast_action

    state, battle, attackers = battle_position(seat)
    # Additional complete-printing mana and blocker resources are declared in
    # the initial position. Every spell and later action below is played natively.
    for _ in range(4):
        place(state, seat, 'Forest', Zone.BATTLEFIELD)
    for _ in range(2):
        place_full_printing(state, seat, _official_card('Island'), Zone.BATTLEFIELD)
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    tamiyo = place_full_printing(state, seat, RAW, Zone.HAND)
    state.mechanic_choice_players = {seat}
    forests = [cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Forest']
    for cid in forests[:4]:
        state = act(state, seat, {'type': 'tap_land_for_mana', 'card_id': cid, 'color': 'G'})
    state = act(state, seat, {'type': 'cast_spell', 'card_id': battle})
    assert state.stack[-1].payload['mana_spent'] == 4
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    chosen = state.pending_mechanic_choice['options'][:2]
    assert len(chosen) == 2
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': chosen})
    assert state.cards[battle].counters['defense'] == 3
    before_tapped = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    mark('Task6-paid-Tamiyo-request-isolation-setup-reached')
    state = act(state, seat, {'type': 'cast_spell', 'card_id': tamiyo,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': ['G']})
    assert state.stack[-1].payload['mana_spent'] == 5
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) == before_tapped + 5
    state = resolve_until(state, lambda current: not current.stack)
    assert state.cards[tamiyo].loyalty == 5
    assert_life(state)
    action = {'type': 'activate_loyalty', 'card_id': tamiyo, 'ability_index': 0,
              'targets': {'target_card_ids': [blocker]}}
    original = state
    original_before = deepcopy(serialize_match_snapshot(original))
    mark('Task6-paid-Tamiyo-request-isolation-loyalty-reached')
    state = act(original, seat, action)
    assert serialize_match_snapshot(original) == original_before
    assert state.cards[tamiyo].loyalty == 6
    assert state.stack[-1].payload['__announced_targets']['target_card_ids'] == [blocker]
    accepted_before = deepcopy(serialize_match_snapshot(state))
    # The caller may reuse or discard its request after acceptance. This is an
    # input-document ownership control, not a new gameplay target selection.
    action['targets']['target_card_ids'].clear()
    mark('Task6-accepted-loyalty-request-target-list-isolation-reached')
    assert serialize_match_snapshot(state) == accepted_before
    assert serialize_match_snapshot(original) == original_before
    state = resolve_until(cold(state), lambda current: not current.stack)
    mark('Task6-isolated-request-native-freeze-resolved')
    assert state.cards[blocker].tapped
    assert state.cards[tamiyo].loyalty == 6
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters.get('defense', 0) == 0
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert state.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_structured_battle_search_excludes_a_nonbattle_name_and_completes_siege_play(seat):
    from effects.registry import resolve_effect
    from tests.mana_canonical_76 import raw_card
    from tests.test_battle_transformed_cast import cast_action, reject

    state, battle, attackers = battle_position(seat)
    # This declared library position and direct structured-search effect are a
    # core-policy control, not a claim that an unplayed printed tutor produced it.
    state.players[seat].hand.remove(battle)
    state.cards[battle].move_to_zone(Zone.LIBRARY)
    state.players[seat].library.append(battle)
    forge = place_full_printing(state, seat, raw_card('Battlefield Forge'), Zone.LIBRARY)
    assert set(effective_types(state, forge)) == {'Land'}
    assert set(effective_types(state, battle)) == {'Battle'}
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'search_library', {
        'contains': 'battle', 'destination': 'hand', 'count': 1, 'shuffle': True})
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    mark('Task6-native-bare-Battle-search-type-filter-reached')
    assert set(state.pending_mechanic_choice['options']) == {battle}
    reject(state, seat, {'type': 'choose_mechanic', 'card_ids': [forge]})
    state = act(cold(state), seat, {'type': 'choose_mechanic', 'card_ids': [battle]})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[battle].zone == Zone.HAND
    assert state.cards[forge].zone == Zone.LIBRARY
    assert battle in state.players[seat].hand and forge in state.players[seat].library
    state = paid_front(state, seat, battle)
    assert state.cards[forge].zone == Zone.LIBRARY
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.stack[-1].effect_key == 'battle_defeat'
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert state.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4
    assert state.cards[forge].zone == Zone.LIBRARY
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_natures_spiral_targets_a_graveyard_battle_and_completes_siege_play(seat):
    import json
    from pathlib import Path
    from rules_engine.cast_choice import build_cast_hints
    from tests.test_battle_entry import BATTLE
    from tests.test_battle_transformed_cast import cast_action, reject

    printing = json.loads((Path(__file__).parent / 'fixtures/battle_cast_full_printing/natures-spiral-dom-175.json').read_text())
    assert len(printing) == 63 and printing['object'] == 'card'
    assert printing['id'] == '6666b95e-80de-4bf7-bae6-8a7e991b38ad'
    assert printing['oracle_id'] == '565922d6-8152-411f-8d4d-dc7c8523a49b'
    state, battle, attackers = battle_position(seat)
    # These graveyards are the declared initial legal position. Nature's Spiral
    # has no requirement that a target died or entered the graveyard this turn.
    state.players[seat].hand.remove(battle)
    state.cards[battle].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(battle)
    foreign_battle = place(state, 3-seat, BATTLE, Zone.GRAVEYARD)
    nonpermanent = place_full_printing(state, seat, printing, Zone.GRAVEYARD)
    spell = place_full_printing(state, seat, printing, Zone.HAND)
    before = serialize_match_snapshot(state)
    hints = build_cast_hints(state, state.cards[spell], seat)
    mark('Task6-native-graveyard-Battle-permanent-target-hints-reached')
    assert {target['id'] for target in hints.get('graveyard_permanent_targets', [])} == {battle}
    assert serialize_match_snapshot(state) == before
    for invalid in (foreign_battle, nonpermanent):
        reject(state, seat, {'type': 'cast_spell', 'card_id': spell,
                            'targets': {'target_card_id': invalid}})
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'cast_spell' and move['card_id'] == spell)
    assert {target['id'] for target in move['target_hints']['graveyard_permanent_targets']} == {battle}
    mark('Task6-native-graveyard-Battle-AI-announcement-reached')
    choice = decision(state, seat)
    assert choice['type'] == 'cast_spell' and choice['card_id'] == spell
    assert choice['targets']['target_card_id'] == battle
    tapped = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)
    state = act(state, seat, choice)
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) - tapped == 2
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.cards[spell].zone == Zone.STACK
    assert state.stack[-1].effect_key == 'return_from_graveyard'
    assert state.stack[-1].payload['target_card_id'] == battle
    state = resolve_until(cold(state), lambda current: current.cards[battle].zone == Zone.HAND)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[nonpermanent].zone == Zone.GRAVEYARD
    assert state.cards[foreign_battle].zone == Zone.GRAVEYARD
    assert battle in state.players[seat].hand
    state = paid_front(state, seat, battle)
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: 'battle:' + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {'type': 'pass_priority'})
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters.get('defense', 0) == 0
    assert state.stack[-1].effect_key == 'battle_defeat'
    state = resolve_until(state, lambda current: current.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    state = act(cold(state), seat, cast_action(battle))
    state = resolve_until(state, lambda current: current.cards[battle].zone == Zone.BATTLEFIELD)
    assert state.cards[battle].name == 'Awakened Skyclave'
    assert set(effective_types(state, battle)) == {'Creature', 'Land'}
    assert effective_power(state, battle) == effective_toughness(state, battle) == 4
    assert_life(state)
