# Activated Ability Hint Copy

Separate incremental product over frozen counter-cost integration908c.
Only production change: three inserted lines replacing one line in
`stack_engine.resolve_top_of_stack`'s single-target ability hint path.

## Change and Source Contract

The existing reader substitutes the genuine ability body on a copied source,
but previously retained the source's SPELL mana cost for target hints. Ballista
therefore inherited an unrelated `{X}{X}` requirement at resolution despite a
fixed one-counter ability cost and already-paid activation.

The reader now creates a separate hint copy with `mana_cost=""`, matching the
existing activation announcement surface. It leaves announced targets and
selected X, compiled effect payload, actual source/LKI and the source passed
to protection/hexproof unchanged. No fabricated X, action weakening, new card
branch, source ID/zone fabrication, fake StackItem or recomputed incarnation.
No compiler/events/costs/SBA/legend/mana/schema/AI changes.

## Executed Qualification

Exclusive local source, qualified Python3.12.3, all requirements exact and
pip-check clean; no installs. Whole modules, serial bounded invocations, no
`-k`, skips or xfails. Network/foreign-SQLite guards during qualification.

- Unchanged original133 BEFORE:117PASS/16strictFAIL,18warnings,31.37s,exit1.
- NEW22 BEFORE:18PASS/4strictFAIL,2warnings,7.33s,exit1.
- Original133 + unchanged NEW22 AFTER:155PASS,18warnings,37.37s,exit0,bound600.
- 17 whole affected neighbors:367PASS,77warnings,45.51s,exit0,bound900.
- Distinct candidate qualification:21whole modules,522ordinaryPASS.

No terminal old campaign restarted. Raw logs/XML/exit receipts and exact module
list retained. Earlier counter-cost778 neighbors are NOT relabelled as this
increment's execution. No parent composition qualification is substituted.

All original133 tests and the existing cold HTTP worker are byte-identical.
Thus actual both-seat counter announcement/payment, last-counter source death,
retained true LKI, real damage resolution, full invalid root/controller/SQL
immutability, both-seat privacy, snapshot roundtrips and cold local SQLite/HTTP
recovery now pass their original desired assertions.

NEW hint-copy tests observe the genuine runtime reader during checked actions,
call the original hint/protection functions without overriding their result,
and compare full roots around queries. They prove the hint copy is separate,
has no spell mana cost or invented X, and does not mutate the source. The real
protection source still has `{X}{X}` and the identical source LKI; last-counter
and surviving-source cases execute and resolve for both seats after restart.

NEW genuine X controls use full raw canonical Goblin Dynamo, fetched before
tests from the retained Scryfall URL with full-byte SHA/provenance. Its actual
second ability is `{X}{R}, {T}, Sacrifice this creature: It deals X damage to
any target.` NOT a handwritten substitute. Real X=0/2/3 announcements pay the
selected mana, sacrifice the real source, retain actual red-source LKI and
resolve exactly the selected damage after restart for both seats. Missing,
negative, boolean, unpayable X and matching red protection reject with the
entire root unchanged. Actual paid X damage against nonmatching protection
also resolves. No invented Oracle, partial cost, synthetic gameplay effect or
stack injection. Starting battlefield positions are explicitly controlled
canonical fixtures, NOT a claim of legally cast source/entry episodes.

Unchanged neighbors cover X activations, activation modifiers, modes, modal
faces, linked/same-object targets, retained effective source type/color,
source-departure/LKI, hand activations, stack copies and target kinds.
The inherited synthetic/controlled neighbor fixtures remain unchanged; they
are not described as new full-raw canonical episodes.

## Pins and Composition

Immutable input:source-counter-cost-product/mtg-counter-cost-product-7B2Ddj/
`candidate-source.tar.gz`,SHA256
`ecfaf2156793aac6aeedeca6de5827915c496005a264e3cc96030731313b80a5`.
Its integration patch SHA:
`908c6f3ed791bfd5fe6ef13c78b2d816795f4f920531a922004f7b4c499c1f76`.
Full source manifest verified on extraction; no moving parent/main reads.

- Stack pre:`d805c4ac4210905c08be8ee7b0e49c9c43d9a5c51b36e4408d65a3fb28f6338e`.
- Stack post:`dd7e7e3c56b9c9a1c5718860dfe5ec9ef43ce838062e269d699cba97662720d5`.
- Oracle remains:`02f8f2706d4d22fbef504890f9fc105c324d2a981941db14d7c763866e060f72`.
- Costs remains:`458e28725cc9534d5476d0675b244ac37705973865f8c5b011de86b41d66b94b`.

Exact substitution proof verifies EVERY other inherited backend byte unchanged,
not merely other function AST. Production patch is stack hunk ONLY. Integration
adds NEW22, full raw fixture/provenance and this report. Original908c archive
and earlier proposal remain immutable; this is a separately qualified increment.
Lagrange compiler/events ownership is disjoint; his no-overlap scope was relayed
by the parent. No concurrent/shared-root writes or wholefile overlays.

This closes the observed inherited-spell-cost hint rejection on this frozen
source. It is not all-card/mode/X/target/LKI certification, a deployed/main
promotion, or proof of the parent's coupled compiler composition. No scoring,
search-budget or legality alternatives are altered. Active SQLite stays local;
completed source/snapshot/log evidence is frozen on verified writable NFS.

Freeze verification initially found three SVG image-cache files generated by
neighbor tests, absent from the immutable input and patch. Their exact paths,
bytes and failed first reconstruction ledger are preserved separately as runtime
test artifacts. Only these three generated SVGs are excluded from the source
reconstruction manifest/archive; inherited image assets are retained. No code,
tests, desired assertions or production patch changed to address that mismatch.
