# Task 3.3 opponent-archetype replay priors

## Status and boundary

October 15 follow-up: the extractor now retains explicitly supplied valid
archetype labels and action indices; see
[the executed extraction checks](task33-extracted-context.md). It still does
not infer missing producer fields or create qualified game data. The producer
inspection below describes its stated historical base, not the new extractor.

Code and synthetic component controls only. Task 3.3 is **not complete**:
immutable base `ba3b8fb34a005b6a4ca6386851b481af96894370` contains zero
committed `training_runs/` files, so no genuine qualified matchup priors were
rebuilt. No synthetic fixture is a game, learned artifact, or strength claim.

Authority: `docs/plans/2026-09-09-ai-knowledge-base.md`, Task 3.3.
The plan's claim that `opp_archetype` already exists in trace JSON is false
for this base. `analytics.decision_quality.build_trace_payload` emits neither
archetype alias nor an execution index; `scripts.extract_training_examples`
does not retain those fields; `training.dataset.baseline_teacher_config`
sets `opponent_archetype` to `None`. These producers are intentionally untouched.

Owned paths: `backend/ai/log_priors.py`,
`backend/scripts/build_ai_log_priors.py`, only
`AIAgent._historical_cast_timing_bias` in `backend/ai/agent.py`,
`backend/tests/test_log_priors_archetype.py`, and this document.
Integration belongs to the parent. Do not replace the parent agent module;
apply only the function-specific agent patch. No commits, pushes, parent
writes, live/private traces, database reads, or dependency copies are required.

## Context contract

- Accept explicit string `opp_archetype` or `opponent_archetype`, validated
  against the existing `ai.deck_analysis.ARCHETYPES` vocabulary, without calling
  its classifier. Store lowercase keys. Conflicting aliases, unknown labels,
  non-string values, and missing labels provide no matchup context.
- Add `opponent_archetypes` only when at least two known contexts each have
  three casts. Each row has casts, average turn, early/mid/late rates, and
  preferred minimum turn. Land plays retain their legacy aggregate contribution
  but do not manufacture matchup cast samples.
- Logs require the next cast/activation to match the physical `pid` actor:
  factory names `Player A`/`Player B`, or an explicitly supplied `player_name`.
  Custom names without explicit association are unavailable. A new trace,
  malformed trace, mismatched actor/card, or consumed cast cannot reuse context.
  Card ownership is not actor identity. Never infer an archetype from either
  hand, a deck name, card names, hidden lists, or private observations.
- Standalone builders keep context local to each supplied trace/example.
  Legacy aggregate counters and board-role calculations remain unchanged,
  including their preexisting thresholds and log/example overlap behavior.
- `_merge_card_rows` adds actual context rows with cast-weighted averages and
  deterministic ordering. Returned nested rows do not alias either input.
  Summary rows cannot prove event uniqueness: export reconciliation happens
  before context aggregation, not by guessing identities from summaries.

## Offline export reconciliation

From `backend/`, use an explicitly prepared, provenance-reviewed export root:

```sh
python3 -m scripts.build_ai_log_priors --training-root /absolute/export/root
```

This mode never imports the SQL path or reads the main/live database. The
no-argument CLI retains its existing database behavior using lazy imports;
it was not executed during qualification.

The offline context path requires an existing export directory, explicit
string/integer `game`, nonnegative integer **supplied** `action_index`, valid
physical `pid`, and integer turn. `action_index` must identify the same executed
action across trace and example exports in that directory/game. This code
never generates it, persists it into exports, or treats encoded action content
as a unique execution ID. Existing producers do not supply this provenance.

Copies with consistent actor, turn, action type, card, and label contribute
once to context only. Conflicting identities invalidate all associated copies;
missing provenance is counted as unavailable. Distinct directories/games/actions
remain disjoint. Aggregate logs/examples are still counted exactly as before.
Context thresholds apply after reconciling all qualified raw observations,
including individually subthreshold sources. Export files are never rewritten.

No eligible context means `context_available: false`, `saved: false`, and an
explicit Task 3.3 gap report. The existing priors artifact is left untouched.
Unavailability reason counts describe input records, not simulated games.

## Agent confidence and fallback

The existing six-aggregate-casts gate remains. A validated two-archetype
breakdown with three casts in the matching row takes precedence over role
timing. Otherwise the old aggregate/board-role path runs unchanged, including
the three-role-casts gate and stabilize/defend-to-control fallback. The original
penalty/reward coefficients and counter handling are unchanged. Malformed or
unknown context rows cannot override legacy timing. No live database access,
weights, named-card dispatch, or hidden-opponent deduction is added.

## Verification and handoff

The sidecar evidence includes a hard SQL/socket/provider/process denial runner
installed before pytest collection, strict RED logs, final pure controls, full
existing log-prior tests and neighboring consumer/decision tests, and genuine
legacy-function differential executions. SQL native/public/dbapi aliases,
native/public/bare-new sockets, provider imports, and process creation have
negative canaries. No full database/process-enabled backend suite is claimed.

Preimage SHA-256:

```text
a3db65e60e6746ec1c35af8f46cbf422a3520e80336ce71e393675b991d4cd81  backend/ai/log_priors.py
2b0442470fd396e884541fed482367a2506ec0e46837b7a3cf0d3cc2de212719  backend/scripts/build_ai_log_priors.py
1ecf19996f3c57c954ecc003e41459232fb4cc4301d9b29c213e5e59b417da6c  backend/ai/agent.py
```

The evidence report records exact commands, pre/post hashes, a five-path patch,
separate method-only delta, source-boundary byte equality, test counts, review
status, and the verified NFS archive location. Run `graphify update .` in the
owned source root only, after terminal verification. Keep generated graph and
test evidence out of the integration patch. Preserve archived member bytes and
archive SHA-256 before removing successful disposable checkouts.

## P2 corrective increment

The original frozen NFS stage is preserved separately. Context reconciliation
now accepts qualifying examples without a board-role hint, so a conflicting
duplicate cannot hide behind that aggregate-only field. The legacy aggregate
reader retains its role-hint filter and exact counting behavior.

Context timing validation rejects nonfinite and overflowed numeric values,
including preferred minimum turn, rather than interrupting agent fallback.
The six-line agent delta, coefficients and thresholds are unchanged. New
synthetic controls reproduce both peer findings before implementation and
compare actual fallback result bytes. Whole original pure modules run without
node selection/deselection; the six original SQLite/autoplay node IDs and their
fixture seams are recorded separately for parent-owned full-I/O qualification.
These corrections do not fill the genuine-training-data gap or complete Task 3.3.

Further typed-row controls guard role-hintless unhashable action types and raw
integer turns that overflow before payload averaging. Complete identifiable
non-cast copies participate in provenance contradiction checks but never supply
cast timing samples. Rejections remain context-only; legacy aggregate admission,
counts, and the six-line agent delta are untouched. The prior 321-test whole-pure
gate belongs to its exact preceding snapshot; the final component gate and
parent-owned composed-source full-I/O gate are recorded separately.
Raw-trace action association also requires a string action type before membership
checks; malformed action values leave all legacy aggregate bytes unchanged.
