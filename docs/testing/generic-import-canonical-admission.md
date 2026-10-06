# Generic Import Canonical Admission

`DeckService.import_deck_text` now classifies a read-only canonical hydration of
its parsed mainboard after existing local-knowledge materialization. It uses the
same admission predicate as qualified cold bootstrap/cohort: nonempty mainboard,
source provenance and readiness for every card, full type coverage, positive
actual analyzer confidence, and no missing/partial/fallback signals. The exact
actual primary archetype is used only when admitted; otherwise the new stored
and returned guess is explicitly `unknown`. Diagnostic analysis remains actual,
including positive partial estimates or the analyzer's zero-confidence fallback.
No invented card, named-deck classifier, model quality label or score-weight change.

Existing parsed quantities/sideboards, parser errors, images, cache-display
`resolved_mainboard_cards`/`resolved_sideboard_cards`, mana curve and color profile
are unchanged. Existing ordinary user import history remains append-only; catalog
source-upsert behavior/IDs are unchanged. No repository/schema/migration is needed.
Existing canonical local materialization remains local; no network sync is added.

Optional additive response fields:
- `classification_status`: `resolved` or `unknown` for mainboard metadata admission.
- `classification_provenance`: actual analyzer and facts method, admission contract
  `complete-local-canonical-v1`, source kinds, canonical resolved-mainboard SHA256,
  and per-card source/readiness facts.

`analysis` now refers to the canonical facts identified by this provenance, not
necessarily the cache-display records. A cold offline import can classify Burn
correctly while the preserved cache-display/curve still shows missing entries.
Consumers must not treat those different representations as the same source.
The provenance hash uses deterministic sorted JSON and is recomputable from the
shared canonical hydrator. It includes actual normalized facts, not a fabricated
source verification or rules-engine execution certificate.

Admission does not certify deck legality, complete mechanics execution or sideboard
readiness. Existing parser errors still prevent persistence; known four-card
facts may be classified diagnostically while the minimum-size error blocks import.
Sideboard display/validation remain their existing independent contract. Existing
`/decks/analyze` and `/matches/start` readiness gates remain untouched and reject
missing/partial data with `card_data_unavailable`. Runtime AI style still derives
from resolved facts, never a newly forced stored guess.

NEW ordinary desired tests use real canonical Burn/Dimir Control, actual catalog
sideboard text, memory/file SQL, source-only API tests without lifespan/sockets,
missing/partial facts and injected unknown-admission results. They preserve old
row columns/IDs and legacy display fields, prove fresh runtime profile parity,
and execute original AI decisions with private views, checked-action legality,
full-root immutability and persisted restart equality.

The unchanged 24-case audit is a frozen pre-fix characterization, not silently
rewritten as a desired feature gate. Its fallback/cache-analysis assertions have
expected post-fix transitions. New desired tests prove the intended replacement
contracts; original audit bytes and baseline observations remain archived.

Only `backend/decks/service.py` is changed in product source. No AI, main/API,
training, parser, repository, cold-bootstrap, cohort, token/trigger/spell-surface
or frontend product edits. A future shared helper may avoid predicate drift,
but this patch does not broaden ownership or create a service-to-bootstrap cycle.
