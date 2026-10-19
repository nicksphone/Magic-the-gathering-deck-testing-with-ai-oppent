# Trigger-order intent audit

NEW tests/report only. Source: frozen current `mtg-composed-release-xxWjrw`
candidate, plus immutable pending-intent guard `7bb0b2ac` and its original audit
test dependency `0b8b3dc2`. Production files are unchanged from that composition.

## Finding

Both seats: `lookup_intent` silently drops unsupported non-null AND null keys
for `choose_trigger_order`, whereas strict `lookup` and raw HTTP reject them.
The keys tested are `unknown_choice`, `trigger_ids`, `pending_trigger_order`,
and `action`. Non-null nested action requests carry an explicitly reversed
order; pending-context requests carry actual retained engine context.

Each case has exactly one unsupported-intent rejection expectation. There is
no accepted unsupported witness, normalized execution, contradictory assertion,
skip, xfail, monkeypatch, or conditional expectation in the audit tests.
Raw API 422 and full-root/SQLite dump invariance pass before that sole assertion.
The test's finally block also checks request and training root immutability.

Complete serial gate: **16 FAIL / 16 PASS**, 93 datetime deprecation warnings,
39.48 seconds, exit 1. All 16 failures are `DID NOT RAISE ActionRejected` at the
final unsupported-intent assertion, not fixtures or engine failures. This is
diagnostic evidence, not a green release gate or an implemented fix.

## Canonical Controls

Actual Soul Warden and Reclamation Sage ETB triggers after casting Sage, with
a public opponent Sol Ring available for Sage's next target phase. Original
fixture card fields are reused; no invented oracle text or game cards.

Sixteen independent passing controls:
- Both seats and both legitimate explicit order permutations (4): strict action
  roundtrip, sanitized hint and actual whole HTTP view parity, deterministic
  pending snapshot replay, exact resulting stack-label order, HTTP execution,
  persisted full-snapshot restart to the target-choice boundary.
- Duplicate, stale, and partial orders on both seats (6): strict lookup/intent
  and raw HTTP rejection, root/database purity.
- Wrong-seat typed action rejection on both seats (2).
- Presentation context without an explicit order rejects on both seats (2).
- Opposing hidden hand/library identity and order permutation preserves actor
  model-input bytes on both seats; opposing actor receives no prompts (2).

## Narrow Proposal

Public schema is `api_contracts.TriggerChoice`: required `type` discriminator
`choose_trigger_order` plus `trigger_order: CardIDs`. The actual qualified whole
legal view has exactly `type`, `trigger_order`, `trigger_labels`, and `event`.
Labels are ordered public strings; observed event is `stack_resolution`.

A separately authorized consumer-only fix can add this public model to the
existing pre-completion `lookup_intent` guard, allowing ONLY qualified display
keys `trigger_labels` and `event`. Unknown choice aliases, including null, and
uninterpreted nested root action/pending context should reject BEFORE completion.
Do not derive an order from labels, event, or pending context; keep actual chosen
`trigger_order` validation and legality on strict `checked_action`.
No action_contract, API/schema, engine, or producer redesign is needed for this
observed consumer mismatch. No production correction is included here.

This is bounded two-trigger evidence, not complete APNAP, >6-trigger permutation,
all-event, trigger-target, or action-alias completeness qualification.
