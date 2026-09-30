# Ward Trigger and Payment Boundary

## Implemented

Ward is a triggered ability on the stack, not an extra casting cost. Opponent
spell/ability targets are captured before paying costs. Each supported ward
instance creates a separate trigger referring to the particular stack object;
repeated scans do not retrigger unchanged targets. Targeted entry abilities and
spell copies generate their ward wave before priority returns. Stifle can counter
ward, leaving the original spell or ability untouched.

Supported printed costs: mana symbols, fixed life, life equal to the protected
creature's effective power, discard cards, and sacrifice supported permanent
types/counts including legendary, nonland and nontoken qualifications. Power is
evaluated at resolution, with battlefield-incarnation-aware last-known values
after departure. Supported attached mana ward grants use the continuous-effect
evaluator; bounded unconditional global grants preserve separate instances.

Payment is voluntary and belongs to the targeted stack object's controller.
Choices persist the interrupted resolving ability. Mana eligibility uses the
shared payment path, so artifact-only resources cannot pay ward. Discard and
sacrifice costs request exact eligible cards; ordinary discard/death events still
fire. Declining attempts to counter the referenced spell/ability and honors
supported spell counterability. The permanent owning ward is not countered.

Human pay/decline buttons and exact-card selection work for either seat. The
shared AI prices cheap discard/sacrifice resources and compares a bounded local
payment projection with losing the stack object. It declines lethal life costs
and redundant payments for supported uncounterable spells. It does not assume
opponent responses or solve a full strategic search tree.

## Evidence

Rules basis: official [2026-09-25 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
702.21a-b and 118.11-12. Locally retrieved text SHA-256:
`8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.

Thirty provenance-backed fixture rows were extracted read-only from the local
canonical Scryfall knowledge cache. Graveyard Trespasser uses its actual first
face; these tests do not certify its complete transform/day-night functionality.
No decklists or printed card characteristics were changed to adjust matchups.

Independent parent probes against `bd2101e` reproduce Lightning Bolt remaining
in hand with only its printed mana available, and Prodigal Pyromancer's targeting
ability receiving no ward trigger. Both revised paths put ward above the original
stack object. Targeted canonical tests cover both seats, ownership rejection,
snapshot resume, Stifle, live/last-known power, voluntary card selection, exact
sacrifice qualifications, Vein Ripper's death trigger, separate grants, divided
targets, real activated/entry abilities, Twincast and ten AI archetype policies.
The synthetic stack-object unit fixture tests infrastructure only, not a new card.

Final verification: **2,096 backend tests passed** (292 existing deprecation
warnings, 246.20 seconds), **246 focused checks**, frontend lint/build/unit and
the full Chromium harness passed, including seat-two mana/discard payments and
natural human/human, human/AI and AI/AI BO3 flows. Two independent AI card-cost
probes verify legal discard selection, declining wasteful sacrifice and planning
purity. Eight seeded seat-paired games repeat identical reported objects/logs
across sixteen executions, with no timeout or cast/target rejection line.

Detailed results, source hashes, parent reproductions and local log locations are
recorded in [ward-resolution.json](ward-resolution.json). Backend tests use an
independent immutable source/database copy; the live SQLite database is not a test
fixture. Existing pinned dependencies were reused, not freshly installed. A
90-second diagnostic dump during a BO3 autoplay request shows ongoing tactical
computation; the test subsequently completes. Per-decision latency needs profiling.

## Known Limitations and Next Upgrades

- Generic ward X definitions and arbitrary/compound cost clauses are not implemented;
  detected unsupported printed costs warn in preflight, not silently certified.
- Arbitrary temporary/global/conditional grants, copy/type/ability suppression
  layers and dependency interactions need explicit golden fixtures. Unknown
  grants are not inferred as unconditional supported ward instances.
- Discard/sacrifice prohibitions, competing cost replacements and all resolution
  payment restrictions are not fully covered by this milestone.
- Pre-cast valuation, multiple remaining ward costs, response representation,
  resource opportunity and sacrifice synergy require deeper AI planning.
- Passing focused scenarios and a small replay matrix does not establish whole-card
  correctness, universal Magic support, professional AI strength or deck balance.
- Manual long-session/LAN UX and arbitrary custom-deck coverage remain release work.
