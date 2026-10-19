# Bounded continuous color classification fix

## Change and provenance

Qualified on exact committed `3ccbdf203a4ee1aeb848e219769c9dfac0f20e8c`
plus the frozen tests/report-only color-domain audit. The sole production change
is the color input of `continuous.py::_subject_match_result`: use the existing
`card_color_symbols(card, state)` instead of stored `card.colors`.
No domain, protection, layer-helper, stack, mana, costs, action-validation,
AI, backend API, or main changes. Existing source activity, query scope,
timestamps, negative predicates and effective-type checks are preserved.

The historical audit report remains a description of the uncorrected baseline,
not the qualification status of this fixed candidate. Its twelve strict ordinary
red assertions are unchanged and now pass. Six Song-removal controls previously
asserted the baseline observation that stats were unchanged despite a live color
change. They now assert the correct before/after stats explicitly: after Song
removal, Liege subjects become 4/4 and the Angel's black subject becomes 3/3.
Those are test corrections needed to remove assumptions of the diagnosed bug,
not relaxed legality, privacy or mutation checks. The first candidate result,
331 passes and six observation-control failures, is preserved as evidence.

## Executed gate

Fresh source-only local checkout `/home/nick/mtg-color-domain-fix-AXRnl6`.
Reused the pinned main backend virtualenv, Python 3.12.3, all eight exact
requirements verified. No dependencies installed.

**337 ordinary passes in 25.86 seconds**, serial, six complete modules:
41 owned audit cases and 296 unchanged neighbor cases. All twelve prior strict
reds and all twelve HTTP cases pass. No skips, xfails, errors, deselections or
`-k` exclusions. Both-seat legal alteration, activated target protection,
domain-count, source-removal, snapshot, hidden-information, root-purity and six
fresh-process restore controls pass. This is not whole-corpus/layer certification.

All 17 audited SQLite connections stayed in the initially absent checkout-local
`backend/mtg_lab.db`; no other DB path or network socket was used. SQLite is
read-only integrity-checked after the tests stop, and only stopped copies are
archived. Pydantic datetime deprecation warnings are unchanged.

From isolated `backend/` with the archived evidence directory as `E`:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" AUDIT_OUTPUT="$E/db-audit.json" PYTEST_ADDOPTS='' \
  "$PY" "$E/qualification.py" -q \
  tests/test_color_domain_audit.py tests/test_qualified_continuous.py \
  tests/test_basic_land_layer_goldens.py \
  tests/test_basic_land_replacement_composition.py \
  tests/test_dynamic_activation_modifiers.py tests/test_conditional_static.py \
  --junitxml="$E/green.xml"
```

## Handoff and limits

Archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/color-domain-fix/20261006-3ccbdf2`.
`production.patch` contains only the narrow consumer input correction.
`incremental.patch` additionally contains the six control corrections and this
new report, over the frozen audit source. `self-contained.patch` supplies all
new audit files plus the fix over committed `3ccbdf2`. The archived baseline,
final source, manifests, JUnit, exact red-to-green inventory, local DB audit,
stopped SQLite copies and graph refresh preserve the actual executed source.

No parent's queued coupled release composition is qualified by this run.
The separate Tokens/Ramp tick902 diagnosis uses the parent's frozen source,
without overlaying this fix or changing any combat search behavior.
