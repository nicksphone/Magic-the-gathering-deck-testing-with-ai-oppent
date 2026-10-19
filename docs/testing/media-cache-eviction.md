# Media Cache Eviction

This increment is over the frozen 4ebcd5f source archive, SHA256
05d5d42fb89efce8c7dd2c77ab6cfc51c78861b3ee1484de8236131bc71bd7f1.

Token memoization revalidates the local file before returning its URI. A missing
indexed token file falls back to the tracked generic token SVG; it is not
redownloaded or replaced with fake canonical art. The persistent index is not
rewritten by gameplay resolution.

Card display checks local root and face URIs before choosing them. If none is
available, presentation installs an explicitly labelled local placeholder.
Remote URI selection remains a pass-through, never an implicit fetch. Explicit
Scryfall synchronization and its uncached HTTP failures are unchanged.

These are resolver-access repairs, not a cache watcher or StaticFiles redirect.
An evicted URI returns 404 until the appropriate resolver is called. Existing
serialized matches retain stored image URIs: media resolution does not rewrite
game state, provenance, card inventory, receipts, or RNG state. Cache writes are
intentional disposable filesystem effects, not database writes.

The original packaging audit and its 87/1 terminal evidence remain immutable.
Its subprocesses explicitly test the pinned original archive, not this repair.
The new tests exercise the repaired source, both actor seats, actual HTTP media,
unchanged SQLite/game snapshots, repository restoration, and visible uncached
sync failure. The separate face-fixture proposal supplies file availability for
an old mocked face-selection unit case without changing its original assertion.
