# Foretell Foundation

## Implemented Scope

Printed Foretell and the supported hand-wide grants share application-code
special actions, payments and durable exile permissions. The action needs
priority, normally on the acting player's turn; it does not use the stack and
can be taken while a split-second spell is on the stack. Casting is permitted
only on a later turn and still respects the selected face's ordinary timing.
Spell/activated-ability cost modifiers do not modify the special action.
Supported explicit Foretell modifiers use the live, unsuppressed battlefield.

The foretelling player, not automatically the owner, receives look and casting
permission. Saved records include the action's turn, order, cost options and
zone-change sequence. Permission survives removal of a granting source, but
does not follow a card leaving and returning to exile. Generic face-down exile
does not grant access. Human controllers receive authorized exile views; other
face-down identities remain hidden. Serialization of a finished game reveals
foretold identities; automatic BO3 transition visibility still needs acceptance.
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

## Final Validation

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

- [ ] Foretold conditional/additional spell effects and tactical X valuation.
- [ ] Effect-created Foretell permissions, including selected-hand and self-exile effects.
- [ ] Broader exile and cast-from-exile reward triggers and interacting replacements.
- [ ] Complete browser later-turn casting, countering, restart and face-choice series.
- [ ] Verify mandatory reveal survives automatic BO3 transitions and saved game history.
- [ ] Authoritative look-permitted face-down costs in wider AI resource/curve planning.
- [ ] Multi-turn/opponent-response planning and measured before/after decision quality.

Unimplemented clauses containing Foretell/foretold remain explicit
`foretell-related effect fidelity` diagnostics. A recognized keyword or modifier
does not certify its complete card; other existing unsupported-clause reports
still apply. This is a foundation milestone, not completion of all Foretell cards.
