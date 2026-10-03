# Hand Activations and Counter Payments

## Implemented Boundary

Regular activated abilities with the recognized `Discard this card` cost are
available from the activating player's hand, not from the battlefield. The selected
ability index binds its cost, targeting hints and effect. A different hand copy
cannot pay that source-bound cost. Tap costs still require battlefield sources.

Costs use the existing event-aware discard operation, including recognized
graveyard-to-exile replacements. The ability goes on the stack independently
of the discarded card; it is not a spell cast and does not cause an ETB event.
An old battlefield incarnation's last-known characteristics are not reused for
a hand activation. Snapshots and SQLite restoration retain the stack object.

Canonical Scryfall fixtures cover two separate Colossal Skyturtle modes,
Twinshot Sniper damage, Greater Tanuki basic-land search with tapped entry,
and Mirrorshell Crab's spell-or-ability counter with a mana payment option.
These are isolated rule fixtures, not fabricated competitive decks or claims
that every clause of those cards is certified.

Generic `return target card from your graveyard` hints include noncreatures
and exclude the other player's graveyard. Shared target validation, AI and
human controls consume the same candidate list. Existing creature-only and
permanent-only contracts remain separate.

Recognized counter-unless-payment effects carry allowed stack kinds. A human
target controller receives a durable Pay/Decline choice at resolution; the
counter's controller cannot make that decision for them. The shared owned
stack-payment continuation resumes the resolving effect after payment and
survives snapshot restoration. AI payment evaluation reuses the existing
public-outcome comparison; noninteractive callers retain the legacy optional
override and pay-if-legal default.

Both seats can announce these hand activations through the existing generic
ability controls. The functional control label now says Card and combat
abilities; this is not the deferred UI redesign.

## Acceptance Evidence

- `backend/tests/test_hand_activations.py`: both-seat source reservation,
  separate costs/modes, spell/ability distinction, stale-LKI isolation,
  graveyard noncreatures/ownership, exile replacement, snapshot/SQLite restore,
  atomic wrong-seat rejection, and human payment ownership/pay/decline.
- Strong/Master lethal-counter decision tests cover Control, Tempo and
  Midrange without named-card AI dispatch.
- `frontend/tests/browser-hand-activations.mjs`: both-seat hand activation,
  noncreature graveyard targeting, actual discard/payment/stack resolution,
  target-owned counter decline, and pending-choice reload through App/API.
- Full-suite, frontend, browser and seeded replay results are recorded in the
  dated CHANGELOG milestone and its RCHFiles evidence archive.

## Known Limitations and Next Upgrades

This does not implement arbitrary graveyard/exile activation permissions,
unknown hand-ability cost clauses, Channel-specific conditional cost reducers,
mandatory replacement ordering during complex cost payments, or all historical
hand mechanics. Unsupported Oracle clauses must remain visible diagnostics.
Ordinary noninteractive counter payment still uses a pay-if-legal policy;
broader resource planning and multi-response search remain open. Casual AI's
lethal-counter miss remains in the saved canonical decision evidence. The
replay matrix is a small repeatability/regression sample, not balance,
tournament strength or arbitrary-card certification.
