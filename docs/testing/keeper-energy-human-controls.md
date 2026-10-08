# Human Keeper and Energy Choices

Baseline: immutable `a2fb4879a074cec0e8bf2a6c83c32f0fe13a50ba`.

Two supported backend continuations were unreachable in Controls:
`legend_keeper` and `exchange_energy_payment`. Both stopped at the explicit
unsupported-mechanic warning. The NEW actual-Controls regression records all six
failing canonical public views on the baseline, rather than weakening the warning.

Controls now exposes one deliberate keeper button per offered public card ID,
with public tapped/sickness/characteristic/counter information to distinguish
copies. It submits exactly `choose_mechanic` plus one `card_ids` entry. Energy
choices use the existing option-button route and submit `choice_id`; labels and
affordability come from the backend. No payment or keeper is inferred, no default
is submitted on render, and unoffered payment does not appear. The two kinds are
listed in the public frontend type. Unknown choices retain the stop warning.

## Actual Evidence

- Both seats: two genuine paid canonical Isamaru casts pause for the legend rule.
  Choosing either older or newer copy after snapshot restore keeps precisely that
  copy on the battlefield and moves the other to its owner's graveyard.
- Both seats: genuine paid canonical Stormdrake cast/entry, deliberate opponent
  ETB target, real control exchange and four energy lead to pay/decline against
  Elvish Mystic, or decline-only against unaffordable Torrential Gearhulk. Restored
  choices have the actual expected target zone and energy balance.
- Wrong seat, duplicate/missing/unknown keeper IDs, unknown energy choice and an
  unavailable pay request reject copy-on-write with full snapshot equality.
- The actual public views pass the existing frontend match/legal contracts;
  compiled Controls callbacks send exact actor and choice payloads for every
  offered option, including both legend IDs. Public characteristics are rendered.
- Final complete configured frontend npm test, lint and build exit 0. Native
  SQL/socket/child audit denial is installed before the NEW Python fixture imports.

The starting decks/board/resource availability are explicit trusted fixtures;
these are real paid episodes, not naturally completed games or full-card
certificates. No injected StackItem/pending choice, Oracle rewrite, backend
production/API/schema/AI/dependency change, SQLite or server run was used here.
The component test uses deterministic hooks, not a mounted React/browser
certificate. Actual browser continuation acceptance remains required.

Verified archive:
`parent-integration/keeper-energy-human-controls-qualified-20261008/`.
