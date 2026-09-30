# Seat-Balanced Replay Protocol

The deterministic regression runner now defines its workload before execution:

```sh
cd backend
python scripts/regression_matrix_replay.py --max-decks 3 --matches-per-pair 1 --best-of 3 --max-ticks 3000 --output training_runs/balanced-smoke.json
```

Run diagnostics in a disposable source checkout: the SQLite path is relative to
backend source, so changing working directory alone does not isolate database writes.

## Schedule and Accounting

- Each unordered deck pair receives `--matches-per-pair` seeds. Each seed runs
  both seat orders; `--single-seat` opts into the legacy, unbalanced smoke mode.
- Each logical series is executed twice to test repeatability. The second
  execution is not another independent match or a win-rate sample.
- Seeds derive from SHA256 of canonical pair names and index. Each game records
  its series seed plus game index. The schedule is deterministic for identical
  selected deck names/order; renamed decks change seeds.
- With D selected decks and S seeds per pair, the default workload is
  `D * (D - 1) / 2 * S * 2` logical series, each repeated twice. BO3 can use
  additional slots for resolved draws, bounded by the existing draw cap.
- Complete repeated result dictionaries must agree, including individual games,
  timeouts, seeds and normalized logs, not just aggregate winners or hashes.
- `winner` remains a seat number. `winner_deck`, `wins` and pair `outcomes`
  use canonical deck identities; `deck_a_seat` makes the orientation explicit.
- A series with any timeout is unresolved even if another game supplies a
  series winner. Unresolved results are counted and excluded from the
  completed-series win-rate denominator. No completed series means a null rate,
  not zero. A draw-cap result is not an ordinary defeat.
- Anomalous logical runs retain their complete normalized trace; nondeterministic
  repetitions also retain the repeat trace and first-divergence context.

## Verification (2026-09-30)

- Final-source backend suite: 1,685 passed, 173 warnings. Frontend lint,
  production build and unit contracts passed; full Chromium actions, recovery,
  simulator, sideboard and all three controller-mode BO3 flows passed.
- Final-code BO3 smoke: three archetype templates (Aggro, Burn, Midrange),
  one seed per unordered pair, both seats: six logical series, 13 games,
  zero reported anomalies, timeouts or determinism failures. Repeatability
  executions are excluded from those counts. This is not tournament-list or
  statistical-strength validation.
- A separate final-code two-deck BO1 smoke completed both seat orders without
  reported anomalies or determinism failures. An earlier three-deck pilot
  used a different selected corpus; its results are not pooled with final evidence.
- Accounting tests cover seed pairing, identity mapping, unknown win rates,
  timeout exclusion, positive workload validation, per-game seeds and metadata
  drift despite matching aggregate hashes/logs.
- Local full-suite/browser logs and final replay JSON are retained in ignored
  `backend/training_runs/seat-balanced-replay-20260930/`.

## Known Limitations and Next Upgrades

This diagnostic runner starts seat 1 each game and does not apply sideboards or
the interactive previous-loser play/draw policy. Swapping seats balances that
diagnostic starting-seat bias, but does not establish live BO3 transition parity.

Paired seeds and determinism repeats are correlated, not independent statistical
samples. No confidence interval or seasoned-player/balance claim is inferred.
Predeclare a larger independent seed corpus, cluster-aware uncertainty, corpus
coverage and accepted timeout rates before strategic certification. Snapshot
restart equivalence and wider supported-mechanic golden fixtures remain open.
