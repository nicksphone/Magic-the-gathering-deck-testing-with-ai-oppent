# Paired Kicker Count Acceptance

Isolated application baseline: 8cfcb4f4dbc06a96b59c2b992cc629131b18d275. Parent later March oracle-only additions require separate current-parent composition; no oracle, coverage, AI, API or main changes in this packet.

## Product Contract

The complete, closed two-price permanent body is recognized generically, not by card name: two mana prices joined by `and/or`, supported optional flying/lifelink keyword line, and two independent self-entry damage clauses conditioned on kicked once and twice. Unknown tails, partial rewards, missing second clauses and unsupported keyword lines fail closed. Price-only recognition is not supported.

Existing public `CostChoice.id` transports `base`, `kicker_1`, `kicker_2`, `kicker_1_2`; ordinals follow printed price order. Successfully paid options carry explicit private count 0/1/2 with consistent kicked boolean. No new public request field. Existing single-kicker IDs/helpers remain unchanged.

Optional internal `CardInstance.kicker_count=None` means legacy absence, not paid zero. Durable snapshots omit absent count. Present count must be exact integer 0/1/2 (not bool/null/float/string), consistent with the boolean. Legacy absence plus true means at most one payment; never inferred twice. Present stack count is validated too. Spell copies retain paid count; permanent copies and new incarnations do not inherit it. Old battlefield LKI includes explicit count before zone-reset. HAND-origin retained references and prior Domain/compiler/privacy functions are protected.

## NEW Tests And Dependencies

Add only `backend/tests/test_archangel_pair_paid_desired.py`, `backend/tests/test_archangel_pair_additional_goldens.py`, and ten raw files under `backend/tests/fixtures/archangel_pair/`. Do not replace any old test module. Both modules reuse existing tracked `audit/gate2-domain-compiler/domain_paid_support.py`, the ordinary RulesEngine public action API, and existing static ability-suppression fixture/helper modules. Those dependencies are not donor overwrite payloads.

The original desired whole52 baseline failed52/4.71s: 22 coupled gameplay cases stopped at missing paired menu before payment; 30 detached snapshot diagnostics failed. First product unchanged52 yielded38PASS14FAIL/6.86s due a NEW harness sequencing error (asserting stack frames before offered order/target choices; indexing missing order-phase key). Parent expressly granted a separate sequencing correction. All original assert nodes survive unchanged; additional pre-choice queued count proof was added. Corrected whole52 passed52/11.59s. Raw source comparison1 is retained: exactly one generated generic-token-creature.svg addition; all pre-existing source entries equal.

Additional whole17 passed17/8.41s: both-seat split player/creature targets, deliberate offered reverse order, paid independent Stifle counter and Unsummon fizzle, exact damage/lifelink; source-return old LKI count/ref/controller/keywords; public canonical Humility fixture suppresses entry abilities; five detached closed-body compiler controls. Original additional17 ledger11PASS6FAIL/8.47s is preserved; the test incorrectly read nonexistent `.damage`. The correction reads the real existing `counters['__damage_marked']` representation without changing expected damage/outcomes. Humility is a public starting-position fixture, not a claimed paid Humility cast.

Whole13 neighbor352 was NOT qualified: 350PASS2 setup errors/56.04s, pytest1, FD closurefalse. Whole ability_suppression was misclassified pure: two genuine HTTP fixtures need SQL/socket infrastructure. Original guard missed native socketpair allocation before denied wrapping, causing 2 epoll+2 AF_UNIX descriptors. The entire unchanged module is queued for mixed qualification, not pruned. Failed ledger and actual FD receipts remain immutable. New isolated final pure runner additionally denies both high-level and native socketpair before C allocation, with two extra canaries; original native guard file remains unchanged.

Final actual14 whole pure403 qualification receipt is supplied separately; never infer qualification from planned counts or prior green subsets.

## Boundaries

No SQL/socket/network/child execution is allowed by the final pure transport. JSON cold restores are in-process snapshots, not SQLite or separate OS processes. Mixed whole modules test_kicker, test_nonmana_kicker, test_kicker_goldens, test_stack_copies, test_ability_suppression remain separately queued for an explicitly granted SQL/HTTP contract. No browser/HTTP/main lifecycle certification from pure results. Coverage admission and AI kicker-resource valuation are unmodified and unqualified for the new paired mechanic. Brainstorm full canonical private hand-to-library response remains a separate upstream gap, not fabricated causal evidence. No release requirements are cleared by this isolated packet alone.

## Final Pure Receipt

Actual final14 whole403 passed403/68.15s (two dependency deprecation warnings), pytest0/transport0/closure0/raw source comparison0. Worker2202319 gone; seven pre-import native canaries including high-level/native socketpairs, no unexpected SQL/socket/child attempts, all app imports owned, no default database. Kernel process trace contains exactly initial Python exec and exit0, no child. Final FD/thread/direct-child receipts equal. Source comparison0 is for this final gate's pinned starting tree, which already contains the separately declared token SVG generated by the corrected52 run. It does not relabel corrected52 rawcmp1 or the failed352 FD ledger.
## Current Parent Composition

The parent applied the exact seven tested production postimages over
`1ee3a90798023ebdd5c9eb55f9bbab56366dc7c4`, preserving March's separate Oracle
delta and all unrelated files. A fresh local source-only checkout ran the
original 14 whole Archangel/neighbor modules plus both complete March-target
and inventory modules: **475 passes, two warnings, 69.75 seconds**, exit zero.
All 475 JUnit cases passed with no errors or skips. This is an actual combined
run, not a sum of the earlier donor results.

All 2,438 original input hashes remained equal. The inventory and token paths
generated 156 SVGs (155 placeholders and one generic token). Every filename
and SHA matches the previously qualified a42 closed-source archive exactly;
the full finite manifest is in `independent-acceptance.json`. The token SHA is
`a3114095c760517186807f8753d109000174460a20ee72693ff9b9a69efc5e85`.
Native SQLite/socket/child allocation was denied before imports. The inventory
module's intentional negative SQL/child requests are expected denied controls,
not gameplay IO. Owned imports, absent default database, equal FD/thread/child
identities and ended worker were independently verified. Initial metadata checks
assumed unavailable closure/identity keys and incorrectly expected only one
generated SVG. All three metadata errors are recorded separately; correcting
the receipt keys, raw exit check, and exact asset comparison did not rerun tests.

Evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/archangel-march-current475-1ee-20261007/`.
Mixed HTTP/SQLite modules, admission warnings, current browser and expert AI
remain separate. The donor evidence and its failure history below are preserved.
