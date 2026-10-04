# Foretell Foundation

## Implemented Scope

Printed Foretell and the supported hand-wide grants share application-code
special actions, payments and durable exile permissions. The action needs
priority, normally on the acting player's turn; it does not use the stack and
can be taken while a split-second spell is on the stack. Casting is permitted
only on a later turn and still respects the selected face's ordinary timing.
Spell/activated-ability cost modifiers do not modify the special action.
Supported explicit Foretell modifiers use the live, unsuppressed battlefield.

For the special action, the foretelling player, not automatically the owner,
receives look and casting permission. For an effect making a card foretold,
its owner receives that permission. Saved records include the origin, turn, order, cost options and
zone-change sequence. Permission survives removal of a granting source, but
does not follow a card leaving and returning to exile. Generic face-down exile
does not grant access. Human controllers receive authorized exile views; other
face-down identities remain hidden. Serialization of a finished game reveals
foretold identities. Mandatory game-end reveal events are persisted once and
retained through active-match restart, saved game history and BO3 transitions,
including reveals older than the bounded recent log tail.
Snapshots preserve the records and per-turn counters. Casting records provenance
without treating the special action as a spell cast.

Cosmos Charger reductions accumulate and allow actions on either player's turn;
Ranar's first-action reduction resets each turn. Dream Devourer and Bohn's
supported grants derive the alternative cost from the selected spell face,
preserving colored symbols and X. Self-buff Foretell rewards use ordinary stack
triggers and both battlefield-incarnation and zone-change checks.

Both human seats have a Foretell hand button driven by legal moves. All AI
archetypes share a conservative fallback: consider banking idle main-phase mana
only after choosing to pass, preserve currently affordable known interaction,
and compare actual payment projections. It does not replace a chosen play.
X-cost candidates are deliberately deferred pending tactical sizing.

## Canonical Evidence

`backend/tests/fixtures/foretell.json` preserves 58 canonical Scryfall records
from the complete `o:foretell` search (no next page), retrieved 2026-10-04.
Each record retains Scryfall and Oracle IDs and its source URI. Printed keyword
tests check identity, costs, permissions and privacy, not every card's effects.
The rules reference is the September 25, 2026 Comprehensive Rules, rule 702.143:
[official rules](https://magic.wizards.com/en/rules).

Focused validation: 601 checks, including the preceding public-mana regressions,
passed. Chromium exercised both human seats through the real HTTP special-action
route. Full-suite and replay results are recorded below; these
checks do not establish optimal play, universal rules support or matchup balance.

The final focused selection runs actual AI decisions across 14 archetypes,
three difficulties and both seats, and includes SQLite restoration: 319 checks
pass. A 100-call microbenchmark on a board of 20 irrelevant creatures preserves
identical costs and authoritative state while avoiding unnecessary layer work;
this is not an end-to-end search-latency benchmark.

Replay runs from different scratch database histories selected different
representative rosters. Treat them as separate repeatability smoke tests, not
paired strength/balance or performance evidence. Fixed manifests and cache
provenance remain a diagnostics acceptance item in `plan.md`.

## Foundation Validation (d4b3ecc)

- All 6,359 backend checks pass across four isolated source/database shards:
  1,499 + 1,820 + 1,611 + 1,429. All 280 test files were assigned exactly once.
- Frontend lint, runtime-contract/unit checks and production build pass.
- The complete Chromium human-action/choice/BO3 harness and both-seat Foretell
  controls pass against the final isolated API source.
- Six final-source seat-balanced BO1 samples, each executed twice, finish with
  no reported timeout, anomaly or determinism failure. Earlier 12-sample and
  six-sample runs are retained separately, not pooled as paired balance evidence.
- Graphify AST refresh uses zero API tokens. User services remain on
  `0.0.0.0:9999` and `0.0.0.0:5173` and respond successfully.

Evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/foretell/20261004-working/`.
Superseded failures and interrupted runs are preserved rather than counted as
passes. One mistakenly started live-root command was stopped after 55 AI checks;
the live SQLite database's modification time and size remained unchanged.
The final entire suite ran only in the isolated shards above. Cold browser
startup initially raced the API; a health-gated rerun passed. The slowest shard
took 855.49 seconds, including the existing Control/Ramp live BO3 gate; that
integration/search latency is still an open acceptance item, not fixed by the
small Foretell microbenchmark.

## Remaining Acceptance

- [x] Bounded conditional token creation and additional scry, target fizzle,
  copy/retarget behavior, selected alternative X payment and snapshot continuation.
- [x] Both-seat browser normal/foretold casting, X announcement and scry choices.
- [x] Mandatory reveal survives BO3 transitions, SQLite restoration and saved history.
- [ ] Other Foretold conditional/additional effects and tactical X valuation.
- [x] Bounded selected-hand and self-exile effect-created permissions (see below).
- [ ] Other effect-created Foretell clause families and general exile rewards.
- [ ] Broader exile and cast-from-exile reward triggers and interacting replacements.
- [ ] Complete browser later-turn casting, countering, restart and face-choice series.
- [ ] Authoritative look-permitted face-down costs in wider AI resource/curve planning.
- [ ] Multi-turn/opponent-response planning and measured before/after decision quality.

Unimplemented clauses containing Foretell/foretold remain explicit
`foretell-related effect fidelity` diagnostics. A recognized keyword or modifier
does not certify its complete card; other existing unsupported-clause reports
still apply. This is a foundation milestone, not completion of all Foretell cards.

## Conditional Effects Follow-Up

Two complete clause families compile both printed and foretold branches using
ordinary handlers: extra scry and X tokens instead of one token. Canonical
fixtures are Poison the Cup and Starnheim Unleashed. Unknown Foretell prefixes
remain diagnostic gaps even when followed by a recognized scry suffix. Printed
data remains unchanged. X=0 is a legal human announcement; each X in the selected
cost is paid. Generic X-count token parsing preserves token characteristics.

Spell copies retain X and chosen targets but do not inherit a prior card's
Foretell exile history. This implementation derives that distinction from
CR 702.143c and 707.10, rather than treating the copied alternative cost as
proof that the copy was a foretold card. Copies may retarget normally; an original
whose targets are all illegal does not perform its additional scry. References:
[official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
and [official Kaldheim release notes](https://magic.wizards.com/en/news/feature/kaldheim-release-notes-2021-01-22).

The cross-style checks cover action construction, not strategic choice to cast
now rather than hold. Conservative banking still defers printed X-cost cards;
other effect-created clause families and multi-turn/opponent-response planning remain open.
Follow-up evidence is stored separately from the foundation milestone under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/foretell-effects/20261004-working/`.

### Follow-Up Validation

- All 6,482 backend tests pass in four isolated final-source/database shards:
  1,498 + 1,243 + 1,944 + 1,797. All 281 test files were assigned exactly once;
  123 new checks include canonical conditional effects, copies, targeting,
  durable reveals and 84 alternative-X action-construction combinations.
- The focused final AI/kicker/allocation selection passes 218 tests. The new
  cross-style tests first reproduced 84 failures before the shared selected-cost
  correction; these failures are retained as evidence, not counted as passes.
- Frontend lint, runtime-contract/unit checks and production build pass. The
  complete Chromium human-action/choice/BO3 harness, foundation controls and
  both-seat conditional-effect flows pass against the final isolated API.
  Browser checks include explicit X=0/3 announcements, resulting token stats
  and keywords, target selection and scry confirmation.
- Six final-source seat-balanced BO1 samples, each executed twice, resolve with
  no reported anomaly, timeout or determinism failure. Selected decks are the
  Aetherdrift and Foundations Aggro templates and Duskmourn Tempo template.
  The fresh database has 63 deck rows and zero cached card rows: this is bundled
  offline-data repeatability evidence, not full synced-corpus validation or a
  balance sample. Deck inputs, cache metadata and source hashes are archived.
- The superseded source's full run and six-sample replay remain separate. The
  final slowest shard takes 873.55 seconds including Control/Ramp live BO3;
  wide-state search latency remains open rather than being hidden by a timeout.
- Temporary browser services are stopped; user LAN services remain available
  on `0.0.0.0:9999` and `0.0.0.0:5173`. Live SQLite size/modification time and
  the pre-existing untracked coder plan remain unchanged.

## Effect-Created Permissions Follow-Up

The engine recognizes complete draw/hand-exile and damage/self-exile clauses,
not arbitrary mentions of Foretell. Canonical Ethereal Valkyrie and The Foretold
Soldier exercise these two paths; recognition uses ordinary self references,
not card-name-specific gameplay branches. Other unrecognized clauses retain
unsupported-mechanic diagnostics.

These abilities trigger and use the stack, can be countered and respect printed
ability suppression. Draw replacement processing precedes the durable hand
selection. A failed empty-library draw does not end a resolving ability midway:
state-based loss is checked after its remaining selection/effects finish.
Positive noncombat damage emits a shared event after prevention; combat uses
the existing damage event. Self-exile checks the original object's incarnation,
and token disappearance follows ordinary state-based actions.

Effect-created permissions belong to the owner, not necessarily the trigger
controller, and do not increment special-action Foretell counters or trigger
"whenever you foretell" rewards. Hand-exile reductions preserve colored symbols
and use each selected spell face's mana cost. Printed and granted costs coexist.
Foretell alone does not allow a land face to be played; independent exile-play
permissions still work. Copied battlefield characteristics do not survive in
exile as a card's printed cost. Sources leaving later do not remove an already
created permission.

The shared casting path distinguishes no mana cost (unpayable) from an explicit
`{0}` (payable). Explicit free-cast permissions and supported alternative costs
are still available. Canonical Lotus Bloom, Memnite and Kolvori/Ringhart Crest
records supplement the existing Foretell, suppression and draw fixtures.

AI selection shares existing retention, removal/counter tags and payment reads
across all styles and difficulties. It favors useful cost savings while keeping
lands and affordable interaction when a spell can be exiled instead. It still
must select a land if only lands remain; this is a legal forced effect, not land
play. The heuristic does not establish optimal long-horizon valuation.

Rules grounding: CR 118.6, 702.143c/d and 704.3/704.5b in the
[2026-09-25 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
[Kaldheim release notes](https://magic.wizards.com/en/news/feature/kaldheim-release-notes-2021-01-22)
and [Doctor Who release notes](https://magic.wizards.com/en/news/feature/magic-the-gathering-doctor-who-release-notes).

Evidence archive for this follow-up:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/foretell-permissions/20261004-working/`.

### Permission Follow-Up Validation

- All 6,630 backend tests pass across four isolated database/source shards:
  2,155 + 1,866 + 1,242 + 1,367. All 282 test files are assigned exactly once.
  The 148 new cases include both seats, 84 style/difficulty combinations,
  prevention, suppression, countering, copies, ownership, modal costs,
  replacement-aware draw, invalid choices and HTTP/SQLite restoration.
- Initial failures and corrected retests are retained separately. The empty-
  library test initially expected loss during resolution rather than after it;
  three older priority tests depended on missing card metadata making spells
  free. Their fixtures now supply real costs, mana and targets. Rejected HTTP
  choices use the existing structured 422 contract, not a guessed 409 status.
- Frontend lint, runtime-contract/unit tests, production build and all 41 Chromium
  scripts pass. New both-seat flows use the real selection and priority controls.
  The first broad browser attempt used the wrong test API configuration; the
  corrected run explicitly points at the isolated fixture API, not the LAN service.
- Two seeds in both seat orders produce four BO1 samples, each executed twice
  with identical complete results/logs. Actual hand/action traces show 10 hand-
  created permissions and seven Soldier self-exile resolutions. No timeout or
  invalid-action/cost messages occur. The 13/22/24/38-turn games use deliberately
  land-heavy 60-card mechanic exercise lists, not tournament/balance baselines.
  Inputs, canonical fixture data, source hashes and full repeated traces are
  preserved. The ad-hoc runner's `created_choices` substring counter is not a
  semantic metric; the validated summary counts actual resolution messages.
- Production source hashes match across all four shards, browser API and replay.
  This reused installed dependencies, not a fresh-install release certification.
  The slowest shard takes 1,112.66 seconds including the live Control/Ramp BO3
  restart case; wide-state planning latency remains unresolved.
- The live SQLite size/mtime and pre-existing untracked coder plan are unchanged.
  Temporary services and scratch are removed only after verified NFS archival;
  the user's LAN services stay available on their existing ports.
