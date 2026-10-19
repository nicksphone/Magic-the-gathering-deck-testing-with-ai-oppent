# Favor Clause Target Binding

## Frozen Scope

Base: 55ebc8c6cba982300f85289bdbe3d114fa29b2e5 plus the unchanged NEW
Favor audit dependency, integration.patch SHA256
6ee2fa54091dbfcdbbc7b395206a5ba9348712f609db41c9e046e67fcbc94531.
Only product change: rules_engine.oracle_effects._infer_targeted_search_effect.
The helper adds clause_text to the existing search_library and add_counters
children of an already fully matched ordered effect_sequence. Exact matched
clauses retain case and punctuation; whitespace normalization is unchanged.
Payloads, announced targets, resolution controller, admission grammar and
unsupported-tail rejection are unchanged. No schema, handler, stack, cost,
blink or animation changes. Product ownership does not extend to other helpers.

Existing clause_target_assignments now independently binds target_player to
the search and optional target_card_id to counters. Existing stack resolution
prunes an illegal child without affecting the remaining legal instruction.
No target is inferred when the optional counter target is omitted or null.
No named-card dispatch, new wire fields or replacement target is introduced.

Oracle preimage SHA256:
348f83afdf8a6def89bf2897ecb7a74b4dddcc71920aa08960fe80d9d9b0b6de

Oracle postimage SHA256:
159bdfc6d029063c476813633b24cdc52bf0e9098653be9f436396e0654314c5

## Complete Terminal Gates

The original two Favor modules, all 42 unchanged cases, on fresh serial local
SQLite: 38 PASS / 4 ordinary FAIL, 34 warnings, 37.65s, exit 1. All eight original
hexproof failures now pass, including both seats' memory/file HTTP continuation
cases. The four unchanged Cloudshift failures stop at the exile-only response:
the frozen blink product dependency is not consumed or certified here.

Whole unchanged compiler/resolver/runtime-dependency modules (61 cases) plus
the new whole clause-binding module (20 cases): 81 PASS, 2 warnings, 11.21s,
exit 0. No skips, exclusions, xfails or modified original assertions.

New controls cover exact complete clauses and unchanged payloads, explicit
selected/omitted/null optional targets, missing player/foreign/wrong-zone target
rejection, typed unknown-alias and late-retarget rejection, both-seat
fail-to-find/zero-target restart, and independent illegal-player/legal-counter
versus all-targets-illegal resolution. The latter uses an explicit retained
unit fixture: canonical Leyline of Sanctity is placed in the real paid Favor
state before resolution. It is NOT a claimed natural flash-Leyline response,
paid Leyline cast, historical repair or injected StackItem. Actual paid Veil
and actual Favor resolution are used; all-illegal resolution neither searches,
shuffles nor applies counters. The converse preserves the legal counter child.

The original 42 retain full paid response, private affected-seat search,
genuine caster/frame/shuffle, wrong-seat/foreign/duplicate/stale action atomicity,
root/SQL parity, cold process restore and actual ASGI choice POST assertions.
All eight file-backed workers succeeded in the final serial gate. ASGI HTTP
is not TCP/browser coverage. Basic-land-only search does not certify shockland
entry-choice pauses or actual target blink.

## Preserved Earlier Receipts

An initial invocation failed before gameplay because the basetemp parent was
missing (42 setup errors); the corrected command and logs are retained.
The first completed original-42 run had 37 PASS / 5 FAIL, 80.85s: four unchanged
Cloudshift failures plus one cold-worker match_storage_unavailable rejection.
No causal storage claim or source workaround is made. The final fresh serial
whole-module run above preserves that failure receipt and changes no test.

The initial new-control run had 71 PASS / 10 FAIL: six new assertions incorrectly
assumed newline-separated printed clauses; four checked extra-field rejection
at the legacy internal dictionary rather than the strict public typed model.
Those NEW tests were corrected to exact canonical sentence boundaries and
ActionRequest validation. Prior tests/logs are retained; no original audit
assertion or mechanical expectation was changed. No schema fix is claimed.

Outside-helper whole-module AST is identical; all 1,459 existing backend/frontend
code/data/asset paths in the frozen audit archive match except the authorized
oracle file. Original 42 tests and their helpers/fixtures are byte unchanged.

## Reproduce

Apply the original Favor audit integration dependency, then this increment,
to a source-only immutable checkout including tracked assets. Never overlay
the full evidence tar onto a moving parent checkout. Use external qualified
Python and create a fresh local runtime parent before pytest:

```sh
export MTG_ISOLATED_TEST_ROOT="$PWD"
mkdir -p "$PWD/.favor-clause-runtime"
cd backend
PYTHONPATH=. /home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python -m pytest \
  tests/test_favor_target_lifecycle.py tests/test_favor_target_lifecycle_http.py \
  --basetemp="$MTG_ISOLATED_TEST_ROOT/.favor-clause-runtime/original42" -q
PYTHONPATH=. /home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python -m pytest \
  tests/test_favor_clause_binding.py tests/test_targeted_library_search_compiler.py \
  tests/test_targeted_search_resolver_contract.py tests/test_targeted_search_runtime_dependencies.py \
  --basetemp="$MTG_ISOLATED_TEST_ROOT/.favor-clause-runtime/new-neighbors" -q
```

Evidence/source/test preimages are privately archived on verified project NFS;
SQLite runs locally only. No parent/main/live writes, deployment, overlapping
compiler/handler edits or general targeted-search certification.
