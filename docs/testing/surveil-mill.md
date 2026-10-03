# Surveil, Fixed Mill and Effect-Authorized Casting

## Implemented Scope

Canonical Scryfall fixtures preserve Oracle IDs, source URIs and unmodified
Oracle text. They are mechanic fixtures, not invented competitive decks or
whole-card certification. Shared grammar and handlers implement these families:

- Fixed positive surveil instructions inspect available cards privately. The
  controller selects any for the graveyard, then orders retained cards topmost
  first. Library changes commit once after both choices, using the existing
  graveyard replacement path. The continuation survives HTTP/SQLite restoration.
- Surveil is not milling or drawing. Positive surveil of an empty library still
  emits its event; surveil zero does not. Short libraries do not lose the game
  until a draw actually fails. These distinctions follow the official
  [Ravnica Remastered release notes](https://magic.wizards.com/en/news/feature/ravnica-remastered-release-notes).
- Complete supported surveil payoff clauses place numeric +1/+1 counters on the
  original object, return that original permanent to its owner's hand, or deal
  fixed damage to opponents and gain fixed life. Source suppression applies.
  First-time-each-turn qualification tracks the player's surveil history, not
  a particular source, and persists through snapshots.
- Complete unconditional cast/noncreature-cast surveil triggers use the normal
  stack. Casting and resolving are distinct; Dragon's Rage Channeler's delirium
  abilities are not certified by testing its surveil trigger.
- Fixed targeted-player, each-opponent and self mill instructions preserve the
  recipient. Supported draw-to-opponent-mill triggers fire once per actual draw.
  Counterspell/surveil, surveil/draw/self-damage and flashback continuations do
  not drop later clauses or repeat earlier operations after choice restoration.

## Effect-Authorized Casting Repair

Traced built-in Tempo/Dimir games exposed an existing path that directly built a
graveyard spell on the stack without validating its announcement. Counterspell
could appear without any spell target. The shared handler now forecasts and
admits a cast through the ordinary engine before committing it:

- The permission waives printed mana cost and ordinary sorcery timing only.
  Targets, casting prohibitions, split second, mandatory additional costs and
  mana taxes still apply. Rejected announcements leave the authoritative state
  unchanged apart from a decline log.
- Announced targets, cast events, ward and per-turn spell counts use the normal
  pipeline. API clients cannot manufacture the internal permission.
- Printed mana-cost X is zero under this waiver. Fixed token-count grammar now
  respects announced X, including zero rather than a default single token.
- Complete singular discard-or-sacrifice additional-cost clauses expose two
  cost options rather than incorrectly demanding both. Ordinary human casts can
  select either; the effect path can use the available alternative.
- Draw-by-mana-spent reads actual payment, including taxes and reductions, not
  printed mana value. A free Memory Deluge with no tax looks at zero cards.
- Recognized exile-instead-of-graveyard permissions survive snapshots and apply
  to resolution/counter departures, not a return to hand. Torrential Gearhulk's
  supported ETB path retains this permission.

## AI Boundary

All three difficulties use only inspected options, their own known hand and
public resources for surveil. They preserve needed lands and color fixing, bin
surplus lands, and can bin an unpayable creature when an actually payable,
complete return-creature-to-battlefield spell is known in hand and graveyard
access is not replaced with exile. Hidden opposing hands and uninspected own
library changes do not alter the constructed decision fixtures.

This is conservative curation, not optimal search: nonlands are otherwise kept.
General graveyard synergies, flashback valuation, opponent-aware ordering and
long-horizon planning remain unfinished. Effect-authorized cast selection still
uses the existing automatic target/mode heuristic; deliberate human optional
cast/mode/target choices and broader AI permission selection remain open.

## Validation

`backend/tests/test_surveil_mill.py` covers both seats, empty/short libraries,
partition/order ownership and admission, source incarnation, per-turn history,
suppression, exile, fixed mill, draw triggers, flashback and HTTP/SQLite resume.
`backend/tests/test_effect_cast_admission.py` covers free-cast targets, taxes,
additional-cost alternatives, cast triggers, timing, X, payment provenance,
departure destinations, Gearhulk ETB restoration and API permission rejection.
`frontend/tests/browser-surveil.mjs` exercises both human seats through the real
App, private choices, refresh, ordered completion and a surveil payoff.

Final commands and outcomes are recorded in CHANGELOG and the verified RCHFiles
archive. Earlier failing tests, short-cap matches and pre-free-cast-fix runs are
retained separately; they are not presented as final acceptance.

## Known Limitations and Next Upgrades

- Dynamic surveil, extra-card inspection modifiers and arbitrary replacements
  remain unsupported; Enhanced Surveillance is explicitly flagged.
- Arbitrary surveil payoff conditions, graveyard-entry/dies composition and
  full simultaneous replacement ordering are not certified.
- Broader cost alternatives, optional kicker with a mana-cost waiver, human
  additional-cost card selection and interrupted payment continuations remain
  open. Testing Bone Shards' cost does not certify arbitrary alternative costs.
- None of these fixtures proves every other clause of the same card works.
  Phantasm's conditional defender permission and unrelated abilities require
  their own acceptance tests.
- Seat-balanced smoke matrices and trace metrics are repeatability and defect
  checks, not tournament training, broad balance evidence or expert-AI proof.
- An optional Python 3.12.3 `faulthandler_timeout=30` diagnostic run exited 139
  while printing a thread traceback. Its logs are retained, not counted as a
  passing test. Normal BO3 execution is checked separately. An
  [upstream traceback race report](https://github.com/python/cpython/issues/158200)
  describes this failure class on another Python build; it does not establish
  this crash's cause. A minimal runtime reproduction remains an investigation.
