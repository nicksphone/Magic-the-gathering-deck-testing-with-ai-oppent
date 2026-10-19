# Builtin First-Import Admission

`ensure_builtin_decks` uses the same local canonical admission for new and existing
builtins. Parsed names/quantities and sideboards are saved unchanged. Hydration
reads existing cache, canonical local knowledge, and the committed offline seed;
it neither syncs remote data nor materializes card-cache records. Generic
`DeckService.import_deck_text` and `/decks/import` remain unchanged.

A nonempty mainboard requires source provenance and `ready_for_match` for every
card. The actual analyzer must report full type coverage, positive confidence,
and no missing/partial/fallback signals before its primary archetype is stored.
No hand-assigned name label, neural-quality label, or execution certificate is
created. Provenance and analysis are available in hydrated facts/test evidence;
no new persistence fields or schema are introduced.

For a new builtin with insufficient facts, `archetype_guess` is explicitly
`unknown`. For an existing unresolved builtin, its stored label is preserved:
that field is historical metadata, not fresh admission evidence. Once complete
facts become available, the latest normalized builtin row alone can refresh its
label. Historical duplicates and user/file/custom rows, IDs, creation dates,
mainboard quantities, and sideboards are preserved under the existing template
refresh contract. Existing intentional template-inventory synchronization remains
unchanged; metadata-only fixtures verify all non-guess columns byte-for-byte.

New tests use actual committed Burn, Dimir Control, Ramp, Tribal and Tempo
fixtures with memory and fresh local-file SQL. Coverage includes initially empty
cache with offline canonical facts, complete canonical cache with offline fallback
disabled, truly absent facts, missing cards/Oracle text/power/faces, zero-confidence
admission, recovery, latest-only refresh and idempotence. No fabricated cards.

Actual `/decks` reads and `/matches/start` consumers use an isolated dependency
override without application startup or listening sockets. The established strict
HTTP contract forwards original AI construction/decisions, checks actor-private
views, checked-action legality and full-root immutability, and restores persisted
state/configuration. Stored labels now agree at first bootstrap with available
canonical analysis. This fixes metadata timing, not AI policy or strategy strength;
production match construction independently resolves its own archetype.

Earlier frozen tests deliberately witnessed first-pass `Midrange`. Their assertion
updates are returned as a separate review proposal, not silently edited. Missing
facts must not turn into concrete archetypes, and existing stored labels need not
become `unknown` merely because facts are temporarily unavailable.
