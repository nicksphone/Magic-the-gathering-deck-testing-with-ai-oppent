# Optional Hand-Exile Human Controls

The frontend recognizes the closed public cost-option metadata:
`hand_exile_color`, `hand_exile_generic_reduction` and `exile_card_ids`.
These three fields must be supplied together with a W/U/B/R/G color, positive
integer reduction and at most 250 distinct nonempty CardIDs. Legacy options
without the metadata remain unchanged. Null and partial metadata fail parsing.

For a matching option, the human deliberately chooses any number of offered
cards, including zero. No card is automatically selected. The submitted
`cost_choice.exile_card_ids` preserves selection order; stale or duplicate
selections disable casting. Ordinary cost options never gain this field.
Existing required discard/sacrifice choices remain required.

The NEW regression renders the actual component with captured both-seat
canonical public views and checks zero, reverse selection, stale IDs, metadata
rejection and ordinary-option compatibility. These are component/contract tests,
not browser actions or a backend payment qualification. Backend repair and its
mixed test gate remain separately owned; the current admission warning stays.

The complete configured frontend test chain, TypeScript build check, lint and
production build pass with the existing qualified dependencies. Python fixture
processes had a pre-start SQLite/socket/child-execution denial hook; it does not
sandbox Node/esbuild or establish browser isolation. Evidence is archived at
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/march-human-optional-pitch/parent-a42-20261008/`.
