# Kicked-cast payoffs and decision guards

## Acceptance checklist

- [x] Canonical fixtures and shared kicked-cast consumer path.
- [x] First-kicked-spell discounts in affordability and actual payment.
- [x] Controller/turn history, restoration, copying and countered-cast checks.
- [x] Original-object self effects, suppression and temporary base-stat fidelity.
- [x] Conditional fixed creature-token ETB support and subsequent cast distinction.
- [x] AI guards for prohibited counters, exhausted draw limits and normal draw deck-out.
- [x] Focused checks: 269 related tests and a final 55-test edge gate pass;
  an additional 319-case draw/counter/mana/temporary-effect gate also passes.
- [x] Full isolated backend suite: 4,013 passed, 364 deprecation warnings,
  633.92 seconds, using installed dependencies rather than a fresh installation.
- [x] Frontend lint, contract tests and production build; complete browser
  suite including sixteen new cases, restart recovery and natural BO3 flows.
- [x] Twelve seat-balanced BO1 replay samples, each executed twice:
  zero reported anomalies, timeouts or determinism failures, 512.689 seconds.

## Shared implementation

Recognized `Whenever you cast a kicked spell` clauses consume the original
announcement's `__kicked` flag. Fixed creature tokens, self +1/+1 counters and
temporary self base-stat setters become ordinary counterable stack objects.
They trigger once per actual cast, for the appropriate controller, not for a
spell copy or ability activation. Sources with suppressed abilities do not
contribute. Original-object references stop self effects following a blink.

Temporary base-stat setting shares the resolved layer/timestamp representation
with ability-loss effects but does not remove abilities. Counters and later
layer contributions remain distinct from printed power/toughness. Cleanup removes
the temporary setting, and snapshots preserve it before expiration.

The first-kicked-spell discount is a scoped generic reduction on the whole cost,
not on an unpaid base branch. Matching active sources accumulate. Both legality
and payment receive the announced kicked flag; per-player histories reset for
each turn and survive snapshots. Copies do not consume the discount. A cast that
is later countered does consume it. Existing free-cast/tax/minimum-cost ordering
remains shared; this is not arbitrary conditional cost parsing.

Roost's recognized fixed token ETB is compiled independently of its cast payoff.
A Roost not yet on the battlefield cannot trigger from its own cast; a kicked
entry can create its ETB token, then later kicked casts can trigger it normally.
Unrecognized kicked-cast clauses receive explicit coverage warnings.

Rules grounding: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules),
effective 2026-09-25, rules 603, 613, 702.33 and 707.10. Primary downloaded rules
text and raw source card responses are preserved with acceptance evidence.

## Real card and AI evidence

`backend/tests/fixtures/kicked_cast_triggers.json` stores unmodified Scryfall
data, Oracle IDs and source URLs for Risen Riptide, Roost of Drakes and Vine Gecko.
Fixtures do not modify competitive decks or invent playable cards.

The actual AI cost-choice path considers recognized ready-board cast payoffs,
avoids buying entry counters blocked by current prohibitions, and estimates draw
capacity from public library counts and draw restrictions. It neither reads future
card identities nor evaluates an opponent's private hand. It avoids repeating a
base-stat payoff that is already active in the exercised scenarios.

`frontend/tests/browser-kicked-cast.mjs` passes sixteen real App/API cases:
both seats, paid/unpaid choices, cast payoffs and conditional Roost entry. They
check stack refresh, effective stats/counters/tokens and exact mana. The complete
browser gate also passes; this is functional evidence, not visual redesign acceptance.

## Corpus inventory

A read-only local inventory found 38,690 knowledge records and 112 runtime-cache
records. The knowledge data contains 270 faces mentioning kicker or kicked;
the bounded compiler recognizes 19 kicker surfaces, and 19 faces mention
multikicker. These are classification counts, not whole-card certification.
The runtime cache alone contains no such surfaces and is not the full corpus.
Persisted knowledge profiles are not yet a production AI decision consumer.
Dual/nonmana/X kicker, multikicker and per-cost linked payoffs remain priorities.

## Known Limitations and Next Upgrades

Arbitrary kicked-cast clauses, multikicker counts and per-cost linked payoffs,
conditional cost variants, face-specific acceptance and general linked-ability
changes remain unfinished. Draw forecasts here do not cover arbitrary replacement,
dredge or draw-trigger chains; payoff scoring is not a full adversarial search.
Token/counter values and resource retention remain estimates, not expert-play
certification. Small deterministic matrices test repeatability rather than balance.
Fresh dependency installation, network deployment and the deferred alpha UI
redesign are not acceptance claims of this backend milestone.
