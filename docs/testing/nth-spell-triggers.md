# Bounded Nth-Spell Triggers

## Scope

The event collector admits full printed first/nth-cast clauses with an exact
draw instruction, an explicit creature-token descriptor with at most one supported
keyword, or an ordered draw-then-token instruction. It reuses existing effect
handlers, staged triggers, stack publication and snapshots. It does not execute
permanent Oracle text as its casting effect or certify an entire card.

Both players' cast counts reset at a turn boundary. A cast through an alternate
method counts; a spell copy does not. Controller identity and opponent-turn
restrictions are checked before publication. Printed ability suppression remains
authoritative; an already-published independent trigger survives source departure.

## Canonical Evidence

Unmodified local canonical rows and their raw hashes are stored under
`backend/tests/fixtures/nth_spell_triggers/`. Clarion Spirit, Jori En, Wavebreak
Hippocamp, Wingblade Disciple and Rammas Echor exercise admitted schemas. Rammas
requires both its draw and its printed white 0/3 Wall with defender, not a partial
first recognized effect. Actual HTTP tests use synthetic public positions with
real cards, both seats, local SQLite and fresh-process snapshot/receipt restore.
They are not natural-match, AI-strength or full-mechanics certifications.

## Unsupported Boundaries

Cori-Steel Cutter's optional attachment and Captain Ripley Vance's counter plus
targeted power-damage rewards remain unsupported by this helper. A recognized
nth-cast header with an unsupported complete reward logs an explicit diagnostic
and does not execute a partial reward. Other header/reward schemas are not
certified. No inferred hidden cards, named-card dispatch or invented tokens are
used. Wedding Announcement's generic compiler coverage risk is separate; its
specialized runtime was not changed.

## Historical Witness Transition

The frozen readiness audit remains immutable in its archive. Two local test
functions (six cases) transition the old missing-Clarion-trigger witnesses to
bounded positive execution regressions, retaining admission, root purity,
database/receipt and diagnostic assertions. Their adapter is a separate patch.
Metadata readiness and empty known-gap lists still do not certify execution.
