# Compound Source Counter Costs

Bounded parser product over published `5d43f71ce525186b6d0ab2d53fa2bf5764494bbc`.
Fertilid's target-player search remains unsupported, not partially executed.
No main, parent, live database, schema, AI, extractor, effect handler, availability
or payment implementation changes. The current generic tap-readiness guard is
retained byte-for-byte.

## Exact Dependencies

- Published source tar SHA256:
  `c0672c38456a3f301f8cddbcaac52180d0b2ad666a33d0f33750571038f3676a`.
- Frozen parser production dependency:
  `c97d22e04d5b0ba101b52a7b48d8b5399e841de187122847a5eaf44c8d460cae`.
- Canonical qbnsL7 audit/fixtures dependency:
  `f49a37384117fb488687bcc6c30aaff1351b78514ed03852046981d772cea9f4`.
- Current `costs.py` preimage:
  `fa7e2132be0d6e7c65f01288a77b6f0244151e329bdffd793a344969d649db40`.
- Current `costs.py` postimage:
  `f90cfe9e1a3c4f1fa8cb9f8bfcd5e09022825f52aae664e61c62d71f082ad588`.

Earlier a608 product and its original failures remain immutable in their own
archive. This requalification is not relabelled as that earlier run. Canonical
Fertilid/Lux Cannon full raw fixtures and provenance are reused unchanged.
Disenchant, Stifle, Walking Ballista and protection fixtures also remain unchanged.

## Product Boundary

Only the removal branch of `parse_activated_cost` changes, with one new private
`_parse_source_counter_cost` helper. Every comma-separated component must match
before any structured supported cost is returned. Exactly one fixed positive
self-source removal is required, for +1/+1 or charge counters. Existing bounded
number words and positive ASCII integer literals are accepted. Fixed supported
mana components and at most one tap symbol are retained together.

Variable amounts/mana, other-object removal, duplicate taps/removals, empty or
trailing components, unknown symbols, duplicate-color hybrids and unsupported
life/discard/sacrifice conjunctions reject the whole cost, never partial payment.
ActivatedCost, reservations, payment choices, source resource validation,
incarnation/sequence revalidation and payment staging are unchanged. AST and
source-text evidence proves every other function/class/import/constant unchanged,
including `activated_cost_available`, plus the noncounter parser body.

## Authorized Test Adaptations

The original 108-case audit is preserved before adaptation, including its raw
failure ledger. Only two obsolete-characterization functions change; decorators,
parameters and all other functions (including all 16 desired search failures)
retain identical ASTs.

The direct-boundary function now checks complete parsing, exact one-time
mana/tap/counter payment, repeat rejection and deterministic full snapshots.
This is explicitly cost-only for Fertilid, not invented search execution.
The HTTP function retains Fertilid's atomic 422/root/controller/SQL assertion.
Lux now deliberately asserts actual paid announcement, exact source/controller,
repeat atomic rejection, persistence recovery and real priority-pass destruction.

Two existing bounded parser tests also adapt only their newly supported grammar
row: standalone charge removal and tap plus self +1/+1 removal. They assert
deliberate structured parsing and payment, not fabricated canonical abilities.
The creature tap row first proves sickness rejection and immutability, then
explicitly positions a ready source. All other unsupported rows are unchanged.

## Current Executed Ledger

All runs are serial, bounded, offline and on one source-only local checkout.
No skips, xfails, deselections or assertion silencing. Python 3.12.3 uses the
existing qualified shared interpreter; all current requirements pins match and
`pip check` passes. No dependency copies or installations. An audit hook rejects
network connections and SQLite connections outside the owned local checkout.

- Original unchanged108 before parser: **80 PASS / 28 strict FAIL**, 42 warnings,
  18.36 seconds, exit 1, bound 600.
- Adapted108 after parser: **92 PASS / 16 strict FAIL**, 42 warnings,
  17.54 seconds, exit 1, bound 600. Exactly 2 Fertilid compiler, 2 admission,
  8 search episode and 4 HTTP admission failures remain. No full search claim.
- Five whole focused modules: **259 PASS**, 26 warnings, 50.25 seconds,
  exit 0, bound 600. Includes all NEW 104 payment/execution/atomicity controls.
- 39 whole neighbors (38 previous modules plus current tap readiness):
  **1039 PASS / 2 FAIL**, 341 warnings, 118.67 seconds, exit 1, bound 1200.
- Unchanged six-case HTTP module on exact current parser preimage:
  **4 PASS / same 2 FAIL**, 8 warnings, 8.21 seconds, exit 1, bound 600.

The two neighbor failures are the discard rows in
`test_activation_payment_choices_http.py`: the retained canonical Rummaging
Goblin defaults to summoning-sick, then the fixture expects its tap ability to
be accepted. The matching unit fixture already marks its source ready to tap.
Both failures reproduce before this parser patch. No readiness guard or HTTP
test was changed. Proposed separate fixture correction: explicitly mark only
that controlled discard source ready before persistence, retaining all payment,
foreign-resource rejection, SQL recovery and snapshot assertions. This report
does not certify that unimplemented correction or claim the neighbor gate green.

## Actual Coverage And Limits

Both-seat canonical Lux Cannon pays three charge counters and a tap immediately,
then destroys only on resolution. Real payable Disenchant/Stifle responses retain
source independence and no refunds. Ballista's last counter can cause real SBA
departure while its ability resolves through retained LKI. Both-seat foreign
controller, protected-target, resource reservation, stale-source fault injection,
full-root rejection, snapshot determinism, private views, local HTTP persistence
and fresh-process restart controls are included. Retained board/counter/mana
positioning is labelled controlled, not claimed as casting/entry evidence.

Fertilid pays correctly only at the direct cost boundary; its real search body
still compiles unsupported and is not announced or partially rewarded. This is
not general counter-cost, all-card, search, readiness or whole-suite certification.

## Reproduction And Storage

Apply the cumulative integration patch to the exact published source tar. It
includes the separately pinned canonical audit/new tests and narrow authorized
adaptations, not an old whole-file production overlay. From the isolated backend:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
MTG_ISOLATED_TEST_ROOT="$ROOT" timeout 600 "$PY" \
  "$ROOT/evidence/run_guarded.py" tests/test_paid_counter_family_audit.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
MTG_ISOLATED_TEST_ROOT="$ROOT" timeout 1200 "$PY" \
  "$ROOT/evidence/run_guarded.py" \
  $(cat "$ROOT/evidence/current-neighbors.modules") -q
```

Exact command receipts, XML, scope proofs, original/adapted ledgers, source
manifest and patches are archived on verified NFS. Completed owned snapshots
and SQL exports are readback-verified before local cleanup. SQLite stays local;
no dependencies or other workers' scratch are copied or removed. Generated
placeholder SVGs and pytest scratch are evidence, not production source changes.
