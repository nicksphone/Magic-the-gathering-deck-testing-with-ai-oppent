"""Explicit controlled-board construction/adoption, never repair captured facts."""
from copy import deepcopy
import random
import uuid

from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone, draw_card


def controlled_library_position(seat):
    """Start an uncertified board, retaining the old canonical Island/RNG setup."""
    from tests.extra_sequence_support import canonical
    from rules_engine.card_types import printed_card_types

    raw = canonical('Island')
    state = MatchState(id=str(uuid.uuid4()),
        players={1: PlayerState(1, 'Player A'), 2: PlayerState(2, 'Player B')},
        cards={}, stack=[], rng=random.Random(7214))
    deck = [{**raw, 'quantity': 60}]
    state.starting_decks = {1: deepcopy(deck), 2: deepcopy(deck)}
    for pid, player in state.players.items():
        # Preserve the two old seeded shuffles, physical IDs and opening-zone visits.
        state.rng.shuffle(list(range(60)))
        for index in range(1, 61):
            cid = f'p{pid}-{index:03d}'
            state.cards[cid] = CardInstance(id=cid, name=raw['card_name'], owner=pid,
                controller=pid, zone=Zone.LIBRARY, types=printed_card_types(raw['type_line']),
                mana_cost=raw.get('mana_cost', ''), oracle_text=raw.get('oracle_text', ''),
                type_line=raw['type_line'], image_uri=raw.get('image_uri'),
                instance_order=index, colors=raw.get('colors'), summoning_sick=False,
                layout=raw.get('layout', ''))
            player.library.append(cid)
    for pid in (1, 2):
        draw_card(state, pid, 7)
    state.log.append('Game start. Both players draw 7 and decide on London mulligans.')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {'W': 0, 'U': 10, 'B': 0, 'R': 10, 'G': 0, 'C': 10}
    return state


def adopt_fixture_state(controller, state, repo=None):
    """Keep the state's genuine identity; move the explicit HTTP fixture binding."""
    import main
    from game_state.serializers import serialize_match_snapshot
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session

    # Validate before touching the controller, registry or persistent rows.
    serialize_match_snapshot(state)
    old_id = controller.state.id
    if main.ACTIVE_MATCHES.get(old_id) is not controller:
        raise ValueError('Fixture controller is not registered')
    if state.id in main.ACTIVE_MATCHES and main.ACTIVE_MATCHES[state.id] is not controller:
        raise ValueError('Fixture identity already registered')

    def adopt(repository):
        controller.state = state
        main._persist_active_match(repository, controller)
        if old_id != state.id:
            repository.delete_active_match(old_id)
            del main.ACTIVE_MATCHES[old_id]
        main.ACTIVE_MATCHES[state.id] = controller

    if repo is None:
        with Session(engine) as session:
            adopt(Repository(session))
    else:
        adopt(repo)
    return controller
