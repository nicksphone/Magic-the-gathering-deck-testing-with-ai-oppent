# Simultaneous wheels and hand-defined characteristics

## Implemented Scope

One shared clause reader recognizes complete each-player whole-hand discard/draw
instructions: fixed draws, each player's actual discarded count (including minus
one), or the largest actual discarded count. Canonical Wheel of Fortune, Windfall,
Dark Deal, Incendiary Command's wheel mode and Chandra Ablaze's -2 are fixtures,
not name-specific dispatch. This does not certify their other modes or abilities.

Mandatory whole-hand discard has no discretionary card selection. Both hands
move through the shared simultaneous discard operation before any draw. Actual
discards count even when replacement exile changes the destination. Existing
events, turn history, counters, copies and draw restrictions remain in force.
Draws use the resumable effect sequence: the active player finishes their draws
first, followed by the other player. Dredge/replacement choices preserve the
resolving spell and remaining effects across snapshots and SQLite restart.

State-based actions wait until resolution finishes, including owned draw choices.
A creature whose stats temporarily become zero during a wheel is not destroyed
mid-resolution. Both players can finish failed draw attempts before the game is
declared a draw. Discard payoff triggers resolve after the wheel finishes.

This sequencing follows the current [Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
effective September 25, 2026: sections 101.4, 121.2c, 121.4 and 704.4. Saved rule
and Scryfall responses are retained with the test evidence.

The shared characteristic calculation recognizes self-referential power/toughness
equal to the controller's hand size. Canonical Maro and Sturmgeist exercise this
with counters, temporary changes, base-setting effects, snapshots and live views.
Known characteristic-defined creatures now receive lethal state checks even when
their printed stats are nonnumeric. Removing their defining ability yields zero
before other modifiers. Truly unknown characteristics remain unknown in public
views; this is not arbitrary characteristic-definition support.

Explicit signed printed stats are preserved (canonical Char-Rumbler is -1/3).
Explicit nonnumeric metadata no longer falls through to a numeric name heuristic.
Older missing-metadata fallback heuristics still exist; they are not certified.
Legacy arithmetic helpers still use zero when a characteristic is truly unknown;
public views preserve unknown values and lethal-state checks do not invent them.
Unmodeled characteristic definitions must not support trusted matchup conclusions.
Old snapshots retain their stored printed-stat fields; start fresh games to test
corrected canonical signed/nonnumeric metadata rather than relying on migration.

## AI Boundary

All difficulties price a recognized wheel using known own-hand retention, the
public opposing hand count, shared expected draw counts and supported draw caps
and multipliers. They avoid the exercised self-deck-out cases and retain tested
good hands, while permitting tested refills or safe opposing deck-out opportunities.
Opposing hidden card identities are not used. Modal scoring shares this estimate.

Unknown draws have a fixed heuristic value. Optional Dredge, interacting discard
payoffs, graveyard combos, opposing responses and draw-versus-loss strategy are
not forecast completely. This is not tournament-trained or optimal wheel timing,
nor certification of every loyalty decision or all clauses on fixture cards.

## Acceptance Checklist

- [x] Initial tracked-source probes reproduce missing wheel/stat semantics.
- [x] Both seats: fixed/count/largest/minus-one draws, empty hands and short hands.
- [x] Countered spells, opposing copies, actual counts with replacement exile,
  doubled draws, failed draws and post-resolution discard payoffs.
- [x] Owned Dredge continuation, snapshots and HTTP/SQLite recovery.
- [x] Known hand-defined and signed stats, counters/base layers and ability loss.
- [x] Names-only cached-card HTTP hydration, effective views and restart.
- [x] Final combined draw/discard/layer/mana-resource regressions: 386 passed,
  30 deprecation warnings, 54.88 seconds; all 114 new checks are included.
- [x] Full isolated backend suite: 4,770 passed, 420 deprecation warnings,
  927.72 seconds. The 18 late HTTP/production-AI checks pass separately in the
  final 114-check wheel selection (18 warnings, 19.77 seconds).
- [x] Frontend lint, runtime contracts and TypeScript/production build.
- [x] Twelve new Chromium cases: all five wheel surfaces, both seats, both owned
  draw continuations and reload. Targeted and full runs pass.
- [x] Complete Chromium harness, including recovery, sideboarding and natural
  AI/human controller-mode BO3 flows. Scripted human opponents remain bounded
  fixtures, not competitive human-release or long-session certification.
- [x] Two seed- and seat-balanced matrices, 12 BO1 samples each, repeated twice:
  zero reported anomaly/timeout/drift. Explicit Dimir Control/Tempo/Tokens/Ramp
  selection took 355.912 seconds; default archetype-template smoke took 211.978.
  These are repeatability samples, not balance or optimal-play estimates.
- [x] All nine Scryfall fixture records match saved raw fields; frozen engine
  source matches the copy used by the full suite. AST-only Graphify refreshed:
  9,532 nodes and 24,484 edges, zero external AI cost.
- [x] RCHFiles evidence archive passes content comparison and SHA-256 verification;
  final source is archived separately and the milestone is published to GitHub.

Keep failed logs: early tests used an unadvertised Dredge ID format and an
incomplete modal target map, and a lazy test import captured fixture hydration.
They were corrected to use production contracts, not weaker engine validation.
The shared lethal-state path also required removing a second printed-toughness
guard. Browser probes now wait for acknowledged casts before passing and return
booleans instead of serializing DOM objects through Chromium. An older kicker
browser test had a command timeout during concurrent backend/replay work; it
passes in the separate targeted rerun and the successful complete harness rerun.

Evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/wheel-draw/20261003T180840Z/`.
Preserve canonical responses, failed/final logs, frozen source copies, replay
outputs, AI decision traces and closed browser artifacts. Verify archive contents
and SHA-256 before removing owned local scratch. Keep the pre-existing user plan
separate and out of the milestone commit.

## Known Limitations and Next Upgrades

Conditional/random/opponent-specific discard sequences, broader linked clauses,
arbitrary replacement costs and characteristic definitions remain unfinished.
Supported full clauses do not certify entire cards. Small repeated matrices prove
bounded repeatability, not matchup balance or expert AI. The deferred UI redesign,
release/security hardening and wider supported-corpus semantic gates remain open.
