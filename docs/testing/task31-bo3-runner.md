# Task 3.1: Offline Fixed-Board BO3 Runner

Implementation base: 46158ddb40a2e67e27a37c0854eba8d2bc05a281 plus this
reviewable increment. Pure protocol qualification is NOT native gameplay,
AI-strength, Phase3 completion or permission to execute the matrix.

## Route

`matchup_round_robin.run_round_robin` -> existing `run_match(best_of=3,
game_runner=play)` -> existing `run_game(trace_builder=trace,budget=budget,
record_game=record)` -> unchanged complete_action/checked_action.
The actual action, full legal menu and engine are not substituted. Builder
receives the retained AIDecision (None for the legacy no-legal pass branch),
before checked_action, and delegates to shared build_trace_payload with actual
reasoning/anonymous knowledge_usage. ResourceBudget accepts the candidate and
inserts exactly one trace. No second rules loop or reference policy.

The no-hook path reconstructs the complete original run_game/run_match AST;
controlled default results/logs/hash compare equal. Genuine engine/default-hook
parity and whole mixed replay modules remain separate runtime qualification.

## Explicit Offline Input

A prepared JSON export has schema_version=1, source_commit=the base above,
builtin_sha256=236bc11807d9aeea3134c2b1ec9d1fa73a29d9dc366bf0e11a79ed605a14c0b3,
corpus_sha256, decks_sha256, decks and sideboard_mode='fixed_no_swaps'.
`make_export` hashes a structurally valid complete roster; it does NOT certify
Oracle authenticity or metadata provenance. The external canonical corpus/export
must be separately source-bound and reviewed before actual execution. The run
also checks exact shipped template inventories and existing ready_for_match.
No repository ensure/hydration refresh/network fallback is invoked.

Each row has source='builtin', the exact unique shipped name, no invented id,
mainboard and explicit sideboard (including an empty list), typed positive int
quantities and complete printed fields. Main size60..250; side size0..250.
Unknown classification remains unknown, not name-inferred or dropped. Identity
is existing source-name cohort_identity; both orientations share the existing
cohort_pair_seed in canonical pair order. Content/roster/source hashes are
provenance, not object acquisition or import/execution authority.

11 builtin decks schedule55 pairs /110 mirrored BO3 series per supplied token.
These are planned counts, not executed gameplay. Token bool/float/negative/
duplicate values reject. Root game slots use existing game_seed. Loser chooses
next start; draw0 retains chooser/consumes a slot but no win. Six draws stop as
unresolved draw_cap. WinnerNone/timeout/error stops the actual series. No forced
outcome, seat relabeling, adaptive-sideboard claim or repeatability double-count.
Both main and side inventories/bodies remain unchanged; even nonempty admitted
sideboards are fixed, never silently discarded. Game input copies are checked
for mutation after return. A later setup error preserves earlier actual game
deliveries/receipts; no constructor failure is invented as an executed game.

## Trace, Budget And Stops

One explicit ResourceBudget per BO3, one deadline and cumulative batch counts
across games. Limits JSON must contain exactly existing policy keys and cannot
widen their values. max_ticks and difficulty are explicit. There is no claim
that these construction/write limits bound total memory, CPU or whole-run
storage. Constructor work happens before begin_game, on admitted bounded boards;
a failed constructor has no fabricated state/log/game. The scheduler records
execution_error and preserves earlier deliveries. Future parent execution needs
separate process memory/time, overall-run and writer/resource closure controls.

`record_game(result_copy,raw_log_copy)` receives actual last accepted RAW before
normalization. Its return cannot override outcome. Four fields survive:
complete=True, exact int bytes, raw_sha256, and reference='game-NN.json' (01..99).
Other fields are stripped; absolute/relative private paths reject. This receipt
is storage provenance only, not authority or native execution proof. The supplied
private writer uses exclusive new files, fsync/readback and directory fsync.
RAW hash uses compact ensure_ascii JSON of the full raw line list; normalized
replay hash retains the original newline hash convention. Both are distinct.

Actual action/resource stop records the last accepted raw state and a finite
stop_reason; a writer failure leaves evidence=None, retains actual outcome,
stops the series and marks its quality unavailable. Earlier files/receipts
remain, with no overwrite/retry. The private directory must be fresh, isolated,
leased local storage under the future parent IO contract (never live/NFS SQL).
This script alone is not a sandbox or a source/lease/grant issuer.

Quality uses shared summarize_trace_rows over independently retained RAW games,
physical-seat mapped to deck identity. Absent/truncated/unknown evidence or a
failed writer yields NULL, not zero; actual measured zero remains zero. Partial
attempted evidence stays visible. Pair win counts are resolved BO3 series,
not games. Wilson uses existing percentage-valued95% intervals; zero resolved
samples gives NULL. Draw-cap/timeouts/errors appear as explicit exclusions.
Mirrored seeds are dependent: descriptive intervals are not A/B certification.
Public output has no RAW log, private hand, error text or locals. Full logs are
private local while active and must be verified/archive-closed separately.

## CLI

Plan-only (does not import engine/storage packages):

```sh
python -I -B backend/scripts/matchup_round_robin.py \
  --deck-export /owned/reviewed-roster.json --seed-token 1 \
  --output /owned/new-plan.json
```

Actual execution is NOT qualified by pure tests. Only after separate parent
review/operational approval, an isolated dependency/runtime environment may
supply --execute, --private-directory, --limits-json, --difficulty and
--max-ticks. MTG_DATABASE_PATH must explicitly point outside source to the
parent-approved isolated path because existing replay imports storage engine
configuration; the runner itself performs no SQL session/bootstrap. Do not use
this option on a live/default DB or infer a grant from the option existing.

## Evidence Scope

24 whole pure tests: the original twelve protocol categories plus complete
scheduler->actual projected series/game functions, constructor/sink/resource
partial retention, trace preflight, exclusive receipt storage, full recovered
legacy AST, genuine ResourceBudget cumulative counts, unknown classification,
plan-only CLI, finite receipt metadata and path/type rejection.

The complete110-series call-route test is INERT: synthetic state/engine/AI and
explicit import bindings. Its counters are protocol calls, NOT native game
counts. Canonical admission is a labeled stand-in; those all-Island fixture rows
are not claimed to implement the eleven real shipped decks. ResourceBudget,
trace summarizer and Wilson function bodies are real source; builder forwarding
uses a controlled spy, not genuine gameplay/quality evidence.

Existing whole modules test_replay_decision_metrics, test_series_policy,
test_replay_protocol, test_replay_manifest, test_replay_output_safety,
test_replay_progress, test_resource_budget and native replay neighbors import
actual engines/storage or run checked games. They are held intact, not pruned,
under this pure grant. A separately approved genuine two-deck BO3/full trace
pilot with closure/default parity must precede a real full matrix. D13 source,
13 styles/52roots/260 cases, counters/caps and unknown quality are untouched.

## Corrective Measured-Source Binding (P1/P2)

The export's schema1 source_commit remains461: it is the deck/template preparation
baseline, NOT the measured executing code. Actual composition may use a later
Git base plus private approved increments (including CAST1ecf). Execution now
requires keyword `source_binding` /CLI `--source-binding` with exactly:

```json
{"schema_version":1,"source_base_commit":"explicit 40-character base SHA",
 "backend_files":{"ai/agent.py":"actual SHA256","rules_engine/engine.py":"actual SHA256"},
 "backend_sha256":"canonical digest of the COMPLETE ordinary backend_files map"}
```

The displayed two file rows are a schema illustration, NOT an admissible partial
map. Parent supplies the full independently reviewed ordinary backend manifest,
including AI, engine, all other modules, ordinary data/fixtures/config, and the
new Task31 code/test files. No Git HEAD query or ambient/default461 is used.
source_base_commit is an externally declared base label, not a proof of commit
identity (a source-only composition has no .git). Complete file-map/digest binds
the actual measured bytes/increments independently of that label. It is file
provenance under parent writer exclusion, NOT live CodeRefs, dependency admission
or execution authority. A fresh process/import/runtime contract remains required.

The finite source inventory excludes standard __pycache__/.pytest_cache/.venv/
venv/node_modules components; root runtime/generated/evidence/training_runs;
card_data/image_cache; and .pyc/.pyo. Other ordinary files are included, including
new/removed files. Source symlinks/nonordinary members reject. Dependency and
runtime files are separate operator obligations, not silently certified source.
Parent must keep actual SQLite/sinks/evidence/runtime outside the source tree.

Entry checks the supplied map/digest BEFORE actual game/dependency imports. A
finally check samples end source, including on a later execution interruption.
Output records input_export_base_commit separately, source_base_commit,
source_binding_sha256, and measured_source before/after digests/file count/equal.
Changed/unreadable end source makes the run incomplete and DQ NULL; actual game
results/receipts are retained. No current committed-source identity or all-files
kernel immutability is inferred from matching file samples.

CLI reserves --output exclusively BEFORE any execution callback. An existing
sentinel, symlink or alias to the input fails without touching original bytes or
calling the matrix. A new reservation is never removed/retried; failure may leave
an empty owned incomplete output which must be archived as a failed attempt,
not mistaken for a completed report. Success flushes/fsyncs the summary.

Old24 test methods and assertion bodies remain byte/AST exact. Only their common
fixture setup supplies the new explicit source binding with a clearly synthetic
base label; no real source/Git/game certification is claimed. NEW10 pure tests
cover whole source inclusion/drift, typed binding, finite exclusions, missing
binding, end closure, output sentinel/alias, and export-vs-measured semantics.
No new actualgame, SQL, fullmatrix, budget expansion or replay-loop change.
