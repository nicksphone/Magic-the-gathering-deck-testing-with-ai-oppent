# Canonical Custom-Deck Training Bridge: Tests First

Status: implemented. The focused module passed 32 cases in 37.00 seconds with no unexpected denials,
equal source/runtime inputs and closed worker resources. The preceding functional
RED is 31 missing-bridge failures and one built-in control pass. Its single
prevented read-denial remains boundary-false; the first 32-pass run has the same
limitation. Both preserve an absent stdlib ZIP metadata-probe denial. A separate
final role admits only that exact verified-absent probe; SQL/socket/process and
source-write denials remain. Separately, both complete original environment/reset
modules passed all 69 cases in 96.03 seconds, with no failures, errors or skips.
That broader run used ordinary trusted pytest, not the focused role's audit
boundary or all-call profiling. Full source/runtime/system hashes, owned process
closure and the coordination-lock release were verified. The earlier 300-second
incomplete run remains historical. The dataset CLI has not run in this component.

Implemented interface:

```python
TrainingEnvironment.reset_from_decks(deck_a, deck_b, *, seed, sandbox=False)
```

`deck_a` and `deck_b` are detached hydrated `list[dict]` inputs, the same row
surface the application supplies to `MatchFactory.from_decks`. They are not
built-in names, raw API name-only requests or an implicit repository lookup.
Canonical intake remains the trusted caller's responsibility. Structural
readiness and content hashes are not authentication of arbitrary printed text.

Reuse `DeckPairInput` for the projected quantity/name fields and sandbox bound,
and the existing hydration readiness/playability checks for the full rows.
Quantity must remain a strict integer. Default sizes are 60-250; explicit
sandbox admits 1-250. This is not a new tournament-format legality validator.
The app preserves duplicate rows and Factory expands their summed quantities;
do not silently merge or otherwise normalize the original list before hashing.

Fixtures reuse `tests.browser_positive83_canonical.raw_card` and its full-object
pins. A read-only in-memory cache returns actual normalizer output to the real
`hydrate_deck_cards`; actual official image URIs avoid placeholder creation.
No ScryfallSyncService instance, Repository, database or HTTP client is created.
Selected parents include Grizzly Bears and both Valki/Tibalt faces; custom
composition and metadata are not restricted to the built-in deck-name registry.

Reset validates and detaches both lists before one real Factory
birth with the final deterministic game ID. Preserve explicit private-choice
flags and original stock capture; never retag or recapture after birth.
`metadata_source='validated_canonical_deck_rows'` distinguishes the new private
provenance. Preserve the exact built-in reset provenance and legacy snapshots.

The accepted narrow restore extension branches on origin, verifies engine,
initial-deck/content hashes, strict seed and episode identity, then stages the
native serializer round-trip before publishing. Use retained initial canonical
rows, never later library/hand/battlefield contents. Hashes retain the existing
trusted-local-snapshot boundary, not hostile-upload authentication.

Initial lists, seed and provenance stay out of observations, prompts and model
inputs. The tests use genuine accepted keep-hand transitions through the existing
dataset producer, plus both-seat hidden-world permutation controls. These do not
claim whole-card mechanics, a trained policy, expert play or measured strength.

Future bounded execution must keep source read-only, disable pytest bytecode and
cache writes, and place its log/temp/basetemp under the parent's owned evidence
root. Import closure includes hydration's Repository type/model definitions,
but no SQL operation is needed. Exact SQL/socket/process denial and source/FD/
thread closure belong to the separately granted runner, not these authored tests.
The focused and original-module executions above are separate cohorts, not a
single 101-case run. The original tests-first packet remains immutable. Graph
refresh is a separate post-test administrative source epoch.
