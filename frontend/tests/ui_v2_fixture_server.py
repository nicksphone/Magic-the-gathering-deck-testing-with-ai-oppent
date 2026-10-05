"""V2 visual stress positions, not played games. Disposable loopback source copy only.

Uses canonical test metadata and real mutation/persistence routes. Optional local
art must be pre-cached as v2-<slug>.jpg; this fixture never downloads card data.
"""
from pathlib import Path
import main
import tests.activation_payment_browser_fixture

if (Path(main.__file__).resolve().parents[1] / ".git").exists():
    raise RuntimeError("UI fixtures require a disposable backend source copy")

from tests.ui_fixture_server import app, publish, fixture, add
from game_state.state import Zone
import tests.life_lock_browser_fixture  # Register disposable effective-restriction scenarios.


@app.post('/fixture/graveyard-permission')
def graveyard_permission(seat: int = 1, name: str = 'Forest'):
    from fastapi import HTTPException
    from tests.test_graveyard_play_permissions import position, ROWS, modal_land
    from tests.test_ai_recurring_engines import add as canonical
    if seat not in (1, 2) or name not in {'Forest', 'Bala Ged Recovery', 'Gravecrawler'}:
        raise HTTPException(422, 'Expected a supported graveyard fixture')
    state = position(seat)
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {color: player.mana_pool.get(color, 0) for color in 'WUBRGC'}
    card = modal_land(state, seat) if name == 'Bala Ged Recovery' else canonical(state, name, seat, Zone.GRAVEYARD, cards=ROWS)
    canonical(state, 'Diregraf Ghoul' if name == 'Gravecrawler' else 'Crucible of Worlds', seat, cards=ROWS)
    state.log.append('Canonical graveyard-permission fixture; not a competitive deck.')
    return {'match': publish(state, [{'quantity': 60, 'card_name': 'Island'}]), 'card_id': card.id}


@app.post('/fixture/cast-resources')
def cast_resources(seat: int = 1, name: str = 'Dig Through Time'):
    from fastapi import HTTPException
    from tests.test_cast_resource_payments import position, ROWS
    from tests.test_ai_recurring_engines import add as canonical
    if seat not in (1, 2) or name not in {'Dig Through Time', 'Siege Wurm', 'Reverse Engineer'}:
        raise HTTPException(422, 'Expected a supported seat and resource fixture')
    state, card = position(seat, name)
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.players[seat].mana_pool = {color: 2 if color == 'U' and name != 'Siege Wurm' else 0 for color in 'WUBRGC'}
    choices = {'delve': [], 'convoke': [], 'improvise': []}
    if name == 'Siege Wurm':
        for creature, count, color in [('Llanowar Elves', 2, 'G'), ('Ornithopter', 5, 'generic')]:
            for _ in range(count):
                resource = canonical(state, creature, seat, cards=ROWS)
                choices['convoke'].append({'card_id': resource.id, 'pay_as': color})
    else:
        kind, count, zone = ('delve', 6, Zone.GRAVEYARD) if name == 'Dig Through Time' else ('improvise', 3, Zone.BATTLEFIELD)
        choices[kind] = [canonical(state, 'Ornithopter', seat, zone, cards=ROWS).id for _ in range(count)]
    state.log.append('Canonical casting-resource UI fixture; not a competitive deck.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'spell_id': card.id, 'choices': choices}


@app.get('/fixture/casting-payment/{match_id}')
def casting_payment(match_id: str):
    from fastapi import HTTPException
    match = main.ACTIVE_MATCHES.get(match_id)
    if match is None or len(match.state.stack) != 1:
        raise HTTPException(422, 'Expected one fixture spell on stack')
    item = match.state.stack[0]
    return {'source_card_id': item.source_card_id, 'mana_spent': item.payload.get('mana_spent'),
            'resources': item.payload.get('__casting_resource_payment')}


@app.post('/fixture/opaque-selection')
def opaque_selection(seat: int = 1, name: str = 'Impulse'):
    from fastapi import HTTPException
    from tests.test_ai_opaque_selection_horizon import position, ROWS
    from tests.test_ai_recurring_engines import add as canonical
    if seat not in (1, 2) or name not in {'Impulse', 'Anticipate', 'Memory Deluge', 'Dig Through Time'}:
        raise HTTPException(422, 'Expected a supported seat and selection fixture')
    state, spell = position(seat, name)
    state.mechanic_choice_players = {1, 2}
    for inspected in ROWS:
        if inspected != name:
            canonical(state, inspected, seat, Zone.LIBRARY, cards=ROWS)
    labels = {cid: card.name for cid, card in state.cards.items()}
    state.log.append('Canonical selection UI fixture; not a competitive deck or played game.')
    result = publish(state, [{'quantity': 60, 'card_name': 'Island'}])
    return {'match': result, 'spell_id': spell.id, 'labels': labels}


@app.get('/fixture/opaque-selection-library/{match_id}')
def opaque_selection_library(match_id: str, seat: int = 1):
    from fastapi import HTTPException
    match = main.ACTIVE_MATCHES.get(match_id)
    if seat not in (1, 2) or match is None:
        raise HTTPException(422, 'Expected an active fixture and valid seat')
    return {'library': match.state.players[seat].library}


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
