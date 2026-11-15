# AI Play Notices

The user wants to see AI spells, not just a life-total change. Use committed
public cast/activation log entries (the stack may already have resolved), with
the longest rolling-log overlap as the frontier. Initial load, game changes,
stale revisions and an unknown frontier are baselines, never history replays.

1. Reproduce the missing resolved-spell notice with pure snapshot tests.
2. Add non-modal, pointer-transparent six-second AI notices plus eight recent
   plays in the existing stack panel. Only public battlefield/graveyard metadata
   may supply artwork/targets; never inspect hands or infer from life loss.
3. Exercise actual App snapshot updates, rolling/repeated casts, timers, focus
   and narrow-screen layout in the synthetic browser fixture. Run frontend
   tests/lint/build and independent review.
4. Refresh the AST graph, archive private evidence, deploy the frontend only,
   and commit/push. Do not mutate the live match or restart its backend.

This is presentation only: no response-timing, autoplay or rules changes.

## Verified Outcome

- Resolved AI casts/activations remain visible for six seconds. The sidebar
  retains eight recent plays. Popups cannot intercept pointer input or focus.
- Pure public-snapshot regressions cover rolling/repeated casts, both seats,
  stale/history baselines, hidden-hand exclusion and retained-stack target
  ambiguity. Independent review found that ambiguity; its regression was
  observed failing, then passed after requiring a new public stack ID.
- The separate hand inspector now uses an explicitly refreshable, labelled
  captured snapshot. Permission errors remain visible across match advances;
  match/game changes cannot carry over the previous hand.
- Whole frontend tests, lint and production build passed. Native synthetic App
  browser checks passed for resolved/repeated casts, expiry/history, mobile,
  click-through, focus, opt-in hand refresh and error feedback. These are UI
  checks, not rules or AI deck-play certification.
- The private preview debug endpoint was enabled only in its runtime service,
  after an integrity-checked online SQLite backup and verified NFS readback.
  The existing match restored at the same revision. The frontend was then
  exchanged atomically without another backend or frontend restart.
