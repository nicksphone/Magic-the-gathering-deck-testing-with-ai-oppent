"""Loopback-only browser fixtures; never mount these routes in production."""
from collections import Counter
from pathlib import Path
if (Path(__file__).resolve().parents[2] / ".git").exists():
    raise RuntimeError("Run browser fixtures only from an isolated source copy, not the live Git checkout")
from main import app, ACTIVE_MATCHES, MatchController, get_match, _persist_active_match
from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.engine import RulesEngine
from persistence.db import init_db, engine
from persistence.repository import Repository
from sqlmodel import Session

init_db()


@app.post("/fixture/start-decks")
def fixture_start_decks():
    deck = [{"quantity": 60, "card_name": "Island"}]
    with Session(engine) as session:
        repo = Repository(session)
        a = repo.save_deck("Start retry A", "fixture", deck, [], "Control")
        b = repo.save_deck("Start retry B", "fixture", deck, [], "Control")
        return {"a": a.id, "b": b.id}


@app.post('/fixture/combat-coverage-decks')
def fixture_combat_coverage_decks():
    import json
    from main import SIM_JOBS
    rows = json.loads((Path(__file__).parent / 'fixtures/combat_coverage.json').read_text())
    card = next(row for row in rows if row['name'] == "Stormtide Leviathan")
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card({'scryfall_id': card['id'], 'name': card['name'],
                         'oracle_text': card['oracle_text'], 'type_line': card['type_line'],
                         'mana_cost': card['mana_cost'], 'power': card['power'], 'toughness': card['toughness'],
                         'colors': ''.join(card['colors'])})
        a = repo.save_deck('Canonical tax coverage fixture', 'fixture',
                           [{'quantity': 4, 'card_name': card['name']}, {'quantity': 56, 'card_name': 'Island'}], [], 'Control')
        b = repo.save_deck('Canonical land coverage fixture', 'fixture',
                           [{'quantity': 60, 'card_name': 'Island'}], [], 'Control')
        return {'a': a.id, 'b': b.id, 'jobs': len(SIM_JOBS)}


@app.get('/fixture/simulation-job-count')
def fixture_simulation_job_count():
    from main import SIM_JOBS
    return {'jobs': len(SIM_JOBS)}


@app.post("/fixture")
def fixture(pregame: bool = False, modal: bool = False, modal_mana: int = 3, face_kind: str = ""):
    if face_kind in {f'devotion_{index}_{seat}' for index in range(7) for seat in [1, 2]}:
        from tests.test_devotion import ROWS, add, fixture as devotion_board
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        name = ['Aspect of Hydra', 'Gray Merchant of Asphodel', 'Fanatic of Mogis',
                'Reverent Hunter', 'Evangel of Heliod', 'Setessan Petitioner', 'Abhorrent Overlord'][index]
        state = devotion_board()
        for player in state.players.values():
            player.mana_pool = {color: 0 for color in 'WUBRGC'}
        state.active_player = state.priority_player = seat
        add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
        add(state, name, seat, Zone.HAND, cards=ROWS)
        state.players[seat].mana_pool.update({color: 8 for color in 'WUBRG'})
        return publish(state, [{'quantity': 60, 'card_name': 'Forest'}])
    if face_kind in {f'conditional_static_{index}_{seat}' for index in range(3) for seat in [1, 2]}:
        from tests.test_conditional_static import setup
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        name = ['Nimble Mongoose', 'Auriok Sunchaser', "Dragon's Rage Channeler"][index]
        state, card, _ = setup(name, seat, True)
        state.players[seat].battlefield.remove(card.id)
        card.move_to_zone(Zone.HAND)
        state.players[seat].hand.append(card.id)
        state.players[seat].mana_pool.update({'W': 1, 'G': 1, 'R': 1, 'C': 2})
        return publish(state, [{'quantity': 60, 'card_name': 'Forest'}])
    if face_kind in {f'characteristic_{index}_{seat}' for index in range(3) for seat in [1, 2]}:
        from tests.test_characteristic_stats import setup
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        name = ['Tarmogoyf', 'Boneyard Wurm', "Death's Shadow"][index]
        state, _ = setup(name, seat, Zone.HAND)
        state.players[seat].mana_pool.update({'G': 2, 'B': 1})
        return publish(state, [{'quantity': 60, 'card_name': 'Forest'}])
    if face_kind in {f'wheel_{index}_{seat}' for index in range(6) for seat in [1, 2]}:
        from tests.test_wheel_draw import setup, SPELLS, canonical
        from tests.test_ai_recurring_engines import add
        from tests.test_linked_discard import ROWS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(SPELLS[index] if index < 5 else 'Windfall', seat, cast=False)
        canonical(state, 'Maro', seat)
        if index == 5:
            for pid in [1, 2]:
                add(state, 'Stinkweed Imp', pid, Zone.HAND, cards=ROWS)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'discard_history_{index}_{seat}' for index in range(3) for seat in [1, 2]}:
        from tests.test_discard_history import setup
        from rules_engine.zone_actions import discard_selected
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, _, hand, _ = setup(['Daretti, Scrap Savant', 'Cathartic Pyre', 'Change of Fortune'][index], seat, cast=False)
        if index == 2:
            discard_selected(state, seat, [hand[0].id])
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'linked_copy_{seat}' for seat in [1, 2]}:
        from tests.test_linked_discard import setup
        from tests.test_surveil_mill import add
        from effects.registry import resolve_effect
        seat = int(face_kind.split('_')[-1])
        state, *_ = setup('Tolarian Winds', seat, pause=False)
        for name in ['Island', 'Swamp']:
            add(state, name, 3-seat, Zone.HAND)
        resolve_effect(state, 3-seat, 'copy_spell', {'target_stack_id': state.stack[-1].id})
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'linked_discard_{index}_{seat}' for index in range(3) for seat in [1, 2]}:
        from tests.test_linked_discard import setup, SPELLS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(SPELLS[index], seat, cast=False)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'variable_cost_{index}_{seat}' for index in range(2) for seat in [1, 2]}:
        from tests.test_variable_spell_costs import setup, NAMES
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(NAMES[index], seat)
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'qualified_cost_{index}_{seat}' for index in range(4) for seat in [1, 2]}:
        from tests.test_qualified_spell_costs import setup, SPELLS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(list(SPELLS)[index], seat)
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'kicker_golden_{index}_{seat}' for index in range(5) for seat in [1, 2]}:
        from tests.test_kicker_goldens import setup, SPELLS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(SPELLS[index], seat)
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'nonmana_kicker_{index}_{seat}' for index in range(3) for seat in [1, 2]}:
        from tests.test_nonmana_kicker import setup, ROWS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(list(ROWS)[index], seat)
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'kicked_cast_{index}_{seat}' for index in range(4) for seat in [1, 2]}:
        from tests.test_kicked_cast_triggers import source
        from tests.test_kicker import setup
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, spell, _ = setup('Burst Lightning', seat)
        state.players[seat].mana_pool['U'] = 10
        if index == 3:
            state.players[seat].hand.remove(spell.id)
            spell.move_to_zone(Zone.LIBRARY)
            state.players[seat].library.append(spell.id)
            source(state, 'Roost of Drakes', seat, Zone.HAND)
        else:
            source(state, ['Risen Riptide', 'Roost of Drakes', 'Vine Gecko'][index], seat)
        state.mechanic_choice_players = {1, 2}
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'permanent_kicker_{index}_{seat}' for index in range(4) for seat in [1, 2]}:
        from tests.test_permanent_kicker import setup, ROWS
        index, seat = [int(value) for value in face_kind.split('_')[-2:]]
        state, *_ = setup(list(ROWS)[index], seat)
        state.mechanic_choice_players = {1, 2}
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'kicker_{index}_{seat}_{free}' for index in range(4) for seat in [1, 2] for free in [0, 1]}:
        from tests.test_kicker import setup
        _, index, seat, free = face_kind.split('_')
        name = ['Burst Lightning', 'Into the Roil', 'Gift of Growth', 'Fight with Fire'][int(index)]
        state, *_ = setup(name, int(seat), bool(int(free)))
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {f'{kind}_{seat}' for kind in ['counted_cost', 'free_counted_cost', 'land_cost'] for seat in [1, 2]}:
        from tests.test_spell_cost_clauses import board, card, add
        seat = int(face_kind[-1])
        state = board(seat)
        land_cost = face_kind.startswith('land_')
        spell = card(state, 'Raze' if land_cost else 'Cathartic Reunion', seat)
        add(state, 'Island', seat, Zone.BATTLEFIELD if land_cost else Zone.HAND)
        add(state, 'Swamp', 3-seat if land_cost else seat, Zone.BATTLEFIELD if land_cost else Zone.HAND)
        state.players[seat].mana_pool.update(R=1, C=1)
        state.mechanic_choice_players = {1, 2}
        if face_kind.startswith('free_'):
            from effects.registry import resolve_effect
            state.players[seat].hand.remove(spell.id)
            state.players[seat].graveyard.append(spell.id)
            spell.move_to_zone(Zone.GRAVEYARD)
            resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': spell.id})
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'spell_cost_1', 'spell_cost_2', 'free_spell_cost_1', 'free_spell_cost_2'}:
        from tests.test_cast_payment_choices import setup
        seat = int(face_kind[-1])
        state, *_ = setup(seat, face_kind.startswith('free_'))
        state.mechanic_choice_players = {1, 2}
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'effect_cast_1', 'effect_cast_2'}:
        from tests.test_surveil_mill import board, add
        seat = int(face_kind[-1])
        state = board(seat)
        state.mechanic_choice_players = {1, 2}
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {1, 2}
        add(state, 'Torrential Gearhulk', seat, Zone.HAND)
        add(state, 'Lightning Bolt', seat, Zone.GRAVEYARD)
        add(state, 'Counterspell', seat, Zone.GRAVEYARD)
        state.players[seat].mana_pool.update(C=4, U=2)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'surveil_1', 'surveil_2'}:
        from tests.test_surveil_mill import board, add
        seat = int(face_kind[-1])
        state = board(seat)
        add(state, 'Otherworldly Gaze', seat, Zone.HAND)
        add(state, 'Dimir Spybug', seat)
        for name in ['Mind Stone', 'Grizzly Bears', 'Island']:
            add(state, name, seat, Zone.LIBRARY)
        state.players[seat].mana_pool.update(U=1)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'legend_graveyard_1', 'legend_graveyard_2', 'legend_search_1', 'legend_search_2'}:
        from tests.test_legendary_channels import board, add
        seat = int(face_kind[-1])
        state = board(seat)
        state.mechanic_choice_players = {1, 2}
        if face_kind.startswith('legend_graveyard_'):
            add(state, 'Takenuma, Abandoned Mire', seat, Zone.HAND)
            add(state, 'Grizzly Bears', seat, Zone.LIBRARY)
            add(state, 'Ugin, the Spirit Dragon', seat, Zone.LIBRARY)
            add(state, 'Swamp', seat, Zone.LIBRARY)
            state.players[seat].mana_pool.update(C=3, B=1)
        else:
            add(state, 'Boseiju, Who Endures', seat, Zone.HAND)
            add(state, 'Mind Stone', 3-seat)
            add(state, 'Forest', 3-seat, Zone.LIBRARY)
            state.players[seat].mana_pool.update(C=1, G=1)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'channel_1', 'channel_2', 'counter_payment_1', 'counter_payment_2'}:
        from tests.test_hand_activations import board, hand_card, add
        from tests.test_counterability_scope import add_card
        seat = int(face_kind[-1])
        state = board(seat)
        state.mechanic_choice_players = {1, 2}
        if face_kind.startswith('channel_'):
            hand_card(state, 'Colossal Skyturtle', seat)
            add_card(state, 'Lightning Bolt', Zone.GRAVEYARD, seat)
            state.players[seat].mana_pool.update(C=2, G=1)
        else:
            hand_card(state, 'Mirrorshell Crab', seat)
            source = add(state, 'Azure Mage', 3-seat)
            state.stack.append(StackItem(state.allocate_object_id(), source.id, 3-seat,
                                         'Azure Mage ability', 'draw_cards', {'count': 1}))
            state.players[seat].mana_pool.update(C=2, U=1)
            state.players[3-seat].mana_pool['C'] = 3
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'bestow_1', 'bestow_2'}:
        from tests.test_bestow import cast_board
        state, _, _ = cast_board(int(face_kind[-1]))
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'recipient_attack_1', 'recipient_attack_2', 'recipient_block_1', 'recipient_block_2'}:
        from tests.test_recipient_combat import recipient_board
        seat = int(face_kind[-1])
        kind = face_kind.split('_')[-2]
        state, _, _ = recipient_board(seat, kind)
        state.players[seat if kind == 'attack' else 3-seat].mana_pool['G'] = 3
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'combat_capacity_1', 'combat_capacity_2'}:
        from tests.test_ai_combat_intents import board, add, activate
        seat = int(face_kind[-1])
        state, _, _ = board(seat)
        add(state, 'Llanowar Elves', 3-seat)
        state.step = Step.DECLARE_ATTACKERS
        state, _ = activate(state, 'War Cadence', seat, 1)
        state.step = Step.DECLARE_BLOCKERS
        state.priority_player = 3-seat
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'conditional_cost_attack_1', 'conditional_cost_attack_2', 'conditional_cost_block_1', 'conditional_cost_block_2'}:
        from tests.test_conditional_combat_costs import board, add
        seat = int(face_kind[-1])
        kind = face_kind.split('_')[-2]
        state, _, _, _ = board(seat, kind)
        if kind == 'attack':
            state.players[seat].mana_pool['U'] = 1
        else:
            add(state, 'Grizzly Bears', 3-seat)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'combat_domain_1', 'combat_domain_2', 'combat_temporary_1', 'combat_temporary_2'}:
        from tests.test_combat_domain_temporary_costs import fixture as clean_state, add, zero_mana, attack_step
        seat = int(face_kind[-1])
        state = clean_state()
        zero_mana(state)
        if face_kind.startswith('combat_domain_'):
            add(state, 'Collective Restraint', 3-seat)
            add(state, 'Hallowed Fountain', 3-seat)
            add(state, 'Forest', 3-seat)
            add(state, 'Grizzly Bears', seat)
            add(state, 'Llanowar Elves', seat)
            state.players[seat].mana_pool['U'] = 3
            attack_step(state, seat)
        else:
            attacker = add(state, 'Prized Unicorn', seat)
            add(state, 'War Cadence', seat)
            add(state, 'Llanowar Elves', 3-seat)
            add(state, 'Grizzly Bears', 3-seat)
            state.active_player = state.priority_player = seat
            state.step = Step.DECLARE_ATTACKERS
            state.attackers, state.attackers_declared = [attacker.id], True
            state.cards[attacker.id].tapped = True
            state.players[seat].mana_pool['R'] = 2
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind in {'combat_branches_1', 'combat_branches_2'}:
        from tests.test_combat_minimums_payments import board
        from tests.test_combat_payments_requirements import add, zero_mana, attack_step
        seat = int(face_kind[-1])
        state, _, _ = board(seat)
        zero_mana(state)
        add(state, "Norn's Annex", 3-seat)
        attack_step(state, seat)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind == 'combat_payments_requirements':
        from tests.test_combat_payments_requirements import fixture as clean_state, add, zero_mana, attack_step
        state = clean_state()
        zero_mana(state)
        add(state, 'Ghostly Prison', 2)
        add(state, 'Llanowar Elves', 2)
        add(state, 'Prized Unicorn')
        add(state, 'Llanowar Elves')
        state.players[1].mana_pool['U'] = 2
        attack_step(state, 1)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind == 'declaration_limits':
        from tests.test_ai_recurring_engines import fixture as clean_state
        from tests.test_declaration_limits import add, attack_step
        from tests.test_ability_suppression import add as printed
        state = clean_state()
        for player in state.players.values():
            player.mana_pool = {color: 0 for color in player.snow_mana_pool}
        add(state, 'Silent Arbiter', 1)
        for _ in range(2):
            card = printed(state, 'Llanowar Elves', 2)
            card.summoning_sick = False
        attack_step(state, 2)
        return publish(state, [{'quantity': 60, 'card_name': 'Swamp'}])
    if face_kind == 'scry':
        from tests.test_named_counters import CARDS
        from tests.test_ai_recurring_engines import add as add_card
        from tests.test_restricted_mana import clean
        from effects.registry import resolve_effect
        from rules_engine.counter_placement import put_counters
        state = clean(2)
        bear = add_card(state, 'Grizzly Bears', 2, cards=CARDS)
        put_counters(state, 'flying', 1, target_card_id=bear.id)
        for name in ('Grizzly Bears', 'Impede Momentum', 'Twiddle'):
            add_card(state, name, 2, Zone.LIBRARY, cards=CARDS)
        resolve_effect(state, 2, 'effect_sequence', {'effects': [
            {'effect_key': 'scry', 'payload': {'amount': 3}},
            {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
        ]})
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'proliferate':
        from tests.test_counter_replacements import source
        from tests.test_restricted_mana import clean
        from effects.registry import resolve_effect
        state = clean(2)
        state.players[2].counters['energy'] = 1
        state.players[2].poison = 1
        source(state, 'Winding Constrictor', 2)
        source(state, "Lae'zel, Vlaakith's Champion", 2)
        state.mechanic_choice_players = {2}
        resolve_effect(state, 2, 'proliferate', {})
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'transformed_counter_entry':
        from tests.test_transformed_entry import jace
        from tests.test_counter_replacements import source
        from tests.test_restricted_mana import clean
        from effects.registry import resolve_effect
        state = clean(2)
        card = jace(state)
        source(state, 'Doubling Season', 2)
        source(state, "Lae'zel, Vlaakith's Champion", 2)
        resolve_effect(state, 2, 'exile_return_transformed', {'target_card_id': card.id})
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'linked_counter_entry_batch':
        from tests.test_linked_entry_counters import hold, release
        from tests.test_linked_exile import _state
        from tests.test_counter_prohibitions import source as permanent
        from tests.test_counter_replacements import source
        state, jailer = _state()
        cards = [permanent(state, "Elspeth, Sun's Champion", seat) for seat in (1, 2)]
        for seat in (1, 2):
            source(state, 'Doubling Season', seat)
            source(state, "Lae'zel, Vlaakith's Champion", seat)
        hold(state, jailer, cards)
        release(state, jailer)
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'token_counter_entry_batch':
        from tests.test_counter_replacements import source
        from tests.test_restricted_mana import clean
        from effects.registry import resolve_effect
        state = clean(2)
        source(state, 'Doubling Season', 2)
        source(state, 'Winding Constrictor', 2)
        resolve_effect(state, 2, 'incubate', {'counters': 3})
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'compleated_entry_order':
        from tests.test_entry_replacement_order import walker
        from tests.test_counter_replacements import source
        from tests.test_spell_entry_counters import spell
        from tests.test_restricted_mana import clean
        state = clean(2)
        card = walker(state, 'Tamiyo, Compleated Sage', 2)
        source(state, 'Doubling Season', 2)
        spell(state, card, __phyrexian_life_symbols=1)
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'read_ahead_entry':
        from tests.test_spell_entry_counters import ROWS, spell
        from tests.test_ai_recurring_engines import add as add_card
        from tests.test_counter_replacements import source
        from tests.test_restricted_mana import clean
        state = clean(2)
        card = add_card(state, 'The Phasing of Zhalfir', 2, cards=ROWS)
        spell(state, card)
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'saga_counter_order':
        from tests.test_saga_counter_events import saga
        from tests.test_counter_replacements import source
        from tests.test_restricted_mana import clean
        state = clean(2)
        card = saga(state, player=2)
        card.counters['__lore'] = 1
        source(state, 'Doubling Season', 2)
        source(state, 'Vorinclex, Monstrous Raider', 2)
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {2}
        RulesEngine()._advance_sagas(state)
        return publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    if face_kind == 'damage_counter_order':
        from tests.test_counter_replacements import source
        from tests.test_counter_prohibitions import source as damage_source
        from tests.test_restricted_mana import clean
        from effects.handlers import grant_keyword
        from rules_engine.combat import _resolve_damage_step
        state = clean()
        source(state, 'Winding Constrictor', 2)
        source(state, 'Vorinclex, Monstrous Raider')
        elf = damage_source(state, 'Glistener Elf')
        grant_keyword(state, 1, {'target_card_id': elf.id, 'keyword': 'lifelink'})
        state.attackers = [elf.id]
        state.step = Step.COMBAT_DAMAGE
        state.combat_damage_stage = 'regular'
        _resolve_damage_step(state)
        return publish(state, [{"quantity": 60, "card_name": "Island"}])
    if face_kind == 'counter_order':
        from tests.test_counter_replacements import source
        from tests.test_player_counters import source as experience_source
        from tests.test_ward_resolution import add
        from tests.test_restricted_mana import clean
        from effects.handlers import destroy_permanent
        from rules_engine.events import emit_event
        from rules_engine.stack_engine import resolve_top_of_stack
        state = clean(2)
        experience_source(state, 'Minthara, Merciless Soul', 2)
        source(state, 'Winding Constrictor', 2)
        source(state, 'Vorinclex, Monstrous Raider', 2)
        bear = add(state, 'Grizzly Bears', 2)
        destroy_permanent(state, 1, {'target_card_id': bear.id})
        emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 2})
        resolve_top_of_stack(state)
        return publish(state, [{"quantity": 60, "card_name": "Island"}])
    if face_kind == 'player_counters':
        from tests.test_player_counters import source
        from tests.test_ward_resolution import add, resolve
        from tests.test_restricted_mana import clean
        from effects.handlers import destroy_permanent
        from rules_engine.events import emit_event
        from rules_engine.action_validation import checked_action
        state = clean(2)
        state.active_player = 1
        card = source(state, 'Minthara, Merciless Soul', 1)
        bear = add(state, 'Grizzly Bears', 1)
        destroy_permanent(state, 2, {'target_card_id': bear.id})
        emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 1})
        resolve(state)
        state.step = Step.CLEANUP
        RulesEngine().next_step(state)
        state.step = Step.PRECOMBAT_MAIN
        state.priority_player = 2
        bolt = add(state, 'Lightning Bolt', 2, Zone.HAND)
        state.players[2].mana_pool.update(R=1, G=1)
        state = checked_action(state, RulesEngine(), 2, {'type': 'cast_spell', 'card_id': bolt.id,
                              'targets': {'target_card_id': card.id}})
        resolve(state)
        return publish(state, [{"quantity": 60, "card_name": "Island"}])
    if face_kind in {"ward_mana", "ward_discard"}:
        from tests.test_ward_resolution import cast_at, add
        from rules_engine.stack_engine import resolve_top_of_stack
        state, *_ = cast_at('Tolarian Terror' if face_kind == 'ward_mana' else 'Graveyard Trespasser',
                            player=2, mana={'R': 1, 'G': 2})
        if face_kind == 'ward_discard':
            add(state, 'Island', 2, Zone.HAND)
            add(state, 'Counterspell', 2, Zone.HAND)
        resolve_top_of_stack(state)
        return publish(state, [{"quantity": 60, "card_name": "Island"}])
    if face_kind == "aura_costs":
        from tests.test_aura_costs import discounted
        state, *_ = discounted(2)
        return publish(state, [{"quantity": 60, "card_name": "Plains"}])
    if face_kind == "equip_context":
        from tests.test_equip_context import add
        from tests.test_restricted_mana import clean
        state = clean(2)
        add(state, "Bonesplitter", 2)
        add(state, "Fervent Champion", 2)
        add(state, "Llanowar Elves", 2).tapped = True
        return publish(state, [{"quantity": 60, "card_name": "Forest"}])
    if face_kind == "attached_predicates":
        from tests.test_attached_scaling import add, CARDS
        from tests.test_ai_recurring_engines import add as add_hand
        from tests.test_restricted_mana import clean
        state = clean(1)
        target = add(state, "Llanowar Elves", 2)
        add(state, "Abzan Runemark", 1).attached_to = target.id
        own = add(state, "Ornithopter", 1)
        add(state, "Strength of Unity", 1).attached_to = own.id
        for _ in range(4):
            add(state, "Swamp", 1)
        for name in ("Island", "Whip of Erebos"):
            add_hand(state, name, 1, Zone.HAND, cards=CARDS)
        return publish(state, [{"quantity": 60, "card_name": "Swamp"}])
    if face_kind == "attached_scaling":
        from tests.test_attached_scaling import add
        from tests.test_restricted_mana import clean, add as payment_card
        state = clean(2)
        target = add(state, "Llanowar Elves", 1)
        source = add(state, "All That Glitters", 1)
        source.attached_to = target.id
        add(state, "Sol Ring", 1)
        other = add(state, "Ornithopter", 1)
        add(state, "Unholy Strength", 1).attached_to = other.id
        unknown = add(state, "Ancestral Mask", 2)
        unknown.attached_to = add(state, "Llanowar Elves", 2).id
        payment_card(state, "Naturalize", 2, Zone.HAND)
        payment_card(state, "Forest", 2)
        payment_card(state, "Forest", 2)
        return publish(state, [{"quantity": 60, "card_name": "Forest"}])
    if face_kind == "restricted_mana":
        from tests.test_restricted_mana import clean, add
        state = clean(2)
        add(state, "Renowned Weaponsmith", 2)
        add(state, "Forest", 2)
        add(state, "Bonesplitter", 2)
        add(state, "Manakin", 2).tapped = True
        add(state, "Sol Ring", 2, Zone.HAND)
        add(state, "Naturalize", 2, Zone.HAND)
        add(state, "Sol Ring", 1)
        return publish(state, [{"quantity": 60, "card_name": "Forest"}])
    if face_kind == "conditional_opening":
        from tests.test_opening_hand import opening_game, add_opening, keep_both
        state = opening_game()
        add_opening(state, "Gemstone Caverns", 2)
        state = keep_both(state)
        return publish(state, [{"quantity": 60, "card_name": "Plains"}])
    if face_kind == "opening_hand":
        from tests.test_opening_hand import opening_game, add_opening, keep_both
        state = opening_game(2)
        add_opening(state, "Leyline of Sanctity", 2)
        state = keep_both(state)
        return publish(state, [{"quantity": 60, "card_name": "Plains"}])
    if face_kind == "stifle_protection":
        from tests.test_counterability_scope import add_card, state_with_card
        state, _ = state_with_card("Allosaurus Shepherd", Zone.BATTLEFIELD)
        add_card(state, "Stifle", Zone.HAND, 1)
        state.players[1].mana_pool["U"] = 1
        return publish(state, [{"quantity": 60, "card_name": "Island"}])
    if face_kind == "surviving_copy":
        from tests.test_copy_stack_characteristics import add_counter, surviving_copy
        state, _, _ = surviving_copy()
        add_counter(state, "Negate")
        deck = [{"quantity": 60, "card_name": "Bonecrusher Giant // Stomp"}]
        return publish(state, deck)
    if face_kind == "attacking_token_target":
        from game_state.state import assign_static_order_on_battlefield_entry
        from rules_engine.combat import declare_attackers
        from rules_engine.stack_engine import resolve_top_of_stack

        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=935)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_ATTACKERS
        cards = [
            CardInstance("adeline", "Adeline, Resplendent Cathar", 1, 1, Zone.BATTLEFIELD,
                         ["Creature"], power=2, toughness=4, oracle_text=(
                             "Vigilance\nAdeline's power is equal to the number of creatures you control.\n"
                             "Whenever you attack, for each opponent, create a 1/1 white Human creature token "
                             "that's tapped and attacking that player or a planeswalker they control."),
                         summoning_sick=False),
            CardInstance("bear", "Grizzly Bears", 1, 1, Zone.BATTLEFIELD,
                         ["Creature"], power=2, toughness=2, summoning_sick=False),
            CardInstance("teferi", "Teferi, Hero of Dominaria", 2, 2, Zone.BATTLEFIELD,
                         ["Planeswalker"], loyalty=1),
        ]
        for card in cards:
            state.cards[card.id] = card
            state.players[card.controller].battlefield.append(card.id)
            assign_static_order_on_battlefield_entry(state, card.id)
        declare_attackers(state, ["bear"])
        resolve_top_of_stack(state)
        return publish(state, deck)
    if face_kind == "linked_copy_x":
        import json
        from card_data.fallback_cards import fallback_card_payload
        from game_state.state import assign_static_order_on_battlefield_entry
        from rules_engine.linked_exile import record_linked_exile

        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=934)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.players[1].mana_pool["B"] = 2
        face = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())[
            "Valki, God of Lies // Tibalt, Cosmic Impostor"
        ]["card_faces"][0]
        source = CardInstance(
            "linked-valki", face["name"], 1, 1, Zone.BATTLEFIELD, ["Creature"],
            mana_cost=face["mana_cost"], oracle_text=face["oracle_text"],
            type_line=face["type_line"], power=int(face["power"]), toughness=int(face["toughness"]),
        )
        state.cards[source.id] = source
        state.players[1].battlefield.append(source.id)
        assign_static_order_on_battlefield_entry(state, source.id)
        printed = fallback_card_payload("Elvish Mystic")
        held = CardInstance(
            "linked-mystic", printed["name"], 2, 2, Zone.EXILE, ["Creature"],
            mana_cost=printed["mana_cost"], oracle_text=printed["oracle_text"],
            type_line=printed["type_line"], power=int(printed["power"]), toughness=int(printed["toughness"]),
        )
        state.cards[held.id] = held
        state.players[2].exile.append(held.id)
        record_linked_exile(state, source.id, source.effect_timestamp, [held.id], Zone.HAND)
        return publish(state, deck)
    if face_kind == "modal_copy_target":
        from effects.handlers import copy_spell
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=933)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        destroy = "Destroy target artifact"
        damage = "Kolaghan's Command deals 2 damage to any target"
        spell = CardInstance(
            id="modal-command", name="Kolaghan's Command", owner=1, controller=1,
            zone=Zone.STACK, types=["Instant"], mana_cost="{1}{B}{R}",
            oracle_text="Choose two —\n• Return target creature card from your graveyard to your hand.\n"
                        "• Target player discards a card.\n• Destroy target artifact.\n"
                        "• Kolaghan's Command deals 2 damage to any target.",
        )
        state.cards[spell.id] = spell
        for cid, name, types, power, toughness in (
            ("modal-ring", "Sol Ring", ["Artifact"], None, None),
            ("modal-spare", "Sol Ring", ["Artifact"], None, None),
            ("modal-bear", "Grizzly Bears", ["Creature"], 2, 2),
        ):
            card = CardInstance(cid, name, 2, 2, Zone.BATTLEFIELD, types, power=power, toughness=toughness)
            state.cards[cid] = card
            state.players[2].battlefield.append(cid)
        state.stack.append(StackItem(
            id="original-command", source_card_id=spell.id, controller=1,
            label=spell.name, effect_key="effect_sequence",
            payload={
                "effects": [
                    {"effect_key": "destroy_permanent", "payload": {"target_card_id": "modal-ring"}, "mode_text": destroy},
                    {"effect_key": "deal_damage", "payload": {"target_card_id": "modal-bear", "amount": 2}, "mode_text": damage},
                ],
                "__announced_targets": {
                    "mode_texts": [destroy, damage],
                    "mode_targets": {destroy: {"target_card_id": "modal-ring"}, damage: {"target_card_id": "modal-bear"}},
                },
            },
        ))
        copy_spell(state, 1, {"target_stack_id": "original-command", "may_choose_new_targets": True})
        return publish(state, deck)
    if face_kind == "divided_copy_target":
        from effects.handlers import copy_spell
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=932)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        spell = CardInstance(
            id="pyrotechnics", name="Pyrotechnics", owner=1, controller=1,
            zone=Zone.STACK, types=["Sorcery"], mana_cost="{4}{R}",
            oracle_text="Pyrotechnics deals 4 damage divided as you choose among any number of targets.",
        )
        bear = CardInstance(
            id="divided-bear", name="Grizzly Bears", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
        )
        state.cards[spell.id] = spell
        state.cards[bear.id] = bear
        state.players[1].battlefield.append(bear.id)
        distribution = {"1": 1, "2": 3}
        state.stack.append(StackItem(
            id="original-pyrotechnics", source_card_id=spell.id, controller=1,
            label=spell.name, effect_key="deal_damage_multi",
            payload={"target_distribution": dict(distribution),
                     "__announced_targets": {"target_distribution": dict(distribution), "divide_total": 4}},
        ))
        copy_spell(state, 2, {"target_stack_id": "original-pyrotechnics", "may_choose_new_targets": True})
        return publish(state, deck)
    if face_kind == "copy_target":
        from effects.handlers import copy_spell
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=931)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        bolt = CardInstance(
            id="copied-bolt", name="Lightning Bolt", owner=1, controller=1,
            zone=Zone.STACK, types=["Instant"], mana_cost="{R}",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
        )
        state.cards[bolt.id] = bolt
        state.stack.append(StackItem(
            id="original-bolt", source_card_id=bolt.id, controller=1,
            label=bolt.name, effect_key="deal_damage",
            payload={"target_player": 2, "amount": 3,
                     "__announced_targets": {"target_player": 2}},
        ))
        copy_spell(state, 2, {"target_stack_id": "original-bolt", "may_choose_new_targets": True})
        return publish(state, deck)
    if face_kind in {"snow_payment", "non_snow_payment"}:
        deck = [{"quantity": 60, "card_name": "Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=930)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        land_id = state.players[1].library.pop()
        land = state.cards[land_id]
        land.name = "Snow-Covered Forest" if face_kind == "snow_payment" else "Forest"
        land.type_line = "Basic Snow Land - Forest" if face_kind == "snow_payment" else "Basic Land - Forest"
        land.zone = Zone.BATTLEFIELD
        state.players[1].battlefield.append(land_id)
        spell = state.cards[state.players[1].hand[0]]
        spell.name = "Icehide Golem"
        spell.types, spell.type_line = ["Artifact", "Creature"], "Snow Artifact Creature - Golem"
        spell.mana_cost, spell.power, spell.toughness = "{S}", 2, 2
        spell.oracle_text = "({S} can be paid with one mana from a snow source.)"
        return publish(state, deck)
    if face_kind == "compleated_payment":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=925)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        state.players[1].mana_pool.update({"C": 2, "G": 2, "U": 1})
        spell = state.cards[state.players[1].hand[0]]
        spell.name = "Tamiyo, Compleated Sage"
        spell.types, spell.type_line = ["Legendary", "Planeswalker"], "Legendary Planeswalker - Tamiyo"
        spell.mana_cost, spell.loyalty = "{2}{G}{G/U/P}{U}", 5
        spell.oracle_text = (
            "Compleated ({G/U/P} can be paid with {G}, {U}, or 2 life. "
            "If life was paid, this planeswalker enters with two fewer loyalty counters.)\n"
            "+1: Tap up to one target artifact or creature. It doesn't untap during its controller's next untap step.\n"
            "-X: Exile target nonland permanent card with mana value X from your graveyard. Create a token that's a copy of that card.\n"
            "-7: Create Tamiyo's Notebook, a legendary colorless artifact token with \"Spells you cast cost {2} less to cast\" and \"{T}: Draw a card.\""
        )
        return publish(state, deck)
    if face_kind == "phyrexian_ability":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=923)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        source = CardInstance(
            id="pestilent-souleater", name="Pestilent Souleater", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Artifact", "Creature"],
            oracle_text="{B/P}: Pestilent Souleater gains infect until end of turn.",
            power=3, toughness=3,
        )
        state.cards[source.id] = source
        state.players[1].battlefield.append(source.id)
        return publish(state, deck)
    if face_kind == "phyrexian_payment":
        deck = [{"quantity": 60, "card_name": "Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=922)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        spell = state.cards[state.players[1].hand[0]]
        spell.name, spell.types, spell.type_line = "Mutagenic Growth", ["Instant"], "Instant"
        spell.mana_cost = "{G/P}"
        spell.oracle_text = "Target creature gets +2/+2 until end of turn."
        creature = CardInstance(
            id="phyrexian-target", name="Llanowar Elves", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
        )
        state.cards[creature.id] = creature
        state.players[1].battlefield.append(creature.id)
        return publish(state, deck)
    if face_kind == "hybrid_payment":
        deck = [{"quantity": 60, "card_name": "Plains"}]
        state = MatchFactory.from_decks(deck, deck, seed=921)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        for _ in range(3):
            cid = state.players[1].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.players[1].battlefield.append(cid)
        spell = state.cards[state.players[1].hand[0]]
        spell.name = "Spectral Procession"
        spell.types, spell.type_line = ["Sorcery"], "Sorcery"
        spell.mana_cost = "{2/W}{2/W}{2/W}"
        spell.oracle_text = "Create three 1/1 white Spirit creature tokens with flying."
        return publish(state, deck)
    if face_kind in {"thoughtseize", "duress", "inquisition", "despise", "appetite"}:
        deck = [{"quantity": 60, "card_name": "Swamp"}]
        state = MatchFactory.from_decks(deck, deck, seed=920)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        state.players[1].mana_pool["B"] = 1
        spell = state.cards[state.players[1].hand[0]]
        spell.name = {
            "thoughtseize": "Thoughtseize", "duress": "Duress",
            "inquisition": "Inquisition of Kozilek", "despise": "Despise",
            "appetite": "Appetite for Brains",
        }[face_kind]
        spell.types, spell.type_line, spell.mana_cost = ["Sorcery"], "Sorcery", "{B}"
        spell.oracle_text = {
            "thoughtseize": "Target player reveals their hand. You choose a nonland card from it. "
                            "That player discards that card. You lose 2 life.",
            "duress": "Target opponent reveals their hand. You choose a noncreature, nonland card from it. "
                      "That player discards that card.",
            "inquisition": "Target player reveals their hand. You choose a nonland card from it with mana value 3 or less. "
                           "That player discards that card.",
            "despise": "Target opponent reveals their hand. You choose a creature or planeswalker card from it. "
                       "That player discards that card.",
            "appetite": "Target opponent reveals their hand. You choose a card from it with mana value 4 or greater "
                        "and exile that card.",
        }[face_kind]
        hand = state.players[2].hand
        forest = state.cards[hand[0]]
        forest.name, forest.types, forest.type_line = "Forest", ["Land"], "Basic Land - Forest"
        bolt = state.cards[hand[1]]
        bolt.name, bolt.types, bolt.type_line, bolt.mana_cost = "Lightning Bolt", ["Instant"], "Instant", "{R}"
        bolt.oracle_text = "Lightning Bolt deals 3 damage to any target."
        elf = state.cards[hand[2]]
        elf.name, elf.types, elf.type_line, elf.mana_cost = "Llanowar Elves", ["Creature"], "Creature - Elf Druid", "{G}"
        elf.power, elf.toughness, elf.oracle_text = 1, 1, "{T}: Add {G}."
        fourth = state.cards[hand[3]]
        if face_kind in {"inquisition", "appetite"}:
            fourth.name, fourth.types, fourth.type_line, fourth.mana_cost = (
                "Serra Angel", ["Creature"], "Creature - Angel", "{3}{W}{W}",
            )
        elif face_kind == "despise":
            fourth.name, fourth.types, fourth.type_line, fourth.mana_cost = (
                "Jace, the Mind Sculptor", ["Planeswalker"], "Legendary Planeswalker - Jace", "{2}{U}{U}",
            )
        return publish(state, deck)
    if face_kind == "revealed_discard":
        deck = [{"quantity": 60, "card_name": "Swamp"}]
        state = MatchFactory.from_decks(deck, deck, seed=919)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        state.players[1].mana_pool.update({"B": 1, "C": 2})
        spell = state.cards[state.players[1].hand[0]]
        spell.name = "Coercion"
        spell.types = ["Sorcery"]
        spell.type_line = "Sorcery"
        spell.mana_cost = "{2}{B}"
        spell.oracle_text = "Target opponent reveals their hand. You choose a card from it. That player discards that card."
        return publish(state, deck)
    if face_kind == "each_player_discard":
        deck = [{"quantity": 60, "card_name": "Swamp"}]
        state = MatchFactory.from_decks(deck, deck, seed=818)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.mechanic_choice_players = {1, 2}
        state.players[1].mana_pool.update({"B": 1, "C": 2})
        spell_id = state.players[1].hand[0]
        spell = state.cards[spell_id]
        spell.name = "Delirium Skeins"
        spell.types = ["Sorcery"]
        spell.type_line = "Sorcery"
        spell.mana_cost = "{2}{B}"
        spell.oracle_text = "Each player discards three cards."
        return publish(state, deck)
    if face_kind == "modal_same_kind":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=914)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool.update({"B": 1, "R": 1, "C": 1})
        cards = (
            CardInstance(id="kolaghan", name="Kolaghan's Command", owner=2, controller=2,
                         zone=Zone.HAND, types=["Instant"], mana_cost="{1}{B}{R}",
                         oracle_text=("Choose two —\n"
                                      "• Return target creature card from your graveyard to your hand.\n"
                                      "• Target player discards a card.\n"
                                      "• Destroy target artifact.\n"
                                      "• Kolaghan's Command deals 2 damage to any target.")),
            CardInstance(id="ring", name="Sol Ring", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Artifact"], oracle_text="{T}: Add {C}{C}."),
            CardInstance(id="bear", name="Grizzly Bears", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2),
            CardInstance(id="elf-grave", name="Llanowar Elves", owner=2, controller=2,
                         zone=Zone.GRAVEYARD, types=["Creature"], power=1, toughness=1),
            CardInstance(id="bear-grave", name="Grizzly Bears", owner=2, controller=2,
                         zone=Zone.GRAVEYARD, types=["Creature"], power=2, toughness=2),
            CardInstance(id="opponent-grave", name="Grizzly Bears", owner=1, controller=1,
                         zone=Zone.GRAVEYARD, types=["Creature"], power=2, toughness=2),
        )
        for card in cards:
            state.cards[card.id] = card
            getattr(state.players[card.owner], card.zone.value).append(card.id)
        return publish(state, deck)
    if face_kind == "modal_two_targets":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=913)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["U"] = 4
        cards = (
            CardInstance(id="cryptic", name="Cryptic Command", owner=2, controller=2,
                         zone=Zone.HAND, types=["Instant"], mana_cost="{1}{U}{U}{U}",
                         oracle_text=("Choose two —\n• Counter target spell.\n"
                                      "• Return target permanent to its owner's hand.\n"
                                      "• Tap all creatures your opponents control.\n• Draw a card.")),
            CardInstance(id="bolt", name="Lightning Bolt", owner=1, controller=1,
                         zone=Zone.STACK, types=["Instant"], mana_cost="{R}",
                         oracle_text="Lightning Bolt deals 3 damage to any target."),
            CardInstance(id="forest", name="Forest", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Land"], type_line="Basic Land — Forest"),
        )
        for card in cards:
            state.cards[card.id] = card
            if card.zone != Zone.STACK:
                getattr(state.players[card.owner], card.zone.value).append(card.id)
        state.stack.append(StackItem("bolt-stack", "bolt", 1, "Lightning Bolt", "deal_damage", {"target_player": 2, "amount": 3}))
        return publish(state, deck)
    if face_kind == "modal_targetless":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=912)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool.update({"U": 1, "R": 1})
        card = CardInstance(
            id="izzet-charm", name="Izzet Charm", owner=2, controller=2,
            zone=Zone.HAND, types=["Instant"], mana_cost="{U}{R}",
            oracle_text=(
                "Choose one —\n"
                "• Counter target noncreature spell unless its controller pays {2}.\n"
                "• Izzet Charm deals 2 damage to target creature.\n"
                "• Draw two cards, then discard two cards."
            ),
        )
        state.cards[card.id] = card
        state.players[2].hand.append(card.id)
        return publish(state, deck)
    if face_kind == "player_hexproof":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=911)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.players[1].mana_pool["R"] = 1
        cards = (
            CardInstance(id="bolt", name="Shock", owner=1, controller=1, zone=Zone.HAND,
                         types=["Instant"], mana_cost="{R}", oracle_text="Shock deals 2 damage to any target."),
            CardInstance(id="shield", name="Leyline of Sanctity", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Enchantment"], oracle_text="You have hexproof."),
            CardInstance(id="bear", name="Grizzly Bears", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2),
        )
        for card in cards:
            state.cards[card.id] = card
            getattr(state.players[card.controller], card.zone.value).append(card.id)
        return publish(state, deck)
    if face_kind == "damage_trigger":
        from effects.handlers import sacrifice
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=603)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.PRECOMBAT_MAIN
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {1}
        cards = (
            CardInstance(id="devil", name="Mayhem Devil", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=3, toughness=3,
                         oracle_text="Whenever a player sacrifices a permanent, this creature deals 1 damage to any target."),
            CardInstance(id="chalice", name="Everflowing Chalice", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Artifact"]),
            CardInstance(id="elf", name="Llanowar Elves", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=1,
                         oracle_text="{T}: Add {G}."),
        )
        for card in cards:
            state.cards[card.id] = card
            state.players[card.controller].battlefield.append(card.id)
        sacrifice(state, 1, {"target_card_id": "chalice"})
        return publish(state, deck)
    if face_kind == "variable_life_x":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=46)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool.update({"B": 1, "C": 2})
        cards = [
            CardInstance(id="deluge", name="Toxic Deluge", owner=2, controller=2,
                         zone=Zone.HAND, types=["Sorcery"], mana_cost="{2}{B}",
                         oracle_text="As an additional cost to cast this spell, pay X life.\nAll creatures get -X/-X until end of turn."),
            CardInstance(id="own-four", name="Giant Spider", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=4, oracle_text="Reach"),
            CardInstance(id="their-two", name="Grizzly Bears", owner=1, controller=1,
                         zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2),
        ]
        for card in cards:
            state.cards[card.id] = card
            getattr(state.players[card.owner], card.zone.value).append(card.id)
        return publish(state, deck)
    if face_kind in {"conditional_land", "conditional_land_effect"}:
        import json
        from effects.handlers import put_land_from_hand
        seed = json.loads((Path(__file__).resolve().parents[1] / "card_data/builtin_oracle_seed.json").read_text())["cards"]["Sacred Foundry"]
        deck = [{"quantity": 1, "card_name": seed["name"], "type_line": seed["type_line"], "oracle_text": seed["oracle_text"]},
                {"quantity": 59, "card_name": "Island", "type_line": "Basic Land - Island"}]
        opponent = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(opponent, deck, seed=45)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        cid = next(cid for cid, card in state.cards.items() if card.owner == 2 and card.name == "Sacred Foundry")
        if cid in state.players[2].library:
            state.players[2].library.remove(cid)
            state.players[2].hand.append(cid)
            state.cards[cid].zone = Zone.HAND
        if face_kind == "conditional_land_effect":
            put_land_from_hand(state, 2, {"land_id": cid, "tapped": False})
        return publish(state, deck)
    if face_kind == "draw_cap":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=37)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        spirit = CardInstance(
            id="draw-spirit", name="Spirit of the Labyrinth", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Enchantment", "Creature"],
            oracle_text="Each player can't draw more than one card each turn.",
            power=3, toughness=1,
        )
        spell = CardInstance(
            id="draw-divination", name="Divination", owner=2, controller=2,
            zone=Zone.HAND, types=["Sorcery"], mana_cost="{2}{U}",
            oracle_text="Draw two cards.",
        )
        state.cards.update({spirit.id: spirit, spell.id: spell})
        state.players[1].battlefield.append(spirit.id)
        state.players[2].hand.append(spell.id)
        state.players[2].mana_pool.update({"C": 2, "U": 1})
        return publish(state, deck)
    if face_kind == "nonland_mana":
        from card_data.token_definitions import named_artifact_token
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=36)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        sources = (
            CardInstance(id="mana-creature", name="Llanowar Elves", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Creature"], oracle_text="{T}: Add {G}.",
                         power=1, toughness=1, summoning_sick=False),
            CardInstance(id="mana-treasure", name="Treasure", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Artifact", "Token"], is_token=True,
                         oracle_text=named_artifact_token("Treasure")["oracle_text"]),
            CardInstance(id="mana-ring", name="Sol Ring", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Artifact"], oracle_text="{T}: Add {C}{C}."),
            CardInstance(id="mana-lotus", name="Gilded Lotus", owner=2, controller=2,
                         zone=Zone.BATTLEFIELD, types=["Artifact"], oracle_text="{T}: Add three mana of any one color."),
        )
        for card in sources:
            state.cards[card.id] = card
            state.players[2].battlefield.append(card.id)
        return publish(state, deck)
    if face_kind == "draw_replacement":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=35)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.turn = 2
        state.step = Step.DRAW
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        reflection = CardInstance(
            id="reflection", name="Thought Reflection", owner=2, controller=2,
            zone=Zone.BATTLEFIELD, types=["Enchantment"],
            oracle_text="If you would draw a card, draw two cards instead.",
        )
        dredger = CardInstance(
            id="stinkweed", name="Stinkweed Imp", owner=2, controller=2,
            zone=Zone.GRAVEYARD, types=["Creature"],
            oracle_text="Flying\nWhenever this creature deals combat damage to a creature, destroy that creature.\nDredge 5 (If you would draw a card, you may mill five cards instead. If you do, return this card from your graveyard to your hand.)",
        )
        state.cards.update({reflection.id: reflection, dredger.id: dredger})
        state.players[2].battlefield.append(reflection.id)
        state.players[2].graveyard.append(dredger.id)
        resolve_effect(state, 2, "draw_cards", {"amount": 1})
        return publish(state, deck)
    if face_kind == "company":
        from rules_engine.ability_model import build_ability_spec
        from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=34)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name in zip(state.players[2].library[-6:],
            ["Grizzly Bears", "Llanowar Elves", "Island", "Plains", "Swamp", "Mountain"]):
            card = state.cards[cid]
            card.name = name
            if name in {"Grizzly Bears", "Llanowar Elves"}:
                card.types = ["Creature"]
                card.type_line = "Creature"
                card.mana_cost = "{1}{G}" if name == "Grizzly Bears" else "{G}"
                card.power = card.toughness = 2 if name == "Grizzly Bears" else 1
            else:
                card.types = ["Land"]
                card.type_line = f"Basic Land - {name}"
        spell = CardInstance(
            id="company", name="Collected Company", owner=2, controller=2,
            zone=Zone.STACK, types=["Instant"],
            oracle_text="Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the battlefield. Put the rest on the bottom of your library in any order.",
        )
        state.cards[spell.id] = spell
        spec = build_ability_spec(state, spell, 2)
        add_to_stack(state, spell.id, 2, spell.name, spec.effect.key, spec.effect.payload)
        resolve_top_of_stack(state)
        return publish(state, deck)
    if face_kind == "iteration":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=32)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name, cost, types in zip(state.players[2].library[-3:],
            ["Lightning Bolt", "Counterspell", "Llanowar Elves"],
            ["{R}", "{U}{U}", "{G}"], [["Instant"], ["Instant"], ["Creature"]]):
            card = state.cards[cid]
            card.name, card.mana_cost, card.types = name, cost, types
        resolve_effect(state, 2, "look_top_choose", {"top_n": 3})
        return publish(state, deck)
    if face_kind == "search":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=33)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name, cost, power in zip(state.players[2].library[-2:],
            ["Llanowar Elves", "Grizzly Bears"], ["{G}", "{1}{G}"], [1, 2]):
            card = state.cards[cid]
            card.name, card.mana_cost, card.types = name, cost, ["Creature"]
            card.type_line = "Creature"
            card.power = card.toughness = power
        resolve_effect(state, 2, "search_library", {"contains": "creature", "destination": "hand", "count": 1, "shuffle": True})
        return publish(state, deck)
    if face_kind in {"bo3", "bo3_sideboard", "bo3_draw"}:
        deck = ([{"quantity": 45, "card_name": "Island", "type_line": "Basic Land - Island"},
                 {"quantity": 15, "card_name": "Mountain", "type_line": "Basic Land - Mountain"}]
                if face_kind == "bo3_sideboard" else
                [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}])
        state = MatchFactory.from_decks(deck, deck, seed=31)
        state.winner = 2 if face_kind == "bo3_sideboard" else (0 if face_kind == "bo3_draw" else 1)
        state.score = {1: 0, 2: 1} if face_kind == "bo3_sideboard" else {1: 1, 2: 0}
        publish(state, deck)
        match = ACTIVE_MATCHES[state.id]
        match.current_game_recorded = True
        match.root_seed = 31
        if face_kind == "bo3_draw":
            match.play_draw_chooser = 2
        if face_kind == "bo3_sideboard":
            match.sideboards[1] = [{"quantity": 15, "card_name": "Forest"}]
        with Session(engine) as session:
            repo = Repository(session)
            if face_kind == "bo3_sideboard":
                # Exercise real hydration without an incidental Scryfall request
                # exceeding the browser's action timeout on an empty cache.
                import json
                rows = json.loads((Path(__file__).parent / "fixtures/sideboard_basics.json").read_text())
                for row in rows:
                    repo.upsert_card({
                        **{key: row[key] for key in ("name", "scryfall_id", "oracle_text", "mana_cost", "type_line", "layout")},
                        "colors": ",".join(row["colors"]),
                        "image_uri": "/card-images/generic-token-creature.svg",
                    })
            _persist_active_match(repo, match)
        return get_match(state.id)
    if face_kind in {"trigger", "cast_trigger"}:
        import json
        rows = json.loads((Path(__file__).parent / "fixtures/permanent_spell_context.json").read_text())
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=17)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {2}
        state.players[2].mana_pool.update({"G": 3, "C": 12 if face_kind == "cast_trigger" else 3})

        for cid, name, owner, zone in (
            ("cast-source" if face_kind == "cast_trigger" else "sage",
             "Ulamog, the Infinite Gyre" if face_kind == "cast_trigger" else "Reclamation Sage", 2, Zone.HAND),
            ("ring", "Sol Ring", 2, Zone.BATTLEFIELD),
            ("copter", "Smuggler's Copter", 1, Zone.BATTLEFIELD),
        ):
            row = rows[name]
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=zone,
                types=row["type_line"].split(" — ")[0].split(),
                type_line=row["type_line"], oracle_text=row["oracle_text"],
                mana_cost=row["mana_cost"],
                power=int(row["power"]) if row["power"] else None,
                toughness=int(row["toughness"]) if row["toughness"] else None,
            )
            state.cards[cid] = card
            getattr(state.players[owner], zone.value).append(cid)
        return publish(state, deck)
    if face_kind == "alternative_target":
        from card_data.fallback_cards import fallback_card_payload

        deck = [{"quantity": 60, "card_name": "Mountain"}]
        state = MatchFactory.from_decks(deck, deck, seed=23)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["R"] = 1
        spell = CardInstance(
            id="lava-spike", name="Lava Spike", owner=2, controller=2, zone=Zone.HAND,
            types=["Sorcery"], mana_cost="{R}",
            oracle_text="Lava Spike deals 3 damage to target player or planeswalker.",
        )
        walker = CardInstance(
            id="teferi", name="Teferi, Hero of Dominaria", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Planeswalker"], loyalty=4,
            type_line="Legendary Planeswalker — Teferi",
            oracle_text=fallback_card_payload("Teferi, Hero of Dominaria")["oracle_text"],
        )
        state.cards.update({spell.id: spell, walker.id: walker})
        state.players[2].hand.append(spell.id)
        state.players[1].battlefield.append(walker.id)
        return publish(state, deck)
    if face_kind == "first_strike_window":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=37)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        swiftblade = CardInstance(
            id="swiftblade", name="Boros Swiftblade", owner=1, controller=1,
            zone=Zone.BATTLEFIELD, types=["Creature"], power=1, toughness=2,
            keywords=["double strike"], oracle_text="Double strike",
        )
        state.cards[swiftblade.id] = swiftblade
        state.players[1].battlefield.append(swiftblade.id)
        state.attackers = [swiftblade.id]
        state.attack_targets = {swiftblade.id: "player:2"}
        state.attackers_declared = True
        state.blockers_declared = True
        return publish(state, deck)
    if face_kind == "combat_damage_assignment":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=83)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        for cid, name, owner, power, toughness in (
            ("courser", "Centaur Courser", 1, 3, 3),
            ("bears", "Grizzly Bears", 2, 2, 2),
            ("giant", "Hill Giant", 2, 3, 3),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        state.attackers = ["courser"]
        state.blocks = {"courser": ["bears", "giant"]}
        return publish(state, deck)
    if face_kind == "shared_trample":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=89)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        for cid, name, owner, power, toughness, keywords, oracle in (
            ("first", "Charging Monstrosaur", 1, 5, 5, ["trample", "haste"], "Trample, haste"),
            ("second", "Charging Monstrosaur", 1, 5, 5, ["trample", "haste"], "Trample, haste"),
            ("guard", "Palace Guard", 2, 1, 4, [], "Palace Guard can block any number of creatures."),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness,
                keywords=keywords, oracle_text=oracle, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        state.attackers = ["first", "second"]
        state.blocks = {"first": ["guard"], "second": ["guard"]}
        return publish(state, deck)
    if face_kind == "banding_damage":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=97)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.mechanic_choice_players = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_BLOCKERS
        state.blockers_declared = True
        for cid, name, owner, power, toughness, keywords in (
            ("courser", "Centaur Courser", 1, 3, 3, []),
            ("hero", "Benalish Hero", 2, 1, 1, ["banding"]),
            ("bears", "Grizzly Bears", 2, 2, 2, []),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness,
                keywords=keywords, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        state.attackers = ["courser"]
        state.blocks = {"courser": ["hero", "bears"]}
        return publish(state, deck)
    if face_kind == "attacking_band":
        deck = [{"quantity": 60, "card_name": "Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=99)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_ATTACKERS
        for cid, name, owner, power, toughness, keywords in (
            ("hero", "Benalish Hero", 1, 1, 1, ["banding"]),
            ("angel", "Serra Angel", 1, 4, 4, ["flying", "vigilance"]),
            ("elf", "Llanowar Elves", 1, 1, 1, []),
            ("bears", "Grizzly Bears", 2, 2, 2, []),
        ):
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
                types=["Creature"], power=power, toughness=toughness,
                keywords=keywords, summoning_sick=False,
            )
            state.cards[cid] = card
            state.players[owner].battlefield.append(cid)
        return publish(state, deck)
    if modal or face_kind:
        import json
        if face_kind == "split":
            raw = json.loads((Path(__file__).parent / "fixtures/split_cards.json").read_text())[0]
        elif face_kind == "aftermath":
            raw = json.loads((Path(__file__).parent / "fixtures/aftermath_cards.json").read_text())[0]
        elif face_kind in {"multi_adventure", "multi_adventure_copy"}:
            raw = json.loads((Path(__file__).parent / "fixtures/multi_target_adventure.json").read_text())
        else:
            name = {"land": "Bala Ged Recovery // Bala Ged Sanctuary", "adventure": "Bonecrusher Giant // Stomp"}.get(face_kind, "Wandering Archaic // Explore the Vastlands")
            raw = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())[name]
        characteristics = {**raw, "oracle_text": raw["card_faces"][0]["oracle_text"]} if face_kind in {"split", "aftermath"} else {**raw["card_faces"][0], "layout": raw["layout"], "card_faces": raw["card_faces"]}
        deck = [{"quantity": 60, "card_name": raw["name"], **characteristics}]
        state = MatchFactory.from_decks(deck, deck, seed=9)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["C"] = modal_mana
        if face_kind == "aftermath":
            state.players[2].mana_pool.update({"C": 4, "U": 2})
            card_id = state.players[2].hand.pop(0)
            state.players[2].graveyard.append(card_id)
            state.cards[card_id].move_to_zone(Zone.GRAVEYARD)
        if face_kind == "adventure":
            state.players[2].mana_pool["R"] = 4
        if face_kind == "split":
            state.players[2].mana_pool.update({"C": 1, "R": 1, "U": 1})
            island = CardInstance("split-target-island", "Island", 1, 1, Zone.BATTLEFIELD,
                                  ["Land"], type_line="Basic Land — Island", oracle_text="{T}: Add {U}.")
            state.cards[island.id] = island
            state.players[1].battlefield.append(island.id)
        if face_kind in {"multi_adventure", "multi_adventure_copy"}:
            state.players[2].mana_pool["C"] = 0
            state.players[2].mana_pool["B"] = 1
            creature_id = state.players[1].hand.pop()
            state.players[1].battlefield.append(creature_id)
            state.cards[creature_id].zone = Zone.BATTLEFIELD
            if face_kind == "multi_adventure_copy":
                from effects.handlers import copy_spell
                from rules_engine.action_validation import checked_action

                own_id = state.players[2].hand.pop(1)
                state.players[2].battlefield.append(own_id)
                state.cards[own_id].zone = Zone.BATTLEFIELD
                state.mechanic_choice_players = {1, 2}
                state = checked_action(state, RulesEngine(), 2, {
                    "type": "cast_spell", "card_id": state.players[2].hand[0], "selected_face_index": 1,
                    "targets": {"target_card_id": creature_id, "target_player": 1},
                })
                copy_spell(state, 2, {"target_stack_id": state.stack[-1].id, "may_choose_new_targets": True})
        return publish(state, deck)
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=15)
    if pregame:
        state.kept_hands = {1}
        state.priority_player = 2
        state.mulligan_count[2] = 1
        return publish(state, deck)
    state.pregame_pending = False
    state.active_player = state.priority_player = 2
    state.step = Step.PRECOMBAT_MAIN
    state.players[2].hand = []
    state.players[2].mana_pool.update({"G": 3, "R": 3})

    def add(cid, name, zone, types, cost="", text="", power=None, toughness=None, type_line=""):
        card = CardInstance(id=cid, name=name, owner=2, controller=2, zone=zone, types=types, mana_cost=cost, oracle_text=text, power=power, toughness=toughness, type_line=type_line.replace(" - ", " \u2014 "), summoning_sick=False)
        state.cards[cid] = card
        getattr(state.players[2], zone.value).append(cid)
        return card

    add("forest", "Forest", Zone.HAND, ["Land"], type_line="Basic Land - Forest")
    add("pyromancer", "Prodigal Pyromancer", Zone.BATTLEFIELD, ["Creature"], "{2}{R}", "{T}: Prodigal Pyromancer deals 1 damage to any target.", 1, 1)
    add("bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], "{1}{G}", power=2, toughness=2)
    add("copter", "Smuggler's Copter", Zone.BATTLEFIELD, ["Artifact"], "{2}", "Flying\nCrew 1", 3, 3, "Artifact - Vehicle")
    add("shock", "Shock", Zone.EXILE, ["Instant"], "{R}", "Shock deals 2 damage to any target.")
    state.players[2].exile_play_until["shock"] = state.turn
    walker = add("walker", "Realmwalker", Zone.BATTLEFIELD, ["Creature"], "{2}{G}", "You may cast creature spells of the chosen type from the top of your library.", 2, 3)
    walker.chosen_creature_type = "Elf"
    add("elf", "Llanowar Elves", Zone.LIBRARY, ["Creature"], "{G}", "{T}: Add {G}.", 1, 1, "Creature - Elf Druid")
    return publish(state, deck)


@app.post("/fixture/history")
def fixture_history():
    import json
    from main import DIAGNOSTICS_ROOT
    retained = dict(ACTIVE_MATCHES)
    for index in range(7):
        fixture()
        retained.update(ACTIVE_MATCHES)
        run = DIAGNOSTICS_ROOT / f'preview-fixture-{index}'
        run.mkdir(parents=True, exist_ok=True)
        (run / 'summary.json').write_text(json.dumps({'matches': 1, 'anomaly_count': 0}), encoding='utf-8')
    ACTIVE_MATCHES.update(retained)
    return {'matches': len(ACTIVE_MATCHES)}


def publish(state, deck):
    ACTIVE_MATCHES.clear()
    ACTIVE_MATCHES[state.id] = MatchController(state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    with Session(engine) as session:
        _persist_active_match(Repository(session), ACTIVE_MATCHES[state.id])
    return get_match(state.id)


@app.get("/fixture/sideboard-pool/{match_id}")
def fixture_sideboard_pool(match_id: str):
    match = ACTIVE_MATCHES[match_id]
    player = match.state.players[1]
    return dict(Counter(match.state.cards[cid].name for cid in player.hand + player.library))
