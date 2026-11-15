# Lossless evaluator replay

The RC matrix exposed a contract gap: `run_game` custom quality traces contain
sorted hand names, structured battlefield rows and a compact action. They are
measurement records, not the legacy action-reconstruction format. In particular,
`compact_action` drops selected mechanic cards and other execution parameters.
The first frozen matrix game fails reconstruction at decision zero (`hand`).
Its original private receipt and failure are retained; missing parameters will
not be inferred or backfilled.

Within the user's instruction to work autonomously toward RC, the implementation
choice is an additive version-one `replay` envelope on custom evaluator traces.
It captures the original ordered hand/battlefield names, legal action types,
actor/phase metadata and complete checked action before transition. Existing
quality fields and the default legacy trace path retain their behavior. The
reader validates the envelope and continues to compare every root, execute with
rejection enabled, and compare complete normalized logs and terminal metadata.
Old compact quality records remain unsupported; legacy replay records still work.

Alternatives were changing measurement field shapes (would break consumers) or
guessing omitted parameters (would invalidate reconstruction). The envelope
keeps execution evidence explicit, detached, and subject to existing trace limits.
No limits, rules, AI policies, source bindings or running matrix inputs change.

## Execution plan

1. Add public canonical-card tests through actual `run_game`, quality builder,
   contextual binding and strict reconstruction, for both starting seats and an
   ordered mulligan-bottom choice. Assert complete actions and input immutability.
   Run them red before production edits.
2. Capture the envelope in the custom trace branch before the checked transition.
   Reserve the `replay` key; reject conflicting builder data. Add reader validation
   for version/type/required fields and agreement with shared outer identity and
   action fields. Preserve legacy validation and complete log comparison.
3. Exercise malformed versions, missing fields, changed actor/hand/action/legal
   data, callback detachment, unchanged legacy behavior and bounded trace rejection.
   Adapt existing exact custom-payload assertions to assert the new envelope as
   well as every original quality field.
4. Run whole neighboring replay, trace-context, quality, action-contract, resource
   and matrix-protocol modules. Obtain an independent read-only review. Document
   results and the unsupported old compact records, then commit the reviewed fix.

## Review focus

- Ordered mechanic/card selections survive recording; no choices are inferred.
- Envelopes cannot silently override conflicting outer actor/action identities.
- Unknown/malformed envelopes fail closed instead of falling back to legacy.
- The checked transition, trace budget and default legacy producer stay intact.
- Raw private matrix data is not added to public tests or source control.

## Execution ledger

- Base: `a4f8df9dd7ce2e6b727790f451e78f8cf991c9ee`; frozen matrix continues separately.
- Initial canonical two-seat tests fail at the original hand/legal-type mismatch;
  the original sixteen-case draft records fifteen failures and one false-positive
  size test. The corrected 300-byte size fixture is red on the old producer and
  rejects the envelope on the new producer. A separate null-operand test is red
  at decision eighty before explicit operand-membership validation.
- The first whole eight-module cohort passes 163 tests. The first seventeen-module
  audited pure cohort passes 285 tests plus 31 subtests with zero denied operations
  and all 22 named input hashes unchanged; the separate legacy CLI module passes 30.
- Independent review initially approves 116 checks, then identifies an Important
  construction-boundary gap on a requested resource follow-up: omitted complete
  action collections could be copied before final payload rejection. Both actual
  callers already supply `complete_action`. The fix preflights the entire action
  with the existing shared bounded walker; no limit changes. Two public
  contract-valid adversarial cases fail at the builder sentinel before this fix.
  Final verification and review follow the correction.
- Final seventeen-module audited cohort: 287 tests and 31 subtests pass in 85.08
  seconds, zero SQL/network/child attempts, all 22 named input hashes unchanged.
  Independent follow-up approves with no remaining findings and reruns both
  affected whole modules: 59 pass. Original failures and overlapping counts are
  retained separately. See the component report for scope and remaining limits.
- The final separate legacy replay/CLI whole module passes 30 tests in 15.22
  seconds. All planned component work is complete; full RC acceptance remains open.
