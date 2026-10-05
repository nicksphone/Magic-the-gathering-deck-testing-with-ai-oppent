# Graveyard Play Permissions

## Implemented Families

- Ordinary self-casting from the graveyard, including a controlled-subtype
  condition and the restriction to graveyard-only casting. The same exact-clause
  parser serves rules and coverage diagnostics; there are no card-name branches.
- Active, unsuppressed battlefield grants for spells of a card type or creature
  subtype. Respect control, current card types and supported changeling state.
- Land-from-graveyard permission, including a modal land face, without adding
  land plays or bypassing priority, main-phase timing, ownership or empty stack.
- Global graveyard/library cast prohibitions, including effect casts without
  paying mana, and creature/nonland-permanent entry prohibitions for these zones.
- Admission checks before reanimation, library search, top-library placement and
  creature-land plays. Already-announced creature spells resolve from the stack,
  not from their previous source zone. Impossible placement creates no departure
  trigger, entry-counter choice or associated life payment.
- Both-seat strict HTTP source flags, public legal card views, saved snapshots
  and the existing land button. AI can choose these real actions and retain
  reusable graveyard cards when selecting delve payments.
- Blocked split searches preserve the original destination assignment; no card
  identity is revealed merely because an intended battlefield move failed.

The rules grounding is CR 101.2, 305.1-305.4, 601.3 and 611.3b in the
[September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
Fixture files retain complete Scryfall responses and per-download SHA-256/source
provenance. Eighteen cards exercise implemented families; three further canonical
fixtures require explicit unsupported-permission diagnostics. Oracle text, card
stats and natural test decks were not modified.

## Qualification

Current qualification supersedes the historical focused-stage notes below.
Runtime `a7d9d7d` passed 8,784 backend tests across 353 files (704 source hashes)
and the complete browser gate, and is integrated into main through the
[consolidated runtime](backend-consolidation.md).
Drain/Tribal, Tokens/Ramp and Tempo/Control natural runs cover six unique seeded,
seat-balanced games repeated twice: all twelve decision reconstructions match,
all retain predecessor results/logs, and the runner reports zero determinism
failures, drift labels or anomalies. This is narrow compatibility evidence,
not arbitrary-card semantics or professional AI certification.

Historical development checks:

- Canonical both-seat checks cover actual graveyard hybrid convoke/delve casts,
  controlled Zombie/changeling conditions, suppression, source-control changes,
  subtype grants, modal land entry, casts already on the stack and real triggers.
- Earlier combined selection: 462 passes; separately 20 HTTP/restart/rejection
  checks pass in a disposable initially DB-free source copy. These are overlapping
  stages, not an exact-source full gate for subsequent parser/diagnostic edits.
- After the final lightweight-view compatibility edit, 195 focused permission,
  admission, coverage and AI checks pass. Full qualification is recorded only
  after all frozen-source shards and browser scenarios terminate successfully.
- Frontend tests, lint and build pass. All six new browser flows pass for both
  seats, including real source flags, exhausted land allowance and reload.
  The first runs exposed a malformed fixture mana pool and an assertion against
  a private rather than public field; both test defects were corrected without
  weakening the runtime contract. Full browser qualification remains outstanding.
- The inherited instant-timing runtime 40302dc passes all 8,674 backend tests
  (350 files, 686 source hashes verified in four DB-free copies) and the full
  browser suite. This does not qualify the new permission/placement runtime.

## Known Limitations And Next Upgrades

Empty gap lists are not whole-card rules certification. Full/browser and the
bounded natural compatibility review above are complete; wider semantics and
tactical-quality evaluation remain open.

The parser deliberately rejects unsupported permission shapes rather than
turning them into unlimited access. Lurrus, Muldrotha and Gisa and Geralf report
`unsupported graveyard play permission` at this historical increment. Subsequent
[limited permission ledgers](limited-graveyard-permissions.md) implement bounded
families on main; their separate limits still apply. Neither increment certifies
those decks in full.

Expand conditions, duration/source-incarnation fidelity, granted permissions,
dynamic subtype/layer interactions, full casting-announcement/source-departure
ordering, ordered compound costs and other battlefield-admission routes. This
batch does not certify every other ability on its fixture cards or arbitrary
Magic semantics. Broader tactical/strategic quality and release gates remain
open; candidate branches have not been rolled into main/live.
