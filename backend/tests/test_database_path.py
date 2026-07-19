from pathlib import Path

from persistence.db import DATABASE_PATH, engine


def test_sqlite_cache_path_is_stable_when_launched_from_any_directory() -> None:
    expected = Path(__file__).resolve().parents[1] / "mtg_lab.db"

    assert DATABASE_PATH == expected
    assert Path(engine.url.database).resolve() == expected
