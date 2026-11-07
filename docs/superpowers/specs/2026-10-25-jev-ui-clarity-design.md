# Jev-Guided UI Clarity

The user delegated routine UI testing and usability improvement to Codex working
with Jev. The existing table layout and visual language remain unchanged.

## Scope

- Ordinary required creature/permanent targets: clicking Cast without an offered selected
  target should explain the missing choice locally and focus the target control,
  without submitting an incomplete API action or choosing a target automatically.
- Combat drafts: show selected/assigned counts and an explicit not-submitted
  status. Selecting a blocker is not the same as assigning or declaring a block.
- Preserve priority responses, Auto behavior, optional targets, modal/linked/multi
  targets, costs, backend rules, AI policy and existing accessible button names.

## Alternatives And Choice

Jev compared disabling incomplete Cast buttons with local click validation. It
favored local guidance/focus and the copy "Choose a creature target before
casting." It strongly preferred informative combat draft status over locking
priority controls. These are advisory judgments, verified with tests, not rules
authority or a replacement for human usability/accessibility checks.

The implementation covers the confirmed ordinary single-card target cases using
existing authoritative metadata, not card names or Oracle parsing. Read-only
inspection of the original rejected casts showed restriction metadata and a
combined creature/permanent offer. The guard accepts that metadata without
reimplementing restrictions, and verifies only the explicitly offered ID. The
resulting guidance is "Choose a target before casting."
Unknown and more complex target families keep their existing behavior.

Private gameplay traces, API credentials and model request artifacts are not
committed. Public tests use explicitly synthetic protocol cases. AI evaluation
and RC qualification remain separate and incomplete.
