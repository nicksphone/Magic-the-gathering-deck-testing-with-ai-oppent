# Complete Linked-Exile Aura Entry

Linked targeted exile must retain its source-incarnation semantics when the
target grammar is `creature or planeswalker` and the printed source reference
is `this Aura`. Discovering only a plain exile substring loses the link: the
target is exiled but fails to return when the source actually leaves.

The bounded compiler accepts one complete self-entry clause, optionally
preceded by one native-valid enchant restriction on an actual Aura. It must
consume the complete raw surface. Unknown suffixes, extra lines, or discarded
unknown parenthetical text in this family must not become a partial plain-exile
effect. The existing linked-exile resolver and source/target incarnation checks
are unchanged. This is not a general Oracle-language capability claim.

## Portable Regression

`backend/tests/test_aura_linked_exile_paid.py` is one public regression module.
It uses full existing canonical rows from the pinned seed155 Scryfall fixture
and the static-global-keywords fixture/provenance. No external audit paths,
model payloads, live database, network fetch, generated event, or manually
constructed stack item is needed. It writes no audit logs into the repository.

Both decks have sixty physical cards with original complete printed facts.
Zone relocation and the foreign-owner/control setup are trusted fixtures, not
claimed played histories. Casts, payments, target offers, target selection,
priority passes, entry, removal, exile, and return use the real checked-action
path. The planeswalker fixture's initial loyalty is its canonical printed
loyalty, not a gameplay activation or fabricated derived value.

The first four parametrized tests cover the eight original paired-seat core
cases: real paid entry/target publication, linked exile/paid removal/return,
empty-opponent legal Aura entry and query purity, and snapshot-preserved links
followed by actual paid removal. Additional cases cover a canonical Nissa
planeswalker target, a foreign-controlled creature returning to its owner,
and paid Disenchant resolving before the source's ETB effect. A canonical
Lay Down Arms control remains ordinary unlinked exile with its real life gain.

Synthetic malformed-text specimens are explicitly separate from canonical
positive evidence. Only those specimens append an unknown instruction, line,
or parenthetical suffix before fixture birth. They must not execute a supported
substring, publish a damaging partial exile, or obtain a source link. The
canonical fixtures themselves are never rewritten.

Banishing Light is absent from these two authorized fixture sets; no stand-in
printing or invented canonical case is supplied. Snow restrictions, Battles,
protection, general no-op recognition, optimal targeting, and AI Aura valuation
are outside this module's claims. The attachment query asserts only unchanged
inputs/RNG, not a required action, positive score, or policy-quality result.

## Evidence Status

Before this portable module was prepared, an external bounded native audit had
four passing observations and four real source-link/return failures. The
parent subsequently applied the two-file compiler correction and ran the exact
original eight-case module: eight passed, with empty guards and unchanged
pinned source during that run. Those original audit bytes remain external and
immutable; no private paths or traces are required by this public regression.

The portable module's initial 22-case run exposed two missing planeswalker
offers, two incorrect test assumptions about where restriction metadata lives,
and two genuine missing-life-gain outcomes in the Lay Down Arms control. The
restriction assertion now reads the actual native hints interface; the real
target-selection and life-gain assertions remain strict. The planeswalker
union reuses the existing protection and hexproof filters and deduplicates IDs.

After those corrections, the full 40-module pure cohort passed 966 tests and
thirteen subtests in 499.90 seconds. The declared 281-file source inventory, forty
module files, the protected fixture and the precollection runner were pinned
before and checked after execution. No SQL, network, process launch or trained
payload access was admitted by that component runner. This does not qualify a
new learned model, a full game, or arbitrary linked-exile grammar.
