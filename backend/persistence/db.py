from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./mtg_lab.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_card_faces_column()


def _ensure_card_faces_column() -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(cardcache)").all()
        columns = {str(row[1]) for row in rows}
        if "card_faces_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE cardcache ADD COLUMN card_faces_json TEXT NOT NULL DEFAULT '[]'")


def get_session() -> Session:
    return Session(engine)
