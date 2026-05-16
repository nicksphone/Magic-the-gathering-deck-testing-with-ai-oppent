from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from ai.log_priors import build_priors_from_logs, save_log_priors
from persistence.db import engine
from persistence.repository import Repository


def _read_training_run_logs(root: Path) -> list[list[str]]:
    out: list[list[str]] = []
    if not root.exists():
        return out
    for path in root.rglob("*.jsonl"):
        if "games" not in path.name and "all_games" not in path.name and "anomaly_games" not in path.name:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
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
                out.append([str(x) for x in log])
    return out


def main() -> None:
    logs: list[list[str]] = []
    with Session(engine) as session:
        repo = Repository(session)
        for match in repo.list_matches():
            try:
                decoded = json.loads(match.log_json)
            except Exception:
                continue
            if isinstance(decoded, list) and decoded:
                logs.append([str(x) for x in decoded])
    logs.extend(_read_training_run_logs(Path(__file__).resolve().parents[1] / "training_runs"))
    payload = build_priors_from_logs(logs)
    saved = save_log_priors(payload)
    print(
        json.dumps(
            {
                "generated_at": saved.get("generated_at"),
                "games": saved.get("samples", {}).get("games", 0),
                "logs": saved.get("samples", {}).get("logs", 0),
                "cards": len(saved.get("cards", {})),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

