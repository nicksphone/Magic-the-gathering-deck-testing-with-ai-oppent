# AI Observations and Public Utility Choices

## Implemented Scope

Every production agent decision receives a private planning copy. Opposing hands,
both uninspected libraries, and unauthorized face-down exile have no card name,
Oracle text, faces, mana cost, keywords, stats, or retained custom metadata in
that copy. Zone membership and counts remain; opaque records are unknowns, not
invented Magic cards. They cannot become virtual free spells after a projected
snapshot round trip. The authoritative state and root legal moves are unchanged.

Own hand, public zones, stack sources, owner-inspectable foretell cards, permitted
top-library action sources, and owned inspection-choice options remain available.
Scry/surveil retained-top ordering and inspected bottom ordering preserve their
authorized observations. Private AI trace lines are removed from planning logs.

Each newly created game's submitted deck composition is persisted privately in
snapshots, independently of shuffle order and physical instance IDs. A decision
copy contains only that pilot's list. Linked discard/search planning uses known
printed land composition minus visible copies, capped by library size; it does
not scan uninspected library instances. Duplicate submitted rows are accounted
for. With hidden removals this is an availability upper bound, not a guarantee.
Actual search resolution uses the engine's legally inspected candidates. Legacy
snapshots without a list remain conservative rather than reverse-engineering it
from hidden cards. The submitted list is absent from public match serialization.

Shared pure-destruction policy projects actual costs and public continuations to
avoid wasting removal on one's unthreatened creatures, including conditional
destruction instructions. Profitable friendly destruction and death-trigger wins
remain available. Unsupported/private continuations remain explicitly unknown;
this is not a blanket prohibition on self-targeting or sacrifice.

Announced trigger targets and optional acceptance use isolated checked public
effects. The AI can target an enemy artifact and accept its destruction, or
announce a required legal target and then decline optional destruction of its own
mana engine. Newly triggered ward responses and unresolved choices are not
silently discarded as a supposedly complete forecast.

## Verification

Focused tests cover both seats, six archetypes, multiple difficulties, hidden-data
invariance, foretell ownership, inspection continuations, snapshot persistence,
linked discard/search planning, removal conservation, Blood Artist death-trigger
wins, and Reclamation Sage target/optional choices.

The prior commit fails 48 information-boundary probes and 72 of 136 removal/trigger
utility cases. The captured Ramp position previously cast Fatal Push on its own
Nissa-animated Underground Sea; the updated decision passes and preserves both
the spell and authoritative root state. These are decision/outcome fixtures, not
claims that a changed matchup win rate proves better play.

The final source passes all 7,021 backend tests across 289 files in four isolated
shards. The gate caught six linked-discard regressions during development; the
fix retains known submitted composition instead of restoring hidden-library
access. Frontend lint, five unit-contract scripts and the production build pass.
All 41 Chromium scripts pass; affected inspection/BO3 flows are additionally
checked after the final inspection-order change and an isolated API restart.

Ten pinned seed/seat samples span Blue Control/Ramp, Tempo/Tokens, Mono Red
Aggro/Dimir Control, Tribal/Drain, and Midrange/White Weenie. Each sample repeats
twice on the pre-inspection-order stage with identical complete results/logs,
no timeout and no matching announcement-error or target-invalidation lines.
The final inspection-order stage gets a further ten executions compared against
those repeated references. Stages are not additional independent balance samples.
Inputs distinguish resolved offline seed metadata from canonical-corpus
certification. Final-source comparison and terminal run evidence are retained
privately under RCHFiles `diagnostics/ai-information/20261004-working/`.

## Remaining Boundaries

- Bounded previously revealed hand memory is now implemented in the subsequent
  [observation-memory batch](ai-memory.md). Broader public memory, inference from
  public actions, opponent deck priors, bluffing and sampled information-set search
  remain open.
- Unknown replies are not actual unseen counterspells; this boundary does not
  establish optimal strategic play against an unknown opposing hand.
- Draw/reveal continuations and complex interdependent trigger queues can remain
  unforecastable. Isolated effect ranking is not whole-stack tactical search.
- Land search estimates do not yet price every alternative future resource or
  establish availability after hidden zone changes. Legacy games lack the prior.
- Worst-case planning latency, arbitrary Oracle semantics, broad AI strength and
  matchup balance are not certified by these focused or repeated smoke matches.
- The frontend redesign remains deferred; browser regression checks establish
  exercised flows, not a finished competitive-playtesting interface.
