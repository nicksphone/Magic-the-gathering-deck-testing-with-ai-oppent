# Spell payment card selections

## Shared contract

The existing recognized spell costs accept explicit `discard_card_ids` and
`sacrifice_card_ids` inside the typed `cost_choice`. Both lists are validated for
their exact required count, distinct card IDs and the current owned/controlled
eligible zone before mana or life payment. The casting card cannot be discarded
to pay its own cost. Wrong-seat, source, stale, duplicate, excess and wrong-kind
selections are rejected through checked copy-on-write admission.

Legal cost options expose eligible candidate IDs. Both human seats get deliberate
multi-select controls; casting is disabled until the chosen cost's counts are
satisfied. The same controls work for an authoritative graveyard free-cast
permission. Changing an either-cost branch uses its own keyed selection.

Discard costs reuse shared discard operations, preserving destination replacement
and discard events. Sacrifice costs reuse shared selected sacrifice operations,
including owner destination, leave/dies events, last-known information and token
zone changes. Cost triggers are staged during casting and published above the
spell. Exile replacements suppress death triggers, not the sacrifice itself.

## AI

At every difficulty, actual legal cost options provide the candidates used by
ordinary cast materialization. The existing hand-retention and sacrifice-loss
heuristics rank those known cards. Singular discard-or-sacrifice branches sharing
one parent option are compared by payment loss rather than taking the first
printed option. Explicit supplied branches and selections are preserved.
Effect-authorized materialization also receives its waived cost options, so the
same selection logic applies without accidentally charging the printed cost.

This improves known resource choices; it is not exhaustive tactical search or
proof that every resource trade is profitable.

## Validation

`backend/tests/test_cast_payment_choices.py` uses canonical Bone Shards, Blood
Artist, Ornithopter and other shared fixtures. It covers both seats, normal/free
casts, explicit selections, rejection preservation, HTTP/database rejection,
duplicate announcements, death triggers and exile replacement. AI fixtures cover
three difficulties and eight archetype labels; those constructed decisions are
not tournament matchup results. Existing additional-cost, life-payment,
effect-casting, trigger and API tests exercise shared callers.

`frontend/tests/browser-cast-payments.mjs` covers eight human cases through the
actual App/API: both seats, normal/free casts, discard/sacrifice selection,
required-selection button gating, target choice, resolution and refresh. Runtime
boundary tests reject malformed candidate lists and cost counts.

Final acceptance: 3,759 isolated backend cases pass (360 deprecation warnings,
617.07 seconds), along with frontend lint/unit/build and complete Chromium. The
repeated twelve-sample Master matrix reports no timeout, anomaly or drift. Eight
final Drain/Midrange and Tokens/Ramp traces in both seat orders finish without
invalid-payment/target lines; missing quality evidence remains null. This is not
fresh dependency-install, optimal-play or balance certification. The verified
RCHFiles archive is `diagnostics/cast-payment-selections/20261003T091348Z/`.

Fresh canonical probes in that archive reproduce two still-open parser defects:
Cathartic Reunion advertises one discard rather than two, and Raze advertises a
creature sacrifice rather than land. This batch improves selection of modeled
costs, not correctness of every modeled cost. The next fix must parse shared
clauses/counts/types and reject unsupported grammar, without named-card dispatch.

## Known Limitations and Next Upgrades

- This does not extend the existing Oracle cost parser to arbitrary counted,
  qualified, land, exile, reveal or return costs. Those require canonical fixtures
  and explicit unsupported-clause handling before being advertised as supported.
- Kicker conditional resolution, waived-cost kicker, alternative-method identity
  across composed variants and other optional additional costs remain open.
- Activated-cost card selection and interrupted payment continuations are not
  implemented by the spell-announcement fields.
- Life, discard and sacrifice components retain the existing fixed execution
  order. General player-selected payment sequencing remains unfinished.
- Legacy/internal callers omitting the optional selection lists retain automatic
  selection. New human controls supply deliberate choices; this is not a blanket
  API requirement for every legacy caller.
- Small replay and decision fixtures cannot establish expert-level play, arbitrary
  card correctness or statistical matchup balance.
