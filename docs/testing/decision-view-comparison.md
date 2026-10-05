# Private Decision Comparison

Compare two completed version-one reconstruction JSONL exports without running
AI or modifying a game, deck or database:

```sh
cd backend
.venv/bin/python scripts/compare_decision_views.py \
  --baseline /path/to/baseline-views.jsonl \
  --candidate /path/to/candidate-views.jsonl \
  --output /path/to/new-private-report.json
```

Exit 0 means the specified fields match, 1 means a first divergence was retained,
and 2 means invalid inputs or an output collision. Reports are created exclusively
with mode 0600: differences can contain both players' private cards. Do not feed
them into the AI or publish them as ordinary match views.

The full streams must have matching input provenance and seat orientation,
verified terminal footers, and consecutive decisions with consistent game setup.
Different lengths still compare their entire common prefix. A changed action
before a trailing extra decision is therefore reported instead of being skipped.
Every input is consumed and validated even after the first difference.

By default action metadata is compared strictly. Optional
`--allow-added-combat-metadata` tolerates only newly added candidate action fields
`banding_attackers`, `legal_blocks`, and `blocker_capacities`. Each exception and
its value is recorded. Existing metadata changes and explicit attack/block/band
declarations remain differences. Legal-move inventories are explicitly excluded;
this is a comparison of actual traces and retained private state, not a complete
engine-state equivalence proof or optimal-play verdict.

Twenty protocol/CLI regression cases cover unequal lengths, first divergence,
private-state changes, one-sided exceptions, provenance, malformed/truncated
exports, ordering and private non-overwriting output. Real retained paired-seat
exports provide separate acceptance evidence; the synthetic protocol records in
unit tests are not invented Magic cards.

Final comparator plus existing reconstruction selection: 50 tests pass. The CLI
also processes all six unique retained predecessor comparisons: both Drain/Tribal
and both Tempo/Control streams match after explicit metadata exceptions;
Tokens/Ramp reports first changed actions at decisions 531 and 297 despite
unequal lengths, matching the independent review. Repeated executions are not
additional independent samples. This does not qualify the newer selection
runtime's ongoing natural matrix or constitute a full backend gate.
