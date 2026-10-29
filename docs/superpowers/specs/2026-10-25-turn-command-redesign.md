# Table-First Command Layout

The user rejected the previous turn-command placement and explicitly requested
UI-design research and a visual redesign. Implementation choices remain delegated.

## Research Applied

- NN/g's [proximity principle](https://www.nngroup.com/articles/gestalt-proximity/)
  supports grouping related controls near their working context, including across
  responsive layouts. Apply this to a consistent command strip beside the hand,
  rather than burying turn progression among setup and history.
- [Visibility of system status](https://www.nngroup.com/articles/visibility-system-status/)
  supports showing the current decision beside its available action.
- Google's [toolbar guidance/source](https://github.com/material-components/material-components-android/blob/master/docs/components/DockedFloatingToolbars.md)
  distinguishes frequent and contextual actions. Use a small contextual command
  group, not a copied Material theme or a large new navigation bar.
- W3C [focus-not-obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
  and [target-size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
  guidance constrain fixed controls. Measure the dock's actual height, reserve
  scroll space and test keyboard visibility. Aim for 44px controls, above the
  24px AA minimum; this is not a blanket accessibility-conformance claim.

## Design

A persistent bottom command strip groups current phase/decision, Pass Priority,
combat confirmation where offered, and Pause/Resume automatic play. Required
choices link to the real choice panel; never guess or auto-confirm a selection.
Existing form/payment validation, disabled fieldsets and callbacks remain the
execution path. Keep manual stepping and detailed setup secondary.

Use a quieter matte-felt table, restrained warm highlights, readable offline
system fonts, clearer opponent/own zones, compact navigation and less bordered
panel clutter. Cards stay dominant. Collapse optional match help by default;
keep it available and keep all required decisions visible/reachable.

No backend/rules/default-AI/timer/schema/dependency changes. Preserve the live
backend and user match. Avoid fixed-bar focus obstruction at mobile, zoom and
short heights; use measured space rather than a guessed fixed bottom padding.
