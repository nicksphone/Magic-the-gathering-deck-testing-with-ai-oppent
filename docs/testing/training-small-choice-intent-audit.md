# Replacement and trigger-target intent audit

NEW tests/report only; no production correction. Exact input is the current
composed-source pointer `mtg-next-composed-gate-wASfmI`, copied source-only,
plus frozen trigger guard `2c5cd1ac` and its original audit dependency.
This report does not assume a different or later coupled parent snapshot.

## Consumer Gap

Both seats: `lookup_intent` drops unsupported non-null AND null fields for
`choose_replacement` and `choose_trigger_target`. Strict lookup and actual raw
HTTP reject them; controller/full-root/SQLite dump remain unchanged.

Tested requests carry `unknown_choice`; replacement alias `source_id` for the
other actual offered replacement, or trigger alias `targets` specifying the
other actual legal artifact; and actual nested `pending_replacement_choice` or
`pending_trigger_order` context. Each case has exactly one final unsupported
consumer rejection expectation. No unsupported accepted/executed witness or
contradictory assertion precedes it; the finally block checks root/request purity.

Complete serial gate: **24 FAIL / 24 PASS**, 107 datetime warnings, 42.81 seconds,
exit 1. All 24 failures are `DID NOT RAISE ActionRejected` at that final assertion.
No engine/control failures, skips, xfails, or deselection. This is diagnostic
baseline evidence, NOT green release qualification or an implemented fix.

## Independent Canonical Controls

Actual unmodified fixture fields: Grizzly Bears, Hardened Scales, Doubling Season,
Reclamation Sage, Sol Ring. Replacement begins at the actual retained
`add_counters` effect boundary; no invented card text or fabricated API action.
Scales-first results in four counters; Season-first results in three.
Trigger targeting begins after actually casting Sage and resolving its ETB;
choose an own or opposing Sol Ring, then explicitly accept optional destruction.
Only the deliberately chosen artifact goes to its owner's graveyard.

Both-seat pending controller/source checks and 24 independent passing controls:
- Eight deliberate choice controls: strict reversible action, sanitized/actual
  whole legal view parity, deterministic snapshot replay, actual HTTP execution,
  full-pending restart, actual final outcome (both choices in both families).
- Eight missing/stale recognized-choice rejects: lookup/intent/raw HTTP,
  root/database invariance.
- Four other-controller rejects, including actual raw HTTP and root/database.
- Four opposing hand/library hidden-identity/order permutations preserve actor
  input bytes; other controller receives no prompts.

## Narrow Proposal

Public `api_contracts.ReplacementChoice`: required discriminator
`choose_replacement` and `replacement_source_id`. Observed whole legal views
also carry `replacement_name` and `event` (`counter_placement` here).

Public `api_contracts.TriggerTargetChoice`: required `choose_trigger_target`
and `stack_id`, plus exactly one non-null `target_card_id` or `target_player`.
The actual qualified artifact-target views have only those typed action fields,
no extra presentation metadata. Recognized nullable alternative target fields
must not be confused with unsupported null aliases.

A separately authorized `lookup_intent` fix can add both public models to the
existing pre-completion guard; allow only qualified replacement display fields
`replacement_name` and `event`, and no extra trigger-target display fields.
Reject unknown aliases, even null, and uninterpreted nested root contexts before
normalization. Never derive source/target/controller from names or pending
context; retain strict model XOR and actual `checked_action` legality.
No engine, schema, helper, producer, dataset, or main edits proposed here.

Limits: counter replacement and artifact-card targeting only; not all draw,
damage, mana replacement domains, APNAP, player-target triggers, or alias
completeness. Exact source hashes and archived evidence are in REPORT.md.
