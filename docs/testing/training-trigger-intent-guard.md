# Trigger-order consumer guard

Production scope is `TrainingEnvironment.lookup_intent` only. Input is a
source-only copy of the current frozen `mtg-next-composed-gate-wASfmI` parent;
no parent/main, API, engine, normalizer, or producer files are changed.

The public `TriggerChoice` model owns `type` and explicitly selected
`trigger_order`. Known display fields are only `trigger_labels` (nonempty list
of nonempty strings) and `event` (nonempty string). Null, object, nested-action,
and other malformed display values reject before completion. Unknown keys,
including null aliases and uninterpreted nested root action/pending contexts,
reject before normalization. Labels and event never supply or override order.
Legality remains strict `checked_action`, not presentation metadata.

The immutable original trigger audit patch `32420fc9` remains unchanged and is
an explicit test dependency. Its historical 16 sole rejection failures / 16
passing independent controls remain archived; they are not a green release.
With this guard, all original 32 cases pass alongside 26 new regressions:
58 ordinary passes, 113 datetime warnings, 56.18 seconds, exit 0.

Real canonical Soul Warden/Reclamation Sage ETB triggers qualify both seats,
both explicit orders, full actual legal views, selected stack order, HTTP,
snapshot replay/restart, raw rejection/root/database purity, and opposing hidden
identity permutation privacy. New negative controls qualify null/malformed
display and nested action/context rejection without contradictory witnesses.
No helper monkeypatch, skip, or xfail is used to qualify rejection behavior.

The source/evidence report provides the separate neighboring shared gate and
exact hashes. Static AST checks preserve all prior twelve guarded branches and
all production outside `lookup_intent`. Other trigger counts, APNAP, all event
types, and action-alias completeness are not certified by this bounded patch.
