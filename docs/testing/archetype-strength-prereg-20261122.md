# Same-deck AI playing-strength experiment

This pre-registration fixes one experiment before any outcomes are available.
The candidate is the built-in master heuristic. It is evaluated against four
opponents on the same deck within each cell. A passing result applies to these
deck lists, policies, seeds, limits and rules. The RC health result and the
original cross-archetype statistical matrix retain their separate scopes.

## Schedule and agents

The run ID is `archetype-strength-20261122-v3-main1`. Use the nine admitted
built-in lists from the health run. Burn and Mono Red Aggro retain their
existing admission exclusions. Each deck plays itself against each opponent,
with both seat orientations and the same engine seed within an orientation
pair. Nine seeds, `2026112201` through `2026112209`, give
**9 decks × 9 seeds × 4 opponents × 2 seats = 648 games**. The candidate,
master, plays seat 1 in one cell and seat 2 in its partner. Seed and seating
are fixed before execution. The schedule interleaves comparisons within each
deck and seed. Games are single games with no sideboarding.

| Opponent | Policy |
| --- | --- |
| Random | Uniform among unique checked completions of the available move offers, using a private PRNG derived from the deck and engine seed and shared by the pair. |
| Casual | Built-in `AIAgent(difficulty='casual')`. |
| Strong | Built-in `AIAgent(difficulty='strong')`. |
| Master | Built-in `AIAgent(difficulty='master')`. Both seats use the same policy. |

The engine lists move offers. Some are complete actions while others leave
choices such as targets, payment or combat assignment to the player. A
uniform draw from the raw list would sometimes submit an incomplete action.
For random, the harness uses the authorized decision view and the existing
casual action completion helper. Mechanic choices get empty and singleton
proposals for exposed selectors and a built-in completion for more complex
choices. Combat declarations receive the existing declaration completion.
The harness normalizes proposals, checks them against the authoritative
engine, deduplicates equal actions, then samples once. The sampling population
is the resulting checked completions. It does not enumerate all combinations
of all legal targets, payments or combat assignments. An empty population
fails visibly. The game RNG is separate from the sampler. The built-in agents
choose without a learned policy binding, and the engine checks their actions.

The master mirror is a label-swap control. Because both seats use the same
policy and deck with the same engine seed, a valid pair should give
complementary candidate scores. This checks pairing, seat mapping and
determinism. By design it offers no independent strength evidence.

## Scoring, intervals and claim

A verified win is 1, a verified draw is 0.5, and a verified loss is 0. A cell
without a verified genuine outcome is unresolved, including timeouts, quota
or other limits, divergences and missing cells. Report counts, resolved-only
mean and bounds across all scheduled cells, overall for each opponent and
separately for each deck. The lower bound divides verified points by scheduled
cells. The upper bound adds one point per unresolved cell before dividing.
These endpoints express uncertainty about unobserved outcomes. They do not
classify any unresolved cell as a win or loss.

Primary intervals use 2,000 percentile bootstrap replicates, fixed sampler
seed `271828`, with the 2.5th and 97.5th nearest-rank percentiles. Resample
whole seed labels with replacement, keeping both orientations for every deck
within each sampled seed. Each seed is reused across decks, so resampling
deck/seed pairs as independent observations could overstate precision.
Use pessimistic completion for the lower percentile and optimistic completion
for the upper percentile. With complete outcomes this reduces to the paired
seed-block interval on the observed scores. The interval describes variation
across the nine seed clusters within this fixed deck set. Claim thresholds
are applied jointly as a single gate, with separate descriptive intervals
for each comparison.

| Comparison | Pre-registered requirement |
| --- | --- |
| Random | Lower score bound ≥ 0.80 and lower 95% interval bound > 0.65. |
| Casual | Lower score bound ≥ 0.80 and lower 95% interval bound > 0.65. |
| Strong | Lower 95% interval bound > 0.50. |
| Master control | Interval contains 0.50 and all mirror pairs are verified and complementary. |

An overall pass requires all four comparisons, a complete schedule accounting,
valid source/runtime evidence, actual child closure and a closed registry within
the cap. Censored observations may clear a non-control comparison only if its
requirements still hold at the pessimistic endpoint. An interrupted or invalid
run fails. Retain and report the result either way. Do not change thresholds,
replace decks or seeds, resume, or relabel failure after seeing the result.
This is a scoped claim about playing strength against these policies and the
declared random-offer baseline. It makes no claim about arbitrary decks,
human performance, a target win-rate against other engines, full cross-deck
matrix acceptance or release certification.

## Time, registry and evidence

- The upper planning benchmark supplied by the manager is about **320 worker-s
  per game** for master against master. At that rate, 864 games would cost
  76.8 worker-hours before overhead. Reducing the 12 proposed seeds to nine
  makes 648 games × 320 s = **207,360 worker-s (57.6 worker-hours)**. This is a
  planning estimate based on the benchmark. Some games may take longer, even
  against simpler policies. The controller charges both worker slots through
  setup, idle periods and closeout.
- The strength campaign record uses ID `mtg-archetype-strength-20261122` and
  the **120-worker-hour** ceiling. The same host/account registry carries the
  existing **62,796.9 worker-s** charge forward. Strength admission requires
  the closed health rerun record and an active ledger carrying at least its
  recorded charges, so an empty registry cannot start this experiment. The estimated cumulative
  charge is **270,156.9 worker-s (75.04 hours)** before additional overhead.
  The initial balance is **369,203.1 worker-s (102.56 hours)** at the reported
  prior charge. Each refill requires two slots through the next or longest
  in-flight wall horizon plus 60 worker-s. At 3,000 s, this requires **6,060
  worker-s**. Use the real registry balance. The 648-cell theoretical maximum
  alone is 1,944,000 worker-s, so the cap can stop launches. Legacy health and
  pilot plans and records retain their existing 48-hour policy and role limits.
  The charge ledger stays cumulative and the strength run ID is consumed once.
- Per-cell limits are **2,400 CPU / 3,000 wall seconds**, shared between game
  and verification, two one-core slots, 2 GiB per worker, 10,000 actions and
  100 turns. Existing deck-out results use the engine rules.
- Each strength trace is limited to **23 MiB**. The 648 trace ceilings total
  **14.55 GiB**. Preflight additional space for requests, outcomes, logs,
  caches and SQLite. Use the v3 action chain, all state/order/RNG digests and
  exact log deltas. Store full initial/final states and full checkpoints
  every 256 actions and at the terminal action. Reconstruct selected
  first/every-100th/last handler and SQLite parity boundaries by replay,
  including before/after snapshots, whether or not a stored checkpoint exists
  at that action. Every action still receives exact replay and serde checks.
  A trace cap failure remains unresolved. Earlier traces and policies retain
  their original checkpoints, limits and readers.

## Operator commands

After merge and CI, use a clean disposable checkout of that revision under
the same account as earlier runs, on the existing host registry at
`~/.local/state/mtg/archetype-v3`. Use Linux CPython 3.12.3 and a fresh venv with
the full application hash lock installed from `backend/requirements-py312-linux.lock`.
Use an idle host with three available cores, 5 GiB memory headroom and a private
output parent. Review the prior closed charge record before issuing the plan.
Both plan and output paths must be fresh and outside the checkout.

```sh
cd /absolute/clean-checkout/backend
/absolute/fresh-venv/bin/python -B -m scripts.archetype_strength_v3 plan \
  /absolute/private/strength-main1-plan.json
sha256sum /absolute/private/strength-main1-plan.json
```

After reviewing the plan and recording the exact revision, runtime and plan
hash, launch once under the same environment:

```sh
/absolute/fresh-venv/bin/python -B -m scripts.archetype_strength_v3 run \
  /absolute/private/strength-main1-plan.json /absolute/private/strength-main1-out \
  --execute-strength
```

Keep the CLI exit and the terminal report SHA256 alongside the matching closed
registry record and its final charges. Publish the comparison aggregates and
result either way. Keep the raw traces private. An exit 0 with a matching
closed record and a true `strength_passed` field is the success evidence for
this schedule.
