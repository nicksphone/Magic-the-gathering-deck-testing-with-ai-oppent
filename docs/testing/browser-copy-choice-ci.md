# Browser Copy Choice Contract

The `bf9f268e` frontend CI job passes. Its browser job passes the repaired
scry continuation, then stops at `browser-human-actions.mjs` with
`Missing copy target option`. The API exposes a valid `copy_target` choice;
the test looks for a checkbox that the current Controls component does not
render. Copy choices are deliberate one-click buttons.

The test now clicks the offered option label, preserving all selected IDs,
submitted-action assertions, original/copy distinctions and resolved outcomes.
Seven selections across ordinary, divided, modal and Adventure copies use an
offered-kind/ID guard before clicking. The ordered, linked and conditional
copy browser scenarios use their existing deliberate recipient labels instead
of the same obsolete checkbox/confirmation interaction. Other mechanic
checkboxes and confirmation flows are unchanged; no product code changes.

`copy-choice-browser-contract.mjs` executes the actual compiled Controls
callbacks and the browser helper with controlled transport. Both seats cover
keep, player and creature retargeting, exactly one action per click and rejection
of unoffered/stale choices. The old browser script fails this regression; the
corrected script passes. A draft assertion mistakenly included unrelated
priority-stop checkboxes and is preserved separately from the corrected
choice-panel check.

Current source typechecking, source lint and changed-script syntax checks pass.
The existing fixture-handoff and browser navigation regressions also pass.
These checks are not a mounted-browser certificate. The complete corrected
remote browser and backend workflow remains required. Local Chromium/libpng
qualification remains held; no library substitution or browser claim is made.

Raw CI and regression evidence is archived under
`diagnostics/ci/bf9f268e-37925211429-20261009/` in the MTG RCHFiles storage.
