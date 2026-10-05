# Limited Graveyard Permissions (Candidate)

## Implemented Families

- Exact-clause once-per-own-turn permanent-spell permissions with a mana-value
  ceiling, and once-per-own-turn creature-spell permissions by subtype.
- Exact-clause own-turn land and permanent-spell permissions with one usage per
  permanent type. Multi-type spells expose separate cost options: choosing one
  consumes only that type's allowance. Land plays consume the Land allowance
  and remain subject to the normal total land-play limit.
- Source-local, controller-specific usage keys include source zone incarnation
  and clause position. Suppression does not erase already-used allowances;
  source re-entry and subsequent turns permit new uses. Usage survives SQLite
  snapshots and is copied independently into tactical projections.
- Existing cost selectors expose source/type choices; graveyard land buttons
  carry validated source keys. Stale explicit choices reject instead of silently
  falling back to another permission. Implicit cost fallback remains supported.
- Mana-value checks use the actual chosen spell face and X value, not payment
  amount or kicker cost. Existing source ownership, timing, costs, suppression
  and global prohibition rules still apply. AI can execute these real legal
  actions and retain currently reusable cards when selecting graveyard payments.

Canonical fixtures include Lurrus, Gisa and Geralf, Muldrotha, Walking Ballista,
Exploration and the predecessor's raw Scryfall corpus. Full downloaded bytes and
SHA-256/source provenance are retained; no card text, stats or test decks changed.
The source-local/permanent-type rules follow the official
[Double Masters 2022 release notes](https://media.wizards.com/2022/downloads/2X2_Release_Notes/EN_MTG2X2_Release%20Notes_20220418.pdf),
and the mana-value permission follows the official
[March of the Machine release notes](https://media.wizards.com/2023/downloads/MOM_Release_Notes/EN_MTGMOM_ReleaseNotes_20230412.pdf).

## Qualification

- Earlier overlapping broad checks: 902 passed. Earlier HTTP/input selection:
  62 passed in a disposable source copy; four additional restart/resolution
  checks passed after improving the assertions. Final edits and added cases need
  exact-source full qualification; these counts are not a full-suite claim.
- After the final runtime/contract edits, 233 focused backend checks pass;
  frontend tests, lint and build also pass.
- All six focused browser scenarios passed for both seats: real permission
  selection, payment, resolution, reload and exhausted allowances, including
  successive Artifact/Creature allowances for a real multi-type spell.
- Frozen runtime `359904ff7c63833f549025a7890a98c40351b2a3` passes
  8,824 backend tests across all 355 recursive test files. Four initially
  DB-free copies match 710 source hashes; each test file runs exactly once.
  The complete browser suite, including natural AI and both human BO3 flows,
  passes. Evidence is archived under RCHFiles
  `diagnostics/strategic-draw-counts/20261005T102232Z/limited-graveyard-permissions/full-qualification`.
- The predecessor runtime passes 8,784 full backend tests across 353 files and
  the complete browser suite; this is not qualification of the successor.

## Known Limitations And Next Upgrades

Finish seeded decision review and integration qualification, then qualify
duration, granted/replaced abilities, dynamic source/type layering and complete
casting-announcement ordering. Source-incarnation ledgers do not claim complete
ability-instance lifecycle handling. Alternate casting methods and source/type
opportunity-cost decisions need broader fixtures and tactical evidence.

Removing the permission-family diagnostic does not certify every other ability
on these cards: companion setup and other independent mechanics need their own
acceptance. This candidate is isolated; main/live are unchanged. Natural samples
and deterministic repeats are not evidence of universal rules fidelity,
competitive balance or expert-level AI.
