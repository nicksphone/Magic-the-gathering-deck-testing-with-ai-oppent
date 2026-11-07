# Beginner-Friendly Play Table

The user explicitly requested a committed first UI fix followed by broader ease
of use for beginners. Codex owns implementation choices under the user's existing
delegation. Preserve the established table design and all game-action semantics.

## Design

1. A visible, collapsible What to do next guide above the table. Derive its short
   title, explanation and navigation link from public match state and the current
   offered actions, including opening hands, required choices, combat, responses,
   AI turns and results. Never infer a target, hide a required choice, or auto-play
   for the human. Link to existing controls rather than duplicate game callbacks.
2. Clearer lobby deck labels: Your deck and Opponent's deck for player-versus-AI;
   Player 1 and Player 2 for shared-table modes. Keep stable accessible selector
   names and all setup choices. Explain the start/check-support flow.
3. Keep Pass Priority prominent and explain it in plain language. Put technical
   stepping/batched AI tools in a native Advanced turn controls disclosure. Keep
   all existing callbacks, disabled conditions and accessible names intact.
4. Offer a short optional glossary for priority, stack, mana and tapped cards.
   Preserve keyboard navigation, wrap on mobile and keep the guide dismissible.

No new dependencies, rule changes, AI-policy changes, timer changes or private
state in model requests. Preserve optional, compound and cost-payment controls.

## Checks

Pure state-matrix tests, actual component rendering, whole frontend tests, lint,
production build, synthetic browser keyboard/mobile checks, bounded Jev usability
feedback, independent review and frontend-only preview deployment. Keep private
model/screenshots/evidence on NFS, and publish only sanitized code/tests/docs.
