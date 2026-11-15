# Modal decisions found in full games

Full-game review is separate from legality and tactical unit-test coverage.
The private cross-style sweep uses every shipped builtin deck, paired against
a different detected style, both seats and Strong/Master. Its actual completion
and resource-limit outcomes live in the campaign report, not in test counts.
The baseline remains frozen at `2a032891` while fixes are evaluated separately.

## Confirmed defect

In one complete Control/Burn game, Burn twice cast Boros Charm's indestructible
mode while controlling only lands, with an empty stack. Mode scoring applied
the whole card's burn tags to every mode, then also rewarded the word "gain".
The legal four-damage mode lost to protection with no visible payoff.

Checked alternatives at both original decision positions pay the same two
mana but change the opponent's life from 14 to 10 and from 11 to 7, respectively.
The observed mode leaves life unchanged. These are two isolated comparisons
assuming subsequent passes, not eight combined damage or a changed-game winner.

## Correction and controls

Only `AIAgent._score_mode_text` changes. Tags come from the selected mode text.
For indestructibility responding to an existing stack, the existing checked
projection compares two settled branches: the unanswered stack and the stack
after paying for the explicit protection mode. An actual public save adds
value; unknown forecasts retain the mode-local heuristic. No card-name branch,
rule edit, training update or learned-model adoption is involved.

The 24 canonical outcome cases cover both seats and Strong/Master: empty-board
upkeep/draw/main-phase damage, immediate modal lethal, saving real creatures
from paid Supreme Verdict, and not treating indestructibility as an answer to
paid Sunfall. The wider fourteen-module gate passes 494 checks.

## Caching test correction

The expanded gate also exposes 11 pre-existing assertions on the frozen
pre-fix source: they require every stack settlement to be the single root
projection. Necessary per-candidate forecasts introduced earlier make that
assumption obsolete. Original tests and failures are retained privately.

The updated test measures the intended property directly: the unchanged root
removal projection computes once with decision-local caching and more often
without it, with identical actions and authoritative state. Benchmark checks
retain deterministic positive settlement counts, full-reference savings, and
equal counts for copy/field/hotpath-only ablations; they no longer hardcode one
settlement for all work. No caching code or benchmark output is changed.

## Limits

Normal Strong/Master agents use heuristic strategy plus historical priors.
An explicit trusted binding is required for learned Q/V. Logging a game is
not training, and self-play winners alone do not prove human-level competence.
Full hands, legal offers, snapshots and rejected attempts remain in private
evidence, never public Git fixtures. Blocking trade-offs and unfinished games
remain review items; this modal correction is not an all-archetype certificate.
