# Backend Capability Batches

Work is grouped into capabilities, not individual cards. This changes execution
cadence, not the original rules, AI or release requirements in `plan.md`.

## Batch Protocol

1. Choose two to four connected capabilities with a shared engine boundary and
   concrete acceptance criteria. Reproduce the current failure before editing.
2. Use canonical card metadata and both seats. Implement shared rules/effect/cost
   paths; keep unsupported clauses visible rather than inventing behavior.
3. Run focused regressions after each change. Include state purity, legality,
   costs/targets, event ordering and durable continuation where applicable.
4. At the batch gate, run the full isolated backend suite and relevant frontend
   gates. Shared public state/actions/recovery require browser coverage; an
   isolated heuristic need not repeat unrelated visual checks after each edit.
5. Compare pinned, seed- and seat-balanced replay inputs across several deck
   styles. Retain hand/board/legal-action traces locally for investigation and
   distinguish repeated executions from independent samples.
6. Review anomalies before claiming success. A semantic fix may intentionally
   change old decisions: compare optimizations against an actor/rules-correct
   reference, not against preservation of the original defect.
7. Publish one verified capability milestone: README features/limits, plan status,
   changelog, Graphify and code commit. Archive verified evidence on RCHFiles;
   remove only completed owned scratch and leave live databases/services alone.

Backend tests run in tracked-source copies because SQLite paths are source-relative.
After a late isolated change, rerun its affected gates and record exactly which
source revision each broader run checked. Never present earlier evidence as an
unchanged final-source run. Timing comparisons run separately from heavy gates;
instrumented profiling is not a latency benchmark.

## Replay Inputs

In an isolated checkout, export resolved inputs with the existing matrix runner:

```sh
python scripts/regression_matrix_replay.py --max-decks 6 --matches-per-pair 1 \
  --write-deck-manifest /local/scratch/decks.json --progress \
  --output /local/scratch/baseline.json
python scripts/regression_matrix_replay.py --deck-manifest /local/scratch/decks.json \
  --matches-per-pair 1 --progress --output /local/scratch/candidate.json
```

The manifest preserves selected order and resolved card data, includes a canonical
corpus hash and records source provenance. Import validates the entire manifest,
even decks outside `--max-decks`, verifies the digest and bypasses database
bootstrap/hydration. Reports record the file, source-corpus and selected-corpus
hashes. A hash verifies consistency, not Scryfall authenticity or card support.
Names-only decklists are not resolved manifests. Keep inputs and traces private
when they contain user decks; archive completed evidence, not active SQLite, on NFS.

## Upcoming Batch Boundaries

- Extend latency investigation beyond the completed decision-local projection
  reuse batch. Its two late-control hotspots improve 67-78%, but other multi-second
  decisions remain. Preserve checked decisions, choice-policy side effects,
  hidden-information boundaries and mutable-state isolation.
- Hidden-information invariance, harmful forced non-pass fallback repair, public
  pending-choice branching, future-turn resources and response likelihoods,
  evaluated across control, tempo and proactive styles. Preserve useful friendly
  targets/self-sacrifice; use demonstrated outcomes, not blanket card bans.
- Shared mixed/paid/triggered mana and continuous-effect interactions, each with
  canonical fixtures, layers/events and live/replay parity.
- Broader effect-created exile permissions and conditional effects, preserving
  ownership, chosen faces/costs and restart continuations.

These are scheduling groups, not completed features or a reduced release scope.
Rules correctness remains ahead of AI strength. The competitive table v2 is live;
long-session UI, accessibility and deployment validation remain unfinished.
