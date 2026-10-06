# Suspend/Keep And Temporary Group Keyword Composition

Date: 2026-10-06 UTC. Base: published milestone `19a925291364f08547f06dd55fc8344e14fe8c6f`.
This is an isolated integration candidate, not a live deployment or main merge.

## Implemented

- Public SuspendAction and KeepAction validation before intent normalization.
  Suspend display fields must match the current actor's offered action; explicit
  card/bottom choices are retained. Actor validation occurs before helper calls.
  Removing only the two new imports/bindings/branches and actor entry check
  restores the prior environment module AST; prior 21 bindings are preserved.
- Generic complete temporary group keyword clauses use the existing strict
  keyword parser and object-bound keyword effect handler. Recipients are locked
  at resolution, share an effect timestamp, expire at cleanup and do not follow
  cards into a new zone incarnation. Unsupported text still fails closed.
- Fresh-process color tests run from the isolated backend and assert imported
  module paths. The internal alternate-cost test uses official unchanged
  Bringer of the Red Dawn data, not an invented spell lacking a resolution.

## Executed Acceptance

| Gate | Result | Scope |
| --- | --- | --- |
| Suspend/Keep focused | 144 passed, 169 warnings, 172.04s | Three whole modules |
| Actor composition | 44 passed, 2 warnings, 6.37s | Both new families, both seats |
| Coupled consumer gate | 1,507 passed, 583 warnings, 1350.74s | 25 whole modules, before keyword repairs |
| Canonical group HTTP/core | 16 passed, 6 warnings, 7.17s | Both cards/seats; later HTTP-expanded module |
| Current repair gate | 440 passed, 766 warnings, 373.51s | 20 whole modules, including four unchanged seeded autoplay tests |

All completed acceptance gates have exit 0 and no skips, xfails or deselections.
Counts overlap: these are regression checks, not independent matches or evidence
of matchup balance. Backend source manifests were verified before/after each
coupled run. Python uses the isolated upgraded declared-requirements environment;
live dependencies and databases were not changed. Frontend source is unchanged
from the previous milestone; no fresh frontend test result is claimed here.

Canonical full Scryfall responses and URL/time/hash provenance are tracked under
`backend/tests/fixtures/permanent_keyword_grants/` and
`backend/tests/fixtures/cost_choice_fallback/`. No Oracle text was rewritten.

## Preserved Failures And Remaining Work

The initial Suspend/Keep setup run failed because its private source marker had
a trailing newline; runtime setup was corrected before the fresh successful run.
The observed seeded autoplay failure rejected Boros Charm's printed protection
mode as unsupported. Its original witness is retained separately from passing
post-fix tests. The color subprocess import failure and invented alternate-cost
fixture failure are likewise retained as baseline evidence.

A separate immutable full backend baseline collected 15,947 cases and remains
running at publication preparation. It predates the keyword/test repairs and has
observed autoplay, color, cost-fixture and BO3 failures. Its terminal result must
be recorded separately and remaining failures reproduced on the repaired source.
No whole-suite green claim, arbitrary-card certification, professional AI,
shuffle-observer completeness, browser/LAN release or special-land metadata
certification follows from these gates.
