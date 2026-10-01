# Linked Exile Return Entry

## Implemented Scope

Supported source-incarnation-linked exile returns now prepare entry counters and
chapter choices before moving any returning card onto the battlefield. Each
recipient uses its owner's controller context, including existing counter
modifiers. Mixed-owner counter batches and mixed-owner land batches choose in
active-player/nonactive-player order. Two-life land-entry payments reserve life
separately for each owner, not across the whole batch.

Expired links transfer into a durable choice packet. Snapshot restore preserves
the remaining recipients, their exile incarnations, choices and prepared counter
amounts. Commit rechecks exile identity and excludes departed tokens. A return
to hand does not receive battlefield counters or chapter choices. All battlefield
recipients are installed before prepared counters and grouped entry events are
published; incoming global counter bans do not retroactively affect that event.

The shared entry batch retains both the current recipient's controller and the
original completion controller. State-based actions stop if a linked return
creates a mechanic or replacement choice, including when the source dies in an
SBA wave. Further SBA/trigger publication resumes through the normal choice path.

These boundaries follow [Wizards Comprehensive Rules 101.4, 610.3, 614.12,
616.1 and 704](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
Canonical existing card fixtures are reused; test return records are explicitly
labeled core engine operations, not new card definitions.

## Validation

The regression suite covers mixed owners, affected-player counter ordering,
snapshot resume, Read Ahead, owner-versus-stolen-controller scope, two-life land
choices, hand returns, incoming Solemnity, stale exile incarnations and source
death during SBA. The browser fixture exercises both seats' counter decisions
through the real UI/API and checks that neither planeswalker enters early.

Completed evidence is stored on RCHFiles in project diagnostics
`linked-entry-counters/`. Earlier failed fixture/launcher checks are retained
separately from final validation, not presented as passing tests.

Final validation: **2,423 backend tests passed**, with 292 existing deprecation
warnings, in an isolated tracked-source checkout with its own initially empty
database/cache. Frontend lint, boundary unit tests and TypeScript/Vite build
passed. Full Chromium validation passed the mixed-owner fixture, existing human
actions, recovery/restart, simulator preflight, sideboarding and natural BO3
flows. The replay runner completed five seat-balanced games across two BO3
series and their repeated executions with zero determinism failures; its decks
were the existing Aetherdrift/Foundations archetype templates, not tournament
lists. This is a repeatability smoke, not decision-quality or balance evidence.
Graphify's AST refresh completed with 7,503 nodes and 18,785 edges. Modified
backend source and fixtures matched the final tested copy byte-for-byte.

## Known Limitations and Next Upgrades

Supported [transformed returns](transformed-entry.md) now share projected entry
preparation; special opening entries remain disconnected. General replacement-choice ordering across different entry
families, arbitrary intrinsic entry clauses, Aura attachment on noncast entry,
conditional replacement semantics and general continuous/copy projection remain
open. These tests establish supported return paths, not all card mechanics,
professional AI strength or matchup balance.
