# Jev-Guided UI Clarity Implementation Plan

> Execute in the isolated UI branch; preserve the live preview and user game.

**Goal:** Prevent incomplete ordinary-target submissions and clarify uncommitted
combat choices without changing game rules or redesigning the table.

**Spec:** `docs/superpowers/specs/2026-10-25-jev-ui-clarity-design.md`

## Tasks

- [x] Record Jev's bounded, sanitized interaction recommendations privately.
- [x] Verify the whole existing frontend baseline with its supported Python path.
- [x] Add failing readiness/parser tests, then implement local Cast validation,
      inline guidance and accessible target focus for the qualified target family.
- [x] Add failing combat draft/helper/rendering tests, then render explicit
      not-submitted guidance without changing Pass Priority or Submit behavior.
- [x] Run whole frontend tests, lint and production build; review the exact diff.
- [x] Exercise real browser controls, keyboard/focus and responsive layouts using
      labelled frontend fixtures. Use Jev for a bounded follow-up interaction check.
- [ ] Update the graph with AST-only extraction. Verify private evidence on NFS.
- [x] Deploy only the verified frontend build atomically to the existing preview,
      preserving the previous build and all backend/user game state.
- [ ] Publish a scoped PR without private traces; record actual CI status honestly.

## Review Boundaries

- Optional/up-to, modal, alternative, linked and multi-target paths remain intact.
- Stale target IDs cannot be submitted by the new ordinary-target path.
- Untargeted creature spells with targeted ETBs remain castable.
- Combat selection is never auto-assigned or auto-submitted; priority stays usable.
- Labels, keyboard focus, status announcements and mobile wrapping stay accessible.

## Verified Results

- Whole `npm test`, `npm run lint`, and `npm run build` passed. The supported
  `MTG_TEST_PYTHON` path was supplied for existing guarded fixture tests.
- `test:browser:ui-clarity` passed in Chromium with explicitly synthetic UI data:
  both seats, required creature/permanent choices, restriction metadata,
  stale/empty targets, untargeted ETB casting, draft/submit separation, priority
  controls and 390px wrapping. This is not an engine or real-card qualification.
- A separate bounded Jev follow-up chose an offered target and assigned the
  selected blocker before submitting. Actual keyboard selection, pointer input,
  callbacks and focus were checked; model preference alone is not proof.
- The isolated browser required a documented sandbox-disabled fallback because
  the host rejected its sandbox. Only the loopback synthetic fixture was used.
- Initial missing Python-path and stale Vite optimizer setup failures remain in
  private evidence, not silently reclassified as passing product tests.
- Only the preview frontend directory was atomically exchanged. Its prior build
  was archived and verified first; backend/service PIDs and saved game revision
  were unchanged. No backend, rules, autoplay or AI policy was modified.
