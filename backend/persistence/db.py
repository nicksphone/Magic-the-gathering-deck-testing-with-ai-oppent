from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Resolve the local cache from the backend package, not the process cwd. This
# keeps the API, sync jobs, and diagnostics on the same SQLite database.
DATABASE_PATH = Path(__file__).resolve().parents[1] / "mtg_lab.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_card_cache_columns()


def _ensure_card_cache_columns() -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(cardcache)").all()
        columns = {str(row[1]) for row in rows}
        if "card_faces_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN card_faces_json TEXT NOT NULL DEFAULT '[]'")
        if "rulings_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN rulings_json TEXT NOT NULL DEFAULT '[]'")


def get_session() -> Session:
    return Session(engine)
