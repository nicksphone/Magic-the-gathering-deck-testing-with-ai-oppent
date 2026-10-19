from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator
import os

from sqlmodel import Session, SQLModel, create_engine

# Import so CardKnowledge is registered on SQLModel.metadata before create_all.
import knowledge.models  # noqa: F401

# Resolve the local cache from the backend package, not the process cwd. This
# keeps the API, sync jobs, and diagnostics on the same SQLite database.
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "mtg_lab.db"


def configured_database_path() -> Path:
    """Trusted operator-only relocation; never silently abandon a legacy database."""
    from persistence.job_retention import local_path

    configured = os.environ.get("MTG_DATABASE_PATH")
    if configured is None:
        return DEFAULT_DATABASE_PATH
    if not configured or configured != configured.strip():
        raise ValueError("MTG_DATABASE_PATH must be an explicit canonical local file")
    path = local_path(Path(configured), existing=Path(configured).exists())
    if path.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("MTG_DATABASE_PATH must be outside the source tree")
    if DEFAULT_DATABASE_PATH.exists() and not path.exists():
        raise ValueError("Legacy database exists; explicitly relocate and verify it before startup")
    return path


DATABASE_PATH = configured_database_path()
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    # Capacity initialization requires its explicit owner and verified backup.
    SQLModel.metadata.create_all(engine, tables=[table for table in SQLModel.metadata.sorted_tables
                                               if table.name not in {"resourcecapacity", "resourcereservation"}])
    _ensure_card_cache_columns()


def initialize_resource_capacity(owner, backup_path: Path) -> None:
    """Explicit backup-first bootstrap under registered lifetime ownership."""
    from persistence.capacity import initialize_capacity
    initialize_capacity(owner, backup_path)


def _ensure_card_cache_columns() -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(cardcache)").all()
        columns = {str(row[1]) for row in rows}
        if 'loyalty' not in columns:
            conn.exec_driver_sql('ALTER TABLE cardcache ADD COLUMN loyalty TEXT')
        if "layout" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN layout TEXT NOT NULL DEFAULT ''")
        if "card_faces_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN card_faces_json TEXT NOT NULL DEFAULT '[]'")
        if "rulings_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN rulings_json TEXT NOT NULL DEFAULT '[]'")


def get_session() -> Iterator[Session]:
    from persistence.capacity import owner_for_engine
    # FastAPI may enter/exit this generator in different threadpool threads.
    with owner_for_engine(engine).activity(threaded=False):
        with Session(engine) as session:
            yield session
