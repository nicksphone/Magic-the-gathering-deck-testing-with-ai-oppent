# Current Resource-Conditioning Checks

Backend source: `029a3174`. This is constructed canonical decision research,
not complete games, expert labels or accepted model weights.

## Fresh Data

Sixty-four checked Impulse/Anticipate setups cover both seats, own main phase,
opponent upkeep/end step, and upkeep without a retained Counterspell. TRAIN uses
three/four lands; predeclared development uses two/five. Semantic deduplication
leaves 16 rows per partition, with no cross-partition semantic overlap or
conflicting labels. Labels come from the current strong Control heuristic.

Every setup checks both proposed actions, root/RNG purity, hidden opponent-card
identity invariance and snapshot restoration. All 2,649 recorded backend inputs
match before and after. No old protected feature/model body or old development
row was imported. Collection took 63.37 seconds, with native SQL, sockets and
subprocesses denied.

## Matched Fits

All fits use seed 17, learning rate 0.003, temperature 0.25, no value targets,
256 optimizer updates and 512 row exposures. Only TRAIN rows reach the fitter.
TRAIN-only duplication balances cast/pass mass; it does not create new examples.

| Encoder | Head | TRAIN | Development | Complete Contrast Groups |
| --- | --- | --- | --- | --- |
| Trained | Existing life-context | 8/16 | 8/16 | 0/2 |
| Trained | New state-product | 10/16 | 10/16 | 0/2 |
| Fixed initial encoder | Existing life-context | 14/16 | 14/16 | 0/2 |
| Fixed initial encoder | New state-product | 12/16 | 10/16 | 0/2 |

**All four checkpoints are rejected for activation.** In particular, the 14/16
aggregate does not pass the resource-switching requirement: it misses both
TRAIN and development pass cases. The fixed-encoder follow-up reuses already
examined development, not an untouched confirmation set. Its experimental
factory adapter is a research intervention, not a new production training default.

The two end-to-end fits took 162.57/162.52 seconds; the fixed-encoder fits took
96.77/96.43 seconds. These are individual concurrent-run measurements, not an
application speed comparison. Initial attempts stopped before fitting because
the cached training runtime lacked the app's Pydantic path. They are preserved;
the corrected launches append the existing read-only app site-packages without
installing packages or changing data, training budgets or production code.

## What This Changes

A separate TRAIN-only, no-update diagnostic distinguishes the previous locally
flat head from the remaining problem. The trained old head has zero local
state-margin gradient on the upkeep resource contrasts. The product head keeps
that gradient, but its corresponding state distance shrinks from approximately
0.504 initially to `7.82e-5` after fitting. The vectors are not exactly identical.
Fixing the encoder is not sufficient either, so this does not establish
representation shrinkage as the sole cause or justify simply increasing epochs.

The next learning investigation must distinguish TRAIN resource-contrast
separability and numerical/input conditioning before another expensive fit.
There is no new gameplay-strength, unseen-card, BO3 or RC acceptance claim.
Live gameplay and checkpoints are unchanged.

## Protected Evidence

Project NFS archive: `current-resource-conditioning-20261105-qllcLb7B`.
Its 41 regular evidence members, fresh feature buffer and four rejected models
were read back byte-for-byte. They remain private artifacts, not public Git
fixtures. The actual tar name is `source-evidence.private.tar.gz`; its
`train-diagnostic/REPORT.json` contains the latent measurements.
Code qualification is separately archived as
`qv-state-action-conditioning-20261105-ReU6Oy3C`.

## Subsequent Capacity Check

A TRAIN-only closed-form diagnostic separates all 16 directions using the fixed
encoder's interaction features, including after scaling weights into the bound.
A registered-inference readout prototype reaches 16/16 TRAIN but only 6/16
already-examined development and 0/2 development contrast groups. Torch/stdlib
maximum error is `1.81e-16`: generalization, not parity, fails.

The prototype remains rejected; its zero-update header was actually rejected by
live policy binding. No production training API or checkpoint format was added
from this failed experiment. Protected evidence is
`current-resource-readout-diagnostic-20261105-5d0vi1ja`. This is not a held-out-card
or gameplay result, nor a reason to add epochs without investigating the failure.
