# Combat Intent Guard

This incremental change modifies only `TrainingEnvironment.lookup_intent`,
using public `AttackAction` and `BlockAction` for `attack` and `block`.
Raw API, action normalization helper, engine and all 15 previous guards are
unchanged. Existing mechanic continuation fields still exact-compare pending
state; optional-effect display remains empty, not speculatively expanded.

## Contract

Unknown requested fields, even null, reject before `complete_action`.
Authoritative attacker IDs, target maps, bands, block maps and hybrid choices
remain public-model input and are checked by the existing strict lookup and
authoritative engine. No attacker, band, defender or cost-card choice is
derived from suggestions. A separate bounded both-seat probe confirms that
omitted optional bands remain empty even with canonical banding candidates.

Qualified attack display: `options`, `defenders`, `banding_attackers`,
`attack_taxes`, `attack_costs`, `declaration_limits`.
Qualified block display: `attackers`, `blockers`, `legal_blocks`,
`blocker_capacities`, `target_requirements`, `block_taxes`, `block_costs`,
`declaration_limits`.

When metadata is supplied, each value must exactly match canonical JSON of
the current public legal view computed on a state copy for that actor. This
qualifies nested shapes without accepting unknown nested/context requests or
silently dropping chosen aliases. In block display, `attackers` is the actual
`[{id,name}, ...]` candidate list, never a chosen attacker-ID list or object.
Partial metadata is allowed only for supplied known keys matching that view.
Stale/altered metadata rejects; future producer fields require separately
qualified explicit allowances. Complete typed actions need no display query.

## Qualification

Exact source-only baseline: parent `mtg-release-next-coupled-Np7Dla`, 948
backend files with equal beginning/end copy manifests, plus unchanged frozen
combat audit dependency `161abf754bf25550266101ab89b63c73df805bc1e10c128264ffd3359c42af31`.
Trigger and small-choice guards were already present, not reapplied.
No main, parent checkout, live database or other worker source writes.

Completed focused gate: **136 ordinary passes**, 175 warnings, 137.92s,
exit 0. Original 72 cases byte-unchanged, including all 32 former sole consumer
rejection failures, plus 64 new context/nested-display/omitted-assignment
checks. Both seats cover actual canonical full legal views, deliberate typed
and encoded assignment replay, real checked HTTP, complete combat outcomes,
root/controller/SQLite atomic rejection, snapshot restart and actor-private
input byte invariance. No skips, xfails, deselection or contradictory witness.

Separate fresh-SQLite 18-module shared gate: **timeout 900s, exit 124**.
Progress showed no failure marker, but there is no terminal summary and NO
complete shared-green claim. Its partial log and identical beginning/end
source manifests are archived; no restart or exclusions were used to hide it.
Additional shared qualification remains for the integrator's composed gate.

All existing 15 model-map entries and 11 type-branch test/body ASTs are
unchanged; old branch body source segments are byte-identical. Module AST
outside `lookup_intent` is unchanged. The exact guarded source hash, manifests,
closed local test data, independent archive reconstruction and checksums are
in the frozen NFS report. AST-only graph refresh completed without code change.

## Evidence Boundaries

Historical combat audit remains immutable: 32 consumer failures/40 passes,
63.54s, exit 1. This consumer guard closes that specific gap; it is not an
exhaustive combat, performance, policy competence or canonical hybrid-tax
claim. Generic taxes, actual banding and blocker capacity are real fixtures.
Paid-optional metadata compatibility is not expanded or broadly certified.
Separate relayed remaining/pending-family histories are not this combat gate
and are not being duplicated; no full Shark-support claim is made.
