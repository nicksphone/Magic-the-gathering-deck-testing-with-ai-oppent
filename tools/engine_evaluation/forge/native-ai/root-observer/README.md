# Optional native root-decision observer

This modifies **Forge Team/Card-Forge's AI** under GPL-3.0-or-later, retaining
their engine, card programs and source notices. See NOTICE and LICENSE.
It records existing work, not another AI evaluation or a new policy.

`root-observer.patch` is incremental over the exact AiController preimage in
SOURCE-PINS.json (the prior sacrifice-timing -> token-return -> land-expiry
chain), not pristine upstream. Apply on a fresh source copy, verify the
postimage, and rebuild all six emitted AiController classes. Inherit the other
14 source files and 22 non-AiController classes. PAYLOAD.json binds the complete
15-source/28-class schema13 prefix; runtime_profile.py rejects missing classes,
extras, changed hashes and old-schema relabelling. Test classes go in a separate
evaluation directory, never the approved policy shadow. Do not relabel old saves.

## Contract

Install `AiController.setDecisionObserver(Consumer<DecisionTrace>)` on the actual
brain from `PlayerControllerAi.getAi()`. Default is null. The normal root still
runs once and returns its original native list, not an observer replacement.
A trusted sink receives one immutable scalar record after deadline disarm/end.
Configure from the game's caller thread; arbitrary concurrent root calls or
cross-thread sink replacement are not an established contract. Sink
RuntimeExceptions are isolated and counted by `getDecisionObserverFailures()`.
No IO, new policy/payment/legality query, sorting or RNG read is added by the hook.

Stages retain the order actually observed:
- OFFERED: the private list selector input before its existing sort/empty check.
- CONSIDERED: each existing expanded-ability loop visit, before its guards.
- OPINION: the existing enum result, not proof of legal/affordable execution.
- EVAL_TIMEOUT/EVAL_ABORTED: observed existing evaluation exits.

Root outcome is selected/no_action/timeout/exception. Root IDs are controller-local;
ability/card IDs are game-local, not cross-process identities. A path that never
invokes the list selector has no OFFERED stage; it is not a fabricated empty list.
Actual null input is null, actual empty input is []. Affordability is always null
and completeLegalActionSet is always false. Counter/land/shortcut routes are not
a complete candidate inventory. Early break, policy filters, alternative costs
and missing stages prohibit deriving a complete legal-opportunity denominator.

Lists are copied to immutable scalar records. Hidden/face-down hosts redact all
identity fields together. No opponent hand or any library is newly enumerated.
Never publish raw observations: offered own-hand identities are private data.
Visits/identities are bounded at4096, with explicit truncation. The selected
choice has an independent bound. Nonblocking collector locks do not make the
native timeout wait for observation; late events cannot alter published records.
This does not make arbitrary trusted callbacks safe or prove every deadline race.

## Executed scope

Twenty corrected actual-root cases pass, including both-seat ordinary/no-action
and land shortcuts, input-before-sort, eval-worker correlation, immutable/root
separation, sink exceptions and off/on semantic choices, inventory/targets and
exact serialized MyRandom state for controlled equivalent poses. Separate six
internal protocol checks pass: the two review regressions plus four identity
redaction checks. Eight unchanged lifecycle classes pass101 checks. The synthetic
profile module passes48. These are separate cohorts, not naturally dealt games.

The first actual-root cohort was16PASS/4FAIL: its new privacy fixture incorrectly
required an ineligible hidden card to reach OFFERED. Only that fixture expectation
and method name changed; the original run/source are preserved privately. The
corrected root cases show exclusion, not actual redaction; the separate protocol
cases prove redaction at its real snapshot helper. Two genuine first-hook review
regressions failed before correction and pass afterward. See QUALIFICATION.json.

Both Java test files require the existing pinned Forge test dependencies and
guarded bounded evaluation harness. Compile policy classes into the approved
shadow, tests into a distinct directory, and run TestNG's actual-root group for
NativeRootObserverAcceptanceTest, then all NativeRootObserverProtocolTest tests.
Native lifecycle checks use the same eight classes as prior worker qualification.
Exact private launcher/class-origin/canary receipts are archived; no unguarded
JVM, SQL/server access or live/default switch is authorized by this package.

Natural recording and off/on full-game neutrality, broader strategic review,
training and match/BO3 acceptance remain open. This is an opt-in observation tool,
not evidence the overall AI is finished. The older selected-only recorder proposal
is not automatically upgraded or wired merely because this API exists.

## Final Packaged Runtime

A separately declared final cohort executed both whole root/protocol classes:
26PASS/0FAIL/0SKIP in26.92s, with AiController loaded from the strict schema13
15-source/28-class shadow. The eight whole lifecycle classes separately passed
101 checks in27.47s on that same packaged runtime. These are final-runtime
cohorts, not an inferred sum of earlier diagnostic overlays. No natural games
or live/default switch were performed.
