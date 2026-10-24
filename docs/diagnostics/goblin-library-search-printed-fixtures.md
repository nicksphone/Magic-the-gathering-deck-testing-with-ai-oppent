# Canonical Goblin Search Fixture

## Scope

Authored over immutable main `891e862cd44f7aab67691c84c090365baf507086`.
This changes only the four positive library slots in
`backend/tests/test_interactions_expanded.py::test_search_library_returns_all_matching_cards`.
No production implementation, shared fixture helper, old assertion, other test
body, rule choice, RNG, allocator, dependency or resource policy is changed.

| Slot | Genuine Print | Native Facts |
| --- | --- | --- |
| Guide | Goblin Guide, existing complete seed155 RAW | Creature, 2/2, haste |
| Piledriver | Goblin Piledriver, complete new official RAW | Creature, 1/2, protection from blue |
| Historical Marshal slot | Mogg War Marshal, complete new official RAW | Creature, 1/1, full Echo and token clauses |
| Bolt | Lightning Bolt, existing complete seed155 RAW | Instant, no creature power/toughness |

Each complete, unmodified response object reaches the actual `MatchFactory`
before native birth. The existing seeded eight-copy private Factory pattern is
reused; `dataclasses.replace` changes only the scenario ID, owner/controller,
library zone, instance order and summoning-sickness pose. No printed facts are
patched after birth. Guide's already-canonical birth route remains equivalent.

## Explicit Name Correction

The retained official exact-name request for **Goblin War Marshal** returned
404 on 2026-10-24. The positive slot now explicitly uses the distinct genuine
**Mogg War Marshal**, not renamed RAW. Its historic opaque physical ID
`card-goblin-war-marshal` remains to preserve all four slot IDs and library order;
the native card name, official identifiers and RAW remain Mogg War Marshal.

The existing search filter reads Goblin subtypes from `type_line`, so Mogg need
not contain "Goblin" in its name. The three original gameplay assertions remain
unchanged: hand +3, library -3 and the existing three-card search log witness.
The complete local cohort now passes these assertions. No engine correction or
weakened assertion was needed for canonical admission.

The two full new response files and public provenance are under
`backend/tests/fixtures/goblin_search/`. Guide and Bolt reuse the unchanged
`knowledge_profiles/seed155-scryfall.jsonl`. The official404 history is retained
separately; its response hash and explicit disposition are in the provenance.

## Bounded Fidelity And Boundaries

The new four-case module observes full RAW arguments before delegating to the
real Factory, native pre/post birth and the materialized library before search.
It checks characteristic records, complete Oracle text, types, printed stats,
native keywords, colors, layout, physical IDs, RNG and allocator preservation.
These birth witnesses stop before the effect; the unchanged whole original
module remains necessary for actual search/gameplay assertions.

RAW keyword spelling is not confused with the existing native projection:
Piledriver retains RAW `Protection` and native `protection from blue`; Mogg
retains RAW `Echo` and its complete Oracle, while the current innate-keyword
list is empty because the existing parser does not list Echo. No keyword
implementation is added or claimed qualified here.

All other ten original test bodies, including rule-created token and synthetic
protocol/boundary operands, are untouched. They are not relabeled as canonical
real-card births, silently waived or claimed resolved by this patch. In
particular, this is not a general authorization to fabricate real card facts.

## Qualification Status

On October 24, the baseline whole-module cohort ran all original 11 plus four
new cases: 12 passed and three new fidelity assertions failed at the intended
missing/wrong printed-data birth checks. With the fixture correction, the same
whole cohort passes all 15 ordinary cases and 45 setup/call/teardown phases,
without filters, skips or changed old assertions. The new tests were authored
before the positive fixture edit. The pre-existing Guide fidelity companion
remains unchanged and required in complete hosted CI.

An earlier baseline invocation also produced 12 passes and the same three
fidelity failures, but its final harness check incorrectly expected a singleton
image cache. The original tests genuinely create the generic token SVG and two
named placeholders. That invocation remains a harness failure, not a qualified
run. The corrected envelope checks exactly those three real outputs against the
shipped generic asset and the actual pure renderer with pinned canonical input;
it does not preseed images, change production rendering or widen write access.

The original module already imports SQL-library/dormant fixture definitions via
`test_knowledge_ingest`; none of these selected tests requests its SQL fixture.
Both accepted invocations deny native SQL/network/child operations before app
imports, bind genuine media output to owned scratch, restore media globals and
dispose the imported dormant engine. Independent post-recorder checks confirm
closed processes/groups, an available coordination lock and unchanged source,
runtime, system files and inputs. No HTTP, SQL connection or startup is exercised.
Complete hosted qualification remains separate from these local results.
No full Task1.3, AI-quality, training, all-card or RC closure claim is made.
