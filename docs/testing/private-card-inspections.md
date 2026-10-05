# Private Card Inspections

Supported top-card selection effects preserve the complete inspected window
separately from the subset that may be selected. A human sees private card
previews even when no card qualifies; acknowledgement then completes the effect.
An empty library does not create an unfinishable choice.

Recruitment Officer uses its canonical look/reveal instruction, not a draw.
Its unselected cards go to the bottom in random order using saved RNG state.
Other supported any-order instructions use the existing ordering choice.
Selected revealed cards become public observations; unselected identities do not.

Pending decisions survive snapshots and backend restart. Public match responses
do not include the inspection previews; the acting human's legal-move response
does. AI inspection choices remain redacted from the human API. This is a local
shared-seat application contract, not authenticated multiuser isolation.

Evidence includes 73 canonical unit cases, eight actual HTTP scenarios and four
Chromium flows covering both seats, zero-hit acknowledgement, qualifying reveal,
backend restart and browser reload. Canonical records and provenance live in
`backend/tests/fixtures/activated_top_selection/`.

Run `frontend/tests/run-activated-top-selection.sh` from an isolated source copy,
with `MTG_TEST_PYTHON` and `MTG_FRONTEND_DEPS` if dependencies are elsewhere.
The wrapper uses local disposable SQLite, loopback test ports and verified NFS
evidence storage; it does not run against the live match database.
