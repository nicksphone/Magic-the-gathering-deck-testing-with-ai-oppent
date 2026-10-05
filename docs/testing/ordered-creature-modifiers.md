# Independent Creature Modifier Targets

Status: isolated `codex/coupled-targets` implementation, not merged into the live
application and not full targeting-family acceptance.

## Implemented Contract

Complete Oracle text containing separate unqualified temporary creature P/T
modifier sentences is parsed into ordered target instances. The announcement
must supply exactly one creature ID per instance. The same creature may be
chosen more than once; the existing explicitly distinct counter family retains
its distinctness rule. No printed characteristics or card-name special cases
are introduced. Canonical Agony Warp data is retained verbatim as a fixture.

Each effect captures its target incarnation and zone-change sequence. Resolution
rechecks each recipient independently and preserves legal portions; leaving and
returning does not restore the old target. Public stack views expose ordered IDs,
including repeated IDs, without exposing private effect payloads. Snapshot data
continues to preserve the authoritative announcement and effect packets.

Both human seats have ordered controls with per-instance modifier labels. AI
compares checked, paid outcomes for two instances over up to six public targets.
Unknown choices or changes to hidden zones are not guessed; its fallback uses
public benefit/harm and threat values rather than raw candidate order. This is
bounded selection, not optimal-play certification.

## Observed Evidence

- 61 focused backend checks passed before the public-view regression was added.
- 155 expanded backend checks pass, including public-view assertions, existing
  adventure/modal/divided-damage and Ward regressions, all-illegal resolution,
  Ward object-versus-instance checks, gained shroud, and copies retaining their
  targets after the original spell is countered, and both-seat HTTP rejection
  checks preserving complete snapshots and persisted match records. The initial copy probe incorrectly
  expected a handler return value; the corrected check inspects the actual stack.
- Frontend contract tests, lint and build passed before the final public-view fix;
  that fix is backend-only.
- Focused Chromium scenarios pass both seats for shared and different recipients,
  deliberate UI selection, actual payment, pending reload, effective stats and
  final reload. Existing distinct-counter browser scenarios also pass.
- The first browser probe incorrectly expected a private payload in the public
  response. The corrected probe then reproduced an empty public target list;
  the serializer repair makes the assertion pass. Both failures are preserved.
- These are constructed canonical positions, not naturally played games or a
  balance matrix. Browser helpers dispatch DOM events; this is not a complete
  physical-pointer, visual or accessibility review.

## Remaining Acceptance

Changed-control/protection continuations, broader
HTTP fuzz/adversarial invariants, fresh repeated matches, the full isolated
suite and integration with the newer main AI remain outstanding. Activated and
triggered abilities are not established by this spell-only fixture family.
Linked controller-dependent damage and land-entry history remain separate open
work; the conservative coverage warnings stay visible. No absence of a warning
or parser match establishes unrestricted Magic rules fidelity.

## Subsequent Copy Continuation Increment

Ordered modifier and explicitly distinct counter copies now use the shared
copy-choice continuation, preserving per-instance packets and durable references.
Distinct assignments allow swaps but reject prefixes with no valid completion;
old illegal targets may be kept, not chosen as new targets. A returned object can
be explicitly selected anew, refreshing only that instance's object reference.
Ward events wait for complete selection and deduplicate shared recipients.

The AI's existing copy-choice scorer handles each ordered modifier independently:
it avoids harming friendly creatures and recognizes lethal negative toughness.
This is bounded public scoring, not multi-turn or hidden-response optimization.

The subsequent 176-check backend gate passes, including canonical Agony Warp and
Incremental Growth copies, both seats, snapshot resume, distinct swaps, infeasible
prefix prevention, returned objects, Ward and four AI style labels. All six new
copy-continuation tests failed before the implementation; eight AI copy-target
tests failed before scorer integration. The initial infeasible-prefix test was
too strict about later legal swaps; the corrected test verifies that the first
illegal target is kept while later legal choices remain available.

Focused Chromium checks pass sequential shared/different copy targets for both
human seats, reload after each choice, unchanged original targets and actual
copy-only resolution. These are canonical constructed effect positions, not
evidence of a naturally cast copy spell or a complete competitive match.
The earlier pre-copy full suite passes 7,428 checks. After integration with the
published strategic AI, all 7,563 backend checks pass across 309 discovered test
files, as do frontend tests/lint/build and the full Chromium gate, including
naturally finished AI, human/AI and two-human BO3 sessions. These frozen-source
results do not certify changes made afterward or broader replay quality.

## Post-Gate Ward Reference Repair

Additional canonical Twincast checks exercise actual payment and normal priority
passing, choice suspension and reload, both copying seats and ownership, followed
by copy and original resolution. A subsequent both-seat regression reproduces
spurious Ward when a copy keeps an old target after that permanent leaves and
returns. Ordered Ward capture now requires a surviving target-instance reference,
not merely a matching current card ID. The original Ward trigger remains intact.
This repair postdates the 7,563-check source. Its separately frozen final gate
passes all 7,569 checks across 310 discovered test files, with no omitted or
duplicated files; the full Chromium gate also passes, including natural AI,
human/AI and two-human BO3 sessions. Fresh repeated capability matches remain
required before publishing this milestone. None of these gates covers the
independent land-entry/conditional-alternative workstream.
