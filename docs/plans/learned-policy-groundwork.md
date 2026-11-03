# Learned Policy Groundwork

## Current Status: November 3

The experimental learned-policy candidates remain inactive and unfinished. C19
candidate preserves the 1,358 retained ranking floors, including 1,328 strict
comparisons, but still makes two confirmed costly-creature choices for Village
Rites in the reused development checks. Two other disagreements about Opt are
not established misplays. Passing training constraints is not evidence of
general playing strength, and these development cases are not held-out tests.

### Latest C20/C21 Trials

Sixteen new controlled cast-versus-pass examples completed with native actions,
exact branch replay, private-input checks and finite provenance screening. They
contain eight semantic situations, both player seats and 32 action occurrences.
Their conditional preferences cover keeping a valuable creature when unthreatened
and responding when removal has actually been paid. These are not expert labels
or terminal returns. The eight-worker collection completed in 94.70 seconds;
the separate eight-worker numerical encoding completed in 20.73 seconds and
matched the original forward-pass scores without changing any model weights.

Two actual fits then used 143 observed-return rows and those 16 preferences,
retaining physical multiplicities and source epochs. Both started from C18, not
from a previously rejected point. Both were rejected by the final original-loss
ceiling of `1.4735657523454184`:

| Trial | Iteration Limit Reached | Final Original Loss | Result |
| --- | ---: | ---: | --- |
| C20 | 384 | 1.4735882896330614 | Rejected |
| C21 | 1,536 | 1.473565801970536 | Rejected |

Neither optimizer converged. Later acceptance checks were not reached after the
ceiling failure, so no complete retention pass is claimed for either returned
point. C21 reduced the new preference loss from 18.08 to 0.41, but lower training
loss does not override a failed gate. Neither point was exported, evaluated on
the development cohort or activated. Process closure and source/input integrity
checks passed; these were scientific acceptance failures, not resource timeouts.

Separate training-only diagnostics have now measured the later checks without
rescuing either rejected fit. C20 passed the retained comparisons and older-data
bound but failed the original-loss ceiling. C21 also missed the unchanged
ranking-floor tolerance: its minimum residual was about `-1.55e-12`, below the
permitted `-1e-12`. A fixed bias diagnostic measured 19 heads in 11.42 seconds;
none supplied a feasible proposal. No optimizer, encoding or gameplay ran.

A separately planned diagnostic then measured 27 fixed interpolation points
between C18 and the rejected endpoints in 12.24 seconds. The midpoint toward C21
passed all original numerical gates and an additional original-loss safety
margin. It was selected by the predeclared largest-passing-step rule, not by
development answers or preference accuracy. Its new training agreement is only
8/16, compared with 6/16 for C18 and 12/16 for rejected C21; numerical acceptance
is not evidence of better play. Both diagnostics preserved source, inputs and
weights and closed their processes cleanly.

### C22 Construction and Development Result

That single midpoint was constructed under separate C22 provenance and passed
the unchanged numerical gates. Official save/load verification preserved all
16 tensors exactly. This is a parameter construction, not a converged fit or
retroactive C21 success. The initializer's older engine contract remains recorded
separately from the current checkpoint contract. An initial serialization run
failed because its observer counted the loader's internal checkpoint call as an
extra external call; that failure is retained. A separate observer-only correction
verified the actual public and internal call boundaries without changing weights
or serialization code.

The complete original 76-case development cohort then ran in 98.75 seconds:
20 public decisions, six resource witnesses, eight sacrifice decisions and
42 draw checks. C22 met 14 of the 16 scored public targets and six of the eight
sacrifice targets; all 42 draw checks passed. All 28 public/sacrifice actions and
their recorded material effects were unchanged from C19, as were the six
resource witnesses. The same two costly Village Rites sacrifices remain. The
two Opt disagreements are still not established misplays. This is a quality
hold, not 76 passing checks or evidence of improved play.

Both confirmed mistakes occur on the opponent's end step, where the own-main
anti-stall override is inactive. A two-position passive score trace is being
prepared to distinguish model ranking from tactical classification; no cause
has yet been established. A separate training-only capacity diagnostic is also
being prepared. Neither admits development answers into training. A broader,
naturally dealt, seat-balanced comparison is prepared but has not run with this
candidate. C22 remains inactive; private observations, features and weights
remain protected inputs.

### C19 Development Record

New supervision separates conditional heuristic preferences from observed
game returns. C19 retains 38 conditional preferences and adds 47 observed-return
examples: 40 earlier observations and seven joined current-root actions. These
are not expert demonstrations. One bounded head fit reduced error on those 47
examples from 1.59 to 0.41, but older-data loss rose within its declared bound.
The optimizer reached its 384-iteration limit without convergence. Original
engine provenance is retained; iterations are not a count of accepted updates.

A source-current batch ran eight controlled-root continuations concurrently on the
current engine. It accepted and replayed 2,212 actions exactly. Seven branches
reached natural win/loss outcomes; one exhausted its work budget and retains a
null outcome. These are deliberately selected training roots, not eight fresh
unbiased games or a strength comparison. Equal returns in a pair do not supply
an action preference. Exact input/action joins admitted seven root observations
for the fit above. A separate extraction admitted 96 continuation observations
and excluded 16 unfinished-game samples. Nine semantic duplicates of earlier
observations remain explicitly recorded; these are not 96 independent games.
The additional 96 were not part of the C19 fit.

The complete source-bound 76-decision cohort ran: 20 public decisions, six
resource witnesses, eight sacrifice decisions and 42 draw checks. All 42 draw
checks passed, but C19's actions and recorded payment/material effects were
identical to the previous candidate in all 28 public/sacrifice comparisons.
The two confirmed costly-sacrifice errors remain. The first attempt lacked a
canonical test fixture in its isolated package; that partial result is retained
separately from the complete, same-checkpoint run after exact fixture restoration.
Lower training loss has not established better decisions. The targeted training
above addresses declining costly casts, with profitable-sacrifice controls; it
does not replace the original tests or establish expert supervision.

An independently checked [escape-fuel search improvement](../escape-mana-fuel-bound.md)
reduces an impossible-payment search without changing spell costs or payment
choices. The selected regression cohort passes 321 cases. This fixes an engine
latency problem, not learned decision quality. Private traces and model files
remain protected artifacts, not public fixtures.

The next candidate must use the new admissible evidence, retain earlier
regressions, pass the current source/encoding contract, and demonstrate better
native decisions and broader seat-balanced play. No current campaign win-rate,
expert-play, live-policy or complete-AI claim is supported.

## Historical Status: October 29

Offline neural Q/V fitting and source-bound evaluation are implemented and have
run. The latest candidate completed 912 optimizer updates on 452 preference rows,
with 204 observed terminal value targets and 248 preference-only rows. Its
export agreed with the trainer on 1,040 checked action predictions. This fresh
deterministic fit reproduced the previous weights on the same data; it establishes
source compatibility, not improved strategy.

The candidate remains inactive. Raw idle choices are correct on only 2/6 reused
checks, land choices on 8/16 roots, and held-out preference agreement on 27/47
examples. A captured decision took about 98 seconds. A planned 24-game comparison
stopped after ten attempts: nine natural completions, one baseline combat
timeout, and fourteen unstarted games. It does not establish a campaign win rate
or expert play. Two prowess-order regression cases overlap training and are not
independent generalization evidence.

Work continues on decision latency, rejected actions and training coverage.
New data comes from recorded native games with replay-checked actor views and
observed outcomes, not evaluation answers. Five new examples passed finite
provenance and duplicate screening; the additive 457-row dataset passed validation
with all original rows unchanged. Missing historical continuation frames remain
an explicit evaluation limitation, and future evaluation must exclude the sealed
training origins. This prepared dataset has not been fitted. Private game traces
and model artifacts are not public fixtures.

The earlier groundwork status below is historical, not a claim that no fitting
has occurred. The full gates remain applicable; successful fitting and regression
tests do not complete gameplay-quality, broader evaluation or live deployment.

## Earlier Groundwork

The deterministic [training environment](../testing/training-environment.md)
is implemented for built-in decks, private observations, accepted complete
actions, terminal rewards and snapshot restoration. Its action encoding is
partial; some pending choices still require explicit encoding work. The composed
adapter/AI/input/metadata gate passed 323 checks; this is not a trained policy.

The [versioned dataset exporter](../testing/training-dataset.md) is implemented
with actor-private observations, complete accepted action labels, provenance,
bounded immutable shards and explicit incomplete outcomes. Its teacher is a
generic heuristic, not expert supervision. Grouped datasets without a held-out
partition explicitly report NOT evaluation-ready.

At this earlier stage, complete choice encoding, useful feature coverage, expert
data, training and learned-policy evaluation remained unfinished.
Canonical metadata, rulings evidence and tactical tags are knowledge inputs,
not learned gameplay or proof of effect execution. No neural policy had been
trained or deployed at that stage. Heuristic self-play is still not expert
supervision; the current offline results above do not authorize deployment.

## Step-By-Step Gates

1. Verify canonical metadata and complete mechanics for a declared initial corpus.
   Record card/face/Oracle/rulings provenance separately from execution coverage.
   Preserve explicit unsupported and ambiguous effect clauses. Expand the corpus
   as validated mechanics land; do not wait for every Magic card to start learning.
2. Expose a deterministic training environment around the authoritative engine.
   Observations use the existing private AI boundary; only permitted information
   reaches the policy. Legal actions, pending choices and terminal rewards remain
   engine-generated. Illegal policy outputs cannot mutate gameplay state.
3. Export versioned observation/action/choice trajectories and engine/deck hashes.
   Keep private replay evidence out of public fixtures. Split evaluation by seed,
   deck family and retained tactical position; prevent duplicated games or future
   observations from leaking into training examples.
4. Establish a move-ranking/value baseline, initially using verified decision
   examples and suitable expert trajectories. Separate provenance-backed expert
   decisions from current heuristic demonstrations; weak self-play is not expert
   supervision. Specify action encoding, legal masking and uncertainty handling.
5. Train offline with reproducible checkpoints and bounded resource budgets.
   Begin with a small supported corpus; measure sample efficiency and inference
   latency before choosing a larger network or committing expensive compute.
6. Add self-play against a varied opponent population. Preserve engine legality,
   hidden-information limits and loss/draw rules. Validate reward accounting; do
   not force win-rate targets, fabricate cards or rebalance canonical decks.
7. Compare frozen policies against the existing baseline on held-out, seat-balanced
   games and tactical fixtures. Measure missed deployment/land/lethal opportunities,
   resource/counter timing, blocks, illegal outputs, stalls and latency. Report
   sample sizes and uncertainty; matchup win rate alone is insufficient.
8. Integrate behind an explicit policy version/feature switch with deterministic
   inference where configured, fallback and rollback. Persist policy and engine
   provenance in snapshots/results. Keep learning out of live match mutation.

## Acceptance Still Needed

- A concrete observation/action schema and tested adapter for all supported
  pending choices; no opponent-hand or unseen-library access.
- Train/evaluate commands, reproducible dependency/compute requirements, dataset
  manifests, checkpoint loading and offline behavior.
- Before/after evidence on unseen decks and seeds, not just successful training
  or a fixed scripted position. No current seasoned-player guarantee.
- Human review of expert-data availability/licensing and any paid compute budget
  before collecting proprietary data or launching paid training infrastructure.

## References

AlphaZero combines learned policy/value evaluation with search and self-play:
https://deepmind.google/research/alphazero-and-muzero/
AlphaStar combines imitation and reinforcement learning in an imperfect-information
game: https://deepmind.google/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/
These are architecture precedents, not claims of equivalent resources or outcomes.
