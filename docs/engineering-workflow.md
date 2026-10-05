# Engineering Workflow

## Work In Cohesive Batches

Prioritize retained gameplay failures and shared rules/AI roots. Group related
mechanics and their HTTP/UI paths into one implementation batch. Do not invent
card metadata or tune decks to manufacture desired win rates. Keep existing
uncommitted work and user data separate from disposable qualification copies.

## Validate At The Right Boundary

During development, reproduce the failure and run focused affected suites.
Expand checks for shared dependencies and fix failures before proceeding. At a
combined integration milestone, run the full backend and browser/build gates
once against frozen source; verify coverage and source identity. Reuse valid
predecessor evidence, but do not claim it proves changed code. Documentation-only
changes do not require another complete gameplay qualification cycle.

Use retained decision reconstruction for specific AI mistakes. Schedule broader
seed/seat-balanced matches when the change needs actual decision-quality or
strength evidence, not automatically for every clause. Report unique samples
separately from deterministic repeats. Never restart a live test just because a
poll timed out. Continue independent work while bounded checks run.

## Ship And Preserve

Integrate verified batches instead of indefinitely collecting feature branches.
Update README with current capabilities/limits, changelog with history, plan with
unfinished acceptance and Graphify after code changes. Archive completed evidence
on verified writable NFS, compare it before removing owned local scratch, and
keep active code/dependencies/SQLite local. Keep the original arbitrary-card,
strong-AI and release scope open until direct acceptance evidence establishes it.
