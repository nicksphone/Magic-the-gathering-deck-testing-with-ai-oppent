from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from ai.log_priors import build_priors_from_logs, load_log_priors, save_log_priors
from analytics.schemas import AIDiagnosticsRequest, BatchSimulationRequest
from analytics.service import AnalyticsService
from card_data.fallback_cards import fallback_card_payload
from card_data.placeholders import ensure_placeholder_image
from card_data.service import CardService
from card_data.sync import CACHE_DIR, ScryfallSyncService
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from decks.sideboard import SideboardError, apply_sideboard_swaps
from decks.service import DeckService
from data_ingest.service import TournamentIngestService
from game_state.serializers import serialize_match
from game_state.state import MatchFactory, Step
from persistence.db import engine, get_session, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from rules_engine.land_rules import compute_max_land_plays_this_turn

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        _ensure_builtin_decks(repo)
        _ensure_expansion_top_decks(repo)
    yield

app = FastAPI(title="MTG Deck Testing Lab API", version="0.1.0", lifespan=lifespan)
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
SIM_JOBS: dict[str, dict] = {}
SIM_JOBS_LOCK = threading.Lock()


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
    seed: int | None = None

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
    include_expansion_top_decks: bool = True
    include_saved_decks: bool = True
    limit: int = 300


class TournamentIngestRequest(BaseModel):
    payload: dict


class BatchSimulationJobStartResponse(BaseModel):
    job_id: str
    status: str


class BatchSimulationJobStatusResponse(BaseModel):
    job_id: str
    status: str
    completed_matches: int
    total_matches: int
    started_at: float
    finished_at: float | None = None
    error: str | None = None
    result: dict | None = None


def get_repo(session: Session = Depends(get_session)) -> Repository:
    return Repository(session)





@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/cards/sync")
def sync_card(name: str, repo: Repository = Depends(get_repo)) -> dict:
    return ScryfallSyncService(repo).sync_card_by_name(name)


@app.post("/cards/sync-bulk")
def sync_cards_bulk(payload: BulkSyncRequest, repo: Repository = Depends(get_repo)) -> dict:
    names = {n.strip() for n in payload.names if n.strip()}
    service = DeckService(repo)
    if payload.include_builtins:
        for deck_name in service.list_builtins():
            parsed = service.parser.parse(service.get_builtin_text(deck_name))
            for item in parsed.mainboard + parsed.sideboard:
                names.add(item["card_name"])
    if payload.include_expansion_top_decks:
        for item in service.list_expansion_top_decks():
            deck = service.get_expansion_top_deck(item["code"])
            parsed = service.parser.parse(deck["deck_text"])
            for card in parsed.mainboard + parsed.sideboard:
                names.add(card["card_name"])
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


@app.get("/decks/expansion-top")
def list_expansion_top_decks(repo: Repository = Depends(get_repo)) -> list[dict]:
    return DeckService(repo).list_expansion_top_decks()


@app.get("/decks/expansion-top/{code}")
def get_expansion_top_deck(code: str, repo: Repository = Depends(get_repo)) -> dict:
    service = DeckService(repo)
    try:
        item = service.get_expansion_top_deck(code)
    except KeyError:
        raise HTTPException(status_code=404, detail="Expansion top deck not found") from None
    return {
        "code": item["code"],
        "expansion": item["expansion"],
        "release_year": item["release_year"],
        "name": item["deck_name"],
        "archetype": item["archetype"],
        "deck_text": item["deck_text"],
    }


@app.post("/decks/expansion-top/{code}/import")
def import_expansion_top_deck(code: str, repo: Repository = Depends(get_repo)) -> dict:
    service = DeckService(repo)
    try:
        return service.import_expansion_top_deck(code)
    except KeyError:
        raise HTTPException(status_code=404, detail="Expansion top deck not found") from None


@app.post("/decks/expansion-top/import-all")
def import_all_expansion_top_decks(repo: Repository = Depends(get_repo)) -> dict:
    service = DeckService(repo)
    results = service.import_all_expansion_top_decks()
    imported = [r for r in results if r.get("deck_id")]
    errors = [r for r in results if r.get("errors")]
    return {
        "requested": len(results),
        "imported": len(imported),
        "with_errors": len(errors),
    }


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
    latest_by_key: dict[tuple[str, str], object] = {}
    for row in rows:
        key = ((row.name or "").strip().lower(), (row.source or "").strip().lower())
        if key not in latest_by_key:
            latest_by_key[key] = row
    out = []
    for row in latest_by_key.values():
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


@app.post("/ingest/tournaments/import-json")
def ingest_tournament_json(payload: TournamentIngestRequest, repo: Repository = Depends(get_repo)) -> dict:
    try:
        return TournamentIngestService(repo).ingest_event_payload(payload.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ingest/tournaments/events")
def list_tournament_events(limit: int = 50, repo: Repository = Depends(get_repo)) -> list[dict]:
    rows = repo.list_tournament_events(limit=max(1, min(limit, 500)))
    return [
        {
            "id": r.id,
            "external_id": r.external_id,
            "source": r.source,
            "name": r.name,
            "format": r.format,
            "event_date": r.event_date,
            "url": r.url,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.get("/ingest/tournaments/events/{event_id}/summary")
def tournament_event_summary(event_id: int, repo: Repository = Depends(get_repo)) -> dict:
    return TournamentIngestService(repo).summarize_event(event_id)


@app.post("/matches/start")
def start_match(payload: StartMatchRequest, repo: Repository = Depends(get_repo)) -> dict:
    deck_a = _hydrate_deck_cards(repo, payload.deck_a)
    deck_b = _hydrate_deck_cards(repo, payload.deck_b)
    state = MatchFactory.from_decks(deck_a, deck_b, seed=payload.seed)
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


@app.get("/matches/{match_id}/replay")
def get_match_replay(match_id: str) -> dict:
    match = ACTIVE_MATCHES.get(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    entries: list[dict] = []
    current_turn = 1
    for idx, line in enumerate(match.state.log):
        if line.startswith("Turn ") and line.endswith("."):
            try:
                current_turn = int(line.split()[1].strip("."))
            except Exception:
                pass
        entries.append({"index": idx, "turn": current_turn, "line": line})
    return {
        "match_id": match_id,
        "game_number": match.game_number,
        "winner": match.state.winner,
        "entries": entries,
    }


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
                # Safety: if AI returns an action not in legal moves, treat as pass
                legal_types = {m["type"] for m in legal}
                if action.get("type") not in legal_types:
                    action = {"type": "pass_priority"}
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


@app.post("/simulate/batch/start", response_model=BatchSimulationJobStartResponse)
def simulate_batch_start(payload: BatchSimulationRequest, repo: Repository = Depends(get_repo)) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "completed_matches": 0,
        "total_matches": int(payload.matches),
        "started_at": time.time(),
        "finished_at": None,
        "error": None,
        "result": None,
    }
    with SIM_JOBS_LOCK:
        SIM_JOBS[job_id] = job

    def _runner() -> None:
        with SIM_JOBS_LOCK:
            if job_id in SIM_JOBS:
                SIM_JOBS[job_id]["status"] = "running"
        try:
            with Session(engine) as session:
                thread_repo = Repository(session)
                def _progress(done: int, total: int) -> None:
                    with SIM_JOBS_LOCK:
                        if job_id in SIM_JOBS:
                            SIM_JOBS[job_id]["completed_matches"] = int(done)
                            SIM_JOBS[job_id]["total_matches"] = int(total)

                result = AnalyticsService(thread_repo).run_batch(
                    payload.deck_a,
                    payload.deck_b,
                    payload.matches,
                    payload.difficulty,
                    max_ticks=payload.max_ticks,
                    progress_callback=_progress,
                )
            with SIM_JOBS_LOCK:
                if job_id in SIM_JOBS:
                    SIM_JOBS[job_id]["status"] = "completed"
                    SIM_JOBS[job_id]["completed_matches"] = int(payload.matches)
                    SIM_JOBS[job_id]["finished_at"] = time.time()
                    SIM_JOBS[job_id]["result"] = result
        except Exception as exc:
            with SIM_JOBS_LOCK:
                if job_id in SIM_JOBS:
                    SIM_JOBS[job_id]["status"] = "failed"
                    SIM_JOBS[job_id]["finished_at"] = time.time()
                    SIM_JOBS[job_id]["error"] = str(exc)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/simulate/batch/{job_id}", response_model=BatchSimulationJobStatusResponse)
def simulate_batch_status(job_id: str) -> dict:
    with SIM_JOBS_LOCK:
        job = SIM_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Simulation job not found")
        return dict(job)


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


@app.get("/ai/priors")
def get_ai_priors() -> dict:
    return load_log_priors()


@app.post("/ai/priors/rebuild")
def rebuild_ai_priors(repo: Repository = Depends(get_repo)) -> dict:
    logs: list[list[str]] = []
    for match in repo.list_matches():
        try:
            decoded = json.loads(match.log_json)
        except Exception:
            continue
        if isinstance(decoded, list) and decoded:
            logs.append([str(x) for x in decoded])
    training_root = Path(__file__).resolve().parent / "training_runs"
    if training_root.exists():
        for p in training_root.rglob("*.jsonl"):
            if "games" not in p.name and "all_games" not in p.name and "anomaly_games" not in p.name:
                continue
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for raw in lines:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                log = row.get("log")
                if isinstance(log, list) and log:
                    logs.append([str(x) for x in log])
    payload = build_priors_from_logs(logs)
    saved = save_log_priors(payload)
    AIAgent._log_priors_cache = saved
    return {
        "generated_at": saved.get("generated_at"),
        "games": saved.get("samples", {}).get("games", 0),
        "logs": saved.get("samples", {}).get("logs", 0),
        "cards": len(saved.get("cards", {})),
    }


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
        stale = sorted(
            {
                row.name
                for row in cached.values()
                if not (getattr(row, "image_uri", None) and getattr(row, "mana_cost", None) is not None and getattr(row, "type_line", None))
            }
        )
        to_sync = sorted(set(missing + stale))
        if to_sync:
            sync = ScryfallSyncService(repo)
            for name in to_sync:
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
        if not out.get("image_uri"):
            out["image_uri"] = ensure_placeholder_image(
                name=str(out.get("card_name") or item.get("card_name") or "Card"),
                type_line=str(out.get("type_line") or ""),
                token=False,
            )
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


def _ensure_expansion_top_decks(repo: Repository) -> None:
    existing = {
        (row.name.strip().lower(), (row.source or "").strip().lower())
        for row in repo.list_decks()
    }
    service = DeckService(repo)
    for item in EXPANSION_TOP_DECKS:
        name = item["deck_name"]
        source = f"expansion_top:{item['code']}".lower()
        key = (name.strip().lower(), source)
        if key in existing:
            continue
        service.import_deck_text(name=name, deck_text=item["deck_text"], source=source)


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
    step_key = _step_key(state.step)
    if step_key not in {"precombat_main", "postcombat_main"}:
        return None
    player = state.players[player_id]
    max_land_plays = compute_max_land_plays_this_turn(state, player_id)
    if getattr(player, "last_land_play_turn", 0) == state.turn:
        used_land_plays = max(
            int(getattr(player, "lands_played_this_turn", 0)),
            int(getattr(player, "land_plays_recorded_on_turn", 0)),
        )
    else:
        used_land_plays = 0
    if used_land_plays >= max_land_plays:
        return None
    land_moves = [m for m in legal_moves if m.get("type") == "play_land"]
    if not land_moves:
        # Defensive fallback: if legal-move generation misses land actions,
        # derive them directly from hand card identities.
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


def _step_key(step_obj) -> str:
    value = getattr(step_obj, "value", step_obj)
    raw = str(value or "").strip()
    if raw.startswith("Step."):
        raw = raw.split(".", 1)[1]
    return raw.lower()
