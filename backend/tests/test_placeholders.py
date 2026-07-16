from __future__ import annotations

from pathlib import Path

from card_data.placeholders import CACHE_DIR, ensure_placeholder_image


def test_placeholder_image_is_name_specific_and_written_to_disk() -> None:
    uri_a = ensure_placeholder_image("White Soldier", "Token Creature", token=True)
    uri_b = ensure_placeholder_image("Blue Spirit", "Token Creature", token=True)

    assert uri_a != uri_b
    assert uri_a.startswith("/card-images/")
    assert uri_b.startswith("/card-images/")

    path_a = CACHE_DIR / Path(uri_a).name
    path_b = CACHE_DIR / Path(uri_b).name
    assert path_a.exists()
    assert path_b.exists()

    svg = path_a.read_text(encoding="utf-8")
    assert "White Soldier" in svg
    assert "Token Creature" in svg
