"""V2 visual stress positions, not played games. Disposable loopback source copy only.

Uses canonical test metadata and real mutation/persistence routes. Optional local
art must be pre-cached as v2-<slug>.jpg; this fixture never downloads card data.
"""
from pathlib import Path
import main

if (Path(main.__file__).resolve().parents[1] / ".git").exists():
    raise RuntimeError("UI fixtures require a disposable backend source copy")

from tests.ui_fixture_server import app, publish, fixture, add
from game_state.state import Zone
import tests.life_lock_browser_fixture  # Register disposable effective-restriction scenarios.


@app.post('/fixture/life-conversion')
def life_conversion(seat: int = 1):
    if seat not in (1, 2):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected a valid seat')
    from tests.test_ai_beneficial_alternatives import damage_gain_position
    from tests.test_life_conversion import permanent
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from rules_engine.stack_engine import resolve_top_of_stack
    state, spell = damage_gain_position(seat, 'lightning-helix')
    state.players[seat].mana_pool = {color: int(color in 'WR') for color in 'WUBRGC'}
    converter = permanent(state, 'plague-drone', 3-seat)
    archive = permanent(state, 'alhammarrets-archive', seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
                           'card_id': spell.id, 'targets': {'target_card_id': converter.id}})
    assert not resolve_top_of_stack(state)
    assert state.pending_replacement_choice
    assert state.cards[converter.id].counters['__damage_marked'] == 3
    state.log.append('Canonical paused life-conversion UI fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Mountain'}])
    return {'match': result, 'spell_id': spell.id, 'converter_id': converter.id,
            'archive_id': archive.id}


@app.post('/fixture/linked-damage')
def linked_damage(seat: int = 1, primary: str = 'player', enhanced: bool = False):
    if seat not in (1, 2) or primary not in ('player', 'planeswalker'):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected a valid seat and primary target kind')
    from tests.test_linked_damage_targets import position
    state, spell, creature, walker, targets = position(seat, primary)
    state.players[seat].mana_pool = {color: 2 if color == 'R' else 0 for color in 'WUBRGC'}
    if enhanced:
        state.land_entries_this_turn[seat] = 1
    before = state.players[3-seat].life if walker is None else walker.loyalty
    state.log.append('Canonical linked-damage UI fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Mountain'}])
    return {'match': result, 'spell_id': spell.id, 'creature_id': creature.id,
            'walker_id': walker.id if walker else None, 'targets': targets,
            'primary_name': walker.name if walker else state.players[3-seat].name,
            'primary_before': before, 'amount': 3 if enhanced else 1}


@app.post('/fixture/linked-copy')
def linked_copy(seat: int = 1, primary: str = 'player'):
    if seat not in (1, 2) or primary not in ('player', 'planeswalker'):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected a valid seat and primary target kind')
    from tests.test_linked_copy_targets import copied_position
    state, original, first, second, walker = copied_position(seat, primary, paid=True)
    for player in state.players.values():
        player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
    state.log.append('Canonical paid linked-copy UI fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Mountain'}])
    return {'match': result, 'original_id': original, 'first_id': first,
            'second_id': second, 'walker_id': walker, 'primary_name': state.players[seat].name}


@app.post('/fixture/conditional-copy')
def conditional_copy(seat: int = 1, name: str = 'groundswell', enhanced: bool = False):
    if seat not in (1, 2) or name not in ('groundswell', 'rest-for-the-weary', 'lightning-helix', 'essence-drain'):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected a valid seat and supported alternative')
    import json
    from tests.test_landfall_alternatives import position
    from tests.test_linked_damage_targets import raw_card
    from tests.test_ai_recurring_engines import add
    from tests.test_real_ordered_spell_copy import pass_twice
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    if name in ('lightning-helix', 'essence-drain'):
        from tests.test_ai_beneficial_alternatives import damage_gain_position
        state, spell = damage_gain_position(seat, name)
        old = add(state, 'Torrential Gearhulk', seat)
        targets = {'target_player': 3-seat}
    else:
        state, spell, old, targets = position(name, seat)
    copier = 3-seat
    new = add(state, 'Torrential Gearhulk', copier)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    original = state.stack[-1].id
    raw = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/twincast.json').read_text())
    twincast = raw_card(state, raw, copier, Zone.HAND)
    state.players[copier].mana_pool = {'U': 2}
    state.land_entries_this_turn[copier] = int(enhanced)
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), copier,
                           {'type': 'cast_spell', 'card_id': twincast.id,
                            'targets': {'target_stack_id': original}})
    state = pass_twice(state)
    assert state.pending_mechanic_choice is not None
    for player in state.players.values():
        player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
    state.log.append('Canonical paid conditional-copy UI fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'original_id': original, 'old_id': old.id, 'new_id': new.id,
            'spell_name': spell.name, 'recipient_name': new.name if name == 'groundswell' else state.players[seat].name}


@app.post('/fixture/ordered-modifiers')
def ordered_modifiers(seat: int = 1):
    if seat not in (1, 2):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected seat one or two')
    from tests.test_ordered_creature_modifiers import position
    state, spell, first, second = position(seat)
    state.log.append('Canonical ordered-modifier casting fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'spell_id': spell, 'creature_ids': [first, second]}


@app.post('/fixture/ordered-copy')
def ordered_copy(seat: int = 1, shared: bool = False):
    if seat not in (1, 2):
        from fastapi import HTTPException
        raise HTTPException(422, 'Expected seat one or two')
    from tests.test_ordered_copy_targets import copied_position
    state, original, first, second = copied_position(seat, shared)
    state.log.append('Canonical copy-effect choice fixture; not a played competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'original_id': original, 'creature_ids': [first, second]}


@app.post("/fixture/table-v2")
def table_v2(seat: int = 1, crowded: bool = True, artwork: bool = True):
    if seat not in (1, 2):
        raise ValueError("Expected seat one or two")
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in (1, 2):
        state.players[player].mana_pool = {color: 0 for color in "WUBRGC"}
        state.players[player].mana_pool["G"] = 2
        state.players[player].snow_mana_pool = {color: 0 for color in "WUBRGC"}
        for index in range(15 if crowded else 3):
            card = add(state, ["Grizzly Bears", "Llanowar Elves", "Torrential Gearhulk"][index % 3], player)
            card.summoning_sick = index == 0
            card.tapped = index % 4 == 2
            if index == 1:
                card.counters["+1/+1"] = 1
                card.counters["__damage_marked"] = 1
        for index in range(20 if crowded else 5):
            card = add(state, "Swamp", player)
            card.tapped = index < 3
        for index in range(15 if crowded else 4):
            add(state, ["Grizzly Bears", "Go for the Throat", "Naturalize", "Swamp"][index % 4], player, Zone.HAND)
        add(state, "Grizzly Bears", player, Zone.GRAVEYARD)
        if artwork:
            for zone in ("battlefield", "hand", "graveyard"):
                for card_id in getattr(state.players[player], zone):
                    card = state.cards[card_id]
                    filename = "v2-" + card.name.lower().replace(" ", "-") + ".jpg"
                    if (main.CACHE_DIR / filename).is_file():
                        card.image_uri = "/card-images/" + filename
    state.log.append("V2 UI stress fixture: canonical cards; constructed position, not a played game.")
    return publish(state, [{"quantity": 60, "card_name": "Swamp"}])
