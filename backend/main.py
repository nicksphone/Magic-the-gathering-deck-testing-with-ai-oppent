from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.schemas import AIDiagnosticsRequest, BatchSimulationRequest
from analytics.service import AnalyticsService
from card_data.fallback_cards import fallback_card_payload
from card_data.service import CardService
from card_data.sync import CACHE_DIR, ScryfallSyncService
from decks.builtin_decks import BUILTIN_DECKS
from decks.sideboard import SideboardError, apply_sideboard_swaps
from decks.service import DeckService
from game_state.serializers import serialize_match
from game_state.state import MatchFactory, Step
from persistence.db import engine, get_session, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine

app = FastAPI(title="MTG Deck Testing Lab API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/card-images", StaticFiles(directory=str(CACHE_DIR)), name="card-images")


@dataclass
class MatchController:
    state: object
    rules: RulesEngine
    controllers: dict[int, str]
    ai: dict[int, AIAgent]
    mode: str
    deck_ids: tuple[int | None, int | None]
    mainboards: dict[int, list[dict]]
    sideboards: dict[int, list[dict]]
    game_number: int
    current_game_recorded: bool
    match_complete: bool
    best_of: int


ACTIVE_MATCHES: dict[str, MatchController] = {}


class DeckImportRequest(BaseModel):
    name: str
    deck_text: str
    source: str = "user"


class StartMatchRequest(BaseModel):
    deck_a: list[dict]
    deck_b: list[dict]
    deck_a_sideboard: list[dict] = []
    deck_b_sideboard: list[dict] = []
    deck_a_id: int | None = None
    deck_b_id: int | None = None
    controller_a: Literal["human", "ai"] = "human"
    controller_b: Literal["human", "ai"] = "ai"
    ai_difficulty: str = "master"
    mode: Literal["player_vs_ai", "ai_vs_ai", "human_vs_human"] = "player_vs_ai"
    best_of: int = Field(default=3, ge=3, le=15)

    @field_validator("best_of")
    @classmethod
    def validate_best_of_odd(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("best_of must be an odd number")
        return value


class ActionRequest(BaseModel):
    player_id: int
    action: dict


class SideboardRequest(BaseModel):
    player_id: int
    cards_out: list[dict]
    cards_in: list[dict]


class PriorityStopsRequest(BaseModel):
    player_id: int
    stops: list[str] = []


class BulkSyncRequest(BaseModel):
    names: list[str] = []
    include_builtins: bool = True
    include_saved_decks: bool = True
    limit: int = 300


def get_repo(session: Session = Depends(get_session)) -> Repository:
    return Repository(session)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with Session(engine) as session:
        _ensure_builtin_decks(Repository(session))


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/cards/sync")
def sync_card(name: str, repo: Repository = Depends(get_repo)) -> dict:
    return ScryfallSyncService(repo).sync_card_by_name(name)


@app.post("/cards/sync-bulk")
def sync_cards_bulk(payload: BulkSyncRequest, repo: Repository = Depends(get_repo)) -> dict:
    names = {n.strip() for n in payload.names if n.strip()}
    if payload.include_builtins:
        service = DeckService(repo)
        for deck_name in service.list_builtins():
            parsed = service.parser.parse(service.get_builtin_text(deck_name))
            for item in parsed.mainboard + parsed.sideboard:
                names.add(item["card_name"])
    if payload.include_saved_decks:
        for row in repo.list_decks():
            for item in json.loads(row.mainboard_json) + json.loads(row.sideboard_json):
                names.add(item["card_name"])

    sync = ScryfallSyncService(repo)
    ok: list[str] = []
    failed: list[dict] = []
    for name in sorted(names)[: max(1, payload.limit)]:
        try:
            sync.sync_card_by_name(name)
            ok.append(name)
        except Exception as exc:
            failed.append({"name": name, "error": str(exc)})
    return {"requested": len(names), "synced": len(ok), "failed": failed[:50], "sample_synced": ok[:20]}


@app.get("/cards")
def list_cards(repo: Repository = Depends(get_repo)) -> list[dict]:
    return CardService(repo).list_cards()


@app.get("/cards/suggest")
def suggest_card(name: str, repo: Repository = Depends(get_repo)) -> dict:
    return CardService(repo).suggest_name(name)


@app.get("/decks/builtin")
def builtin_decks() -> list[str]:
    return sorted(BUILTIN_DECKS.keys())


@app.get("/decks/builtin/{name}")
def builtin_deck_text(name: str) -> dict:
    if name not in BUILTIN_DECKS:
        raise HTTPException(status_code=404, detail="Deck not found")
    return {"name": name, "deck_text": BUILTIN_DECKS[name]}


@app.post("/decks/import")
def import_deck(payload: DeckImportRequest, repo: Repository = Depends(get_repo)) -> dict:
    return DeckService(repo).import_deck_text(payload.name, payload.deck_text, payload.source)


@app.post("/decks/import-file")
async def import_deck_file(name: str, file: UploadFile = File(...), repo: Repository = Depends(get_repo)) -> dict:
    raw = (await file.read()).decode("utf-8")
    return DeckService(repo).import_deck_text(name, raw, "file")


@app.get("/decks")
def list_decks(repo: Repository = Depends(get_repo)) -> list[dict]:
    rows = repo.list_decks()
    out = []
    for row in rows:
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "source": row.source,
                "archetype_guess": row.archetype_guess,
                "mainboard": json.loads(row.mainboard_json),
                "sideboard": json.loads(row.sideboard_json),
                "created_at": row.created_at,
            }
        )
    return out


@app.post("/matches/start")
def start_match(payload: StartMatchRequest, repo: Repository = Depends(get_repo)) -> dict:
    deck_a = _hydrate_deck_cards(repo, payload.deck_a)
    deck_b = _hydrate_deck_cards(repo, payload.deck_b)
    state = MatchFactory.from_decks(deck_a, deck_b)
    state.best_of = payload.best_of
    rules = RulesEngine()
    a_ai = AIAgent(difficulty=payload.ai_difficulty, archetype=guess_archetype(payload.deck_a))
    b_ai = AIAgent(difficulty=payload.ai_difficulty, archetype=guess_archetype(payload.deck_b))
    controller = MatchController(
        state=state,
        rules=rules,
        controllers={1: payload.controller_a, 2: payload.controller_b},
        ai={1: a_ai, 2: b_ai},
        mode=payload.mode,
        deck_ids=(payload.deck_a_id, payload.deck_b_id),
        mainboards={1: deck_a, 2: deck_b},
        sideboards={1: payload.deck_a_sideboard, 2: payload.deck_b_sideboard},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=payload.best_of,
    )
    ACTIVE_MATCHES[state.id] = controller
    return _serialize_match_controller(controller)


@app.get("/matches/{match_id}")
def get_match(match_id: str) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return _serialize_match_controller(match)


@app.get("/matches/{match_id}/legal-moves")
def get_legal_moves(match_id: str, player_id: int | None = None) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    pid = player_id or _default_player_for_state(match)
    return {"player_id": pid, "moves": match.rules.legal_moves(match.state, pid)}


@app.post("/matches/{match_id}/action")
def take_action(match_id: str, payload: ActionRequest, repo: Repository = Depends(get_repo)) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match.rules.take_action(match.state, payload.player_id, payload.action)
    _post_step_finalize(match, repo)
    return _serialize_match_controller(match)


@app.post("/matches/{match_id}/autoplay")
def autoplay_tick(match_id: str, ticks: int = 1, repo: Repository = Depends(get_repo)) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    ticks = max(1, min(100, ticks))
    for _ in range(ticks):
        if match.match_complete:
            break
        if match.state.winner is not None:
            _post_step_finalize(match, repo)
            if match.match_complete:
                break
            if _is_full_ai_match(match):
                _start_next_game_state(match)
                continue
            break
        pid = _default_player_for_state(match)
        if match.controllers.get(pid) == "ai":
            legal = match.rules.legal_moves(match.state, pid)
            forced_land = _force_ai_land_action(match, pid, legal)
            if forced_land is not None:
                match.rules.take_action(match.state, pid, forced_land)
            else:
                decision = match.ai[pid].choose_action(match.state, legal, pid)
                action = decision.action
                # Strict backend invariant: on legal own-main land-drop windows,
                # override any non-land action to ensure deterministic land development.
                if action.get("type") != "play_land":
                    guard_land = _force_ai_land_action(match, pid, legal)
                    if guard_land is not None:
                        action = guard_land
                match.rules.take_action(match.state, pid, action)
        else:
            if match.state.pregame_pending:
                break
            if _human_priority_pause(match, pid):
                break
            match.rules.take_action(match.state, pid, {"type": "pass_priority"})
        if not match.state.pregame_pending and match.state.step == match.state.step.COMBAT_DAMAGE:
            match.rules.take_action(match.state, match.state.active_player, {"type": "combat_damage"})
    _post_step_finalize(match, repo)
    return _serialize_match_controller(match)


@app.post("/matches/{match_id}/priority-stops")
def set_priority_stops(match_id: str, payload: PriorityStopsRequest) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if payload.player_id not in [1, 2]:
        raise HTTPException(status_code=400, detail="Invalid player_id")
    valid = {s.value for s in Step}
    chosen = {s for s in payload.stops if s in valid}
    match.state.priority_stops[payload.player_id] = {Step(s) for s in chosen}
    match.state.log.append(
        f"{match.state.players[payload.player_id].name} priority stops updated: {', '.join(sorted(chosen)) or 'none'}."
    )
    return _serialize_match_controller(match)


@app.post("/matches/{match_id}/sideboard")
def apply_sideboard(match_id: str, payload: SideboardRequest, repo: Repository = Depends(get_repo)) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if payload.player_id not in [1, 2]:
        raise HTTPException(status_code=400, detail="Invalid player_id")
    if match.state.winner is None:
        raise HTTPException(status_code=400, detail="Current game still in progress.")
    try:
        next_main, next_side = apply_sideboard_swaps(
            match.mainboards[payload.player_id],
            match.sideboards[payload.player_id],
            payload.cards_out,
            payload.cards_in,
        )
    except SideboardError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    match.mainboards[payload.player_id] = _hydrate_deck_cards(repo, next_main)
    match.sideboards[payload.player_id] = next_side
    match.state.log.append(f"{match.state.players[payload.player_id].name} sideboarded for next game.")
    return _serialize_match_controller(match)


@app.post("/matches/{match_id}/next-game")
def next_game(match_id: str) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.match_complete:
        raise HTTPException(status_code=400, detail="Match is complete.")
    if match.state.winner is None:
        raise HTTPException(status_code=400, detail="Current game not finished.")

    _start_next_game_state(match)
    return _serialize_match_controller(match)


@app.post("/simulate/batch")
def simulate_batch(payload: BatchSimulationRequest, repo: Repository = Depends(get_repo)) -> dict:
    return AnalyticsService(repo).run_batch(
        payload.deck_a,
        payload.deck_b,
        payload.matches,
        payload.difficulty,
        max_ticks=payload.max_ticks,
    )


@app.post("/ai/diagnostics")
def ai_diagnostics(payload: AIDiagnosticsRequest, repo: Repository = Depends(get_repo)) -> dict:
    rows = repo.list_decks()
    by_id = {row.id: row for row in rows}

    selected_rows = []
    if payload.deck_ids:
        for deck_id in payload.deck_ids:
            row = by_id.get(deck_id)
            if row is not None:
                selected_rows.append(row)
    else:
        builtins = [r for r in rows if (r.source or "").strip().lower() == "builtin"]
        others = [r for r in rows if (r.source or "").strip().lower() != "builtin"]
        if payload.include_builtins:
            selected_rows.extend(sorted(builtins, key=lambda r: r.name.lower()))
        selected_rows.extend(others)

    # De-duplicate while preserving order.
    seen: set[int] = set()
    dedup_rows = []
    for row in selected_rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        dedup_rows.append(row)
    selected_rows = dedup_rows[: payload.max_decks]

    if len(selected_rows) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 decks for diagnostics.")

    deck_pool = []
    for row in selected_rows:
        mainboard = _hydrate_deck_cards(repo, json.loads(row.mainboard_json))
        deck_pool.append({"id": row.id, "name": row.name, "mainboard": mainboard})

    return AnalyticsService(repo).run_ai_diagnostics(
        deck_pool=deck_pool,
        matches_per_pair=payload.matches_per_pair,
        difficulty=payload.difficulty,
        max_ticks=payload.max_ticks,
    )


@app.get("/analytics/history")
def analytics_history(repo: Repository = Depends(get_repo)) -> dict:
    return AnalyticsService(repo).aggregate_history()


def _post_step_finalize(match: MatchController, repo: Repository) -> None:
    state = match.state
    if state.winner is None or match.current_game_recorded:
        return
    p1 = state.players[1]
    p2 = state.players[2]
    state.log.append(
        "Game ended summary: "
        f"{p1.name} life={p1.life}, library={len(p1.library)}; "
        f"{p2.name} life={p2.life}, library={len(p2.library)}."
    )
    if state.winner in state.score:
        state.score[state.winner] += 1
    match.current_game_recorded = True
    winner_name = state.players[state.winner].name
    games_needed = (match.best_of // 2) + 1
    if state.score[state.winner] >= games_needed:
        match.match_complete = True
        state.log.append(f"Match complete. {winner_name} wins best-of-{match.best_of}.")
    deck_a_id, deck_b_id = match.deck_ids
    if deck_a_id and deck_b_id:
        repo.save_match(
            deck_a_id=deck_a_id,
            deck_b_id=deck_b_id,
            winner=winner_name,
            mode=match.mode,
            turns=state.turn,
            log=state.log,
        )


def _serialize_match_controller(match: MatchController) -> dict:
    payload = serialize_match(match.state)
    payload["mode"] = match.mode
    payload["controllers"] = {str(pid): controller for pid, controller in match.controllers.items()}
    payload["game_number"] = match.game_number
    payload["best_of"] = match.best_of
    payload["match_complete"] = match.match_complete
    payload["games_needed"] = (match.best_of // 2) + 1
    payload["sideboard_sizes"] = {
        "1": sum(x["quantity"] for x in match.sideboards.get(1, [])),
        "2": sum(x["quantity"] for x in match.sideboards.get(2, [])),
    }
    return payload


def _hydrate_deck_cards(repo: Repository | None, deck: list[dict]) -> list[dict]:
    names = [item["card_name"] for item in deck]
    cached = repo.get_cached_cards_by_names(names) if repo else {}
    if repo:
        missing = sorted({name for name in names if name.strip() and name.strip().lower() not in cached})
        if missing:
            sync = ScryfallSyncService(repo)
            for name in missing:
                try:
                    sync.sync_card_by_name(name)
                except Exception:
                    # Match start should still proceed if external sync is unavailable.
                    continue
            cached = repo.get_cached_cards_by_names(names)
    hydrated: list[dict] = []
    for item in deck:
        row = cached.get(item["card_name"].lower())
        out = dict(item)
        if row:
            out["oracle_text"] = row.oracle_text
            out["mana_cost"] = row.mana_cost
            out["type_line"] = row.type_line
            out["power"] = row.power
            out["toughness"] = row.toughness
            out["image_uri"] = row.image_uri
            loyalty = getattr(row, "loyalty", None)
            if loyalty is not None:
                out["loyalty"] = loyalty
        else:
            fallback = fallback_card_payload(item["card_name"])
            if fallback:
                out.update({k: v for k, v in fallback.items() if v is not None})
        hydrated.append(out)
    return hydrated


def _default_player_for_state(match: MatchController) -> int:
    if match.state.pregame_pending:
        for pid in [1, 2]:
            if pid not in match.state.kept_hands:
                return pid
    return match.state.priority_player


def _is_full_ai_match(match: MatchController) -> bool:
    return match.controllers.get(1) == "ai" and match.controllers.get(2) == "ai"


def _start_next_game_state(match: MatchController) -> None:
    prior_log_tail = list(match.state.log[-80:])
    prior_id = match.state.id
    p1_name = match.state.players[1].name
    p2_name = match.state.players[2].name
    new_state = MatchFactory.from_decks(match.mainboards[1], match.mainboards[2], player_a_name=p1_name, player_b_name=p2_name)
    new_state.id = prior_id
    new_state.score = dict(match.state.score)
    new_state.best_of = match.best_of
    new_state.active_player = 1 if match.game_number % 2 == 1 else 2
    new_state.priority_player = new_state.active_player
    transition = f"--- Starting game {match.game_number + 1} ---"
    new_state.log = prior_log_tail + [transition] + new_state.log
    match.state = new_state
    match.game_number += 1
    match.current_game_recorded = False


def _ensure_builtin_decks(repo: Repository) -> None:
    existing = {
        (row.name.strip().lower(), (row.source or "").strip().lower())
        for row in repo.list_decks()
    }
    service = DeckService(repo)
    for name in sorted(BUILTIN_DECKS.keys()):
        key = (name.strip().lower(), "builtin")
        if key in existing:
            continue
        service.import_deck_text(name=name, deck_text=BUILTIN_DECKS[name], source="builtin")


def _human_priority_pause(match: MatchController, player_id: int) -> bool:
    state = match.state
    legal = match.rules.legal_moves(state, player_id)
    has_non_pass = any(m.get("type") != "pass_priority" for m in legal)
    has_land_play = any(m.get("type") == "play_land" for m in legal)
    step_stop = state.step in state.priority_stops.get(player_id, set())
    # Always pause on a legal land drop for human players so autoplay cannot skip
    # the primary main-phase development window.
    if has_land_play:
        return True
    if state.stack and has_non_pass:
        return True
    if step_stop and has_non_pass:
        return True
    return False


def _force_ai_land_action(match: MatchController, player_id: int, legal_moves: list[dict]) -> dict | None:
    state = match.state
    if state.pregame_pending or state.stack:
        return None
    if state.active_player != player_id:
        return None
    if state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}:
        return None
    if state.players[player_id].lands_played_this_turn >= 1:
        return None
    land_moves = [m for m in legal_moves if m.get("type") == "play_land"]
    if not land_moves:
        # Defensive fallback: if legal-move generation misses land actions,
        # derive them directly from hand card identities.
        player = state.players[player_id]
        for cid in list(player.hand):
            card = state.cards.get(cid)
            if card and _card_looks_like_land(card):
                land_moves.append({"type": "play_land", "card_id": cid})
    if not land_moves:
        return None
    # Let AI keep color-aware land selection by choosing among only play-land actions.
    # Hard-fallback to first legal play_land if AI returns a non-land action.
    picked = match.ai[player_id].choose_action(state, land_moves, player_id).action
    if picked.get("type") == "play_land":
        return picked
    return land_moves[0]


def _card_looks_like_land(card) -> bool:
    if "Land" in getattr(card, "types", []):
        return True
    type_line = (getattr(card, "type_line", "") or "").lower()
    if "land" in type_line:
        return True
    oracle = (getattr(card, "oracle_text", "") or "").lower()
    mana_cost = (getattr(card, "mana_cost", "") or "").strip()
    nonland_typed = any(
        t in set(getattr(card, "types", []))
        for t in ["Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker"]
    )
    if not mana_cost and not nonland_typed and (("{t}:" in oracle and "add {" in oracle) or "add one mana of any color" in oracle):
        return True
    name = (getattr(card, "name", "") or "").strip().lower()
    return any(basic in name for basic in ["island", "swamp", "mountain", "forest", "plains"])
