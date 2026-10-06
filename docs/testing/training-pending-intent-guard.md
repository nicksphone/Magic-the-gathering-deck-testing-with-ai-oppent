# Pending intent consumer guard

Scope: `TrainingEnvironment.lookup_intent` only, on a source-only snapshot of
the frozen `mtg-composed-release-xxWjrw` candidate. No raw API, engine, producer,
normalizer, dataset, or main-directory edits.

`choose_mechanic` uses public `MechanicChoice`; `choose_optional_effect` uses
public `OptionalEffectChoice`. Unknown requested keys, including null aliases,
reject before completion. Existing ten guarded families retain their behavior.
Explicit card selections and accept/decline remain caller-owned; display options
and pending continuation payloads never supply omitted authoritative choices.

Qualified mechanic display fields are `kind`, `options`, `count`, `min_count`,
`label`, `option_labels`, and `option_type_lines`. Optional-effect views need no
extra display fields. Whole canonical Daretti engine views also carry
`player_id`, `effect_controller`, `followup_effect`, and `resolving_item`.
These server-context fields must exactly match current pending state for the
acting seat, comparing canonical JSON (including boolean/integer distinctions).
Mismatched, null, or nested override contexts reject before normalization;
matched context is presentation only and cannot replace engine state.

The unchanged original audit has 16 sole unsupported-rejection cases and 16
independent controls: both-seat Daretti discard/draw and Reclamation Sage
optional destruction, actual HTTP execution, full-root/SQLite rejection purity,
snapshot restart, replay equality, and opposing hidden-identity permutation.
Its immutable baseline was 16 failures / 16 passes, not a qualified release.
The consumer fix passes all 32 unchanged cases plus 24 new context regressions:
56 ordinary passes, 91 datetime warnings, 38.47 seconds, exit 0.

The evidence report supplies exact source hashes and the separate shared gate.
This patch does not certify all mechanic display formats (for example inspected
top-card metadata), alter producer privacy, or expand action encoding. Raw API
still rejects presentation/context keys; use explicitly typed chosen actions.
Trigger ordering (`choose_trigger_order`) remains a separate audit proposal.
