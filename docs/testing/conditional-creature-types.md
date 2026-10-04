# Conditional Creature Types: Backend Acceptance

## Scope

A shared pure layer-four view handles complete self-only single-/two-color
conditional devotion type-removal clauses. Combat, targeting, continuous
selectors, costs, resources, AI and public views use effective battlefield types;
printed classification, copiable characteristics and snapshots remain separate.

Supported removal orders against timestamped object-bound animation and precedes
later ability loss. Creature subtypes are absent while Creature is absent and
return with that type. Noncreature combatants leave combat without automatically
rejoining; blocked attackers stay blocked and announced bands persist. Shared
life-loss counts cannot restore removed types from printed metadata.

Return/search/control entry paths track continuous control for all permanents,
so later animation or devotion cannot bypass summoning sickness. Simultaneous
sacrifices capture last-known types before devotion resources leave. Both-seat
HTTP legal hints, SQLite restoration, public stats, Humility ordering, resource
and control changes, animation expiry and actual UI casts have coverage.

Twenty normalized Scryfall responses supply fifteen original devotion Gods and
five real devotion resources. Other fixtures reuse canonical existing rows.
No production cards, decklists, stats or matchup percentages are invented or
changed. Coverage of the type clause does not certify every other card ability.

## Acceptance Evidence

Tests use isolated source-relative databases, never the live user database.

| Check | Observed result |
| --- | --- |
| Corrected baseline against `0415fd2` | 12 failures / 4 passing controls |
| Band persistence regression before fix | 2 failures, both seats |
| Counted life-loss regression before fix | 4 failures, both seats/two God families |
| Current new regressions + existing banding | 111 passed: 102 new + 9 existing |
| Current frontend lint / contracts / build | Passed |
| Corrected-source full backend suite | 5,609 passed; 551 warnings; 1,023.97 seconds |
| Corrected-source repeated archetype matrix | 24 seat-balanced samples / 48 executions; zero anomalies, timeouts or drift |
| Corrected-source complete Chromium harness | Passed alone: four new transitions, recovery/sideboard and natural AI/human BO3 flows |

The original attack baseline queried the wrong legal-move field; only its
corrected rerun establishes the twelve failures. An earlier full run had 5,594
passes and four obsolete Xenagos unsupported-warning failures. Negative tests
now use canonical Thunderfoot Baloth's unsupported Lieutenant clause; positive
type-admission tests cover the newly supported clause. Negative coverage was
preserved rather than deleted.

Earlier frontend and complete browser runs passed, and twelve seat-balanced
Tempo/Dimir Control/Tokens/Ramp BO1 samples repeated twice reported no anomaly,
timeout or determinism drift. Subsequent review found the band/count regressions,
so earlier green runs do not qualify the corrected source. Superseded validation
processes were explicitly stopped after source changed, not counted as passes.

Browser runs also recorded five-second state-read timeouts. The prior targeted
and complete reruns passed unchanged assertions; a review rerun timed out again.
The root cause is not established. Failed logs are retained. Final browser
acceptance passed separately from heavy simulation tests without weakening
assertions or timeouts; this does not establish causality for the earlier failures.
Backend source and tests byte-match the final full-suite, matrix and browser
copies. Repeatability remains a bounded check, not broad AI-strength evidence.

Evidence and source backups are under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/conditional-types/`.
Completed scratch is archived and verified before deletion; active code and live
databases stay local. The user-authored untracked plan is preserved separately
and excluded from the commit.

## Checklist

- [x] Map current code through Graphify; reproduce real single-/two-color cases.
- [x] Implement shared effective types, animation ordering and ability-loss parity.
- [x] Route state-aware rules/AI/views through current characteristics.
- [x] Preserve last-known types, subtype correlation and entry/control tenure.
- [x] Reproduce/fix announced-band and printed-count fallback regressions.
- [x] Verify both-seat HTTP/snapshot and human control coverage in focused runs.
- [x] Finish corrected-source full backend, Chromium and repeated matrix gates.
- [x] Update feature status and AST-only Graphify (zero API token cost).
- [x] Verify final source/evidence archives; publication and closed-scratch
  cleanup receipts accompany the evidence archive.

## Rules Grounding

The [official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
sections 205, 613 and 700.5 ground types, layers and devotion. Rule 702.22e
preserves announced bands through combat; existing block assignment excludes
members no longer attacking. Rule 509.1h preserves blocked status when blockers
leave combat.

## Known Limitations and Next Upgrades

Arbitrary conditional/global type effects, dependencies, full copy/subtype layers,
devotion mana, complete-card certification and expert AI remain open. Replay
repeatability is not a balance or AI-strength certificate. The alpha UI redesign
remains deferred. Earlier browser state-read timeouts remain a retained,
unexplained diagnostic; the isolated final harness passed unchanged checks.
