# Proposed Master interactive budget head-to-head

This document fixes the proposed comparison for review. The existing v3
strength CLI accepts only the existing campaign schedules. Implementation
and separate run authorization are prerequisites to issuing this plan.

## Question and policies

Does the interactive cutoff retain enough of unlimited Master's playing
strength on admitted mirror decks? The archived probe matched 36 normal
actions. In 30 timeout positions it chose 19 alternate substantive plays
and paused 11 times. Those figures motivated a whole-game comparison and
were excluded from its outcomes.

Both seats use a fresh Master agent from the same measured revision, with
the same profile and native search policy. The candidate uses the PR118
cutoff with 128 charged planning/simulation operations and a cooperative
1,000 ms elapsed deadline per decision. Keep the best completed, checked
choice at cutoff. Apply these settings only to the candidate seat.
Unlimited means that both **interactive** limits are disabled. Existing
Master search limits remain active in both roles. Use the normal engine
for every accepted action. A candidate pause ends the cell as unresolved.
Record the pause and the last verified boundary. There is no automatic
pass, retry, or extra decision allowance.

The policy reference is PR118 at
`e5f05b0cc40da574e17d3046c6275c04cfc10c48`, incorporating the incumbent
fix measured on archived decisions. The issue step must use this policy
and commit a reviewable source and runtime identity for both arms. Any
policy or rules changes before issue require an updated pre-registration.
Use the exact built-in deck source with SHA-256
`236bc11807d9aeea3134c2b1ec9d1fa73a29d9dc366bf0e11a79ed605a14c0b3`.
The admission screen still excludes Burn and Mono Red Aggro.

## Exact schedule

Proposed run ID `archetype-budget-h2h-20261126-v3-main1`. Schedule 216
single games with no sideboarding and 108 mirrored seed/deck pairs.
The same engine seed is used in both games of a pair. Seat 1 and seat 2
may receive different hands because the shuffle is bound to engine seat.
Swapping the policy assignments gives each policy both physical seats.

Use seeds **2026112601 through 2026112612** inclusive. These differ from
rerun3's `2026112501` through `2026112509`. Iterate seeds in ascending
order, the deck rows below in order, and candidate seat 1 followed by 2.

| Deck index | Identical deck in both seats |
| ---: | --- |
| 0 | Blue Control |
| 1 | Dimir Control |
| 2 | Drain Deck |
| 3 | Midrange |
| 4 | Ramp |
| 5 | Tempo |
| 6 | Tokens |
| 7 | Tribal |
| 8 | White Weenie |

Cell index is `18 * (seed - 2026112601) + 2 * deck_index + candidate_seat - 1`.
The schedule is the ordered JSON array of objects with keys `index`,
`deck_a`, `deck_b`, `seed`, and `budgeted_seat`. Its SHA-256 is
`205d23c90e200fddbdba77cd10daec2aceb61d2727f72101cc72db7d55e11cf9`
over canonical UTF-8 JSON with sorted keys, compact separators and no
trailing newline. The future driver must regenerate and verify this
schedule before it admits a run.

## Evidence and acceptance

- Reference the current v3 strength verification boundary. Keep per-action
  state/RNG/card-order digests, full sequential replay and per-action
  restore checks. Keep selected first, every-100th and final handler/SQLite
  parity. Use the 512-action checkpoint interval and a 23 MiB trace cap per
  cell. Report quota refusal as unresolved, with no truncated trace used
  as completed evidence.
- Pin the clean checkout and hash-locked runtime, schedule, seed roster,
  exact policy and budget before issue. Attach the cutoff reason,
  retained-branch availability and decision CPU/wall telemetry to the
  private evidence in the future driver. The clock cutoff is host-sensitive.
  Replay checks the recorded actions and state transitions. Recalling the
  timed policy would not reproduce elapsed-time decisions reliably.
- Score verified wins 1, draws 0.5, losses 0. Deck-out follows the engine.
  Pauses and resource limits are unresolved. Report the complete scheduled
  denominator, resolved-only score, and lower and upper score bounds
  overall and per deck. The endpoints assign unresolved outcomes 0 and
  1 for bounding. They are not classified as losses or wins.
- Bootstrap 2,000 replicates with sampler seed `271828`. Resample 12
  whole seed labels with replacement. Each draw keeps all nine decks and
  both seats for that seed. Use the 50th ordered pessimistic replicate
  and 1,950th optimistic replicate as the interval endpoints. Freeze the
  acceptance gate at **score lower bound ≥ 0.45** and **95% lower endpoint
  > 0.40**. Report pause rates and per-deck breakdowns separately.
- Require terminal accounting of all 216 cells, valid traces for resolved
  outcomes, no replay/parity divergences or integrity errors, and actual
  child closure with a closed registry. An incomplete or invalid campaign
  fails the gate even if bounds from early rows could pass. Record either
  outcome. No resume, replacement seeds, or retrospective threshold
  changes. The finding applies to this deck roster and exact cutoff.

## Admission and budget

Use eight one-core workers with 2 GiB per worker. Require at least nine
allowed CPUs including the controller and 17 GiB available memory at
admission. Use v3 host-sleep and child-closure guards, with a 4,800 CPU s
and 6,000 wall s **combined generation-and-verification cap per cell**,
10,000 actions and 100 turns. Run alone on an idle host. Peak trace
allowance is about 4.85 GiB across 216 cells, plus private DBs and receipts.

The historical 156 resolved unlimited-Master mirrors averaged 423.8 s
including verification. Applying that observed resolved-cell rate gives
**25.4 worker-hours and 3.2 elapsed hours under ideal eight-way use**.
At 600 s per game the estimates are 36 and 4.5 hours. Resolved-cell
observations omit timeouts and cannot bound the new policy. The sum of
per-cell wall ceilings is 360 worker-hours.

Propose a separately approved **52 worker-hour** campaign allocation.
Keep it separate from the strength rerun's allocation and preserve all
existing ledger records. Reuse v3 slot-time charging and issue under
one new unique run ID. At eight workers the conservative admission
reserve is `8 * 6000 + 60 = 48060` worker-seconds. From the proposed
`187200` worker-seconds cap, a full-reserve launch decision therefore
requires no more than `139140` charged seconds so far (38.65 worker-hours).
That leaves headroom above the 36-hour planning scenario. The reserve can
leave some cells unstarted even below the cap. Budget exhaustion is a
recorded incomplete result under the same acceptance gate. Publish
only aggregates after the operator records the terminal outcome.
