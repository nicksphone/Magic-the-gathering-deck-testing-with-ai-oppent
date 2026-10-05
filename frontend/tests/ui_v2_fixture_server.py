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
