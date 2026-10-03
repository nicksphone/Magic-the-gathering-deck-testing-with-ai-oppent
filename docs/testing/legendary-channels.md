# Legendary Channel Lands and Shared Resolution Choices

## Implemented Scope

Canonical Scryfall fixtures retain Oracle IDs and source URIs for all five
Kamigawa: Neon Dynasty legendary Channel lands. These are rules fixtures, not
invented decks or complete-card certification. Production behavior uses shared
Oracle grammar and effect handlers, never card-name dispatch.

- Selected regular hand abilities discount generic mana by controlled legendary
  creatures. Opposing creatures and legendary lands do not count; colors remain
  payable and unrelated mana abilities keep their own costs. Costs lock before
  source discard and mana consumption.
- Target unions support artifact/creature/enchantment/planeswalker bounce and
  opponent artifact/enchantment/nonbasic-land destruction. Combat-only damage
  checks attacking/blocking status at announcement and resolution.
- Destruction followed by optional search captures the affected controller before
  the permanent leaves. Search/Decline belongs to that controller. A land with a
  basic land type may be nonbasic: it is not the basic-land predicate. Accepted
  searches may fail to find and still shuffle; declined searches do not shuffle.
- Fixed-count milling moves available library cards through shared graveyard
  replacement handling. Milling an empty library is not drawing and does not
  itself lose the game. A following non-targeted creature/planeswalker return
  chooses after milling, including freshly milled cards, rather than requiring
  premature announcement-time targets.
- Direct adjacent token haste instructions create temporary keyword effects.
  Token colors and printed keywords stay unchanged; haste survives snapshots
  and expires at cleanup.

Human choices retain owner/options/continuation across snapshots and SQLite.
Wrong owners and stale graveyard selections are rejected atomically. Nested land
entry resumes the same resolution without destroying or milling twice. Both-seat
App/API controls and reload are tested; this is not the deferred UI redesign.

## Tactical AI Boundary

Master's bounded public-board setup can create the first hasty attackers. Before
forced land development consumes a card with a legal hand activation, the same
forecast may retain it for a proved winning ability. No archetype label or card
name selects this behavior. Bounce targets prefer opposing threats while
preserving explicitly selected friendly targets.

Forecasts permit known public cards to return into a hand without revealing its
existing opaque contents. Draws, existing-hand removal/reordering, unknown
additions and library changes still stop forecasting. Opposing hidden-card
variants must produce the same public line in the tests; this is not universal
hidden-information certification.

AI accepts supported optional searches and uses the existing hand-retention
heuristic for graveyard choices. Noninteractive callers retain automatic search
and last-eligible return. Neither policy establishes optimal resource planning.

## Acceptance Evidence

- `backend/tests/test_legendary_channels.py`: both-seat pricing, target admission
  and rechecks, optional searches, typed nonbasic entry, mill/return ordering,
  replacements, token lifetime, rejection and HTTP/SQLite recovery. Master
  token/bounce decisions cover five archetype labels and both seats without
  mutating authoritative state.
- `frontend/tests/browser-legendary-channels.mjs`: both-seat actual activation,
  targeting, payment/discard, priority, owned choices and refresh/resume.
- Final suite, complete Chromium and repeated seat-balanced replay results are
  recorded in CHANGELOG with the RCHFiles archive. Small samples validate
  repeatability/regressions, not matchup balance or tournament strength.

Saved independent probes compare twenty Master decisions per revision against
committed `3ec814c`, retaining complete hands, boards, legal moves, reasons and
checked results. Winning token/bounce continuations improve from 0 to 20 across
five archetype labels and both seats. These are constructed public-board states,
not independent match samples or an optimal-play claim.

Rules reference: [Wizards' Kamigawa: Neon Dynasty release notes](https://magic.wizards.com/en/news/feature/kamigawa-neon-dynasty-release-notes-2022-02-09).
Fixtures retain current Scryfall Oracle text rather than substituting printed
release-note wording for canonical data.

## Known Limitations and Next Upgrades

Unrecognized target qualifications, dynamic mill expressions, arbitrary mill
triggers, complex replacement ordering and interrupted cost continuations remain
unfinished. Temporary-token keyword inference is deliberately limited to adjacent
unconditional instructions. Whole-card and arbitrary Oracle certification remain
open.

Master's setup bound excludes wide boards, exhaustive target alternatives,
multi-action setup and adversarial responses. Strong/Casual adoption, long-term
land retention, optional-search strategy and graveyard resource planning need
additional evidence. Do not force equal win rates or infer seasoned-player AI
from constructed lethal scenarios.
