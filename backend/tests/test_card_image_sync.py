from __future__ import annotations

from card_data.sync import ScryfallSyncService


class _DummyRepo:
    pass


def test_extract_remote_image_uri_prefers_root_normal() -> None:
    service = ScryfallSyncService(_DummyRepo())
    raw = {"image_uris": {"normal": "https://img.example/root-normal.jpg", "png": "https://img.example/root.png"}}
    assert service._extract_remote_image_uri(raw) == "https://img.example/root-normal.jpg"


def test_extract_remote_image_uri_falls_back_to_face_images() -> None:
    service = ScryfallSyncService(_DummyRepo())
    raw = {
        "card_faces": [
            {"image_uris": {}},
            {"image_uris": {"png": "https://img.example/face2.png"}},
        ]
    }
    assert service._extract_remote_image_uri(raw) == "https://img.example/face2.png"

