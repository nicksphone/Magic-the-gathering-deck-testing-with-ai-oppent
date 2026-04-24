from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./mtg_lab.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
