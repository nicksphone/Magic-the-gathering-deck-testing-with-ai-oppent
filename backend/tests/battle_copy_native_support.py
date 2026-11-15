"""Original printing readers and paid native Battle-copy/SBA acceptance."""
from collections import Counter
import hashlib,json
from pathlib import Path

import pytest

from game_state.state import MatchFactory,Step,Zone
from tests.test_conditional_graveyard_self_copy import position,row as existing_row,place,act,activate_copy,finish,copy_offer
from tests.stage_metadata import mark as _stage_metadata

BATTLE='Invasion of Zendikar // Awakened Skyclave'

def row(name,quantity):
    if name!=BATTLE:return existing_row(name,quantity)
    path=Path(__file__).resolve().parents[1]/'tests/fixtures/battle_full_printing/invasion-of-zendikar-mom-194.json'
    data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()=='1e49bb006e579e3a88052ab773f5974f761e4a8fedd6fda669768d92f2b82d74'
    card=json.loads(data)
    assert card['object']=='card' and card['name']==BATTLE and len(card)==60
    assert card['id']=='8fed056f-a8f5-41ec-a7d2-a80a238872d1'
    assert card['oracle_id']=='4b1874af-4ea5-4e22-a4d4-e718d75fe95e'
    return {**card,'card_name':name,'quantity':quantity}

def battle_position(seat):
    names=('Shifting Woodland',BATTLE,'Counterspell','Cultivate','Forest')
    counts=Counter(names);counts['Forest']+=60-sum(counts.values())
    deck=[row(name,quantity) for name,quantity in counts.items()]
    state=MatchFactory.from_decks(deck,deck,seed=71203)
    state.pregame_pending=False;state.kept_hands={1,2};state.turn=5
    state.active_player=state.priority_player=seat;state.step=Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY);player.library.append(cid)
        player.hand.clear();player.mana_pool={}
        player.lands_played_this_turn=player.land_plays_recorded_on_turn=1
        player.last_land_play_turn=state.turn
    source=place(state,seat,'Shifting Woodland',Zone.BATTLEFIELD)
    for _ in range(6):place(state,seat,'Forest',Zone.BATTLEFIELD)
    target=place(state,seat,BATTLE,Zone.GRAVEYARD)
    for name in ('Counterspell','Cultivate','Forest'):place(state,seat,name,Zone.GRAVEYARD)
    return state,source,target

def mark(label):
    _stage_metadata(label)











def paid_copy_without_entry_defense(seat):
    mark('original-canonical-Battle-reader-request-started')
    data=row(BATTLE,1)
    mark('original-canonical-Battle-reader-returned')
    assert data['object']=='card' and data['name']==BATTLE
    assert data['card_faces'][0]['type_line']=='Battle — Siege'
    assert data['card_faces'][0]['defense']=='3'
    state,source,target=battle_position(seat)
    mark('native-Battle-Factory-birth-and-graveyard-position-reached')
    assert state.cards[target].zone==Zone.GRAVEYARD and 'Battle' in state.cards[target].types
    assert len(copy_offer(state,seat,source))==1
    state=activate_copy(state,seat,source,target)
    mark('native-Battle-copy-cost-paid-and-ability-announced')
    state=finish(state)
    mark('native-Battle-copy-resolution-and-SBA-check-reached')
    copied=state.cards[source]
    if (copied.zone==Zone.BATTLEFIELD and copied.name=='Invasion of Zendikar'
            and copied.type_line=='Battle — Siege' and copied.counters.get('defense',0)==0):
        mark('paid-copy-is-zero-defense-Siege-still-on-battlefield')
    assert state.cards[source].zone==Zone.GRAVEYARD
    mark('copied-source-moved-to-graveyard')
    assert state.cards[source].name=='Shifting Woodland'
    mark('copied-source-restored-physical-name-in-graveyard')
    assert state.cards[target].zone==Zone.GRAVEYARD and target in state.players[seat].graveyard
    assert source in state.players[seat].graveyard and not state.stack and not state.pending_mechanic_choice
    mark('native-Battle-copy-zero-defense-SBA-acceptance-passed')
