"""Complete official births; explicit unit poses never rewrite printed facts."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone

FIXTURES=Path(__file__).parent/'fixtures'
SOURCES_SHA='7490f45d3924dcdf8362e69e6cf74eb81a8cfbcbc8c6ab887bfc7ce2f166a618'
RUNTIME_POSE=frozenset({'id','owner','controller','zone','summoning_sick','entered_turn'})


def raw_card(name):
    data=(FIXTURES/'combat_assignment022/SOURCES.json').read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCES_SHA:
        raise ValueError('Combat fixture source pins changed')
    source=json.loads(data)[name]
    data=(FIXTURES/source['file']).read_bytes()
    if hashlib.sha256(data).hexdigest()!=source['file_sha256']:
        raise ValueError('Combat fixture full RAW changed')
    raw=json.loads(data.splitlines()[source['line']-1] if source['line'] else data)
    for key in source['steps']:raw=raw[key]
    digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if (digest!=source['object_sha256'] or raw.get('object')!='card' or raw.get('name')!=name
            or raw.get('id')!=source['id'] or raw.get('oracle_id')!=source['oracle_id']):
        raise ValueError('Combat fixture official identity changed')
    return raw


def canonical_entry(name,quantity):
    raw=raw_card(name)
    normalized=ScryfallSyncService._normalize_payload(raw,ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw,**normalized,'card_name':name,'quantity':quantity,
            'colors':raw['colors'],'card_faces':json.loads(normalized['card_faces_json'])}


def canonical_card(name,**pose):
    if pose.keys()-RUNTIME_POSE:
        raise ValueError('Only original runtime poses are allowed; no printed overrides')
    native=MatchFactory.from_decks([canonical_entry(name,8)],[],seed=0)
    card=next(card for card in native.cards.values() if card.zone==Zone.LIBRARY)
    # The existing synthetic battlefield/GY pose is separate from printed birth.
    return replace(card,**{'instance_order':0,'summoning_sick':True,**pose})
