"""Pinned real-card sources shared by the bounded metadata audit only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory
from game_state.serializers import serialize_match_snapshot
from rules_engine.card_faces import select_cast_face
from rules_engine.colors import card_color_symbols

FAMILIES = [('Brutal Cathar','queued_sequence','Brutal Cathar // Moonrage Brute','Plains'),
            ('Delver of Secrets','human_transform_audit','Delver of Secrets // Insectile Aberration','Island')]
MODES = ['seed','knowledge','cache','partial_cache']


def raw_card(family):
    name,folder,key,land=family
    path=Path(__file__).parent/'fixtures'/folder/'canonical.json'
    pin=json.loads(path.with_name('provenance.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['canonical_sha256']
    raw=json.loads(path.read_text())[key]
    assert raw['object']=='card' and raw['layout']=='transform' and len(raw['card_faces'])==2
    return raw


def board(family):
    return [{'card_name':family[0],'quantity':4},{'card_name':family[3],'quantity':56}]


def setup(repo,family,mode):
    raw=raw_card(family)
    if mode=='knowledge':
        repo.upsert_card_knowledge({'name':raw['name'],'scryfall_id':raw['id'],'oracle_source':'scryfall',
          'profiles':{'schema_version':1,'card_data':raw,'rulings_verified':False,'rulings':[]}})
    if mode in {'cache','partial_cache'}:
        payload=ScryfallSyncService._normalize_payload(raw,ScryfallSyncService._extract_remote_image_uri(raw))
        if mode=='partial_cache':
            payload={**payload,'oracle_text':'','card_faces_json':'[]','colors':'','image_uri':None}
        repo.upsert_card(payload)
    return raw


def projection(facts,family,seat):
    state=MatchFactory.from_decks(facts,facts,seed=8128)
    card=next(c for c in state.cards.values() if c.owner==seat and c.card_faces)
    before=deepcopy(serialize_match_snapshot(state))
    rows=[]
    for index in (0,1):
        face=select_cast_face(card,index)
        rows.append({'index':index,'name':face.name,'type_line':face.type_line,'oracle_text':face.oracle_text,
          'mana_cost':face.mana_cost,'power':face.power,'toughness':face.toughness,
          'printed_power':face.printed_power,'printed_toughness':face.printed_toughness,
          'image_uri':face.image_uri,'colors':sorted(card_color_symbols(face))})
    assert serialize_match_snapshot(state)==before
    return rows
