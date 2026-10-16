# Explicit canonical front context through the existing Factory ABI

This fixture-only increment follows immutable `4f86df95dfe8e4ebb60f41e1a8229ee633c7d009`
plus the frozen canonical stage `34b3e174...` and damage increment `b80eb19e...`.
All old archives and their strict RED ledgers remain unchanged.

## Supported input, before printed capture

`MatchFactory.from_decks` already reads each entry's `selected_face_index` into
the physical `CardInstance`. For transform cards it saves that input, applies
the genuine front face, then restores the saved selection in both the card and
its printed-restoration record before the final copiable-value initialization.
No new Factory/state/face-restoration behavior is necessary.

The test-only materializer now accepts optional `selected_face_index`. A supplied
value is added to the normalized deck entry **before** Factory construction.
The default `None` still omits the entry key. Only the original Delver test birth
requests explicit `0`; the old assertion and every subsequent action stay exact.
There are no private printed-record writes, late capture overrides, changed RAW
facts/stats, global front defaults, or production changes in this increment.

## Actual tests

Five whole modules: all previous 91 plus 22 plus five new controls. Same qualified
pre-import SQL/socket/child/provider-denied profile, 900-second TERM plus 15-second
KILL bound; no HTTP/browser/native/SQL execution.

- Baseline **116 PASS / 2 FAIL, 11.92s**: the old literal-front assertion and a
  new capture of its actual omitted Factory input fail. Four genuine Factory
  cases already pass, proving the existing supported ABI rather than missing API.
- Corrected **118 PASS / 0 FAIL / 0 ERROR / 0 SKIP, 11.92s**.

The four context cases cover both seats, implicit omitted selection and explicit
zero, genuine checked cast/payment, stack resolution, transform, bounce, and
snapshot round-trip. Complete canonical parent and face facts remain unchanged.
The fifth control observes the original test's actual input and Factory-produced
printed records before its first card insertion/consumer.

The inherited 22 cases remain byte-exact, including both implicit-None Delver
characterizations. All original 32 names/108 assertion ASTs and the old 58 fidelity
case bodies/assertions remain unchanged. The only original function adaptation is
the authorized construction-context operand, not an assertion, move or resource.

Full existing source and qualified runtime bytes match before/end in both gates;
five native denial canaries fire, unexpected denials are empty, FDs match,
MainThread is alone and no child or app-server import is observed.

The production toxic helper remains exactly its prior qualified postimage:
`d5cdd263a5a3109ca7af81775b06f46c63e57f56e9e55b2a31ad8f775d987fa2`.
Factory/state source remains exactly its immutable preimage. This is bounded pure
component qualification, not browser/HTTP/full-program or global Task1.3 signoff.
