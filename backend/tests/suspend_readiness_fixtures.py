"""Read-only canonical repository projection; no SQL or network transport."""
from copy import deepcopy
from types import SimpleNamespace

from card_data.sync import ScryfallSyncService
from tests.test_suspend_lifecycle import CARDS


class ReadonlyCanonicalRows:
    """Repository boundary double backed ONLY by unchanged hash-pinned raw rows."""
    def __init__(self, names):
        self.raw = {name: deepcopy(CARDS[name]) for name in names}
        self.cached = {}
        for name, raw in self.raw.items():
            image = ScryfallSyncService._extract_remote_image_uri(raw)
            normalized = ScryfallSyncService._normalize_payload(raw, image)
            self.cached[name.casefold()] = SimpleNamespace(id=None, **normalized)
    def get_cached_cards_by_names(self, names):
        return {name.casefold(): self.cached[name.casefold()] for name in names if name.casefold() in self.cached}
    def get_card_knowledge_by_names(self, names):
        return {}
